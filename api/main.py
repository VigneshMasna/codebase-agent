"""
codebase-agent FastAPI application.

Startup sequence:
  1. Load .env (dotenv)
  2. init_resources() — connect Neo4j, load embedding model, scanner, agent
  3. Mount all routers
  4. Serve via uvicorn (see api/run.py)

All resources initialise independently: a failure loading the scanner does NOT
prevent the server from starting; affected endpoints return HTTP 503 with a
descriptive message until the underlying issue is resolved.
"""
from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

# ── Bootstrap paths & env ─────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent
for _p in (str(_ROOT), str(_ROOT / "graph_rag")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("codebase_agent.api")

# ── Local imports (after path setup) ─────────────────────────────────────────
from api.config import init_resources, cleanup_resources, get_neo4j, get_scanner, get_agent
from api.routes import scan, ingest, chat, graph


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting codebase-agent API…")
    init_resources()
    _log_startup_status()
    yield
    logger.info("Shutting down codebase-agent API…")
    cleanup_resources()


def _log_startup_status() -> None:
    _, neo4j_err   = get_neo4j()
    _, scanner_err = get_scanner()
    _, agent_err   = get_agent()

    logger.info("──────────────────────────────────────────")
    logger.info("  Neo4j   : %s", "OK" if not neo4j_err   else f"UNAVAILABLE — {neo4j_err}")
    logger.info("  Scanner : %s", "OK" if not scanner_err else f"UNAVAILABLE — {scanner_err}")
    logger.info("  Agent   : %s", "OK" if not agent_err   else f"UNAVAILABLE — {agent_err}")
    logger.info("──────────────────────────────────────────")


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="codebase-agent API",
        description=(
            "Vulnerability scanning and GraphRAG conversational analysis for codebases.\n\n"
            "**Three pillars:**\n"
            "- `/scan/*` — run GraphCodeBERT + LLM vulnerability detection\n"
            "- `/ingest` — extract the full code knowledge graph into Neo4j\n"
            "- `/chat` — ask natural-language questions about any ingested codebase\n"
            "- `/api/graph` — fetch graph data for interactive visualisation\n"
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    _cors_origins = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
        if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global exception handler ──────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(exc)},
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(scan.router,   prefix="/scan",   tags=["Scan"])
    app.include_router(ingest.router, prefix="/ingest", tags=["Ingest"])
    app.include_router(chat.router,   prefix="/chat",   tags=["Chat"])
    app.include_router(graph.router,  prefix="/api",    tags=["Graph"])

    # ── Health check ──────────────────────────────────────────────────────────
    # (defined before static mount so /health is never shadowed)
    @app.get("/health", tags=["Health"], summary="Server health check")
    async def health():
        _, neo4j_err   = get_neo4j()
        _, scanner_err = get_scanner()
        _, agent_err   = get_agent()
        return {
            "status":  "ok",
            "neo4j":   "ok"           if not neo4j_err   else "unavailable",
            "scanner": "ok"           if not scanner_err else "unavailable",
            "agent":   "ok"           if not agent_err   else "unavailable",
            "version": "1.0.0",
        }

    # ── Static frontend (production only) ────────────────────────────────────
    # Catch-all: serve the exact file if it exists (JS/CSS/images/favicon),
    # otherwise return index.html so React Router handles routing client-side.
    # This must be defined LAST so all API routes above take priority.
    _static = _ROOT / "static"
    if _static.exists():
        logger.info("Serving React frontend from %s", _static)

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            file_path = _static / full_path
            if file_path.is_file():
                return FileResponse(str(file_path))
            return FileResponse(str(_static / "index.html"))

    return app


# ── Module-level app instance (for uvicorn) ───────────────────────────────────
app = create_app()
