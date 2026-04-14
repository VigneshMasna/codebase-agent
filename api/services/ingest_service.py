"""
IngestService — wraps the full graph extraction pipeline for use by the API.

This mirrors the logic in graph_rag/run_extraction.py but:
  1. Never calls sys.exit() — raises exceptions instead.
  2. Reports progress via a callback so the caller can stream SSE events.
  3. Returns a result dict with node/edge counts on success.

The service is instantiated fresh for each ingest job (not a singleton) because
it creates its own Neo4j client and embedder per run.

Progress callback signature:
    callback(step: int, step_name: str, message: str, pct: int) -> None
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, Optional

# Ensure graph_rag sub-packages are importable with short names
_ROOT = Path(__file__).parent.parent.parent
for _p in (str(_ROOT), str(_ROOT / "graph_rag")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

# Fix relative GOOGLE_APPLICATION_CREDENTIALS
_gac = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
if _gac and not Path(_gac).is_absolute():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str((_ROOT / _gac).resolve())


# Supported file extensions → language mapping (mirrors run_extraction.py)
EXT_TO_LANG: dict[str, str] = {
    ".java": "java",
    ".c":    "c",
    ".h":    "c",
    ".cpp":  "cpp",
    ".cc":   "cpp",
    ".cxx":  "cpp",
    ".hpp":  "cpp",
}

ProgressCallback = Callable[[int, str, str, int], None]


class IngestService:
    """
    Runs the 10-step code graph extraction pipeline.

    Usage:
        def on_progress(step, step_name, message, pct):
            print(f"[{step}/10] {step_name}: {message}")

        service = IngestService(progress_callback=on_progress)
        result = service.run(folder_path="/path/to/repo", clear_first=False)
        # result == {"nodes_created": N, "edges_created": M, ...}
    """

    def __init__(
        self,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> None:
        self._cb = progress_callback or _noop_callback

    # ── Public ────────────────────────────────────────────────────────────────

    def run(
        self,
        folder_path: str,
        clear_first: bool = False,
        skip_enrich: bool = False,
        skip_scan: bool = False,
    ) -> dict:
        """
        Execute the full extraction pipeline.

        Returns a result dict on success.
        Raises RuntimeError or ConnectionError on fatal failure.
        """
        repo = Path(folder_path).resolve()
        if not repo.exists():
            raise FileNotFoundError(f"Repository path does not exist: {repo}")
        if not repo.is_dir():
            raise ValueError(f"Repository path is not a directory: {repo}")

        # ── Step 1: Neo4j connection ───────────────────────────────────────
        self._progress(1, "Connecting to Neo4j", "Opening database connection…", 5)
        from graph.neo4j_client import Neo4jClient
        from graph.neo4j_graph_builder import Neo4jGraphBuilder

        # Let Neo4jClient raise ConnectionError on failure (handled by caller)
        client = Neo4jClient(
            uri=os.getenv("NEO4J_URI",      "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER",    "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", ""),
        )
        builder = Neo4jGraphBuilder(client)

        try:
            if clear_first:
                self._progress(1, "Connecting to Neo4j", "Clearing existing graph…", 7)
                builder.clear_graph()

            self._progress(1, "Connecting to Neo4j", "Creating uniqueness constraints…", 9)
            builder.create_constraints()

            # ── Step 2: Embedding model ────────────────────────────────────
            self._progress(2, "Loading embedding model", "Loading all-MiniLM-L6-v2…", 12)
            from embedding.embedding_generator import EmbeddingGenerator
            embedder = EmbeddingGenerator()  # raises RuntimeError on failure
            self._progress(2, "Loading embedding model", "Embedding model ready.", 15)

            # ── Step 3: File discovery ─────────────────────────────────────
            self._progress(3, "Scanning repository", f"Discovering files in {repo}…", 18)
            from ingestion.repo_scanner import scan_repository
            files = scan_repository(str(repo))
            supported = [f for f in files if Path(f).suffix.lower() in EXT_TO_LANG]
            if not supported:
                self._progress(3, "Scanning repository",
                               f"WARNING: No supported source files found. "
                               f"Supported: {sorted(EXT_TO_LANG.keys())}", 20)
            else:
                self._progress(3, "Scanning repository",
                               f"{len(supported)} supported files ({len(files)} total).", 20)

            # ── Step 4: AST extraction ─────────────────────────────────────
            self._progress(4, "Extracting code graph", "Parsing AST symbols…", 22)
            from extraction.symbol_models import CodeGraph
            from extraction.symbol_index import SymbolIndex
            from extraction.symbol_extractor import SymbolExtractor
            from parsing.treesitter_parser import TreeSitterParser

            global_graph = CodeGraph()
            symbol_index = SymbolIndex()
            total = len(supported)

            # ── Pre-create all language parsers before the file loop ──────────
            # CRITICAL: creating parsers inside the try/except loop means a
            # tree-sitter binary failure (e.g. glibc mismatch on Linux) silently
            # [skip]s every file → empty graph → 0 nodes pushed as a fake success.
            # By creating parsers here, any binary failure raises immediately.
            langs_needed = {EXT_TO_LANG[Path(f).suffix.lower()] for f in supported}
            parsers: dict[str, TreeSitterParser] = {}
            for lang_name in langs_needed:
                try:
                    parsers[lang_name] = TreeSitterParser(lang_name)
                except Exception as exc:
                    raise RuntimeError(
                        f"Tree-Sitter failed to initialise the '{lang_name}' parser: {exc}. "
                        f"This may indicate a binary incompatibility of tree-sitter-languages "
                        f"on this platform. Check the installed wheel version."
                    ) from exc

            skip_count = 0
            for idx, file_path in enumerate(sorted(supported)):
                ext  = Path(file_path).suffix.lower()
                lang = EXT_TO_LANG[ext]
                rel  = os.path.relpath(file_path, str(repo)).replace("\\", "/")
                pct  = 22 + int((idx / max(total, 1)) * 20)  # 22 → 42

                try:
                    tree = parsers[lang].parse_file(file_path)
                    extractor = SymbolExtractor(lang, symbol_index, embedder)
                    subgraph  = extractor.extract(tree.root_node, rel)
                    global_graph.merge(subgraph)
                    self._progress(4, "Extracting code graph",
                                   f"[{lang}] {rel}", pct)
                except Exception as exc:
                    skip_count += 1
                    self._progress(4, "Extracting code graph",
                                   f"[skip] {rel}: {exc}", pct)

            self._progress(4, "Extracting code graph",
                           f"Extraction complete. {global_graph.stats()}", 42)

            # ── Guard: fail loudly if all files were skipped ──────────────────
            # Without this guard, the pipeline continues and pushes an empty
            # graph to Neo4j — returning nodes_created=0 as a fake success.
            non_file_nodes = sum(
                1 for n in global_graph.get_nodes() if n.label != "File"
            )
            if total > 0 and non_file_nodes == 0:
                raise RuntimeError(
                    f"AST extraction produced 0 code nodes from {total} supported file(s) "
                    f"({skip_count} skipped). "
                    f"Check the Step 4 '[skip]' progress messages above for individual errors. "
                    f"Common causes: encoding issues, malformed source files, or empty files."
                )

            # ── Step 5: Call resolution ────────────────────────────────────
            self._progress(5, "Resolving function calls", "Cross-file call resolution…", 45)
            from extraction.call_resolver import resolve_calls
            resolve_calls(global_graph, symbol_index)
            self._progress(5, "Resolving function calls",
                           global_graph.stats(), 48)

            # ── Step 5b: Inheritance resolution ───────────────────────────
            self._progress(6, "Resolving inheritance",
                           "INHERITS_FROM / IMPLEMENTS edges…", 50)
            from extraction.inheritance_resolver import resolve_inheritance
            resolve_inheritance(global_graph, symbol_index)
            self._progress(6, "Resolving inheritance",
                           global_graph.stats(), 53)

            # ── Step 6: Graph metrics ──────────────────────────────────────
            self._progress(7, "Computing graph metrics",
                           "fan-in, fan-out, impact scores…", 55)
            from enrichment.metrics_computer import compute_metrics
            compute_metrics(global_graph)
            self._progress(7, "Computing graph metrics", "Metrics done.", 58)

            # ── Step 7: Semantic enrichment (optional) ─────────────────────
            if not skip_enrich:
                self._progress(8, "Semantic enrichment",
                               "Enriching nodes with Gemini summaries + tags…", 60)
                try:
                    from enrichment.summary_enricher import SummaryEnricher
                    enricher = SummaryEnricher(embedder=embedder)
                    count = enricher.enrich(global_graph)
                    self._progress(8, "Semantic enrichment",
                                   f"Enriched {count} nodes.", 70)
                except Exception as exc:
                    self._progress(8, "Semantic enrichment",
                                   f"WARNING: enrichment failed — {exc}. Continuing.", 70)
            else:
                self._progress(8, "Semantic enrichment",
                               "Skipped (skip_enrich=True).", 70)

            # ── Step 8: Similarity edges ───────────────────────────────────
            self._progress(9, "Computing similarity edges",
                           "SIMILAR_TO edges from embedding cosine similarity…", 72)
            from enrichment.similarity_enricher import add_similarity_edges
            add_similarity_edges(global_graph, threshold=0.78, top_k=5)
            self._progress(9, "Computing similarity edges",
                           global_graph.stats(), 75)

            # ── Step 9: Push to Neo4j ──────────────────────────────────────
            # Re-verify connectivity before insert — the client may have been
            # idle for several minutes during enrichment (AuraDB drops idle
            # connections), so ping Neo4j to force a reconnect if needed.
            self._progress(10, "Pushing graph to Neo4j",
                           "Inserting nodes and edges…", 78)
            try:
                client.driver.verify_connectivity()
            except Exception:
                # Re-create client if the connection was dropped
                client.close()
                client = Neo4jClient(
                    uri=os.getenv("NEO4J_URI",      "bolt://localhost:7687"),
                    user=os.getenv("NEO4J_USER",    "neo4j"),
                    password=os.getenv("NEO4J_PASSWORD", ""),
                )
                builder = Neo4jGraphBuilder(client)
            stats = builder.insert_graph(global_graph)
            self._progress(10, "Pushing graph to Neo4j",
                           f"Nodes: {stats.get('nodes_created', 0)}, "
                           f"Edges: {stats.get('edges_created', 0)}", 90)

            # ── Step 10: Bug annotation (optional) ────────────────────────
            bug_stats: dict = {}
            if not skip_scan:
                self._progress(10, "Vulnerability scan",
                               "Scanning functions with GraphCodeBERT + LLM…", 92)
                try:
                    from enrichment.bug_annotator import BugAnnotator
                    annotator = BugAnnotator(client)
                    bug_stats = annotator.annotate()
                    self._progress(10, "Vulnerability scan",
                                   f"Scanned {bug_stats.get('total', 0)} functions, "
                                   f"{bug_stats.get('bugs', 0)} bugs found.", 98)
                except RuntimeError as exc:
                    self._progress(10, "Vulnerability scan",
                                   f"WARNING: scan failed — {exc}. Continuing.", 98)
            else:
                self._progress(10, "Vulnerability scan",
                               "Skipped (skip_scan=True).", 98)

            self._progress(10, "Complete", "Pipeline finished successfully.", 100)

        finally:
            client.close()

        return {
            "nodes_created":      stats.get("nodes_created", 0),
            "edges_created":      stats.get("edges_created", 0),
            "tags_created":       stats.get("tags_created", 0),
            "files_processed":    len(supported),
            "functions_scanned":  bug_stats.get("total", 0),
            "bugs_found":         bug_stats.get("bugs", 0),
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _progress(self, step: int, step_name: str, message: str, pct: int) -> None:
        try:
            self._cb(step, step_name, message, pct)
        except Exception:
            pass  # never let a broken callback abort the pipeline


def _noop_callback(step: int, step_name: str, message: str, pct: int) -> None:
    pass
