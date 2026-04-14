"""
Two-pass inheritance resolver.

After ALL files are extracted and the SymbolIndex is fully populated, this
module resolves INHERITS_FROM and IMPLEMENTS edges whose target_uid was stored
as "unresolved::{ClassName}" because the parent class/interface was defined in
a file not yet processed at extraction time.

Why a second pass is needed
─────────────────────────────
Java/C++ files are processed one at a time. If FileA.java contains:

    class AuthService extends BaseService { ... }

and BaseService is defined in FileB.java, the java_extractor stores:

    Edge(AuthService_uid → "unresolved::BaseService", INHERITS_FROM)

because BaseService's uid isn't in the SymbolIndex yet.

After all files are processed the SymbolIndex has BaseService's uid, so this
resolver rewrites the provisional edge target to the real uid.

Edges that STILL cannot be resolved after this pass (third-party base classes,
framework classes like Activity, ViewModel, etc.) are left as "unresolved::"
and silently dropped by the Neo4j graph builder — which already skips edges
whose target starts with "unresolved::".
"""
from __future__ import annotations

from extraction.symbol_models import CodeGraph
from extraction.symbol_index import SymbolIndex


def resolve_inheritance(graph: CodeGraph, symbol_index: SymbolIndex) -> None:
    """
    In-place: resolve provisional INHERITS_FROM / IMPLEMENTS edge targets.
    Must be called AFTER all files have been extracted and the SymbolIndex
    is fully populated.
    """
    resolved = 0
    still_unresolved = 0

    for edge in graph.edges:
        if edge.relation not in ("INHERITS_FROM", "IMPLEMENTS"):
            continue
        if not edge.target_uid.startswith("unresolved::"):
            continue

        class_name = edge.target_uid[len("unresolved::"):]

        # Try class index first, then struct (C++ structs can be base types)
        resolved_uid = (
            symbol_index.resolve_class(class_name)
            or symbol_index.resolve_struct(class_name)
        )

        if resolved_uid:
            edge.target_uid = resolved_uid
            resolved += 1
        else:
            still_unresolved += 1

    total = resolved + still_unresolved
    if total:
        print(
            f"  Inheritance resolved: {resolved}/{total} "
            f"({still_unresolved} remain unresolved — external/framework classes)"
        )
    else:
        print("  No inheritance edges to resolve.")
