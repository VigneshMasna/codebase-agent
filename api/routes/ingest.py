"""
Ingest routes — submit a codebase for full graph extraction + vulnerability scan.

Endpoints:
  POST /ingest              — start a job from a server-side folder path
  POST /ingest/upload       — upload a .zip of the codebase, extract + ingest
  GET  /ingest/status/{id}  — poll JSON status (status, pct, result, error)
  GET  /ingest/progress/{id}— Server-Sent Events stream of progress events
  GET  /ingest/jobs         — list all jobs
  DELETE /ingest/{id}       — remove a completed / errored job

Flow (both variants):
  1. POST → job created, background thread started → {"job_id": "..."}
  2. Frontend opens GET /ingest/progress/{job_id} (SSE stream)
  3. Pipeline pushes events into job.events list
  4. SSE generator yields events as they arrive
  5. Final "done" or "error" event closes the stream
  6. For /upload: temp directory is cleaned up after the pipeline finishes

SSE event shape:
  {"type": "progress", "step": N, "step_name": "...", "message": "...", "progress_pct": 0-100}
  {"type": "error",    "step": 0, "step_name": "...", "message": "..."}
  {"type": "done",     "status": "complete"|"error", "result": {...} | "error": "..."}

Zip-slip protection:
  All paths inside the uploaded zip are validated before extraction to
  prevent directory-traversal attacks.
"""
from __future__ import annotations

import asyncio
import shutil
import tempfile
import threading
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import json
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from api.models.requests import IngestRequest
from api.models.responses import IngestJobStarted, IngestStatus
from api.services.ingest_service import IngestService

router = APIRouter()

_MAX_ZIP_BYTES   = 512 * 1024 * 1024  # 512 MB hard limit on uploaded zips
_MAX_FILE_BYTES  = 10  * 1024 * 1024  # 10 MB limit for individual code files

# Extensions accepted as single-file uploads (must match repo_scanner)
_CODE_EXTENSIONS = {".c", ".cpp", ".h", ".java"}


# ── In-memory job store ───────────────────────────────────────────────────────

@dataclass
class IngestJob:
    job_id:       str
    folder_path:  str
    status:       str = "running"          # running | complete | error
    events:       list[dict] = field(default_factory=list)
    result:       Optional[dict] = None
    error:        Optional[str] = None
    started_at:   str = field(default_factory=lambda: _now())
    finished_at:  Optional[str] = None
    _done:        bool = field(default=False, repr=False)

    def add_event(self, type_: str, step: int, step_name: str,
                  message: str, pct: int) -> None:
        self.events.append({
            "type":         type_,
            "step":         step,
            "step_name":    step_name,
            "message":      message,
            "progress_pct": pct,
            "ts":           _now(),
        })

    def finish(self, result: dict) -> None:
        self.status      = "complete"
        self.result      = result
        self.finished_at = _now()
        self._done       = True

    def fail(self, error: str) -> None:
        self.status      = "error"
        self.error       = error
        self.finished_at = _now()
        self._done       = True


_jobs: dict[str, IngestJob] = {}
_jobs_lock = threading.Lock()


# ── POST /ingest ──────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=IngestJobStarted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start ingestion from a server-side folder path",
    description=(
        "Starts the full extraction pipeline as a background task. "
        "Returns a job_id immediately. "
        "Connect to GET /ingest/progress/{job_id} for live SSE progress."
    ),
)
async def start_ingest(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
) -> IngestJobStarted:
    # ── Early validation — fail fast before starting the background thread ──
    folder = Path(request.folder_path)
    if not folder.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Folder not found: {folder}. "
                   "Provide an absolute path to a directory on the server.",
        )
    if not folder.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path is not a directory: {folder}",
        )

    job_id = str(uuid.uuid4())
    job    = IngestJob(job_id=job_id, folder_path=str(folder.resolve()))

    with _jobs_lock:
        _jobs[job_id] = job

    background_tasks.add_task(
        _run_pipeline,
        job_id=      job_id,
        folder_path= str(folder.resolve()),
        clear_first= request.clear_first,
        skip_enrich= request.skip_enrich,
        skip_scan=   request.skip_scan,
        cleanup_dir= None,
    )

    return IngestJobStarted(job_id=job_id)


# ── POST /ingest/upload ───────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=IngestJobStarted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a .zip codebase and ingest it",
    description=(
        "Upload a .zip archive of your codebase. The server extracts it to a "
        "secure temporary directory, runs the full extraction pipeline, then "
        "deletes the temporary files. "
        "Max upload size: 512 MB. "
        "Returns a job_id immediately — connect to GET /ingest/progress/{job_id} "
        "for live SSE progress events."
    ),
)
async def upload_and_ingest(
    background_tasks: BackgroundTasks,
    file:        UploadFile  = File(...,        description="Codebase archive (.zip only)"),
    clear_first: bool        = Form(False,      description="Wipe existing Neo4j graph first"),
    skip_enrich: bool        = Form(False,      description="Skip Gemini enrichment (faster)"),
    skip_scan:   bool        = Form(False,      description="Skip vulnerability scan"),
) -> IngestJobStarted:
    # Validate file type
    filename  = file.filename or ""
    suffix    = Path(filename).suffix.lower()
    is_zip    = suffix == ".zip"
    is_code   = suffix in _CODE_EXTENSIONS

    if not is_zip and not is_code:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type '{suffix}'. "
                "Upload a .zip archive or an individual code file "
                "(.java, .c, .cpp, .h)."
            ),
        )

    size_limit = _MAX_ZIP_BYTES if is_zip else _MAX_FILE_BYTES
    limit_label = "512 MB" if is_zip else "10 MB"

    # ── Stream upload to temp directory ──────────────────────────────────────
    tmp_dir  = Path(tempfile.mkdtemp(prefix="codebase_ingest_"))
    save_path = tmp_dir / filename

    try:
        bytes_written = 0
        with save_path.open("wb") as dest:
            while True:
                chunk = await file.read(1024 * 1024)  # 1 MB chunks
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > size_limit:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Upload exceeds the {limit_label} limit ({bytes_written} bytes received).",
                    )
                dest.write(chunk)
    except HTTPException:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {exc}",
        )
    finally:
        await file.close()

    # ── Determine repo_path ───────────────────────────────────────────────────
    if is_zip:
        # Extract zip safely (zip-slip protection)
        extract_dir = tmp_dir / "extracted"
        extract_dir.mkdir()
        try:
            _safe_extract(save_path, extract_dir)
        except (zipfile.BadZipFile, ValueError) as exc:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid or unsafe zip file: {exc}",
            )
        except Exception as exc:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to extract zip: {exc}",
            )
        # If the zip contains a single top-level folder, use that as repo root
        repo_path = _find_repo_root(extract_dir)
        msg = f"Zip extracted ({bytes_written // 1024} KB). Pipeline started."
    else:
        # Single code file — the temp dir itself is the repo root
        repo_path = tmp_dir
        msg = f"File received ({bytes_written // 1024} KB). Pipeline started."

    job_id = str(uuid.uuid4())
    job    = IngestJob(job_id=job_id, folder_path=str(repo_path))

    with _jobs_lock:
        _jobs[job_id] = job

    background_tasks.add_task(
        _run_pipeline,
        job_id=      job_id,
        folder_path= str(repo_path),
        clear_first= clear_first,
        skip_enrich= skip_enrich,
        skip_scan=   skip_scan,
        cleanup_dir= str(tmp_dir),   # deleted after pipeline finishes
    )

    return IngestJobStarted(
        job_id=  job_id,
        message= (
            f"{msg} Connect to /ingest/progress/{job_id} for live updates."
        ),
    )


# ── GET /ingest/status/{job_id} ───────────────────────────────────────────────

@router.get(
    "/status/{job_id}",
    response_model=IngestStatus,
    summary="Poll ingest job status (JSON)",
    description=(
        "Returns the current status, progress percentage, and result. "
        "Use this as a lightweight polling fallback if SSE is not available."
    ),
)
def get_ingest_status(job_id: str) -> IngestStatus:
    job        = _get_job(job_id)
    last_event = job.events[-1] if job.events else None
    return IngestStatus(
        job_id=       job.job_id,
        status=       job.status,
        current_step= last_event["step_name"]    if last_event else None,
        progress_pct= last_event["progress_pct"] if last_event else 0,
        result=       job.result,
        error=        job.error,
    )


# ── GET /ingest/progress/{job_id} — SSE stream ────────────────────────────────

@router.get(
    "/progress/{job_id}",
    summary="Stream ingest progress via Server-Sent Events",
    description=(
        "Connect with EventSource to receive live progress events while the "
        "pipeline runs. Reconnecting clients receive all previously emitted "
        "events first (catch-up), then live events. "
        "The stream closes automatically when the job completes or errors."
    ),
)
async def stream_progress(job_id: str) -> StreamingResponse:
    _get_job(job_id)  # raises 404 if not found
    return StreamingResponse(
        _sse_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


async def _sse_generator(job_id: str):
    """
    Yields SSE-formatted events as they are added to the job's event list.
    Reconnecting clients catch up instantly — all prior events are replayed
    before switching to live-polling mode.
    """
    idx = 0
    yield ": connected\n\n"

    while True:
        job = _jobs.get(job_id)
        if job is None:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Job not found'})}\n\n"
            return

        # Drain any unread events (replay for reconnecting clients too)
        while idx < len(job.events):
            yield f"data: {json.dumps(job.events[idx])}\n\n"
            idx += 1

        if job._done:
            final: dict = {"type": "done", "status": job.status}
            if job.result:
                final["result"] = job.result
            if job.error:
                final["error"] = job.error
            yield f"data: {json.dumps(final)}\n\n"
            return

        await asyncio.sleep(0.5)


# ── GET /ingest/jobs ──────────────────────────────────────────────────────────

@router.get(
    "/jobs",
    summary="List all ingest jobs",
    description="Returns a summary list of all known ingest jobs and their statuses.",
)
def list_jobs() -> list[dict]:
    with _jobs_lock:
        return [
            {
                "job_id":       j.job_id,
                "folder_path":  j.folder_path,
                "status":       j.status,
                "started_at":   j.started_at,
                "finished_at":  j.finished_at,
                "progress_pct": j.events[-1]["progress_pct"] if j.events else 0,
            }
            for j in _jobs.values()
        ]


# ── DELETE /ingest/{job_id} ───────────────────────────────────────────────────

@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an ingest job record",
    description="Remove a completed or errored job. Cannot delete a running job.",
)
def delete_job(job_id: str) -> None:
    job = _get_job(job_id)
    if not job._done:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a running job. Wait for it to complete or error first.",
        )
    with _jobs_lock:
        _jobs.pop(job_id, None)


# ── Background pipeline task ──────────────────────────────────────────────────

def _run_pipeline(
    job_id:      str,
    folder_path: str,
    clear_first: bool,
    skip_enrich: bool,
    skip_scan:   bool,
    cleanup_dir: Optional[str],
) -> None:
    """
    Runs IngestService in a background thread.
    Updates IngestJob with live progress and final result / error.
    Cleans up cleanup_dir (temp extraction dir) when done, if provided.
    """
    job = _jobs.get(job_id)
    if job is None:
        return

    def on_progress(step: int, step_name: str, message: str, pct: int) -> None:
        job.add_event("progress", step, step_name, message, pct)

    try:
        service = IngestService(progress_callback=on_progress)
        result  = service.run(
            folder_path= folder_path,
            clear_first= clear_first,
            skip_enrich= skip_enrich,
            skip_scan=   skip_scan,
        )
        job.finish(result)

        # Refresh agent's graph context so /chat reflects the new codebase
        try:
            from api.config import refresh_agent_context
            refresh_agent_context()
        except Exception:
            pass

    except (FileNotFoundError, ValueError) as exc:
        job.add_event("error", 0, "Validation error", str(exc), 0)
        job.fail(str(exc))
    except (ConnectionError, RuntimeError) as exc:
        job.add_event("error", 0, "Pipeline error", str(exc), 0)
        job.fail(str(exc))
    except Exception as exc:
        job.add_event("error", 0, "Unexpected error", str(exc), 0)
        job.fail(f"Unexpected error: {exc}")
    finally:
        # Always clean up the temp directory from zip uploads
        if cleanup_dir:
            shutil.rmtree(cleanup_dir, ignore_errors=True)


# ── Zip helpers ───────────────────────────────────────────────────────────────

def _safe_extract(zf_path: Path, dest: Path) -> None:
    """
    Extract a zip file to dest, preventing zip-slip path traversal.

    Raises ValueError if any member path escapes the destination directory.
    """
    dest_resolved = dest.resolve()
    with zipfile.ZipFile(zf_path) as zf:
        for member in zf.infolist():
            member_path = (dest / member.filename).resolve()
            if not str(member_path).startswith(str(dest_resolved)):
                raise ValueError(
                    f"Unsafe path in zip: '{member.filename}' escapes the extraction directory."
                )
        zf.extractall(dest)


def _find_repo_root(extract_dir: Path) -> Path:
    """
    If the zip contains a single top-level directory (the common zip pattern
    where repo.zip → repo/ → files…), return that directory as the repo root.
    Otherwise return extract_dir itself.
    """
    entries = [e for e in extract_dir.iterdir() if not e.name.startswith(".")]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return extract_dir


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_job(job_id: str) -> IngestJob:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingest job '{job_id}' not found.",
        )
    return job


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
