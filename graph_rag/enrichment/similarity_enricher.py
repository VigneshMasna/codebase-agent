"""
Similarity Enricher — adds SIMILAR_TO edges between semantically similar Function nodes.

Uses cosine similarity on the node embeddings (generated from function bodies or
summaries if the SummaryEnricher has already run).

SIMILAR_TO edges power agent queries like:
  "Find functions similar to validatePassword"
  "Show me code that does the same thing as connectDB"
  "Are there duplicate implementations of this logic?"

Design decisions:
  - Only Function nodes are connected (not File / Package / Include)
  - External functions (external::*) are excluded
  - Similarity threshold: default 0.78 (tunable)
  - Each node gets at most top_k=5 similar edges (prevents graph explosion)
  - Edge is added in ONE direction only (A→B, not B→A) — both directions are stored
    so the agent can find similar functions from either end using:
      MATCH (f)-[:SIMILAR_TO]-(g)   (undirected)
"""
from __future__ import annotations

import numpy as np

from extraction.symbol_models import CodeGraph, Edge


def _cosine(a: list, b: list) -> float:
    try:
        va = np.array(a, dtype=np.float32)
        vb = np.array(b, dtype=np.float32)
        norm = np.linalg.norm(va) * np.linalg.norm(vb)
        if norm == 0:
            return 0.0
        return float(np.dot(va, vb) / norm)
    except Exception:
        return 0.0


def add_similarity_edges(
    graph: CodeGraph,
    threshold: float = 0.78,
    top_k: int = 5,
) -> int:
    """
    In-place: compute pairwise cosine similarity between all Function node embeddings
    and add SIMILAR_TO edges for pairs above the threshold.

    Returns the number of SIMILAR_TO edges added.
    """
    # Collect internal Function nodes with valid embeddings
    func_nodes = [
        n for n in graph.get_nodes()
        if n.label == "Function"
        and n.embedding
        and len(n.embedding) > 0
        and not n.uid.startswith("external::")
    ]

    if len(func_nodes) < 2:
        return 0

    # Avoid adding duplicate edges (A→B and B→A)
    seen: set[tuple[str, str]] = set()
    added = 0

    for i, node_a in enumerate(func_nodes):
        # Compute similarity against all other nodes
        scored: list[tuple[float, str]] = []
        for j, node_b in enumerate(func_nodes):
            if i == j:
                continue
            pair = (min(node_a.uid, node_b.uid), max(node_a.uid, node_b.uid))
            if pair in seen:
                continue

            sim = _cosine(node_a.embedding, node_b.embedding)
            if sim >= threshold:
                scored.append((sim, node_b.uid))

        # Keep only top_k most similar
        scored.sort(reverse=True)
        for sim_score, target_uid in scored[:top_k]:
            pair = (min(node_a.uid, target_uid), max(node_a.uid, target_uid))
            if pair in seen:
                continue
            seen.add(pair)

            graph.add_edge(Edge(
                source_uid=node_a.uid,
                target_uid=target_uid,
                relation="SIMILAR_TO",
            ))
            added += 1

    print(f"  Added {added} SIMILAR_TO edges (threshold={threshold}, top_k={top_k})")
    return added
