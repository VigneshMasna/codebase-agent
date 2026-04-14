"""
Chat routes — multi-turn conversational interface to the CodebaseAgent.

Endpoints:
  POST /chat            — send a message, receive a complete answer
  POST /chat/stream     — send a message, stream live events via SSE
  DELETE /chat/session/{session_id} — clear a conversation session
  GET  /chat/sessions   — list active sessions (ids + turn counts)

Session management:
  - Sessions are keyed by session_id (UUID string).
  - Conversation history (list[Content]) is stored in-memory AND persisted to
    a JSON file (.chat_sessions.json in the project root) so sessions survive
    server restarts.
  - If no session_id is provided a new one is created and returned in the
    response — pass it back on subsequent turns for multi-turn dialogue.
  - Each session stores: history, title (first user message), created_at,
    last_active timestamps.

Streaming (/chat/stream):
  The agent is run in a background thread via stream_chat_with_history().
  Events are pushed through a thread-safe queue.Queue and pulled by the
  async SSE generator, so the event loop is never blocked.

  SSE event types the client receives:
    {"type": "thinking"}                         — agent started reasoning
    {"type": "tool_call",   "tool": "...", "args": {...}}   — tool invoked
    {"type": "tool_result", "tool": "...", "chars": N}      — tool returned
    {"type": "chunk",       "text": "word "}     — final answer, word by word
    {"type": "done",        "session_id": "..."}            — all done
    {"type": "error",       "message": "..."}    — something went wrong
"""
from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import queue as stdlib_queue
import threading
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from api.dependencies import require_agent
from api.models.requests import ChatRequest, ChatStreamRequest
from api.models.responses import ChatResponse, ChatSessionInfo

logger = logging.getLogger("codebase_agent.chat")

router = APIRouter()

# ── Persistence file ──────────────────────────────────────────────────────────

_ROOT = Path(__file__).parent.parent.parent
_SESSIONS_FILE = Path(os.getenv("SESSIONS_FILE", str(_ROOT / ".chat_sessions.json")))


# ── In-memory session store ───────────────────────────────────────────────────
#
# Structure:
#   _sessions[session_id] = {
#       "history":     list[Content],   ← live Gemini objects
#       "title":       str,             ← first user message (truncated)
#       "created_at":  str,             ← ISO 8601 UTC
#       "last_active": str,             ← ISO 8601 UTC
#   }

_sessions: dict[str, dict] = {}
_sessions_lock = threading.Lock()

# Load persisted sessions once at import time
_load_attempted = False


def _now() -> str:
    return datetime.datetime.utcnow().isoformat()


# ── Serialisation helpers (Content ↔ plain dict) ──────────────────────────────

def _content_to_dict(content) -> dict:
    """
    Serialise a google.genai types.Content to a JSON-safe dict.
    Thought parts (chain-of-thought) are skipped — they are internal reasoning
    tokens that should not be replayed to the model in resumed sessions.
    """
    parts = []
    for p in content.parts:
        # Skip chain-of-thought parts
        if getattr(p, "thought", False):
            continue

        pd: dict = {}

        if p.text is not None:
            pd["text"] = p.text

        elif p.function_call is not None:
            try:
                args = dict(p.function_call.args) if p.function_call.args else {}
            except (TypeError, ValueError):
                args = {}
            pd["function_call"] = {"name": p.function_call.name, "args": args}

        elif p.function_response is not None:
            try:
                response = dict(p.function_response.response) if p.function_response.response else {}
            except (TypeError, ValueError):
                response = {}
            pd["function_response"] = {
                "name": p.function_response.name,
                "response": response,
            }

        if pd:
            parts.append(pd)

    return {"role": content.role, "parts": parts}


def _dict_to_content(data: dict):
    """
    Deserialise a plain dict back to a google.genai types.Content object.
    Silently skips any part format that cannot be reconstructed.
    """
    from google.genai import types

    parts = []
    for pd in data.get("parts", []):
        try:
            if "text" in pd:
                parts.append(types.Part(text=pd["text"]))

            elif "function_call" in pd:
                fc = pd["function_call"]
                parts.append(types.Part(
                    function_call=types.FunctionCall(
                        name=fc["name"],
                        args=fc.get("args", {}),
                    )
                ))

            elif "function_response" in pd:
                fr = pd["function_response"]
                parts.append(types.Part(
                    function_response=types.FunctionResponse(
                        name=fr["name"],
                        response=fr.get("response", {}),
                    )
                ))
        except Exception as exc:
            logger.warning("Skipping unrestorable part %s: %s", pd, exc)

    return types.Content(role=data["role"], parts=parts)


# ── File I/O ──────────────────────────────────────────────────────────────────

def _load_sessions() -> None:
    """Load persisted sessions from the JSON file into _sessions (called once at startup)."""
    global _load_attempted
    if _load_attempted:
        return
    _load_attempted = True

    if not _SESSIONS_FILE.exists():
        logger.info("No persisted sessions file found at %s — starting fresh.", _SESSIONS_FILE)
        return

    try:
        raw: dict = json.loads(_SESSIONS_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Could not read sessions file %s: %s — starting fresh.", _SESSIONS_FILE, exc)
        return

    loaded = 0
    for sid, data in raw.items():
        try:
            history = [_dict_to_content(c) for c in data.get("history", [])]
            _sessions[sid] = {
                "history":     history,
                "title":       data.get("title", "Untitled"),
                "created_at":  data.get("created_at", _now()),
                "last_active": data.get("last_active", _now()),
            }
            loaded += 1
        except Exception as exc:
            logger.warning("Skipping corrupt session %s: %s", sid[:8], exc)

    logger.info("Loaded %d persisted chat session(s) from %s", loaded, _SESSIONS_FILE)


def _persist_sessions() -> None:
    """Write all current sessions to the JSON file. Called after every mutation."""
    try:
        serialised: dict = {}
        with _sessions_lock:
            snapshot = dict(_sessions)  # shallow copy for iteration

        for sid, data in snapshot.items():
            try:
                serialised[sid] = {
                    "history":     [_content_to_dict(c) for c in data["history"]],
                    "title":       data.get("title", "Untitled"),
                    "created_at":  data.get("created_at", _now()),
                    "last_active": data.get("last_active", _now()),
                }
            except Exception as exc:
                logger.warning("Could not serialise session %s: %s — skipping.", sid[:8], exc)

        tmp = _SESSIONS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(serialised, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(_SESSIONS_FILE)          # atomic rename — no partial writes
    except Exception as exc:
        logger.error("Failed to persist sessions to %s: %s", _SESSIONS_FILE, exc)


# Load on first import
_load_sessions()


# ── POST /chat ────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=ChatResponse,
    summary="Send a message to the codebase agent",
    description=(
        "Submits a message and returns the agent's complete answer. "
        "Pass session_id from a previous response to continue a multi-turn "
        "conversation; omit it to start a new session. "
        "Sessions are persisted across server restarts."
    ),
)
async def chat(
    request: ChatRequest,
    agent=Depends(require_agent),
) -> ChatResponse:
    session_id, history = _get_or_create_session(request.session_id, request.message)

    try:
        answer, updated_history = await asyncio.get_event_loop().run_in_executor(
            None,
            agent.chat_with_history,
            request.message,
            history,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent error: {exc}",
        )

    _save_session(session_id, updated_history)
    return ChatResponse(answer=answer, session_id=session_id)


# ── POST /chat/stream ─────────────────────────────────────────────────────────

@router.post(
    "/stream",
    summary="Stream a chat response via Server-Sent Events",
    description=(
        "Runs the agent in a background thread and streams live events:\n\n"
        "- `thinking` — agent started\n"
        "- `tool_call` — a graph tool is being invoked (name + args)\n"
        "- `tool_result` — tool returned (chars count)\n"
        "- `chunk` — one word of the final answer\n"
        "- `done` — session_id + completion signal\n"
        "- `error` — something went wrong\n\n"
        "Connect with `EventSource` or `fetch` + `ReadableStream` on the frontend."
    ),
)
async def chat_stream(
    request: ChatStreamRequest,
    agent=Depends(require_agent),
) -> StreamingResponse:
    session_id, history = _get_or_create_session(request.session_id, request.message)

    return StreamingResponse(
        _sse_stream(agent, request.message, session_id, history),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


async def _sse_stream(agent, message: str, session_id: str, history: list):
    """
    Runs agent.stream_chat_with_history() in a daemon thread.
    Events are pushed into a stdlib Queue and pulled here without blocking
    the asyncio event loop.
    """
    event_queue: stdlib_queue.Queue = stdlib_queue.Queue()

    def _run():
        try:
            for event in agent.stream_chat_with_history(message, history):
                event_queue.put(event)
        except Exception as exc:
            event_queue.put({"type": "error", "message": str(exc)})
        finally:
            event_queue.put(None)  # sentinel — signals the generator to stop

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    # Flush headers immediately
    yield ": connected\n\n"

    while True:
        # Non-blocking poll — avoids occupying a thread-pool slot
        try:
            event = event_queue.get_nowait()
        except stdlib_queue.Empty:
            # Thread still running — yield control and try again shortly
            if not thread.is_alive() and event_queue.empty():
                # Thread died without sending sentinel (unexpected crash)
                yield f"data: {json.dumps({'type': 'error', 'message': 'Agent thread terminated unexpectedly'})}\n\n"
                return
            await asyncio.sleep(0.05)
            continue

        if event is None:
            # Sentinel received — stream is complete
            return

        if event["type"] == "done":
            # Save updated history, strip it from the SSE payload
            _save_session(session_id, event.pop("history"))
            event["session_id"] = session_id
            yield f"data: {json.dumps(event)}\n\n"
            return

        yield f"data: {json.dumps(event)}\n\n"
        # Yield control after every event so the loop stays responsive
        await asyncio.sleep(0)


# ── DELETE /chat/session/{session_id} ─────────────────────────────────────────

@router.delete(
    "/session/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear a conversation session",
    description="Deletes the conversation history for the given session_id (from memory and file).",
)
def clear_session(session_id: str) -> None:
    with _sessions_lock:
        if session_id not in _sessions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' not found.",
            )
        del _sessions[session_id]
    _persist_sessions()


# ── GET /chat/sessions ────────────────────────────────────────────────────────

@router.get(
    "/sessions",
    response_model=list[ChatSessionInfo],
    summary="List all chat sessions",
    description=(
        "Returns all sessions with their IDs, titles, turn counts, "
        "and timestamps. Sessions persist across server restarts."
    ),
)
def list_sessions() -> list[ChatSessionInfo]:
    with _sessions_lock:
        return [
            ChatSessionInfo(
                session_id=  sid,
                title=       data.get("title", "Untitled"),
                turn_count=  len(data["history"]),
                created_at=  data.get("created_at"),
                last_active= data.get("last_active"),
            )
            for sid, data in _sessions.items()
        ]


# ── Session helpers ───────────────────────────────────────────────────────────

def _get_or_create_session(session_id: Optional[str], first_message: str = "") -> tuple[str, list]:
    """
    Look up an existing session or create a new one.
    Returns (id, history_copy) — the copy is passed to the agent so mutations
    don't affect the store until _save_session is called.
    """
    with _sessions_lock:
        if session_id and session_id in _sessions:
            return session_id, list(_sessions[session_id]["history"])

        new_id = session_id or str(uuid.uuid4())
        title = (first_message[:60] + "…") if len(first_message) > 60 else first_message
        _sessions[new_id] = {
            "history":     [],
            "title":       title or "Untitled",
            "created_at":  _now(),
            "last_active": _now(),
        }
        return new_id, []


def _save_session(session_id: str, history: list) -> None:
    """Update in-memory store and flush to disk."""
    with _sessions_lock:
        if session_id in _sessions:
            _sessions[session_id]["history"]     = history
            _sessions[session_id]["last_active"] = _now()
        else:
            # Edge case: session was deleted mid-stream — recreate it
            _sessions[session_id] = {
                "history":     history,
                "title":       "Restored session",
                "created_at":  _now(),
                "last_active": _now(),
            }
    _persist_sessions()
