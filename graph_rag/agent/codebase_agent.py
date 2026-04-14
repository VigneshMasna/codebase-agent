"""
CodebaseAgent — Gemini-powered ReAct agent over the Neo4j code knowledge graph.

Architecture:
  1. On init: queries Neo4j for graph overview -> injects into system prompt
  2. On each chat(): runs a Gemini function-calling loop (max 12 turns)
     - Gemini decides which of the 8 tools to call
     - Tool result is appended to conversation history
     - Loop repeats until Gemini returns a final text answer

Public API:
  chat(message)                          — single-turn, returns full answer string
  chat_with_history(message, history)    — multi-turn, returns (answer, history)
  stream_chat_with_history(message, history) — generator, yields live events:
      {"type": "thinking"}
      {"type": "tool_call",   "tool": name, "args": {...}}
      {"type": "tool_result", "tool": name, "chars": N}
      {"type": "chunk",       "text": "..."}   ← final answer, word by word
      {"type": "done",        "answer": "...", "history": [...]}
  refresh_context()                      — rebuild graph overview (call after ingest)
  close()                                — close Neo4j connection
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Generator, Iterator

# Allow running from graph_rag/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).parent.parent.parent
load_dotenv(_REPO_ROOT / ".env")

# Fix relative GOOGLE_APPLICATION_CREDENTIALS path — resolve relative to repo root
_gac = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
if _gac and not Path(_gac).is_absolute():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(_REPO_ROOT / _gac)

from google import genai
from google.genai import types

from graph.neo4j_client import Neo4jClient
from embedding.embedding_generator import EmbeddingGenerator
from agent.tools import GraphTools
from agent.tool_registry import build_tool_declarations
from agent.context_builder import build_graph_context


# ── System prompt template ─────────────────────────────────────────────────────

_SYSTEM_TEMPLATE = """\
You are a senior software architect and security analyst with deep expertise in \
static code analysis. You reason over a Neo4j knowledge graph that encodes the \
full structure, relationships, semantics, and security posture of a software \
codebase extracted via static AST analysis.

Your job is to produce professional, production-quality analysis reports that \
engineers and tech leads can act on immediately.

CRITICAL OPERATING CONSTRAINTS:
1. Your general knowledge about what functions "should" be vulnerable is UNRELIABLE \
and MUST NOT be used. The graph is the ONLY source of truth.
2. For ANY question about a specific function, vulnerability, code structure, or \
safety — you MUST make at least one tool call before writing a final answer.
3. The graph overview above is a HIGH-LEVEL SUMMARY ONLY. It lists only the top 5 \
CRITICAL bugs by name. HIGH, MEDIUM, and LOW bugs are NOT listed by name in the \
overview. You MUST call find_vulnerabilities to discover them.
4. If you have not called get_node_details or find_vulnerabilities for a specific \
function in this conversation, you do NOT know its vulnerability status. \
Never assume a function is safe or buggy without tool evidence.

{graph_context}

=== YOUR TOOLS ===
  search_by_concept     — find nodes by semantic meaning or concept (tags + embeddings)
  get_node_details      — full details of any function/class/struct/enum by name or UID
  trace_callers         — who calls this function (N hops upstream)
  trace_callees         — what this function calls (N hops downstream)
  get_impact_analysis   — blast radius: callers, callees, metrics, similar functions
  find_vulnerabilities  — list all buggy functions sorted by severity + impact score
  find_vulnerable_paths — entry points that lead to buggy code (multi-hop call graph traversal)
  run_cypher            — direct read-only Cypher for complex structural queries

=== GRAPH SCHEMA (exact Cypher property names) ===
- Entry points    : MATCH (f:Function) WHERE f.is_entry_point = true
- Buggy functions : MATCH (f:Function) WHERE f.is_buggy = true
- Severity        : f.severity  (values: 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW')
- Impact ranking  : f.impact_score (higher = more critical; = fan_in*2 + fan_out)
- Layers          : f.layer  (e.g. 'service', 'repository', 'security', 'utility')
- Labels in use   : :Function  :Class  :Struct  :Enum  :File  :Tag  :CodeEntity
- NO label :EntryPoint — use f.is_entry_point = true
- NO property f.vulnerable — use f.is_buggy = true

=== REASONING RULES ===
1. ALWAYS use tools — never hallucinate names, file paths, relationships, or source code
2. "What does X do?" / "explain X"       -> get_node_details first; fallback to search_by_concept if not found
3. "Show me the code / source of X"      -> get_node_details — the `body` field IS the full source code; always display it verbatim in a code block
4. "What calls X / impact of X?"         -> get_impact_analysis (includes callers + callees)
5. "Find X-related code"                 -> search_by_concept
6. "What exists in layer Y?"             -> run_cypher
7. "Explain architecture / flow"         -> search_by_concept + run_cypher combined
8. "What bugs / vulnerabilities exist?" / "show me HIGH/CRITICAL bugs" -> ALWAYS call find_vulnerabilities (with the appropriate severity_filter) — NEVER answer from the context overview alone; the context summary is incomplete and lacks exact file paths and per-severity details
9. "Is X safe?" / "is X buggy?" / "does X have vulnerabilities?" -> call get_node_details(X); report is_buggy and severity fields exactly as returned — NEVER infer severity from other functions
10. "Which entry points -> bugs?"         -> find_vulnerable_paths (multi-hop call graph traversal)
11. If get_node_details returns not found -> ALWAYS retry with search_by_concept before giving up
12. Chain multiple tools for complex questions; one tool is rarely enough
13. NEVER guess or infer file paths, function names, severities, or code — only report what tools explicitly return
14. NEVER cross-contaminate data between tool results — each function's severity comes ONLY from its own entry in get_node_details (is_buggy + severity fields) or from find_vulnerabilities output where it explicitly appears
15. If a function does NOT appear in find_vulnerabilities results, it is SAFE — never assign it a severity level
16. When asked "is [category] code safe?": call search_by_concept to find relevant functions, then call get_node_details for EACH function and report the is_buggy and severity fields verbatim — do NOT infer severity from other bugs in the codebase

=== RESPONSE FORMAT ===
Structure every response as a professional report:

## [Descriptive Title]

**[One-sentence direct answer to the question.]**

### Section 1 — [Relevant heading e.g. "Overview", "Function Details", "Vulnerabilities Found"]
- Use bullet points or numbered lists for multiple items
- Each item: **name** — explanation (file, layer, impact score where relevant)
- Show call chains as: `funcA` -> `funcB` -> `funcC`

### Section 2 — [e.g. "Impact Analysis", "Risk Assessment", "Call Graph"]
- Specific, actionable details from graph data
- Highlight key risks, bottlenecks, or important observations in **bold**
- For bugs: always state severity level + which callers are affected

### Summary
- 2-4 bullet points capturing the most important takeaways
- End with a concrete recommendation or next step where applicable

FORMATTING RULES:
- Use ## for main title, ### for sections, **bold** for key names/risks
- Use backticks for inline function names: `functionName()`
- Use fenced code blocks with language tag for source code: ```java ... ``` or ```cpp ... ```
- Use numbered lists when order matters, bullets otherwise
- Severity labels always in CAPS: CRITICAL, HIGH, MEDIUM, LOW
- Never use vague phrases like "some functions" — always name them specifically
- Never say "I cannot show source code" — use get_node_details which returns the body field
- NEVER state a severity level (CRITICAL/HIGH/MEDIUM/LOW) for any function unless that exact function appeared in a tool result with that exact severity in THIS conversation
- Keep sections tight — depth over breadth
"""


class CodebaseAgent:
    """
    Production GraphRAG agent.

    Usage:
        agent = CodebaseAgent()
        answer = agent.chat("What does validateCredentials do?")

        # Multi-turn conversation
        history = []
        answer, history = agent.chat_with_history("Explain login flow", history)
        answer, history = agent.chat_with_history("What about security?", history)
    """

    def __init__(
        self,
        neo4j_uri:      str | None = None,
        neo4j_user:     str | None = None,
        neo4j_password: str | None = None,
        max_turns:      int = 12,
    ) -> None:
        uri  = neo4j_uri      or os.getenv("NEO4J_URI",      "bolt://localhost:7687")
        user = neo4j_user     or os.getenv("NEO4J_USER",     "neo4j")
        pwd  = neo4j_password or os.getenv("NEO4J_PASSWORD", "")

        print("Connecting to Neo4j...")
        self._neo4j = Neo4jClient(uri, user, pwd)

        print("Loading embedding model...")
        self._embedder = EmbeddingGenerator()

        self._tools_impl  = GraphTools(self._neo4j, self._embedder)
        self._tool_decls  = build_tool_declarations()
        self._max_turns   = max_turns

        print("Initialising Gemini client...")
        self._gemini = genai.Client(
            vertexai=True,
            project=os.getenv("GCP_PROJECT_ID", ""),
            location=os.getenv("GCP_LOCATION", "global"),
        )
        self._model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        print("Building graph context from Neo4j...")
        graph_ctx = build_graph_context(self._neo4j)
        self._system_prompt = _SYSTEM_TEMPLATE.format(graph_context=graph_ctx)

        print(f"Agent ready. Model: {self._model}\n")

    # ── Public API ─────────────────────────────────────────────────────────────

    def chat(self, message: str) -> str:
        """Single-turn chat. Returns the agent's final text answer."""
        answer, _ = self.chat_with_history(message, [])
        return answer

    def chat_with_history(
        self,
        message:  str,
        history:  list[types.Content],
    ) -> tuple[str, list[types.Content]]:
        """
        Multi-turn chat that maintains conversation history.

        Args:
            message : the new user message
            history : previous conversation turns (Content objects)

        Returns:
            (answer_text, updated_history)
        """
        conversation: list[types.Content] = list(history) + [
            types.Content(role="user", parts=[types.Part(text=message)])
        ]

        for turn in range(self._max_turns):
            response = self._gemini.models.generate_content(
                model=self._model,
                contents=conversation,
                config=self._get_config(),
            )

            candidate     = response.candidates[0]
            model_content = candidate.content

            # Guard: Gemini 2.5 thinking models emit empty/thought-only turns
            # during internal reasoning — just continue the loop rather than bail.
            if model_content is None or not model_content.parts:
                continue

            function_calls = self._extract_function_calls(model_content)
            tool_call_made = bool(function_calls)

            if function_calls:
                conversation.append(model_content)
                response_parts: list[types.Part] = []
                for fn in function_calls:
                    args = dict(fn.args)
                    print(f"  [tool] {fn.name}({_fmt_args(args)})")
                    result = self._call_tool(fn.name, args)
                    print(f"  [tool] -> {len(result)} chars returned")
                    response_parts.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=fn.name,
                                response={"result": result},
                            )
                        )
                    )
                conversation.append(types.Content(role="user", parts=response_parts))

            if not tool_call_made:
                text_parts = [
                    p.text for p in model_content.parts
                    if p.text and not getattr(p, "thought", False)
                ]
                answer = "\n".join(text_parts).strip()
                conversation.append(model_content)
                return answer, conversation

        return (
            "I reached the maximum reasoning steps for this question. "
            "Please try a more specific query.",
            conversation,
        )

    def stream_chat_with_history(
        self,
        message: str,
        history: list[types.Content],
    ) -> Iterator[dict]:
        """
        Streaming version of chat_with_history.

        Yields live events so callers can show real-time progress:
          {"type": "thinking"}
          {"type": "tool_call",   "tool": name, "args": {safe_args}}
          {"type": "tool_result", "tool": name, "chars": N}
          {"type": "chunk",       "text": "word "}   ← final answer, word by word
          {"type": "done",        "answer": full_text, "history": updated_history}

        Designed to run in a background thread; pull events via queue.Queue.
        """
        conversation: list[types.Content] = list(history) + [
            types.Content(role="user", parts=[types.Part(text=message)])
        ]

        yield {"type": "thinking"}

        for turn in range(self._max_turns):
            response = self._gemini.models.generate_content(
                model=self._model,
                contents=conversation,
                config=self._get_config(),
            )

            candidate     = response.candidates[0]
            model_content = candidate.content

            if model_content is None or not model_content.parts:
                continue

            function_calls = self._extract_function_calls(model_content)

            if function_calls:
                conversation.append(model_content)
                response_parts: list[types.Part] = []

                for fn in function_calls:
                    args   = dict(fn.args)
                    yield {"type": "tool_call", "tool": fn.name, "args": _safe_args(args)}

                    result = self._call_tool(fn.name, args)
                    yield {"type": "tool_result", "tool": fn.name, "chars": len(result)}

                    response_parts.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=fn.name,
                                response={"result": result},
                            )
                        )
                    )

                conversation.append(types.Content(role="user", parts=response_parts))

            else:
                # Final answer turn — stream word by word then emit done
                text_parts = [
                    p.text for p in model_content.parts
                    if p.text and not getattr(p, "thought", False)
                ]
                answer = "\n".join(text_parts).strip()
                conversation.append(model_content)

                words = answer.split(" ")
                for i, word in enumerate(words):
                    yield {"type": "chunk", "text": word if i == 0 else " " + word}

                yield {"type": "done", "answer": answer, "history": conversation}
                return

        # Max turns reached
        fallback = (
            "I reached the maximum reasoning steps for this question. "
            "Please try a more specific query."
        )
        yield {"type": "chunk", "text": fallback}
        yield {"type": "done", "answer": fallback, "history": conversation}

    def refresh_context(self) -> None:
        """
        Rebuild the graph overview injected into the system prompt.
        Call this after a new codebase ingest so the agent reflects the
        latest graph without requiring a server restart.
        """
        try:
            graph_ctx = build_graph_context(self._neo4j)
            self._system_prompt = _SYSTEM_TEMPLATE.format(graph_context=graph_ctx)
            print("Agent graph context refreshed.")
        except Exception as exc:
            print(f"Warning: failed to refresh agent context — {exc}")

    def close(self) -> None:
        """Close Neo4j connection."""
        self._neo4j.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _get_config(self) -> types.GenerateContentConfig:
        """Single source of truth for Gemini generation config."""
        return types.GenerateContentConfig(
            tools=self._tool_decls,
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="AUTO")
            ),
            system_instruction=self._system_prompt,
            temperature=0.2,
        )

    def _extract_function_calls(self, model_content: types.Content) -> list:
        """
        Extract all function_call parts from a model Content object,
        skipping internal thought parts emitted by Gemini thinking models.

        Gemini requires: #function_response == #function_call in the same turn.
        Collecting all calls upfront ensures we always match the count.
        """
        return [
            part.function_call
            for part in model_content.parts
            if part.function_call and not getattr(part, "thought", False)
        ]

    # ── Tool dispatch ──────────────────────────────────────────────────────────

    def _call_tool(self, name: str, args: dict) -> str:
        try:
            match name:
                case "search_by_concept":
                    return self._tools_impl.search_by_concept(
                        args["search_query"], int(args.get("top_k", 5))
                    )
                case "get_node_details":
                    return self._tools_impl.get_node_details(args["entity_name"])
                case "trace_callers":
                    return self._tools_impl.trace_callers(
                        args["function_name"], int(args.get("depth", 2))
                    )
                case "trace_callees":
                    return self._tools_impl.trace_callees(
                        args["function_name"], int(args.get("depth", 2))
                    )
                case "get_impact_analysis":
                    return self._tools_impl.get_impact_analysis(args["function_name"])
                case "find_vulnerabilities":
                    return self._tools_impl.find_vulnerabilities(
                        args.get("severity_filter", "")
                    )
                case "find_vulnerable_paths":
                    return self._tools_impl.find_vulnerable_paths()
                case "run_cypher":
                    return self._tools_impl.run_cypher(args["cypher_query"])
                case _:
                    return f"Unknown tool: {name}"
        except Exception as exc:
            return f"Tool '{name}' error: {exc}"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_args(args: dict) -> str:
    """Format args for compact console logging."""
    parts = []
    for k, v in args.items():
        v_str = str(v)
        if len(v_str) > 60:
            v_str = v_str[:57] + "..."
        parts.append(f"{k}={v_str!r}")
    return ", ".join(parts)


def _safe_args(args: dict) -> dict:
    """
    Truncate long arg values for SSE payloads (keeps JSON small).
    Values longer than 200 chars are trimmed to avoid overwhelming the client.
    """
    return {
        k: (v[:197] + "...") if isinstance(v, str) and len(v) > 200 else v
        for k, v in args.items()
    }


# ── CLI for quick testing ──────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  CodebaseAgent — Interactive CLI")
    print("  Type 'quit' to exit, 'reset' to clear history")
    print("=" * 60 + "\n")

    agent   = CodebaseAgent()
    history: list[types.Content] = []

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            break
        if user_input.lower() == "reset":
            history = []
            print("History cleared.\n")
            continue

        answer, history = agent.chat_with_history(user_input, history)
        print(f"\nAgent: {answer}\n")

    agent.close()
