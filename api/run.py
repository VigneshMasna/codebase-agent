"""
Entry point for the codebase-agent API server.

Usage:
    # From the repo root:
    python -m api.run

    # Or directly:
    python api/run.py

    # Or with uvicorn directly (auto-reload for development):
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

Environment variables (all optional, fall back to defaults):
    API_HOST    — bind host  (default: 0.0.0.0)
    API_PORT    — bind port  (default: 8000)
    API_RELOAD  — auto-reload for development (default: false)
    API_WORKERS — number of worker processes (default: 1; >1 disables reload)
    LOG_LEVEL   — uvicorn log level: debug|info|warning|error (default: info)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path when run as a script
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import uvicorn
from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")


def main() -> None:
    host    = os.getenv("API_HOST",    "0.0.0.0")
    port    = int(os.getenv("API_PORT",    "8000"))
    reload  = os.getenv("API_RELOAD",  "false").lower() in ("1", "true", "yes")
    workers = int(os.getenv("API_WORKERS", "1"))
    log_lvl = os.getenv("LOG_LEVEL",   "info").lower()

    # Workers > 1 is incompatible with reload mode
    if reload and workers > 1:
        print("WARNING: API_WORKERS > 1 is incompatible with reload mode. Using 1 worker.")
        workers = 1

    print(f"\n{'='*54}")
    print(f"  codebase-agent API")
    print(f"  http://{host}:{port}")
    print(f"  Docs:  http://{host}:{port}/docs")
    print(f"  Reload: {reload}  |  Workers: {workers}  |  Log: {log_lvl}")
    print(f"{'='*54}\n")

    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        log_level=log_lvl,
        # Allows the SSE responses to flush immediately without buffering
        timeout_keep_alive=65,
    )


if __name__ == "__main__":
    main()
