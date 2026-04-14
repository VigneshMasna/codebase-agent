"""
Graph Metrics Computer.

Computes structural metrics for every Function node from the resolved call graph.
All metrics are stored as properties on the Node objects (in-place mutation).

Metrics computed:
  fan_in        — how many distinct callers this function has
                  (critical for impact analysis: "who breaks if I remove this?")

  fan_out       — how many distinct functions this function calls
                  (indicates complexity / coupling)

  is_entry_point — fan_in == 0 for non-constructor/destructor functions
                   → these are the public API surface or main entry points

  is_leaf        — fan_out == 0
                   → pure utility functions; safe to analyze in isolation

  is_recursive   — direct self-call (CALLS edge from node back to itself)
                   → flags potential stack overflow risk

  impact_score   — weighted: fan_in * 2 + fan_out
                   → fan_in weighted more because callers break if removed

These answer:
  "What happens if we remove X?"   → impact_score, fan_in, traverse CALLS backward
  "What are the most critical functions?"  → ORDER BY impact_score DESC
  "What are the entry points of this codebase?" → WHERE is_entry_point = true
  "Show me leaf utility functions"  → WHERE is_leaf = true
  "Are there recursive functions?"  → WHERE is_recursive = true
"""
from __future__ import annotations

from collections import defaultdict

from extraction.symbol_models import CodeGraph


def compute_metrics(graph: CodeGraph) -> None:
    """
    In-place: compute and store all graph metrics on Function nodes.
    Must be called AFTER call resolution (resolve_calls) so all CALLS edges exist.
    """
    # ── Pass 1: count fan-in / fan-out from CALLS edges ───────────────────────
    fan_in: dict[str, int] = defaultdict(int)
    fan_out: dict[str, int] = defaultdict(int)
    direct_callees: dict[str, set[str]] = defaultdict(set)

    for edge in graph.edges:
        if edge.relation != "CALLS":
            continue

        src = edge.source_uid
        tgt = edge.target_uid

        # Exclude external:: nodes (stdlib / framework calls) from both
        # fan_in and fan_out so metrics reflect internal coupling only.
        if tgt.startswith("external::"):
            continue

        fan_out[src] += 1
        direct_callees[src].add(tgt)
        fan_in[tgt] += 1

    # ── Pass 2: write metrics back onto Function nodes ─────────────────────────
    for uid, node in graph.nodes.items():
        if node.label != "Function":
            continue

        node.fan_in  = fan_in.get(uid, 0)
        node.fan_out = fan_out.get(uid, 0)

        # Entry point: nothing calls this function internally
        # Exclude constructors (<init>) and destructors (~) from this flag
        is_ctor_or_dtor = node.name.startswith("<init>") or node.name.startswith("~")
        node.is_entry_point = (node.fan_in == 0) and not is_ctor_or_dtor

        # Leaf: this function calls nothing
        node.is_leaf = (node.fan_out == 0)

        # Direct recursion: does this function call itself?
        node.is_recursive = uid in direct_callees.get(uid, set())

        # Impact score: callers matter more (breaking callers = higher blast radius)
        node.impact_score = round(node.fan_in * 2.0 + node.fan_out * 1.0, 2)

    print(
        f"  Metrics computed: "
        f"{sum(1 for n in graph.nodes.values() if n.label == 'Function' and n.is_entry_point)} entry points, "
        f"{sum(1 for n in graph.nodes.values() if n.label == 'Function' and n.is_leaf)} leaves, "
        f"{sum(1 for n in graph.nodes.values() if n.label == 'Function' and n.is_recursive)} recursive"
    )
