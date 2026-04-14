"""
Shared resource management for the codebase-agent API.

Singletons (_scanner, _agent, _neo4j) are created once at server startup via
init_resources() and torn down at shutdown via cleanup_resources().

Design:
  - Failures during init are LOGGED but do NOT crash the server.
    Each resource records its own error string so endpoints can return
    503 with a clear message instead of a blind 500.
  - _neo4j is separate from the agent's internal connection so the
    /api/graph and /api/scan-results routes can run independent queries.
  - refresh_agent_context() rebuilds the agent's graph overview after
    an ingest job finishes so it reflects the newly ingested codebase.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Path bootstrapping ────────────────────────────────────────────────────────
# Makes graph_rag sub-packages (agent, graph, embedding, …) importable with
# short names (e.g. "from graph.neo4j_client import …") matching the existing
# convention across the codebase.  Also ensures the repo root is on sys.path
# so "from vuln_scanner.core.scanner import …" keeps working.

_ROOT = Path(__file__).parent.parent  # repo root

for _p in (str(_ROOT), str(_ROOT / "graph_rag")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ── Singleton storage ─────────────────────────────────────────────────────────

_scanner = None          # vuln_scanner.core.scanner.CodeScanner
_agent   = None          # graph_rag.agent.codebase_agent.CodebaseAgent
_neo4j   = None          # graph_rag.graph.neo4j_client.Neo4jClient

_scanner_error: Optional[str] = None
_agent_error:   Optional[str] = None
_neo4j_error:   Optional[str] = None


# ── Lifecycle ─────────────────────────────────────────────────────────────────

def init_resources() -> None:
    """
    Initialize all shared resources at server startup.

    Every resource is attempted independently so a failure in one (e.g. missing
    GraphCodeBERT model weights) does NOT prevent others from loading.
    """
    global _scanner, _agent, _neo4j
    global _scanner_error, _agent_error, _neo4j_error

    _fix_gac_path()

    # 1. Neo4j — used by /api/graph + /api/scan-results
    logger.info("Connecting to Neo4j...")
    try:
        from graph.neo4j_client import Neo4jClient  # short import via sys.path
        _neo4j = Neo4jClient(
            uri=os.getenv("NEO4J_URI",      "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER",    "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", ""),
        )
        logger.info("Neo4j connected.")
    except Exception as exc:
        _neo4j_error = str(exc)
        logger.error("Neo4j unavailable at startup: %s", exc)

    # 2. Vulnerability scanner — used by /scan/*
    logger.info("Loading vulnerability scanner (GraphCodeBERT + LLM)...")
    try:
        from vuln_scanner.core.scanner import CodeScanner
        _scanner = CodeScanner()
        logger.info("Vulnerability scanner loaded.")
    except Exception as exc:
        _scanner_error = str(exc)
        logger.error("Scanner unavailable: %s", exc)

    # 3. Codebase agent — used by /chat/*
    # The agent creates its own internal Neo4j + embedder, so it is independent
    # of the _neo4j singleton above.
    logger.info("Initialising codebase agent (loads embedding model + Neo4j + Gemini)...")
    try:
        from agent.codebase_agent import CodebaseAgent  # short import
        _agent = CodebaseAgent(
            neo4j_uri=      os.getenv("NEO4J_URI",      "bolt://localhost:7687"),
            neo4j_user=     os.getenv("NEO4J_USER",     "neo4j"),
            neo4j_password= os.getenv("NEO4J_PASSWORD", ""),
        )
        logger.info("Codebase agent ready.")
    except Exception as exc:
        _agent_error = str(exc)
        logger.error("Agent unavailable: %s", exc)


def cleanup_resources() -> None:
    """Close all long-lived connections at server shutdown."""
    global _neo4j, _agent

    if _agent is not None:
        try:
            _agent.close()
        except Exception as exc:
            logger.warning("Error closing agent: %s", exc)

    if _neo4j is not None:
        try:
            _neo4j.close()
        except Exception as exc:
            logger.warning("Error closing Neo4j client: %s", exc)

    logger.info("API resources cleaned up.")


def refresh_agent_context() -> None:
    """
    Rebuild the agent's graph overview after a successful ingest.

    This is called by the ingest service once the pipeline completes so that
    subsequent /chat queries reflect the new codebase without a server restart.
    """
    if _agent is None:
        return
    try:
        # Delegates to the agent's own public method — no private attribute access
        _agent.refresh_context()
        logger.info("Agent graph context refreshed after ingest.")
    except Exception as exc:
        logger.warning("Failed to refresh agent context: %s", exc)


# ── Accessors ─────────────────────────────────────────────────────────────────

def get_scanner():
    """Return (scanner_instance_or_None, error_string_or_None)."""
    return _scanner, _scanner_error


def get_agent():
    """Return (agent_instance_or_None, error_string_or_None)."""
    return _agent, _agent_error


def get_neo4j():
    """Return (neo4j_client_or_None, error_string_or_None)."""
    return _neo4j, _neo4j_error


# ── Internal helpers ──────────────────────────────────────────────────────────

def _fix_gac_path() -> None:
    """
    Resolve a relative GOOGLE_APPLICATION_CREDENTIALS value to an absolute path
    anchored at the repo root.  Some Google libraries fail silently on relative
    paths depending on the working directory.
    """
    gac = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if gac and not Path(gac).is_absolute():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str((_ROOT / gac).resolve())
