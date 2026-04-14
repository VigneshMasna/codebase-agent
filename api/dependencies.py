"""
FastAPI dependency injection helpers.

Usage in route handlers:
    from api.dependencies import require_scanner, require_agent, require_neo4j

    @router.post("/scan/code")
    def scan_code(req: ScanCodeRequest, scanner = Depends(require_scanner)):
        ...

Each `require_*` raises HTTP 503 (Service Unavailable) with a human-readable
message when the underlying resource failed to initialise at startup, rather
than propagating an unintelligible 500 error.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, status

from api.config import get_scanner, get_agent, get_neo4j


# ── Scanner ───────────────────────────────────────────────────────────────────

def require_scanner():
    """
    Dependency that resolves to the CodeScanner singleton.
    Raises 503 if the scanner could not be loaded (e.g. missing model files).
    """
    scanner, error = get_scanner()
    if scanner is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Vulnerability scanner is unavailable: {error}. "
                "Check that GraphCodeBERT model files exist and GCP credentials are set in .env."
            ),
        )
    return scanner


# ── Agent ─────────────────────────────────────────────────────────────────────

def require_agent():
    """
    Dependency that resolves to the CodebaseAgent singleton.
    Raises 503 if the agent failed to initialise.
    """
    agent, error = get_agent()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Codebase agent is unavailable: {error}. "
                "Check Neo4j connectivity, GCP_PROJECT_ID, and embedding model."
            ),
        )
    return agent


# ── Neo4j (direct graph queries) ──────────────────────────────────────────────

def require_neo4j():
    """
    Dependency that resolves to the Neo4jClient singleton used by graph routes.
    Raises 503 if Neo4j is unreachable.
    """
    client, error = get_neo4j()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Neo4j is unavailable: {error}. "
                "Check NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD in .env."
            ),
        )
    return client
