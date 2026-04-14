"""
codebase-agent — Full Graph Extraction + Enrichment Pipeline

Pipeline stages:
  1. Connect to Neo4j, create constraints
  2. Load embedding model (all-MiniLM-L6-v2)
  3. Discover all source files in repo
  4. Extract AST symbols from every file → CodeGraph
  5. Resolve cross-file CALLS (UnresolvedCall → Edge)
  6. Compute graph metrics (fan_in, fan_out, impact_score, entry points, …)
  7. Enrich with Gemini (summary, core_functionality, tags, layer) + re-embed
  8. Add SIMILAR_TO edges from embedding cosine similarity
  9. Push complete graph to Neo4j

Usage:
    cd graph_rag
    python run_extraction.py                          # default test_repo
    python run_extraction.py /path/to/repo            # any codebase
    python run_extraction.py /path/to/repo --clear    # wipe + rebuild
    python run_extraction.py /path/to/repo --no-enrich  # skip Gemini step (faster)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")


# ── Config ────────────────────────────────────────────────────────────────────

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
DEFAULT_REPO   = os.getenv(
    "DEFAULT_REPO_PATH",
    str(Path(__file__).parent / "test_suite"),
)


# ── Imports ───────────────────────────────────────────────────────────────────

from ingestion.repo_scanner import scan_repository
from parsing.treesitter_parser import TreeSitterParser
from extraction.symbol_extractor import SymbolExtractor
from extraction.symbol_index import SymbolIndex
from extraction.call_resolver import resolve_calls
from extraction.inheritance_resolver import resolve_inheritance
from extraction.symbol_models import CodeGraph
from embedding.embedding_generator import EmbeddingGenerator
from graph.neo4j_client import Neo4jClient
from graph.neo4j_graph_builder import Neo4jGraphBuilder
from enrichment.metrics_computer import compute_metrics
from enrichment.summary_enricher import SummaryEnricher
from enrichment.similarity_enricher import add_similarity_edges
from enrichment.bug_annotator import BugAnnotator


EXT_TO_LANG: dict[str, str] = {
    ".java": "java",
    ".c":    "c",
    ".h":    "c",
    ".cpp":  "cpp",
    ".cc":   "cpp",
    ".cxx":  "cpp",
    ".hpp":  "cpp",
}


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run(repo_path: str, clear_first: bool = False, skip_enrich: bool = False, skip_scan: bool = False) -> None:
    repo = Path(repo_path).resolve()
    if not repo.exists():
        print(f"ERROR: repo path does not exist: {repo}")
        sys.exit(1)
    if not repo.is_dir():
        print(f"ERROR: repo path is not a directory: {repo}")
        sys.exit(1)

    _banner(repo, skip_enrich, skip_scan)

    # ── 1. Neo4j connection ───────────────────────────────────────────────────
    _step(1, "Connecting to Neo4j")
    try:
        client = Neo4jClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
        builder = Neo4jGraphBuilder(client)
    except ConnectionError as exc:
        print(f"\n  ERROR: {exc}")
        sys.exit(1)

    if clear_first:
        print("  Clearing existing graph...")
        builder.clear_graph()

    print("  Creating uniqueness constraints...")
    builder.create_constraints()

    # ── 2. Embedding model ────────────────────────────────────────────────────
    _step(2, "Loading embedding model (all-MiniLM-L6-v2)")
    try:
        embedder = EmbeddingGenerator()
    except RuntimeError as exc:
        print(f"\n  ERROR: {exc}")
        client.close()
        sys.exit(1)

    # ── 3. File discovery ─────────────────────────────────────────────────────
    _step(3, "Scanning repository")
    try:
        files = scan_repository(str(repo))
    except (FileNotFoundError, ValueError) as exc:
        print(f"\n  ERROR: {exc}")
        client.close()
        sys.exit(1)
    supported = [f for f in files if Path(f).suffix.lower() in EXT_TO_LANG]
    if not supported:
        print(f"  WARNING: No supported source files found in {repo}")
        print(f"  Supported extensions: {sorted(EXT_TO_LANG.keys())}")
    else:
        print(f"  {len(supported)} supported source files ({len(files)} total)")

    # ── 4. AST extraction ─────────────────────────────────────────────────────
    _step(4, "Extracting code graph from AST")
    global_graph = CodeGraph()
    symbol_index = SymbolIndex()
    parsers: dict[str, TreeSitterParser] = {}

    for file_path in sorted(supported):
        ext  = Path(file_path).suffix.lower()
        lang = EXT_TO_LANG[ext]
        rel  = os.path.relpath(file_path, str(repo)).replace("\\", "/")

        try:
            if lang not in parsers:
                parsers[lang] = TreeSitterParser(lang)
            tree = parsers[lang].parse_file(file_path)
            extractor = SymbolExtractor(lang, symbol_index, embedder)
            subgraph  = extractor.extract(tree.root_node, rel)
            global_graph.merge(subgraph)
            print(f"  -> [{lang:4}] {rel}")
        except Exception as exc:
            print(f"  [skip] {rel}: {exc}")

    print(f"\n  {symbol_index.stats()}")
    print(f"  Graph after extraction : {global_graph.stats()}")

    # ── 5. Call resolution ────────────────────────────────────────────────────
    _step(5, "Resolving cross-file function calls")
    resolve_calls(global_graph, symbol_index)
    print(f"  Graph after call resolution : {global_graph.stats()}")

    # ── 5b. Inheritance resolution ────────────────────────────────────────────
    _step("5b", "Resolving cross-file inheritance (INHERITS_FROM / IMPLEMENTS)")
    resolve_inheritance(global_graph, symbol_index)
    print(f"  Graph after inheritance res : {global_graph.stats()}")

    # ── 6. Graph metrics ──────────────────────────────────────────────────────
    _step(6, "Computing graph metrics (fan-in, fan-out, impact scores)")
    compute_metrics(global_graph)

    # ── 7. Semantic enrichment (optional) ─────────────────────────────────────
    if not skip_enrich:
        _step(7, "Semantic enrichment via Gemini (summary, tags, layer)")
        try:
            enricher = SummaryEnricher(embedder=embedder)
            enricher.enrich(global_graph)
        except (ValueError, RuntimeError) as exc:
            print(f"  WARNING: Semantic enrichment failed — {exc}")
            print("  Continuing without enrichment (use --no-enrich to skip this step).")
    else:
        print("\n[7/9] Semantic enrichment SKIPPED (--no-enrich flag set)")

    # ── 8. Similarity edges ───────────────────────────────────────────────────
    _step(8, "Computing embedding similarity (SIMILAR_TO edges)")
    add_similarity_edges(global_graph, threshold=0.78, top_k=5)
    print(f"  Graph after similarity : {global_graph.stats()}")

    # ── 9. Push to Neo4j ──────────────────────────────────────────────────────
    _step(9, "Pushing graph to Neo4j")
    try:
        stats = builder.insert_graph(global_graph)
    except (RuntimeError, ConnectionError) as exc:
        print(f"\n  ERROR: Failed to push graph to Neo4j — {exc}")
        print("  Check your network connection and that NEO4J_URI is reachable.")
        client.close()
        sys.exit(1)

    # ── 10. Bug annotation ────────────────────────────────────────────────────
    bug_stats = {}
    if not skip_scan:
        _step(10, "Scanning functions for vulnerabilities (GraphCodeBERT + LLM)")
        try:
            annotator = BugAnnotator(client)
            bug_stats = annotator.annotate()
        except RuntimeError as exc:
            print(f"  WARNING: Vulnerability scan failed — {exc}")
            print("  Continuing without bug annotation (use --no-scan to skip this step).")
    else:
        print("\n[10/10] Vulnerability scan SKIPPED (--no-scan flag set)")

    client.close()
    _summary(stats, bug_stats)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _banner(repo: Path, skip_enrich: bool, skip_scan: bool = False) -> None:
    print(f"\n{'='*62}")
    print(f"  codebase-agent — Graph Extraction Pipeline (10 steps)")
    print(f"{'='*62}")
    print(f"  Repo   : {repo}")
    print(f"  Neo4j  : {NEO4J_URI}")
    print(f"  Enrich : {'yes (Gemini summaries + tags)' if not skip_enrich else 'no'}")
    print(f"  Scan   : {'yes (vulnerability detection)' if not skip_scan else 'no'}")
    print()


def _step(n, label: str) -> None:
    print(f"\n[{n}/10] {label}...")


def _summary(stats: dict, bug_stats: dict) -> None:
    print()
    print("=" * 62)
    print("  PIPELINE COMPLETE")
    print(f"  Nodes inserted  : {stats.get('nodes_created', 0)}")
    print(f"  Edges inserted  : {stats.get('edges_created', 0)}")
    print(f"  Tag nodes       : {stats.get('tags_created', 0)}")

    if bug_stats:
        total   = bug_stats.get("total", 0)
        bugs    = bug_stats.get("bugs", 0)
        crit    = bug_stats.get("CRITICAL", 0)
        high    = bug_stats.get("HIGH", 0)
        medium  = bug_stats.get("MEDIUM", 0)
        low     = bug_stats.get("LOW", 0)
        print()
        print(f"  Functions scanned : {total}")
        print(f"  Bugs found        : {bugs}")
        if bugs:
            print(f"    CRITICAL : {crit}")
            print(f"    HIGH     : {high}")
            print(f"    MEDIUM   : {medium}")
            print(f"    LOW      : {low}")

    print()
    print("  Graph now enables queries like:")
    print('    "What does authenticateUser do?"')
    print('    "What bugs exist in this codebase?"')
    print('    "Show me all critical vulnerabilities"')
    print('    "What is the blast radius of this buggy function?"')
    print('    "Which entry points lead to vulnerable code?"')
    print("=" * 62)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _args  = [a for a in sys.argv[1:] if not a.startswith("--")]
    _flags = {a for a in sys.argv[1:] if a.startswith("--")}

    run(
        repo_path   = _args[0] if _args else DEFAULT_REPO,
        clear_first = "--clear"     in _flags,
        skip_enrich = "--no-enrich" in _flags,
        skip_scan   = "--no-scan"   in _flags,
    )
