"""
Two-pass call resolver.

After all files are extracted and the SymbolIndex is fully populated, this
module converts UnresolvedCall records into concrete CALLS edges:

  UnresolvedCall(caller_uid="auth.java::AuthService::authenticateUser",
                 callee_name="validatePassword",
                 caller_file="auth_service.java")
  →
  Edge(source_uid="auth.java::AuthService::authenticateUser",
       target_uid="password_utils.java::PasswordUtils::validatePassword",
       relation="CALLS")

Calls that cannot be resolved (stdlib, framework APIs, etc.) become:
  Edge(source_uid=caller_uid,
       target_uid="external::validatePassword",
       relation="CALLS")
  with a corresponding ExternalFunction node added to the graph.
"""
from __future__ import annotations

from extraction.symbol_models import CodeGraph, Edge, Node
from extraction.symbol_index import SymbolIndex


def resolve_calls(graph: CodeGraph, symbol_index: SymbolIndex) -> None:
    """
    In-place: resolve all UnresolvedCall entries in `graph` and add CALLS edges.
    ExternalFunction nodes are added to the graph for unresolvable callees.
    """
    # Deduplicate: avoid creating duplicate CALLS edges
    seen_calls: set[tuple[str, str]] = set()

    for ucall in graph.unresolved_calls:
        caller_uid = ucall.caller_uid
        callee_name = ucall.callee_name

        # Skip empty or obviously invalid names
        if not callee_name or len(callee_name) < 2:
            continue

        # Attempt resolution
        target_uid = symbol_index.resolve_function(
            callee_name, caller_file=ucall.caller_file
        )

        if target_uid is None:
            # Unresolvable → create / reuse ExternalFunction node
            target_uid = f"external::{callee_name}"
            if target_uid not in graph.nodes:
                graph.add_node(Node(
                    uid=target_uid,
                    label="ExternalFunction",
                    name=callee_name,
                    file="",
                ))

        edge_key = (caller_uid, target_uid)
        if edge_key in seen_calls:
            continue
        seen_calls.add(edge_key)

        graph.add_edge(Edge(
            source_uid=caller_uid,
            target_uid=target_uid,
            relation="CALLS",
        ))

    # Clear resolved calls to avoid double-processing if called again
    graph.unresolved_calls.clear()
