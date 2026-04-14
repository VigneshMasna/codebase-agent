# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Build the React frontend
# No VITE_* env vars are used in the source code — the frontend uses relative
# API paths (baseURL: '') so the same FastAPI process serves both backend and
# frontend with no env baking needed.
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /frontend

# Copy dependency manifests first for better layer caching
COPY package.json package-lock.json ./
RUN npm install --ignore-scripts

# Copy all frontend source files
COPY index.html vite.config.js tailwind.config.js postcss.config.js ./
COPY src/ ./src/

# Build the production bundle → /frontend/dist
RUN npm run build


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Python backend
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# System dependencies:
#   build-essential  — compiles C extensions (tree-sitter-languages, tokenizers)
#   git              — used by some HuggingFace packages at install time
#   curl             — used by the HEALTHCHECK
#   libgomp1         — required by PyTorch CPU builds on Debian slim images
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# --extra-index-url for CPU-only PyTorch (defined in requirements.txt)
# --timeout 600 prevents read-timeout when downloading large wheels (~200 MB)
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 600 -r requirements.txt

# ── Smoke-test tree-sitter-languages at build time ────────────────────────────
# This is the exact failure that caused "0 nodes" on Cloud Run:
# the manylinux wheel installed fine but its pre-compiled .so couldn't load
# the C/C++/Java grammars at runtime, silently skipping every file.
# Catching it here (build time) is far better than catching it after deploy.
RUN python - <<'EOF'
try:
    from tree_sitter_languages import get_language, get_parser
    for lang in ("c", "cpp", "java"):
        get_language(lang)
        get_parser(lang)
    print("tree-sitter-languages: C / C++ / Java parsers OK")
except Exception as e:
    raise SystemExit(
        f"FATAL: tree-sitter-languages binary is incompatible with this platform: {e}\n"
        "Fix: check the manylinux wheel for tree-sitter-languages on python:3.11-slim."
    )
EOF

# ── Pre-download HuggingFace models ──────────────────────────────────────────
# Baking models into the image eliminates cold-start download delays on
# Cloud Run (GraphCodeBERT x2 + all-MiniLM-L6-v2 = ~1 GB total).
# HF_HOME is set here so the cache lands in the same path used at runtime.
ENV HF_HOME=/app/.hf_cache
RUN python - <<'EOF'
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSequenceClassification

print("Downloading all-MiniLM-L6-v2...")
SentenceTransformer("all-MiniLM-L6-v2")

print("Downloading graphcodebert-c-bug-detector...")
AutoTokenizer.from_pretrained("2451-22-749-016/graphcodebert-c-bug-detector")
AutoModelForSequenceClassification.from_pretrained("2451-22-749-016/graphcodebert-c-bug-detector")

print("Downloading graphcodebert-java-bug-detector...")
AutoTokenizer.from_pretrained("2451-22-749-016/graphcodebert-java-bug-detector")
AutoModelForSequenceClassification.from_pretrained("2451-22-749-016/graphcodebert-java-bug-detector")

print("All models cached.")
EOF

# ── Copy application source ───────────────────────────────────────────────────
COPY api/         ./api/
COPY graph_rag/   ./graph_rag/
COPY vuln_scanner/ ./vuln_scanner/
COPY main.py      .

# ── Copy compiled React frontend ──────────────────────────────────────────────
# FastAPI serves index.html + static assets from /app/static via the
# catch-all route defined in api/main.py (the SPA mount).
COPY --from=frontend-builder /frontend/dist ./static/

# ── Runtime configuration ─────────────────────────────────────────────────────
# PORT: Uvicorn bind port (overridable via docker-compose environment).
ENV PORT=8080

EXPOSE 8080

# Health check — gives 120 s for startup because GraphCodeBERT models (~1 GB)
# are downloaded from HuggingFace Hub on the very first container start.
# Subsequent starts are fast (cache hit in the hf_model_cache volume).
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Start the FastAPI server.
# uvicorn loads api.main:app which, in its lifespan handler, connects to Neo4j,
# loads the GraphCodeBERT tokenizer + model from HF Hub (or local cache), and
# loads the all-MiniLM-L6-v2 sentence-transformer.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
