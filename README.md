# Codebase Agent

An AI-powered source code analysis platform that combines graph-based code representation, vulnerability detection, and conversational analysis. The system extracts complete software architecture from source code into a Neo4j knowledge graph, detects security vulnerabilities using a GraphCodeBERT + Gemini hybrid, and enables engineers to ask natural-language questions about their codebase through a ReAct agent.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Module Reference](#module-reference)
  - [api/](#api)
  - [graph\_rag/](#graph_rag)
  - [vuln\_scanner/](#vuln_scanner)
  - [models/](#models)
- [Data Flow](#data-flow)
  - [Ingest Pipeline](#ingest-pipeline)
  - [Chat / Agent Flow](#chat--agent-flow)
  - [Scan Flow](#scan-flow)
- [API Reference](#api-reference)
- [Configuration](#configuration)
- [Installation](#installation)
- [Running the System](#running-the-system)
- [Common Issues](#common-issues)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Server                           │
│  /scan   /ingest   /chat   /api   /health                       │
└────────────┬────────────────────────────────────────────────────┘
             │
    ┌────────▼────────────────────────────────────┐
    │            INGESTION PIPELINE               │
    │  File Discovery → AST Extraction            │
    │  → Call/Inheritance Resolution              │
    │  → Metrics → Gemini Enrichment              │
    │  → Similarity Edges → Bug Annotation        │
    └────────┬────────────────────────────────────┘
             │
    ┌────────▼──────────────┐    ┌─────────────────────────┐
    │   Neo4j Knowledge     │◄───│   GraphCodeBERT + LLM   │
    │      Graph            │    │   Vulnerability Scanner  │
    └────────┬──────────────┘    └─────────────────────────┘
             │
    ┌────────▼──────────────┐
    │   Gemini ReAct Agent  │
    │   (8 graph tools)     │
    └───────────────────────┘
```

---

## Project Structure

```
codebase-agent/
├── api/                        # FastAPI REST server
│   ├── main.py                 # App factory, lifespan, middleware
│   ├── run.py                  # uvicorn entry point + CLI config
│   ├── config.py               # Resource initialization (Neo4j, scanner, agent)
│   ├── dependencies.py         # Dependency injection for 503 graceful degradation
│   ├── models/
│   │   ├── requests.py         # Pydantic request models
│   │   └── responses.py        # Pydantic response models
│   ├── routes/
│   │   ├── scan.py             # POST /scan/* — code/file/folder/upload scanning
│   │   ├── ingest.py           # POST /ingest/* — folder/zip ingestion + SSE progress
│   │   ├── chat.py             # POST /chat/* — single-turn, stream, session management
│   │   └── graph.py            # GET /api/* — graph data, scan results, stats
│   └── services/
│       ├── ingest_service.py   # Orchestrates the 10-step extraction pipeline
│       └── graph_service.py    # Queries Neo4j for frontend visualization
│
├── graph_rag/                  # Graph-RAG extraction + agent core
│   ├── agent/
│   │   ├── codebase_agent.py   # Gemini ReAct agent (function-calling loop, max 12 turns)
│   │   ├── tools.py            # 8 graph query tools
│   │   ├── tool_registry.py    # Converts tools to Gemini FunctionDeclarations
│   │   └── context_builder.py  # Builds graph overview for agent system prompt
│   ├── embedding/
│   │   └── embedding_generator.py  # SentenceTransformer all-MiniLM-L6-v2
│   ├── enrichment/
│   │   ├── metrics_computer.py     # fan_in, fan_out, impact_score, entry points
│   │   ├── summary_enricher.py     # Gemini: summary, core_functionality, tags, layer
│   │   ├── similarity_enricher.py  # SIMILAR_TO edges via cosine similarity
│   │   └── bug_annotator.py        # Runs scanner + writes is_buggy/severity to Neo4j
│   ├── extraction/
│   │   ├── symbol_models.py        # Node, Edge, CodeGraph, UnresolvedCall models
│   │   ├── symbol_index.py         # Global name → UID index
│   │   ├── symbol_extractor.py     # Language router to per-language extractors
│   │   ├── java_extractor.py       # Classes, methods, inheritance from Java AST
│   │   ├── c_extractor.py          # Functions, structs, typedefs from C AST
│   │   ├── cpp_extractor.py        # Classes, namespaces, templates from C++ AST
│   │   ├── call_resolver.py        # UnresolvedCall → CALLS edges via SymbolIndex
│   │   └── inheritance_resolver.py # INHERITS_FROM, IMPLEMENTS edges
│   ├── graph/
│   │   ├── neo4j_client.py         # Neo4j driver wrapper (connect, query, constraints)
│   │   └── neo4j_graph_builder.py  # Inserts nodes/edges; creates uniqueness constraints
│   ├── ingestion/
│   │   └── repo_scanner.py         # Walks repo tree, discovers .c/.cpp/.h/.java files
│   ├── parsing/
│   │   └── treesitter_parser.py    # Tree-Sitter parser wrapper (C, C++, Java)
│   ├── retrieval/
│   │   └── hybrid_retriever.py     # Semantic + keyword retrieval (placeholder)
│   ├── run_extraction.py           # Standalone extraction script for testing
│   └── test_repo/                  # Sample codebase (Java + C++ files for testing)
│       ├── AuthService.java
│       ├── BaseService.java
│       ├── User.java
│       ├── auth_manager.cpp
│       ├── db_connection.cpp
│       ├── user_manager.cpp
│       └── logger.cpp
│
├── vuln_scanner/               # Standalone vulnerability scanner
│   ├── cli.py                  # CLI entry point (--folder/--file/--code)
│   ├── core/
│   │   ├── scanner.py          # CodeScanner: orchestrates extraction + detection + decision
│   │   ├── models.py           # ScanResult dataclass
│   │   ├── extraction.py       # Regex-based 2-phase function extraction
│   │   └── language.py         # Language detection from file extensions
│   ├── config/
│   │   └── settings.py         # Settings dataclass (model paths, GCP, defaults)
│   ├── detectors/
│   │   ├── graphcodebert.py    # PyTorch-based GraphCodeBERT classifier
│   │   └── llm.py              # Gemini semantic vulnerability analysis
│   └── reporting/
│       ├── json_report.py      # Export results to JSON
│       └── text.py             # Formatted text report to stdout
│
├── models/                     # Pre-trained ML models (local storage)
│   ├── graphcodebert_c_bug_detector/    # Hugging Face model for C vulnerability detection
│   └── graphcodebert_java_bug_detector/ # Hugging Face model for Java vulnerability detection
│
├── main.py                     # Root entry point → vuln_scanner.cli.run_cli()
├── requirements.txt            # Python dependencies
├── package.json                # Frontend dependencies (React, Tailwind, etc.)
├── .env                        # Environment configuration (credentials, URIs, paths)
├── .gitignore
└── .chat_sessions.json         # Persisted chat session history (auto-managed)
```

---

## Tech Stack

### Backend (Python)

| Library | Purpose |
|---|---|
| FastAPI 0.111+ | REST API framework |
| uvicorn 0.30+ | ASGI server |
| Neo4j (official driver) | Graph database client |
| PyTorch + Transformers | GraphCodeBERT model inference |
| google-genai | Gemini API for LLM enrichment, agent, and vulnerability analysis |
| SentenceTransformers | all-MiniLM-L6-v2 embedding model (384-dim) |
| tree-sitter + tree_sitter_languages | AST parsing for C, C++, Java |
| python-dotenv | Environment variable loading |
| Pydantic v2 | Request/response validation |

### Frontend (Node.js)

| Library | Purpose |
|---|---|
| React | UI framework |
| React Router | Client-side routing |
| TailwindCSS | Utility-first CSS |
| Framer Motion | Animations |
| Axios | HTTP client |
| Zustand | Lightweight state management |
| Lucide React | Icon library |

### Infrastructure

| Service | Purpose |
|---|---|
| Neo4j Aura (or self-hosted) | Graph database for code knowledge graph |
| Google Vertex AI / Gemini | LLM for enrichment, agent reasoning, and vulnerability analysis |
| GCP Service Account | Authentication for Gemini API |

---

## Module Reference

### `api/`

The FastAPI server is the primary entry point for the full system. It initializes all resources at startup and exposes REST endpoints for scanning, ingestion, chat, and graph visualization.

#### `api/main.py`

App factory with lifespan management. On startup, calls `initialize_resources()` which connects Neo4j, loads the embedding model, initializes the scanner and the Gemini agent. Configures CORS and mounts all routers.

#### `api/config.py`

Holds singleton instances: `neo4j_client`, `scanner`, `agent`, `embedding_generator`. Each resource initializes independently — if one fails, others still work and affected endpoints return HTTP 503. This is the **graceful degradation** pattern.

#### `api/dependencies.py`

FastAPI dependency factories. Each resource (`get_neo4j_client()`, `get_scanner()`, `get_agent()`) raises HTTP 503 if the resource is unavailable, with a descriptive error body explaining which resource failed and why.

#### `api/models/requests.py`

Pydantic request bodies:
- `ScanCodeRequest` — raw code + language string
- `ScanFileRequest` — absolute file path
- `ScanFolderRequest` — folder path
- `IngestFolderRequest` — folder path + optional clear flag
- `ChatRequest` — message + optional session_id

#### `api/models/responses.py`

Pydantic response bodies:
- `BugResult` — function name, severity, confidence, explanation
- `ScanResponse` — list of BugResult + summary stats
- `GraphNode` / `GraphEdge` — visualization primitives
- `IngestJobStatus` — job_id, status, progress, events list

#### `api/routes/scan.py`

Four scan endpoints. All delegate to `scanner.scan_*()` and return `ScanResponse`. The upload endpoint accepts `multipart/form-data`, saves to a temp file, scans, and cleans up.

#### `api/routes/ingest.py`

Ingest endpoints that trigger the 10-step extraction pipeline as a background task. The job is created immediately (returns `job_id`) while the pipeline runs asynchronously. Progress events are pushed to an in-memory job queue and streamed via Server-Sent Events (SSE) at `GET /ingest/progress/{job_id}`. Clients that connect mid-run receive all events from the beginning (replay). The upload endpoint accepts a `.zip` file, extracts it to a temp folder, and ingests.

#### `api/routes/chat.py`

Chat endpoints backed by `CodebaseAgent`. Sessions are maintained in memory + persisted atomically to `.chat_sessions.json` on every response. The session file is loaded at startup. The `POST /chat/stream` endpoint streams the agent's response token-by-token via SSE using the agent's streaming interface.

#### `api/routes/graph.py`

Read-only graph data endpoints backed by `GraphService`. Used by the frontend for visualization.

#### `api/services/ingest_service.py`

Orchestrates the 10-step ingestion pipeline with progress callbacks:

| Step | Action |
|---|---|
| 1 | Connect to Neo4j, create uniqueness constraints |
| 2 | Load embedding model (all-MiniLM-L6-v2) |
| 3 | Discover source files (repo_scanner) |
| 4 | AST extraction (TreeSitter → SymbolExtractor → CodeGraph) |
| 5 | Call resolution (UnresolvedCall → CALLS edges) |
| 6 | Inheritance resolution (INHERITS_FROM, IMPLEMENTS edges) |
| 7 | Metrics computation (fan_in, fan_out, impact_score, entry points) |
| 8 | Gemini semantic enrichment (summary, tags, layer) |
| 9 | Similarity edges (cosine sim) + push all to Neo4j |
| 10 | Bug annotation (GraphCodeBERT + LLM scan → write is_buggy/severity) |

Each step calls `progress_callback(step, total, message)` which pushes an SSE event to the job's event queue.

#### `api/services/graph_service.py`

Runs Cypher queries against Neo4j and returns structured data for the frontend. Returns graph nodes with positions, edges with relationship types, scan results (buggy functions), and aggregate stats (node count, edge count, bug count, entry points).

---

### `graph_rag/`

Core intelligence layer. Contains all extraction, resolution, enrichment, graph storage, and agent logic.

#### `graph_rag/extraction/`

**`symbol_models.py`** — Domain models:
- `Node` — single code entity with `uid`, `label`, `name`, `file`, `properties`
- `Edge` — directed relationship between two node UIDs
- `CodeGraph` — container: `nodes: List[Node]`, `edges: List[Edge]`, `unresolved_calls: List[UnresolvedCall]`
- `UnresolvedCall` — a deferred call record `(caller_uid, callee_name, caller_file)` resolved in pass 2

**UID format**: `{relative_file_path}::{qualified_name}` — e.g., `src/auth/AuthService.java::AuthService::login`

**`symbol_index.py`** — Global registry built during pass 1. Maps `name → [uid, ...]` and `qualified_name → uid`. Used by `CallResolver` and `InheritanceResolver` during pass 2 to look up nodes by name across files.

**`symbol_extractor.py`** — Language router. Accepts a file path, detects language by extension, dispatches to `JavaExtractor`, `CExtractor`, or `CppExtractor`. Returns a `CodeGraph`.

**`java_extractor.py`** — Walks Tree-Sitter Java AST. Extracts:
- `Class`, `Interface`, `Enum` nodes
- `Function` (method) nodes with bodies
- `INHERITS_FROM` / `IMPLEMENTS` edges (as UnresolvedCalls for deferred resolution)
- `HAS_METHOD`, `CONTAINS` structural edges
- All function call sites → `UnresolvedCall` records

**`c_extractor.py`** — Walks Tree-Sitter C AST. Extracts:
- `Function` nodes (name, signature, body)
- `Struct`, `Enum`, `Typedef` nodes
- `INCLUDES` edges (from `#include` directives)
- Call sites → `UnresolvedCall` records

**`cpp_extractor.py`** — Walks Tree-Sitter C++ AST. Extracts:
- `Class`, `Struct`, `Namespace` nodes
- `Function` nodes with template support
- Class inheritance via `base_class_clause`
- Call sites → `UnresolvedCall` records

**`call_resolver.py`** — Pass 2. For each `UnresolvedCall`, calls `symbol_index.resolve_function(callee_name, caller_file)`:
1. Look for same-file match first
2. Fall back to unique repo-wide match
3. Fall back to first match
4. If still unresolved, create `ExternalFunction` node with `uid = external::{name}`
Adds `CALLS` edges to the `CodeGraph`.

**`inheritance_resolver.py`** — Pass 2. Resolves class-level inheritance. Maps base class names to known UIDs via `SymbolIndex`, creates `INHERITS_FROM` / `IMPLEMENTS` edges.

---

#### `graph_rag/parsing/`

**`treesitter_parser.py`** — Thin wrapper around `tree_sitter_languages.get_parser()`. Returns the root AST node for a given source string and language. Supported languages: `c`, `cpp`, `java`.

---

#### `graph_rag/ingestion/`

**`repo_scanner.py`** — Recursively walks a directory. Skips common non-source directories (`node_modules`, `venv`, `__pycache__`, `.git`, `build`, `dist`, `target`). Returns a list of source file paths with extensions `.c`, `.cpp`, `.h`, `.hpp`, `.java`.

---

#### `graph_rag/graph/`

**`neo4j_client.py`** — Neo4j driver wrapper. Manages the driver instance, runs parameterized Cypher queries via `run_query(cypher, params)`, handles connection errors, and exposes `is_connected()`.

**`neo4j_graph_builder.py`** — Inserts a `CodeGraph` into Neo4j:
1. `create_constraints()` — `CREATE CONSTRAINT IF NOT EXISTS` for `uid` on both the primary label and the `:CodeEntity` secondary label. The secondary label is critical for Aura (hosted Neo4j) where index lookup by primary label alone can fail.
2. `insert_nodes()` — MERGE on `uid`, SET all properties, add `:CodeEntity` secondary label.
3. `insert_edges()` — MATCH by `uid` on `:CodeEntity`, MERGE the relationship.

---

#### `graph_rag/embedding/`

**`embedding_generator.py`** — Wraps `SentenceTransformer("all-MiniLM-L6-v2")`. Exposes `encode(text) → List[float]` (384-dim). Models are lazy-loaded on first use. Used during enrichment (node embeddings) and at query time (similarity search in agent tools).

---

#### `graph_rag/enrichment/`

**`metrics_computer.py`** — Runs Cypher aggregations on Neo4j to compute and write back:
- `fan_in` = count of incoming CALLS edges
- `fan_out` = count of outgoing CALLS edges
- `impact_score` = `fan_in * 2 + fan_out` (higher weight for being called = more downstream impact if changed)
- `is_entry_point` = `fan_in == 0` and not a constructor/destructor

**`summary_enricher.py`** — For each `Function` and `Class` node (in batches), calls Gemini with the node's source code body. Parses the JSON response to extract:
- `summary` — 2-3 sentence description
- `core_functionality` — 1-sentence core purpose
- `tags` — list of semantic keywords (e.g., `["authentication", "session", "jwt"]`)
- `layer` — architectural layer (`service`, `repository`, `utility`, `controller`, etc.)

After enrichment, re-encodes `"{name}: {core_functionality}"` as the node's semantic embedding.

**`similarity_enricher.py`** — Loads all node embeddings from Neo4j into memory. Computes pairwise cosine similarity. For pairs exceeding a threshold (default 0.85), creates a `SIMILAR_TO` edge with `similarity_score` property. This powers the `search_by_concept` agent tool.

**`bug_annotator.py`** — Iterates over all `Function` nodes. For each, calls `CodeScanner` (GraphCodeBERT + LLM). Writes `is_buggy`, `severity`, `bug_confidence`, and `bug_explanation` properties back to the node in Neo4j. Nodes already annotated (has `is_buggy` property) are skipped unless `force=True`.

---

#### `graph_rag/agent/`

**`codebase_agent.py`** — The conversational AI core. Uses Gemini's function-calling API in a ReAct loop (max 12 turns):
1. Builds system prompt using `ContextBuilder.build_overview()` — includes total node/edge counts, top entry points, recent vulnerabilities, and reasoning guidelines
2. Sends user message + history to Gemini
3. If Gemini returns a `FunctionCall`, dispatches to the appropriate tool
4. Appends tool result to history
5. Repeats until Gemini returns a final text response
6. Returns `(answer: str, updated_history: list)`

**`tools.py`** — 8 graph query tools, each running Cypher queries against Neo4j:

| Tool | Description |
|---|---|
| `search_by_concept` | Find nodes by tags (exact) + semantic embedding similarity |
| `get_node_details` | Full node properties by name or UID |
| `trace_callers` | Upstream call graph (who calls this function, N levels deep) |
| `trace_callees` | Downstream call graph (what this function calls, N levels deep) |
| `get_impact_analysis` | Blast radius: nodes affected if this function changes |
| `find_vulnerabilities` | Return all `is_buggy=true` nodes, optionally filtered by severity |
| `find_vulnerable_paths` | Trace paths from entry points to buggy functions |
| `run_cypher` | Execute arbitrary read-only Cypher (for advanced queries) |

**`tool_registry.py`** — Converts each tool's Python function signature and docstring into a Gemini `FunctionDeclaration` object, enabling Gemini to reason about which tool to call and with what parameters.

**`context_builder.py`** — Runs lightweight Cypher queries to build the agent's system prompt context: node/edge counts by label, top-10 highest-impact entry points, and top-10 most severe buggy functions.

---

#### `graph_rag/retrieval/`

**`hybrid_retriever.py`** — Placeholder for a standalone semantic + keyword hybrid retrieval module. Currently the retrieval logic lives in `agent/tools.py`.

---

### `vuln_scanner/`

A fully standalone vulnerability scanner that works independently of the graph pipeline. Can be used via CLI or imported as a library.

#### `vuln_scanner/core/scanner.py`

`CodeScanner` — the main orchestrator:
1. Calls `extract_functions()` to get function code blocks
2. For each function: runs `GraphCodeBERTDetector.predict()` and `LLMBugDetector.analyze()`
3. `_decide(graphcodebert_result, llm_result) → ScanResult`:
   - Both say BUG → BUG (high confidence)
   - LLM says BUG and severity is CRITICAL or HIGH → BUG (override)
   - Otherwise → SAFE
4. Returns `List[ScanResult]`

**Rationale for hybrid decision**: GraphCodeBERT has high false-positive rate on clean code patterns it wasn't trained on. LLM provides semantic understanding but may miss syntax-level patterns. Consensus reduces false positives; LLM override on critical severity prevents false negatives on dangerous vulnerabilities.

#### `vuln_scanner/core/extraction.py`

Two-phase regex-based function extraction (not AST-based, for speed and language-agnostic fallback):
1. **Phase 1** — Find all function signatures via regex patterns per language
2. **Phase 2** — Extract the function body by tracking brace depth from the opening `{` until depth returns to 0

Works for C, C++, and Java. Returns `List[FunctionCode(name, code, language)]`.

#### `vuln_scanner/core/language.py`

Maps file extensions to language strings: `.java → java`, `.c → c`, `.cpp/.cc/.cxx → cpp`, `.h/.hpp → cpp`. Returns `None` for unknown extensions.

#### `vuln_scanner/config/settings.py`

`Settings` dataclass loaded from environment variables:
- `graphcodebert_c_model_path` — path to C vulnerability model
- `graphcodebert_java_model_path` — path to Java vulnerability model
- `gcp_project_id`, `gcp_location` — Gemini API settings
- `gemini_model` — model name (e.g., `gemini-2.5-flash-lite`)

#### `vuln_scanner/detectors/graphcodebert.py`

`GraphCodeBERTDetector` — PyTorch-based classifier:
- Loads the appropriate model (C or Java) based on language
- Tokenizes function code using the model's tokenizer
- Runs forward pass through transformer + classification head
- Returns `(label: "BUG" | "SAFE", confidence: float)`
- Models are lazy-loaded on first use per language

Supported languages: `c`, `cpp` (uses C model), `java`. Other languages return `SAFE` with 0.5 confidence.

#### `vuln_scanner/detectors/llm.py`

`LLMBugDetector` — Gemini-based semantic analyzer:
- Prompts Gemini with the function code + structured output schema
- Returns `(is_bug: bool, severity: str, confidence: float, explanation: str)`
- Severity levels: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `NONE`
- Handles Gemini API errors gracefully (returns SAFE on failure)

#### `vuln_scanner/cli.py`

CLI entry point wrapping `CodeScanner`. Accepts:
- `--folder PATH` — scan all source files recursively
- `--file PATH` — scan a single file
- `--code CODE --language LANG` — scan a raw code string
- `--json-out PATH` — export results to JSON file

Prints formatted text report to stdout by default.

---

### `models/`

Local model storage for GraphCodeBERT classifiers. Each subdirectory is a Hugging Face model checkpoint:

- **`graphcodebert_c_bug_detector/`** — Fine-tuned GraphCodeBERT for C/C++ vulnerability detection (binary classification: BUG / SAFE). Trained on CVE-annotated C/C++ function datasets.
- **`graphcodebert_java_bug_detector/`** — Fine-tuned GraphCodeBERT for Java vulnerability detection. Trained on Java CVE and bug datasets.

Each model directory contains: `config.json`, `model.safetensors`, `tokenizer.json`, `tokenizer_config.json`, `special_tokens_map.json`, `vocab.json`.

---

## Data Flow

### Ingest Pipeline

```
User: POST /ingest { "folder": "/path/to/repo" }
  │
  ├─ [API] Create IngestJob (job_id) → return immediately
  │
  └─ [Background Task] IngestService.run()
       │
       ├─ Step 1: Neo4jClient.connect() + create_constraints()
       ├─ Step 2: EmbeddingGenerator.load()
       ├─ Step 3: RepoScanner.scan(folder) → [file_paths]
       │
       ├─ Step 4: For each file:
       │     TreeSitterParser.parse(file) → AST
       │     SymbolExtractor.extract(AST) → CodeGraph fragment
       │     Merge into global CodeGraph + SymbolIndex
       │
       ├─ Step 5: CallResolver.resolve(CodeGraph, SymbolIndex)
       │     UnresolvedCall("login", "auth.java") → CALLS edge
       │
       ├─ Step 6: InheritanceResolver.resolve(CodeGraph, SymbolIndex)
       │     "BaseService" → INHERITS_FROM edge
       │
       ├─ Step 7: MetricsComputer.compute(neo4j)
       │     → writes fan_in, fan_out, impact_score, is_entry_point
       │
       ├─ Step 8: SummaryEnricher.enrich(nodes, gemini)
       │     code body → Gemini → summary, tags, layer
       │     → re-encode embedding with "{name}: {core_functionality}"
       │
       ├─ Step 9: SimilarityEnricher.add_edges(neo4j)
       │     cosine(embed_A, embed_B) > 0.85 → SIMILAR_TO edge
       │     Neo4jGraphBuilder.insert(CodeGraph)
       │
       └─ Step 10: BugAnnotator.annotate(all_functions, neo4j)
              CodeScanner.scan(function_code) per function
              → write is_buggy, severity, bug_confidence to Neo4j
```

### Chat / Agent Flow

```
User: POST /chat { "message": "What are the security-critical functions?", "session_id": "..." }
  │
  ├─ [API] Load or create chat session
  │
  └─ [CodebaseAgent] chat_with_history(message, history)
       │
       ├─ ContextBuilder.build_overview(neo4j)
       │     → graph stats, top entry points, top vulnerabilities
       │
       ├─ Build system prompt with graph context + tool descriptions
       │
       └─ Gemini function-calling loop (max 12 turns):
             │
             ├─ Gemini decides: call find_vulnerabilities(severity="HIGH")
             ├─ Tool executes: Cypher → [{name, severity, explanation}, ...]
             ├─ Append tool result to history
             │
             ├─ Gemini decides: call get_impact_analysis(uid="auth.java::AuthService::login")
             ├─ Tool executes: Cypher → [{affected_node, depth}, ...]
             ├─ Append tool result to history
             │
             └─ Gemini returns final text answer
                  → Save session → Return to user
```

### Scan Flow

```
User: POST /scan/code { "code": "void foo() {...}", "language": "c" }
  │
  └─ [CodeScanner]
       │
       ├─ extraction.extract_functions(code, language)
       │     Phase 1: regex match function signatures
       │     Phase 2: brace-tracking to extract body
       │     → [FunctionCode("foo", "void foo() {...}")]
       │
       ├─ For each function:
       │     GraphCodeBERTDetector.predict(code, language)
       │       → ("BUG", 0.87) or ("SAFE", 0.92)
       │
       │     LLMBugDetector.analyze(code)
       │       → (is_bug=True, severity="HIGH", explanation="...")
       │
       │     _decide(graphcodebert_result, llm_result)
       │       → ScanResult(name, is_bug, severity, confidence, explanation)
       │
       └─ Return List[ScanResult]
```

---

## API Reference

### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Resource status: Neo4j, scanner, agent (each shows ok/error) |
| `GET` | `/` | Redirect to `/docs` |

### Scan

| Method | Path | Body | Description |
|---|---|---|---|
| `POST` | `/scan/code` | `{ code, language }` | Scan raw code snippet |
| `POST` | `/scan/file` | `{ file_path }` | Scan single file by path |
| `POST` | `/scan/folder` | `{ folder_path }` | Recursively scan a folder |
| `POST` | `/scan/upload` | `multipart: file` | Upload and scan a single file |

### Ingest

| Method | Path | Body | Description |
|---|---|---|---|
| `POST` | `/ingest` | `{ folder_path, clear? }` | Start ingestion from server folder |
| `POST` | `/ingest/upload` | `multipart: file (.zip)` | Upload zip, extract, ingest |
| `GET` | `/ingest/status/{job_id}` | — | Poll job status as JSON |
| `GET` | `/ingest/progress/{job_id}` | — | SSE event stream (real-time progress) |
| `GET` | `/ingest/jobs` | — | List all ingest jobs |
| `DELETE` | `/ingest/{job_id}` | — | Remove completed job |

### Chat

| Method | Path | Body | Description |
|---|---|---|---|
| `POST` | `/chat` | `{ message, session_id? }` | Single-turn Q&A (creates session if needed) |
| `POST` | `/chat/stream` | `{ message, session_id? }` | Same but streams tokens via SSE |
| `GET` | `/chat/sessions` | — | List active session IDs + message counts |
| `DELETE` | `/chat/session/{session_id}` | — | Clear a session's history |

### Graph

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/graph` | All nodes + edges for frontend visualization |
| `GET` | `/api/scan-results` | All buggy functions with severity + explanations |
| `GET` | `/api/stats` | Aggregate counts (nodes, edges, bugs, entry points) |
| `GET` | `/api/node/{uid}` | Full details for a single node by UID |

---

## Configuration

All configuration is via environment variables, loaded from `.env` at startup.

### `.env` Template

```ini
# === Google Vertex AI / Gemini ===
GOOGLE_APPLICATION_CREDENTIALS=./gcp-credentials.json
GCP_PROJECT_ID=your-gcp-project-id
GCP_LOCATION=global
GEMINI_MODEL=gemini-2.5-flash-lite

# === ML Model Paths ===
GRAPHCODEBERT_C_MODEL_PATH=./models/graphcodebert_c_bug_detector
GRAPHCODEBERT_JAVA_MODEL_PATH=./models/graphcodebert_java_bug_detector

# === Neo4j Database ===
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password

# === API Server (optional — shown with defaults) ===
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=false
API_WORKERS=1
LOG_LEVEL=info

# === CORS (optional — defaults allow localhost:3000 and localhost:5173) ===
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# === Session persistence (optional) ===
SESSIONS_FILE=./.chat_sessions.json

# === Scanner (optional) ===
DEFAULT_SCAN_FOLDER=./graph_rag/test_repo
```

### Required Credentials

**GCP Service Account (`gcp-credentials.json`)**  
Must be a valid GCP service account key JSON with Vertex AI / Generative AI API access enabled. Place at the path specified by `GOOGLE_APPLICATION_CREDENTIALS`. Relative paths are resolved from the repo root.

**Neo4j Database**  
Any Neo4j 5.x instance (Aura cloud or self-hosted). The user must have write access. Constraints are created automatically on first ingest. The URI protocol determines TLS: `neo4j+s://` for encrypted (Aura), `bolt://` for local.

**Pre-trained Models**  
GraphCodeBERT models must exist at the configured paths. These are Hugging Face model checkpoints. If the paths are wrong, the API starts but scanner endpoints return 503.

---

## Installation

### Prerequisites

- Python 3.10+
- Node.js 18+ (for frontend only)
- A running Neo4j 5.x instance (or a Neo4j Aura free tier account)
- A GCP project with Vertex AI / Gemini API enabled

### Steps

```bash
# 1. Navigate to the project directory
cd "d:/Vs Codings/codebase-agent"

# 2. Create and activate a Python virtual environment
python -m venv venv
source venv/Scripts/activate       # Windows (Git Bash / WSL)
# OR
venv\Scripts\activate.bat          # Windows (Command Prompt)

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install Node.js dependencies (for frontend)
npm install

# 5. Configure environment variables
# Copy the template above into a new .env file and fill in your credentials

# 6. Verify models exist
ls models/graphcodebert_c_bug_detector/
ls models/graphcodebert_java_bug_detector/
```

---

## Running the System

### Option A: Full API Server (Recommended)

Starts the FastAPI server with all endpoints available.

```bash
# Activate virtual environment first
source venv/Scripts/activate

# Start the server
python -m api.run

# Or with uvicorn directly
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

- API available at: `http://localhost:8000`
- Interactive docs (Swagger UI): `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

Environment overrides for the server:

```bash
API_PORT=9000 API_RELOAD=true python -m api.run
```

---

### Option B: Standalone Vulnerability Scanner (CLI)

Scan code without Neo4j or the agent. Only requires GCP credentials and the model files.

```bash
# Scan a folder recursively
python main.py --folder /path/to/your/repo

# Scan a single file
python main.py --file /path/to/AuthService.java

# Scan a raw code snippet
python main.py --code "void transfer(int amount) { balance -= amount; }" --language c

# Export results to JSON
python main.py --folder /path/to/repo --json-out results.json
```

---

### Option C: Run Extraction Pipeline Directly (Testing / Development)

Runs the full 10-step ingestion pipeline as a standalone script, bypassing the API.

```bash
cd graph_rag

# Use the built-in test_repo
python run_extraction.py

# Use a custom repository
python run_extraction.py /path/to/your/repo

# Clear existing Neo4j data and re-ingest
python run_extraction.py /path/to/your/repo --clear

# Skip Gemini enrichment (faster, no API calls)
python run_extraction.py /path/to/your/repo --no-enrich
```

---

### Typical End-to-End Workflow

```
1. Start API server
   python -m api.run

2. Ingest your codebase
   POST http://localhost:8000/ingest
   Body: { "folder_path": "/absolute/path/to/repo", "clear": true }
   → Returns: { "job_id": "abc123" }

3. Watch ingestion progress (Server-Sent Events)
   GET http://localhost:8000/ingest/progress/abc123
   → Streams step-by-step progress events

4. Query with natural language
   POST http://localhost:8000/chat
   Body: { "message": "Which functions are most critical to security?" }
   → Returns: AI answer + session_id for follow-up questions

5. Visualize the graph
   GET http://localhost:8000/api/graph
   → Returns nodes + edges for your frontend visualization

6. View vulnerability report
   GET http://localhost:8000/api/scan-results
   → Returns all detected vulnerabilities with severity and explanations
```

---

## Common Issues

### Nodes inserted but no edges appear in Neo4j

**Cause**: Label-based index lookup fails on Neo4j Aura for cross-file relationships.  
**Fix**: Already handled — all nodes receive a secondary `:CodeEntity` label, and constraints are created on both the primary label and `:CodeEntity`. All `MATCH` clauses in `neo4j_graph_builder.py` use `:CodeEntity` as the anchor.

### GraphCodeBERT model not found / scanner returns 503

**Cause**: Model paths in `.env` don't point to existing directories.  
**Check**: Verify `./models/graphcodebert_c_bug_detector/config.json` and `./models/graphcodebert_java_bug_detector/config.json` exist.  
**Fix**: Set correct absolute paths in `GRAPHCODEBERT_C_MODEL_PATH` and `GRAPHCODEBERT_JAVA_MODEL_PATH`.

### Gemini API authentication error

**Cause**: Invalid or missing GCP credentials.  
**Check**: Confirm `gcp-credentials.json` exists at the path in `GOOGLE_APPLICATION_CREDENTIALS`. Confirm the service account has Vertex AI API access enabled in GCP Console.  
**Fix**: Re-download the service account key from GCP IAM and update the file.

### Ingest fails on large codebases

**Cause**: Gemini API rate limits or memory exhaustion during enrichment step.  
**Fix 1**: Use `--no-enrich` flag (run_extraction.py) or temporarily set `GEMINI_MODEL` to a faster model.  
**Fix 2**: Ingest subsystems separately (split the folder).  
**Fix 3**: Add `time.sleep()` between enrichment batches (see `summary_enricher.py`).

### Chat agent gives generic answers / doesn't use graph tools

**Cause**: Neo4j is empty (ingest hasn't run) or `ContextBuilder` returns empty graph overview.  
**Check**: `GET /api/stats` — if all counts are 0, ingest hasn't completed.  
**Fix**: Run the ingest pipeline first, then retry the chat.

### Port already in use

```bash
# Find and kill the process using port 8000
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```
