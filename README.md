# Codebase Agent

An AI-powered source code analysis platform that transforms raw C, C++, and Java codebases into a queryable knowledge graph — with built-in vulnerability detection and a conversational AI agent for natural-language code exploration.

**What it does end-to-end:**
1. Accept a `.zip` upload or folder path containing C / C++ / Java source files
2. Parse every file with Tree-Sitter, extract the full symbol graph (functions, classes, structs, call chains, inheritance)
3. Enrich each node with semantic summaries, architectural tags, and graph metrics using Gemini
4. Detect security vulnerabilities with a GraphCodeBERT + Gemini hybrid scanner
5. Store everything in a Neo4j knowledge graph
6. Let engineers explore the codebase through a Gemini ReAct agent with 8 graph-query tools, an interactive force-directed graph, and a vulnerability dashboard

---

## Table of Contents

- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Ingestion Pipeline](#ingestion-pipeline)
- [Vulnerability Scanner](#vulnerability-scanner)
- [Chat Agent](#chat-agent)
- [Neo4j Graph Schema](#neo4j-graph-schema)
- [API Reference](#api-reference)
- [Frontend](#frontend)
- [Configuration](#configuration)
- [Local Development](#local-development)
- [Docker Deployment](#docker-deployment)
- [Cloud Run Deployment](#cloud-run-deployment)
- [Common Issues](#common-issues)

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  Source Code  ─── C · C++ · Java                                     │
└───────────────────────────┬──────────────────────────────────────────┘
                            │  ZIP upload or folder path
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       Ingestion Pipeline                              │
│                                                                      │
│  Tree-Sitter Parser (AST)                                            │
│       │                                                              │
│  Symbol Extractor  ──  Function · Class · Struct · Interface         │
│       │                                                              │
│  Call & Inheritance Resolver  ──  CALLS · INHERITS_FROM · IMPLEMENTS │
│       │                                                              │
│  Metrics Computer  ──  fan_in · fan_out · impact_score               │
│       │                                                              │
│  Gemini Enrichment  ──  summary · tags · layer                       │
│       │                                                              │
│  Embedding Generator  ──  all-MiniLM-L6-v2 · 384-dim                │
│       │                                                              │
│  Similarity Enricher  ──  SIMILAR_TO edges (cosine ≥ 0.85)          │
└───────────────────────────┬──────────────────────────────────────────┘
                            │                        │
              Enriched CodeGraph          Function Bodies
                            │                        │
                            ▼                        ▼
              ┌─────────────────────┐   ┌────────────────────────────┐
              │  Neo4j Knowledge    │   │  Vulnerability Detection    │
              │      Graph          │   │                            │
              │                     │   │  GraphCodeBERT             │
              │  Cypher Queries ◄───┼───┤  + Juliet + CodeXGLUE      │
              └─────────┬───────────┘   └────────────────────────────┘
                        │                        │
              is_buggy · severity · confidence   │
                        │                        │
                        ▼
              ┌─────────────────────────────────────────────────┐
              │           GraphRAG ReAct Agent                   │
              │                                                  │
              │  Gemini ReAct Agent                              │
              │  8 Graph Query Tools:                            │
              │    nCypher · Trace · Impact · Search             │
              │                                                  │
              │  Natural Language Query ──► Structured Response  │
              └─────────────────────────────────────────────────┘
```

---

## Project Structure

```
codebase-agent/
├── api/                            # FastAPI REST server
│   ├── main.py                     # App factory, lifespan, CORS, SPA catch-all
│   ├── run.py                      # Uvicorn entry point + CLI args
│   ├── config.py                   # Singleton resource init: Neo4j, scanner, agent
│   ├── dependencies.py             # DI: graceful 503 degradation per resource
│   ├── models/
│   │   ├── requests.py             # Pydantic request bodies
│   │   └── responses.py            # Pydantic response bodies
│   ├── routes/
│   │   ├── scan.py                 # POST /scan/{code,file,folder,upload}
│   │   ├── ingest.py               # POST /ingest, /ingest/upload; GET progress/status/jobs
│   │   ├── chat.py                 # POST /chat, /chat/stream; GET/DELETE sessions
│   │   └── graph.py                # GET /api/graph, /api/scan-results, /api/stats, /api/node/{uid}
│   └── services/
│       ├── ingest_service.py       # 10-step ingestion pipeline orchestrator
│       └── graph_service.py        # Neo4j → frontend visualization queries
│
├── graph_rag/                      # Graph extraction + RAG agent core
│   ├── agent/
│   │   ├── codebase_agent.py       # Gemini ReAct agent (function-calling loop, max 12 turns)
│   │   ├── tools.py                # 8 graph query tool implementations
│   │   ├── tool_registry.py        # Tools → Gemini FunctionDeclaration schema
│   │   └── context_builder.py      # Graph overview injected into system prompt
│   ├── embedding/
│   │   └── embedding_generator.py  # SentenceTransformer all-MiniLM-L6-v2 (384-dim)
│   ├── enrichment/
│   │   ├── metrics_computer.py     # fan_in, fan_out, impact_score, entry_points, is_leaf
│   │   ├── summary_enricher.py     # Gemini: summary, core_functionality, tags, layer
│   │   ├── similarity_enricher.py  # SIMILAR_TO edges (cosine ≥ 0.85, top-5 per node)
│   │   └── bug_annotator.py        # Scanner → writes is_buggy/severity/confidence to Neo4j
│   ├── extraction/
│   │   ├── symbol_models.py        # Node, Edge, CodeGraph, UnresolvedCall data models
│   │   ├── symbol_index.py         # Global name → UID lookup index (cross-file resolution)
│   │   ├── symbol_extractor.py     # Language router → per-language extractors
│   │   ├── java_extractor.py       # Classes, methods, inheritance from Java AST
│   │   ├── c_extractor.py          # Functions, structs, typedefs from C AST
│   │   ├── cpp_extractor.py        # Classes, namespaces, templates from C++ AST
│   │   ├── call_resolver.py        # UnresolvedCall → CALLS edges via SymbolIndex
│   │   └── inheritance_resolver.py # INHERITS_FROM, IMPLEMENTS edges
│   ├── graph/
│   │   ├── neo4j_client.py         # Neo4j driver wrapper: connect, query, constraints
│   │   └── neo4j_graph_builder.py  # Batch UNWIND insert nodes/edges; constraint creation
│   ├── ingestion/
│   │   └── repo_scanner.py         # Walk repo tree, discover .c/.cpp/.h/.java files
│   └── parsing/
│       └── treesitter_parser.py    # Tree-Sitter bindings (C, C++, Java grammars)
│
├── vuln_scanner/                   # Standalone vulnerability scanner
│   ├── cli.py                      # CLI: --folder / --file / --code
│   ├── core/
│   │   ├── scanner.py              # CodeScanner: GraphCodeBERT + LLM + decision logic
│   │   ├── models.py               # ScanResult dataclass
│   │   ├── extraction.py           # Regex-based function extraction
│   │   └── language.py             # Language detection from file extension
│   ├── config/
│   │   └── settings.py             # Model IDs, GCP config, env vars
│   ├── detectors/
│   │   ├── graphcodebert.py        # Binary classifier: SAFE / BUG + confidence
│   │   └── llm.py                  # Gemini: severity + reason (CRITICAL/HIGH/MEDIUM/LOW)
│   └── reporting/
│       ├── json_report.py          # Export scan results to JSON
│       └── text.py                 # Formatted text report to stdout
│
├── src/                            # React 19 frontend (Vite)
│   ├── pages/
│   │   ├── Dashboard.jsx           # Upload panel, graph visualisation, summary stats
│   │   ├── ScanResults.jsx         # Vulnerability listing dashboard
│   │   ├── GraphExplorer.jsx       # Interactive force-directed graph
│   │   └── Chat.jsx                # Multi-turn streaming chat interface
│   ├── components/                 # dashboard/, chat/, graph/, scan/, layout/, ui/
│   ├── api/client.js               # Axios wrapper for all backend calls
│   ├── context/IngestContext.jsx   # Global state: ingest jobs, SSE streams
│   ├── hooks/                      # Custom React hooks
│   └── store/                      # Zustand state: sessions, graph, UI
│
├── Dockerfile                      # Multi-stage: frontend build + Python backend
├── docker-compose.yml              # Single-command local run
├── requirements.txt                # Python dependencies
├── package.json                    # Node.js dependencies
├── .env.example                    # Environment variable template
└── main.py                         # Root entry point → vuln_scanner CLI
```

---

## Tech Stack

### Backend

| Library | Version | Purpose |
|---|---|---|
| FastAPI | 0.111+ | REST API framework |
| Uvicorn + UVLoop | 0.30+ | ASGI server |
| Neo4j (official driver) | 5.x | Graph database client |
| PyTorch (CPU) | 2.x | GraphCodeBERT model inference |
| Transformers (HuggingFace) | 4.x | AutoTokenizer / AutoModel loading |
| SentenceTransformers | 3.x | all-MiniLM-L6-v2 embeddings (384-dim) |
| google-genai | latest | Gemini API via Vertex AI |
| tree-sitter-languages | 1.10.2 | Pre-compiled AST parsers for C, C++, Java |
| Pydantic v2 | 2.x | Request / response validation |
| python-dotenv | — | `.env` loading |

### Frontend

| Library | Purpose |
|---|---|
| React 19 + Vite | UI framework and build tool |
| TailwindCSS | Utility-first CSS |
| Zustand | Lightweight global state management |
| Framer Motion | Animations |
| Axios | HTTP client |
| Neovis.js | Force-directed Neo4j graph visualisation |
| Lucide React | Icon library |

### Infrastructure

| Service | Purpose |
|---|---|
| Neo4j Aura (or self-hosted) | Knowledge graph storage |
| Google Vertex AI / Gemini | LLM for enrichment, agent reasoning, vulnerability analysis |
| GCP Service Account | Authentication for Vertex AI |
| Docker + Cloud Run | Container build and production deployment |

---

## Ingestion Pipeline

Triggered via `POST /ingest` (folder path) or `POST /ingest/upload` (ZIP file). Runs as a background task and streams live progress to the client via Server-Sent Events.

| Step | Name | What happens |
|------|------|-------------|
| 1 | **Connect to Neo4j** | Opens connection pool; optionally clears graph (`clear_first`); creates uniqueness constraints on all node labels |
| 2 | **Load embedding model** | Loads `all-MiniLM-L6-v2` from cache (`HF_HOME`) or downloads it |
| 3 | **Discover source files** | Walks the repo tree; filters `.java`, `.c`, `.h`, `.cpp`, `.cc`, `.cxx`, `.hpp` |
| 4 | **Extract AST symbols** | Tree-Sitter parses each file; extractors build `Function`, `Class`, `Struct`, `Enum`, `Interface`, `File`, `Import` nodes + structural edges |
| 5 | **Resolve function calls** | `UnresolvedCall` records → `CALLS` edges using the global `SymbolIndex` |
| 6 | **Resolve inheritance** | `INHERITS_FROM` (class extends) and `IMPLEMENTS` (interface implementation) edges |
| 7 | **Compute graph metrics** | `fan_in`, `fan_out`, `impact_score = fan_in×2 + fan_out`, `is_entry_point`, `is_leaf`, `is_recursive` |
| 8 | **Gemini enrichment** | Calls Gemini for each node: `summary`, `core_functionality`, `tags`, `layer` (skippable via `skip_enrich=true`) |
| 9 | **Similarity edges** | Cosine similarity across all embeddings → `SIMILAR_TO` edges (threshold ≥ 0.85, top-5 per node); pushes all nodes + edges to Neo4j |
| 10 | **Bug annotation** | Runs GraphCodeBERT + Gemini scanner on every Function body; writes `is_buggy`, `severity`, `bug_confidence` back to Neo4j (skippable via `skip_scan=true`) |

**Result** (returned on completion):
```json
{
  "nodes_created": 842,
  "edges_created": 1204,
  "tags_created": 61,
  "files_processed": 24,
  "functions_scanned": 318,
  "bugs_found": 12
}
```

**SSE progress events** (streamed to `GET /ingest/progress/{job_id}`):
```json
{ "type": "progress", "step": 4, "step_name": "Extracting code graph", "message": "Processed 12/24 files", "progress_pct": 34 }
```

New clients that connect mid-run receive all prior events (full replay), then live updates.

---

## Vulnerability Scanner

A two-model ensemble combining a fine-tuned code classifier and Gemini LLM analysis with explicit decision logic.

### GraphCodeBERT Detector

- **Models**: `2451-22-749-016/graphcodebert-c-bug-detector` (C/C++) and `2451-22-749-016/graphcodebert-java-bug-detector` (Java)
- **Input**: Function source code (max 512 tokens, `AutoTokenizer` tokenisation)
- **Output**: `SAFE` or `BUG` + confidence score (0.0–1.0)
- **Temperature**: 1.5 (mild softmax calibration reduces false positives)
- **Threshold**: `bug_prob ≥ 0.52` → BUG

### LLM Detector (Gemini)

- **Model**: Configured via `GEMINI_MODEL` env var (default `gemini-3.1-flash-lite-preview`)
- **Output**: `SAFE`/`BUG` + severity (`CRITICAL` / `HIGH` / `MEDIUM` / `LOW` / `NONE`) + reason
- **Retries**: 3 attempts with exponential back-off (1.5 s, 3 s, 4.5 s)
- **Fallback**: Returns `SAFE` / `NONE` if all retries fail

### Decision Logic

```
GraphCodeBERT confident (≥ 0.80) AND says BUG  →  BUG  (use LLM severity if available)
GraphCodeBERT unsure  AND  LLM says BUG         →  BUG  (use LLM severity)
Both say SAFE                                   →  SAFE
```

GraphCodeBERT handles high-confidence pattern matching; Gemini provides semantic severity grading.

### Standalone CLI

```bash
python main.py --folder ./my-project
python main.py --file path/to/file.c
python main.py --code "void foo() { strcpy(buf, src); }" --language c
```

---

## Chat Agent

A Gemini ReAct agent that can answer any natural-language question about the ingested codebase by reasoning over 8 graph query tools.

### How it works

1. User sends a question (e.g. *"Which functions have the highest security risk?"*)
2. Agent reasons about which tools to call and in what order
3. Agent calls tools (up to 12 function-call cycles), gets structured data back
4. Agent synthesises a markdown-formatted answer with code references, call chains, and severity ratings
5. Response is streamed token-by-token via SSE

### Tools

| Tool | Purpose |
|---|---|
| `search_by_concept` | Two-phase semantic search: tag match + embedding cosine similarity |
| `get_node_details` | Full properties of a single function/class/struct by name or UID |
| `trace_callers` | Who calls this function (upstream, configurable hops) |
| `trace_callees` | What this function calls (downstream, configurable hops) |
| `get_impact_analysis` | Blast radius: all callers, callees, metrics, similar functions |
| `find_vulnerabilities` | All buggy functions sorted by severity + impact score |
| `run_cypher` | Direct read-only Cypher for complex structural queries (write ops blocked) |
| *(derived)* | Composed tools: vulnerable paths, entry-point analysis |

### Session persistence

Multi-turn conversations are written to `.chat_sessions.json` after every response (atomic rename, no data loss on restart). Sessions are reloaded on startup. Chat history is included in every subsequent Gemini call for full context continuity.

### Streaming (POST /chat/stream)

SSE event types:
```
{ "type": "thinking" }
{ "type": "tool_call",   "tool": "find_vulnerabilities", "args": {...} }
{ "type": "tool_result", "tool": "find_vulnerabilities", "chars": 1842 }
{ "type": "chunk",       "text": "The three most critical..." }
{ "type": "done",        "session_id": "uuid", "answer": "..." }
{ "type": "error",       "message": "..." }
```

---

## Neo4j Graph Schema

### Node Labels

All nodes receive a secondary `:CodeEntity` label for fast constraint-indexed MATCH queries.

| Label | Represents |
|---|---|
| `File` | Source file |
| `Package` | Java package / C++ namespace |
| `Namespace` | C++ namespace block |
| `Import` | import / #include statement |
| `Class` | Class declaration |
| `Interface` | Java interface |
| `Struct` | C / C++ struct |
| `Enum` | Enum type |
| `Function` | Function or method |
| `Field` | Member variable |
| `Tag` | Semantic tag (e.g. `"authentication"`, `"crypto"`) |
| `ExternalFunction` | Unresolved external call |

### Key Node Properties

```
uid                  # globally unique ID  (e.g. "src/Auth.java::AuthService::login")
name                 # simple name
qualified_name       # full path
file                 # relative path in repo
line_start / line_end
language             # c | cpp | java
body                 # full source (functions only)
signature            # with parameter types
return_type
visibility           # public | protected | private | default
is_static / is_virtual / is_abstract / is_override / is_recursive

# Semantic enrichment (Gemini)
summary              # one-liner
core_functionality   # 2–3 sentences
tags                 # ["authentication", "parsing", ...]
layer                # service | repository | utility | security | ...

# Graph metrics
fan_in               # number of callers
fan_out              # number of callees
impact_score         # fan_in×2 + fan_out
is_entry_point       # fan_in == 0
is_leaf              # fan_out == 0

# Vulnerability
is_buggy             # boolean
severity             # CRITICAL | HIGH | MEDIUM | LOW | NONE
bug_confidence       # float 0.0–1.0

# Embeddings
embedding            # float[384]  (all-MiniLM-L6-v2)
```

### Relationship Types

| Type | Source → Target | Meaning |
|---|---|---|
| `DEFINES` | File → Function/Class/Struct | File contains definition |
| `IMPORTS` | File → Import | Import statement |
| `INCLUDES` | File → Include | `#include` directive |
| `HAS_METHOD` | Class → Function | Class declares method |
| `HAS_FIELD` | Class → Field | Class declares field |
| `CONTAINS` | Class → any | General containment |
| `CALLS` | Function → Function | Function call |
| `INHERITS_FROM` | Class → Class | Class inheritance |
| `IMPLEMENTS` | Class → Interface | Interface implementation |
| `TAGGED_WITH` | Function/Class/Struct → Tag | Semantic tag |
| `SIMILAR_TO` | Function → Function | Cosine similarity ≥ 0.85 |

---

## API Reference

### Scan — `POST /scan/*`

| Endpoint | Input | Description |
|---|---|---|
| `POST /scan/code` | `{ code, language, source? }` | Scan a raw code snippet |
| `POST /scan/file` | `{ path }` | Scan a file by absolute path |
| `POST /scan/folder` | `{ path }` | Recursively scan a folder |
| `POST /scan/upload` | `multipart/form-data` (`.c` `.cpp` `.h` `.java`) | Upload and scan a file |

**Response** (`ScanResponse`):
```json
{
  "summary": { "total_functions": 12, "bugs_found": 3, "critical": 1, "high": 1, "medium": 1, "low": 0 },
  "results": [
    {
      "function_name": "parseInput",
      "severity": "CRITICAL",
      "confidence": 0.94,
      "final_label": "BUG",
      "function_body": "void parseInput(...) { ... }"
    }
  ]
}
```

---

### Ingest — `POST /ingest*`

| Endpoint | Input | Description |
|---|---|---|
| `POST /ingest` | `{ folder_path, clear_first?, skip_enrich?, skip_scan? }` | Ingest from server-side folder |
| `POST /ingest/upload` | `multipart/form-data` (`.zip`, max 512 MB) + query params | Upload and ingest ZIP |
| `GET /ingest/status/{job_id}` | — | Poll job status (JSON) |
| `GET /ingest/progress/{job_id}` | — | Stream progress (SSE) |
| `GET /ingest/jobs` | — | List all jobs |
| `DELETE /ingest/{job_id}` | — | Delete completed job record |

**Job status values**: `pending` → `running` → `completed` / `failed`

---

### Chat — `POST /chat*`

| Endpoint | Input | Description |
|---|---|---|
| `POST /chat` | `{ message, session_id? }` | Single-turn chat (blocking) |
| `POST /chat/stream` | `{ message, session_id? }` | Streaming chat (SSE) |
| `GET /chat/sessions` | — | List all sessions |
| `DELETE /chat/session/{session_id}` | — | Delete a session |

---

### Graph — `GET /api/*`

| Endpoint | Query params | Description |
|---|---|---|
| `GET /api/graph` | `node_limit`, `include_labels`, `min_impact_score`, `bugs_only` | Nodes + edges for visualisation |
| `GET /api/scan-results` | `severity`, `limit` | All vulnerable functions |
| `GET /api/stats` | — | Aggregate counts (nodes, edges, bugs, files) |
| `GET /api/node/{uid}` | — | Full details of a single node |

---

### Health — `GET /health`

```json
{
  "status": "ok",
  "neo4j": "ok",
  "scanner": "ok",
  "agent": "ok",
  "version": "1.0.0"
}
```

Each resource reports independently. A failed dependency returns `"unavailable"` for that field but does not crash the server — affected endpoints return HTTP 503 with a descriptive error.

---

## Frontend

The React frontend is built with Vite and served directly by FastAPI as a SPA (catch-all route on `/`).

### Pages

**Dashboard** — Upload a `.zip` or enter a folder path, watch real-time ingest progress, see a Neovis.js force-directed graph of the codebase, and review aggregate stats (nodes, edges, bugs, files).

**Scan Results** — Full vulnerability listing from `/api/scan-results`. Filter by severity (CRITICAL / HIGH / MEDIUM / LOW), layer, or language. Click any result to see the full function body, file path, caller chain, and impact score.

**Graph Explorer** — Interactive force-directed graph with click-to-inspect node details, filter by label type, impact score, or bugs-only mode.

**Chat** — Multi-turn streaming chat with the Gemini ReAct agent. Shows live tool calls and results as they happen. Supports multiple named sessions with full history.

### Status Bar

The header shows a live indicator for each backend dependency:
- 🟢 **Neo4j** — graph database reachable
- 🟢 **Scanner** — GraphCodeBERT models loaded
- 🟢 **Agent** — Gemini agent initialised

---

## Configuration

Copy `.env.example` to `.env` and fill in all required values.

```bash
# ── Neo4j ──────────────────────────────────────────
NEO4J_URI=bolt://localhost:7687        # bolt:// for local, neo4j+s:// for Aura
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here

# ── Google Cloud / Gemini ──────────────────────────
GOOGLE_APPLICATION_CREDENTIALS=./gcp-credentials.json
GCP_PROJECT_ID=your_gcp_project_id
GCP_LOCATION=global                    # Vertex AI location
GEMINI_MODEL=gemini-3.1-flash-lite-preview          # or gemini-3.1-flash-lite-preview-lite-preview

# ── HuggingFace (optional overrides) ──────────────
# GRAPHCODEBERT_C_MODEL_ID=2451-22-749-016/graphcodebert-c-bug-detector
# GRAPHCODEBERT_JAVA_MODEL_ID=2451-22-749-016/graphcodebert-java-bug-detector

# ── Application ────────────────────────────────────
PORT=8000

# ── Frontend (Vite, baked at build time) ──────────
VITE_NEO4J_URI=neo4j://0c64ca5d.databases.neo4j.io   # plain neo4j:// for Neovis.js
VITE_NEO4J_USER=your_user
VITE_NEO4J_PASSWORD=your_password
```

**Required GCP permissions** for the service account:
- `Vertex AI User` — Gemini API calls (enrichment, agent, LLM scanner)
- `Secret Manager Secret Accessor` — if credentials are stored in Secret Manager (Cloud Run)

---

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 20+
- Neo4j instance (local or [Aura free tier](https://neo4j.com/cloud/aura-free/))
- GCP project with Vertex AI API enabled + service account JSON

### Backend

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # fill in NEO4J_*, GCP_*, GEMINI_MODEL
uvicorn api.main:app --reload --port 8000
```

### Frontend (dev server with proxy)

```bash
npm install
npm run dev                     # Vite dev server on http://localhost:5173
```

The Vite dev server proxies all `/api`, `/ingest`, `/scan`, `/chat`, `/health` requests to `localhost:8000` — no CORS issues in development.

---

## Docker Deployment

### Running locally with Docker Compose

```bash
# Prerequisites
cp .env.example .env           # fill in all values
# place gcp-credentials.json at project root

# Build + start (first run downloads ~1 GB of HF models — ~10 min)
docker compose up --build

# Subsequent starts (fast, models cached in named volume)
docker compose up -d

# Stop (preserves model cache and chat sessions)
docker compose down

# Stop + wipe everything (forces fresh model download next time)
docker compose down -v
```

App available at **http://localhost:8080**

### What the Dockerfile does

The Dockerfile is a two-stage multi-stage build:

**Stage 1** — `node:20-slim` builds the React frontend (`npm run build` → `/frontend/dist`)

**Stage 2** — `python:3.11-slim`:
1. Installs system deps (`build-essential`, `git`, `curl`, `libgomp1`)
2. Installs Python deps from `requirements.txt`
3. Smoke-tests `tree-sitter-languages` (catches binary incompatibility at build time, not at deploy time)
4. **Pre-downloads HuggingFace models into the image** — `all-MiniLM-L6-v2`, `graphcodebert-c-bug-detector`, `graphcodebert-java-bug-detector` (~1 GB total). This eliminates cold-start download delays on Cloud Run.
5. Copies backend source and compiled frontend
6. Exposes port 8080, sets `HEALTHCHECK` (30 s interval, 120 s start period), runs Uvicorn

### Named volumes

| Volume | Contents | Cleared by |
|---|---|---|
| `hf_model_cache` | HuggingFace model weights (~1 GB) | `docker compose down -v` |
| `sessions_data` | Chat session history | `docker compose down -v` |

---

## Cloud Run Deployment

### One-time setup

```powershell
# Authenticate Docker to Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Create the registry repository (first time only)
gcloud artifacts repositories create codebase-agent `
  --repository-format=docker `
  --location=us-central1 `
  --project=YOUR_PROJECT_ID

# Store GCP credentials as a secret (never bake into image)
gcloud secrets create gcp-credentials `
  --project=YOUR_PROJECT_ID `
  --data-file=./gcp-credentials.json

# Grant Cloud Run's service account access to read the secret
$PROJECT_NUMBER = gcloud projects describe YOUR_PROJECT_ID --format='value(projectNumber)'
gcloud secrets add-iam-policy-binding gcp-credentials `
  --project=YOUR_PROJECT_ID `
  --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" `
  --role="roles/secretmanager.secretAccessor"
```

### Build and push

```powershell
# Build locally
docker build -t codebase-agent-app:latest .

# Tag and push
docker tag codebase-agent-app:latest `
  us-central1-docker.pkg.dev/YOUR_PROJECT_ID/codebase-agent/app:v1

docker push `
  us-central1-docker.pkg.dev/YOUR_PROJECT_ID/codebase-agent/app:v1
```

### Deploy

```powershell
gcloud run deploy codebase-agent `
  --image=us-central1-docker.pkg.dev/YOUR_PROJECT_ID/codebase-agent/app:v1 `
  --region=us-central1 `
  --project=YOUR_PROJECT_ID `
  --platform=managed `
  --allow-unauthenticated `
  --port=8080 `
  --memory=4Gi `
  --cpu=2 `
  --timeout=300 `
  --concurrency=1 `
  --set-secrets=/secrets/gcp-credentials.json=gcp-credentials:latest `
  --set-env-vars="GOOGLE_APPLICATION_CREDENTIALS=/secrets/gcp-credentials.json" `
  --set-env-vars="GCP_PROJECT_ID=YOUR_PROJECT_ID" `
  --set-env-vars="GCP_LOCATION=global" `
  --set-env-vars="GEMINI_MODEL=gemini-3.1-flash-lite-preview" `
  --set-env-vars="NEO4J_URI=neo4j+s://YOUR_AURA_ID.databases.neo4j.io" `
  --set-env-vars="NEO4J_USER=YOUR_USER" `
  --set-env-vars="NEO4J_PASSWORD=YOUR_PASSWORD" `
  --set-env-vars="HF_HOME=/app/.hf_cache"
```

> **Important**: Mount the credentials at `/secrets/gcp-credentials.json`, **not** `/app/gcp-credentials.json`. Cloud Run mounts the secret volume at the parent directory — mounting inside `/app` would shadow the entire application directory.

> **`--concurrency=1`**: PyTorch models are not thread-safe for concurrent CPU inference. Keep at 1 unless you add request queuing.

### Key differences from docker-compose

| Concern | docker-compose | Cloud Run |
|---|---|---|
| GCP credentials | File volume mount | Secret Manager → `/secrets/` |
| HF model cache | Named Docker volume (persists) | Baked into image (no runtime download) |
| Chat sessions | Named Docker volume (persists) | Lost on container restart (stateless) |
| Port | 8080 | Set by Cloud Run via `PORT` env var |

---

## Common Issues

### `ModuleNotFoundError: No module named 'api'` on Cloud Run

The secret volume was mounted inside `/app`, shadowing the entire application directory. Always use `--set-secrets=/secrets/gcp-credentials.json=...` (outside `/app`).

### Container fails startup probe / `No module named 'api'` locally

Run `docker run --rm your-image ls /app/` to verify `api/` is present. If missing, check `.dockerignore` — `api/` should not be excluded.

### 0 nodes / 0 edges after ZIP upload

Likely causes:
1. **Embedding failure silently skipped files** — the `_embed()` method in each extractor wraps `generate()` in a try/except so embedding errors no longer abort extraction
2. **`clear_first=true` wiped the database** — the frontend uses `clear_first=false` by default; re-ingest to repopulate
3. **Neo4j idle connection dropped** — the pipeline re-verifies connectivity before the insert step and reconnects if needed

### Chat agent shows red status (503)

The agent creates its own Neo4j connection at startup. If this fails, the agent is marked unavailable but other endpoints (scan, ingest, graph) still work. Check:
1. `NEO4J_URI` is reachable from the container
2. `GOOGLE_APPLICATION_CREDENTIALS` points to a valid, existing file
3. `GCP_PROJECT_ID` is set and the Vertex AI API is enabled in that project

### `tree-sitter-languages` binary incompatible

The Dockerfile smoke-tests the grammars at build time. If the build fails here, the `tree-sitter-languages` wheel for this Python version / platform is incompatible. Pin to a different version in `requirements.txt`.

### Models downloading on every Cloud Run cold start

Ensure the image was built with the model pre-download step (added to the Dockerfile after the tree-sitter smoke test). The `HF_HOME=/app/.hf_cache` env var must match at both build time and runtime so the pre-cached models are found.

### Gemini model not found

Verify `GEMINI_MODEL` is a valid model ID available in your GCP project and region. Use `gemini-3.1-flash-lite-preview` as a reliable default.
