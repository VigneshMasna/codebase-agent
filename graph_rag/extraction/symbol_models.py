"""
Production-level graph data model.

UID strategy (globally unique across repo):
  File              → "{relative_path}"                         e.g. "auth_service.java"
  Package           → "{package_name}"                          e.g. "auth"
  Namespace (C++)   → "{file}::{namespace}"                     e.g. "db.cpp::std"
  Class             → "{file}::{ClassName}"                     e.g. "auth_service.java::AuthService"
  Interface         → "{file}::{InterfaceName}"
  Struct            → "{file}::{StructName}"
  Method            → "{file}::{ClassName}::{method_name}"      e.g. "auth_service.java::AuthService::login"
  Free Function     → "{file}::{function_name}"                 e.g. "db.cpp::connectDB"
  Include           → "{literal}"                               e.g. "<iostream>" or "db.h"
  ExternalFunction  → "external::{name}"                        e.g. "external::printf"
  Tag               → "tag::{name}"                             e.g. "tag::authentication"

Node enrichment properties (added by enrichment pipeline):
  summary            — LLM-generated natural language description (2-3 sentences)
  core_functionality — LLM-generated 1-sentence core purpose (best for embedding)
  tags               — LLM-extracted semantic keywords ["authentication", "validation", ...]
  layer              — architectural layer: service / repository / utility / security / ...
  fan_in             — number of functions that CALL this function (callers)
  fan_out            — number of functions this function CALLS (callees)
  is_entry_point     — True if fan_in == 0 (nothing calls it → API surface / main)
  is_leaf            — True if fan_out == 0 (calls nothing → pure utility)
  is_recursive       — True if there is a direct CALLS edge back to itself
  impact_score       — weighted importance: fan_in*2 + fan_out (used for ranking)

These power the following agent query types:
  "What does X do?"                → summary, core_functionality
  "What happens if we remove X?"  → fan_in, CALLS traversal, impact_score
  "Find authentication code"       → tags, TAGGED_WITH edges
  "Most critical functions"        → impact_score, fan_in
  "Similar functions to X"         → SIMILAR_TO edges
  "Entry points / public API"      → is_entry_point
  "Service layer functions"        → layer == "service"
  "Recursive functions"            → is_recursive
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Node:
    uid: str                              # globally unique identifier
    label: str                            # Neo4j label: Function, Class, Struct, ...
    name: str                             # simple name (e.g. "login")
    file: str                             # source file (relative path)

    # ── Structural properties ────────────────────────────────────────────────
    qualified_name: str = ""              # "ClassName::method"
    signature: str = ""                   # "void login(String user, String pass)"
    return_type: str = ""                 # "void", "int", "boolean"
    visibility: str = "package"           # public / private / protected / package
    is_static: bool = False
    is_virtual: bool = False              # C++
    is_abstract: bool = False
    is_override: bool = False             # C++
    line_start: int = 0
    line_end: int = 0
    body: str = ""                        # full source text
    language: str = ""                    # c / cpp / java

    # ── Semantic enrichment (filled by SummaryEnricher) ──────────────────────
    summary: str = ""                     # "Authenticates a user by verifying credentials..."
    core_functionality: str = ""          # "Validates user credentials against stored passwords."
    tags: list = field(default_factory=list)   # ["authentication", "security", "validation"]
    layer: str = ""                       # service / repository / utility / security / ...

    # ── Graph metrics (filled by MetricsComputer) ────────────────────────────
    fan_in: int = 0                       # callers count
    fan_out: int = 0                      # callees count
    is_entry_point: bool = False          # fan_in == 0
    is_leaf: bool = False                 # fan_out == 0
    is_recursive: bool = False            # direct self-call
    impact_score: float = 0.0            # fan_in*2 + fan_out

    # ── Embedding ────────────────────────────────────────────────────────────
    embedding: list = field(default_factory=list)   # semantic vector

    def __repr__(self) -> str:
        return f"({self.label}:{self.name} @ {self.file})"


@dataclass
class Edge:
    source_uid: str
    target_uid: str
    relation: str      # CALLS / HAS_METHOD / DEFINES / IMPORTS / INCLUDES /
                       # CONTAINS / INHERITS_FROM / IMPLEMENTS /
                       # TAGGED_WITH / SIMILAR_TO

    def __repr__(self) -> str:
        return f"{self.source_uid} -[{self.relation}]-> {self.target_uid}"


@dataclass
class UnresolvedCall:
    """Recorded during AST traversal; resolved later by CallResolver."""
    caller_uid: str
    callee_name: str
    caller_file: str


class CodeGraph:
    """Multi-file code graph. Nodes keyed by uid (dedup). Edges are a list."""

    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self.unresolved_calls: list[UnresolvedCall] = []

    def add_node(self, node: Node) -> None:
        self.nodes[node.uid] = node

    def add_edge(self, edge: Edge) -> None:
        self.edges.append(edge)

    def add_unresolved_call(self, call: UnresolvedCall) -> None:
        self.unresolved_calls.append(call)

    def get_nodes(self) -> list[Node]:
        return list(self.nodes.values())

    def merge(self, other: "CodeGraph") -> None:
        self.nodes.update(other.nodes)
        self.edges.extend(other.edges)
        self.unresolved_calls.extend(other.unresolved_calls)

    def stats(self) -> str:
        labels = {}
        for n in self.nodes.values():
            labels[n.label] = labels.get(n.label, 0) + 1
        label_str = ", ".join(f"{v} {k}" for k, v in sorted(labels.items()))
        rels = {}
        for e in self.edges:
            rels[e.relation] = rels.get(e.relation, 0) + 1
        rel_str = ", ".join(f"{v} {k}" for k, v in sorted(rels.items()))
        return (
            f"Nodes [{label_str}] | "
            f"Edges [{rel_str}] | "
            f"{len(self.unresolved_calls)} unresolved calls"
        )
