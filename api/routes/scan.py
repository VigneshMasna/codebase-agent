"""
Scan routes — run vulnerability detection on raw code, file, folder, or upload.

Endpoints:
  POST /scan/code     — scan a raw code snippet
  POST /scan/file     — scan a file by absolute path
  POST /scan/folder   — scan all supported files in a folder
  POST /scan/upload   — upload a file and scan it (multipart/form-data)
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from api.dependencies import require_scanner
from api.models.requests import ScanCodeRequest, ScanPathRequest
from api.models.responses import BugResult, ScanResponse, ScanSummary

router = APIRouter()

# Supported upload extensions → language name (for language detection)
_EXT_TO_LANG: dict[str, str] = {
    ".java": "java",
    ".c":    "c",
    ".h":    "c",
    ".cpp":  "cpp",
    ".cc":   "cpp",
    ".cxx":  "cpp",
    ".hpp":  "cpp",
}


# ── POST /scan/code ───────────────────────────────────────────────────────────

@router.post(
    "/code",
    response_model=ScanResponse,
    summary="Scan a raw code snippet",
    description="Submit a code snippet with its language and get vulnerability analysis.",
)
def scan_code(
    request: ScanCodeRequest,
    scanner=Depends(require_scanner),
) -> ScanResponse:
    try:
        results = scanner.scan_code(request.code, request.language, request.source)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Scanner error: {exc}")

    return _build_response(results)


# ── POST /scan/file ───────────────────────────────────────────────────────────

@router.post(
    "/file",
    response_model=ScanResponse,
    summary="Scan a file by absolute path",
    description="Provide an absolute path to a .c/.cpp/.java file on the server.",
)
def scan_file(
    request: ScanPathRequest,
    scanner=Depends(require_scanner),
) -> ScanResponse:
    file_path = Path(request.path)

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {file_path}",
        )
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path is not a file: {file_path}",
        )

    try:
        results = scanner.scan_file(file_path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Scanner error: {exc}")

    return _build_response(results)


# ── POST /scan/folder ─────────────────────────────────────────────────────────

@router.post(
    "/folder",
    response_model=ScanResponse,
    summary="Scan all supported files in a folder",
    description="Recursively scan a folder for C, C++, and Java vulnerabilities.",
)
def scan_folder(
    request: ScanPathRequest,
    scanner=Depends(require_scanner),
) -> ScanResponse:
    folder_path = Path(request.path)

    if not folder_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Folder not found: {folder_path}",
        )
    if not folder_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path is not a directory: {folder_path}",
        )

    try:
        results = scanner.scan_folder(folder_path)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Scanner error: {exc}")

    return _build_response(results)


# ── POST /scan/upload ─────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=ScanResponse,
    summary="Upload a source file and scan it",
    description=(
        "Upload a .c, .cpp, .h, .cc, .cxx, .hpp, or .java file "
        "and receive vulnerability analysis results."
    ),
)
async def scan_upload(
    file: UploadFile = File(..., description="Source code file to scan"),
    scanner=Depends(require_scanner),
) -> ScanResponse:
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()

    if ext not in _EXT_TO_LANG:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type: '{ext}'. "
                f"Supported extensions: {sorted(_EXT_TO_LANG.keys())}"
            ),
        )

    # Write upload to a temp file then scan
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = Path(tmp.name)

        results = scanner.scan_file(tmp_path)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Scanner error: {exc}")
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        await file.close()

    return _build_response(results)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_response(results: list) -> ScanResponse:
    """Convert a list of ScanResult domain objects into the API response model."""
    bugs = [r for r in results if r.final_label == "BUG"]

    sev_counts: dict[str, int] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for r in bugs:
        sev = (r.severity or "").upper()
        if sev in sev_counts:
            sev_counts[sev] += 1

    summary = ScanSummary(
        total_functions=len(results),
        bugs_found=len(bugs),
        critical=sev_counts["CRITICAL"],
        high=sev_counts["HIGH"],
        medium=sev_counts["MEDIUM"],
        low=sev_counts["LOW"],
    )

    bug_results = [
        BugResult(
            source=           r.source,
            language=         r.language,
            function_name=    r.function_name,
            function_body=    r.function_body,
            graphcodebert_label=r.graphcodebert_label,
            confidence=       round(r.confidence, 4),
            llm_label=        r.llm_label,
            severity=         r.severity,
            final_label=      r.final_label,
        )
        for r in results
    ]

    return ScanResponse(summary=summary, results=bug_results)
