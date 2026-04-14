"""
Tool Registry — Gemini FunctionDeclaration schemas for the 6 agent tools.

Keep schemas SIMPLE: use only STRING types, only required parameters.
Optional ints (top_k, depth) are handled with defaults in tools.py.
MALFORMED_FUNCTION_CALL errors occur with complex schemas or optional integers.
"""
from __future__ import annotations

from google.genai import types


def build_tool_declarations() -> list[types.Tool]:
    return [
        types.Tool(
            function_declarations=[

                # ── 1. search_by_concept ──────────────────────────────────
                types.FunctionDeclaration(
                    name="search_by_concept",
                    description=(
                        "Semantically search the codebase knowledge graph for functions, "
                        "classes, or enums related to a concept or topic. "
                        "Uses tag matching and embedding similarity. "
                        "Use when the user asks about a concept or domain "
                        "(e.g. 'authentication', 'database access', 'password hashing') "
                        "or wants to find code by description rather than exact name."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "search_query": types.Schema(
                                type=types.Type.STRING,
                                description=(
                                    "Natural language description of what to find. "
                                    "E.g. 'functions that handle authentication', "
                                    "'database connection management'"
                                ),
                            ),
                        },
                        required=["search_query"],
                    ),
                ),

                # ── 2. get_node_details ───────────────────────────────────
                types.FunctionDeclaration(
                    name="get_node_details",
                    description=(
                        "Get complete details of a specific function, class, struct, "
                        "or enum by its exact name. Returns: full source body, signature, "
                        "summary, core functionality, tags, layer, and metrics. "
                        "Use when the user asks 'what does X do?', 'explain X', "
                        "'show me the code for X', or needs details about a specific node."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "entity_name": types.Schema(
                                type=types.Type.STRING,
                                description=(
                                    "The exact function, class, struct, or enum name. "
                                    "E.g. 'validateCredentials', 'AuthService', 'UserRole'"
                                ),
                            ),
                        },
                        required=["entity_name"],
                    ),
                ),

                # ── 3. trace_callers ──────────────────────────────────────
                types.FunctionDeclaration(
                    name="trace_callers",
                    description=(
                        "Find all functions that call a specific function, tracing "
                        "upstream in the call graph. "
                        "Use when the user asks: 'who calls X?', 'what uses X?', "
                        "'what depends on X?', or for upstream impact analysis. "
                        "Also use as part of 'what breaks if we remove X?'."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "function_name": types.Schema(
                                type=types.Type.STRING,
                                description="Exact function name to trace callers for",
                            ),
                        },
                        required=["function_name"],
                    ),
                ),

                # ── 4. trace_callees ──────────────────────────────────────
                types.FunctionDeclaration(
                    name="trace_callees",
                    description=(
                        "Trace the call tree downstream from a function — what it calls "
                        "and what those functions call. "
                        "Use when the user asks: 'what does X call?', "
                        "'explain the flow of X', 'what does X depend on?', "
                        "'trace execution from X'."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "function_name": types.Schema(
                                type=types.Type.STRING,
                                description="Exact function name to trace callees for",
                            ),
                        },
                        required=["function_name"],
                    ),
                ),

                # ── 5. get_impact_analysis ────────────────────────────────
                types.FunctionDeclaration(
                    name="get_impact_analysis",
                    description=(
                        "Comprehensive impact report: fan_in, fan_out, impact_score, "
                        "direct callers, direct callees, and similar functions. "
                        "Use for: 'what happens if we remove X?', 'how critical is X?', "
                        "'what is the blast radius of X?', 'is X safe to refactor?'."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "function_name": types.Schema(
                                type=types.Type.STRING,
                                description="Exact function name to analyze",
                            ),
                        },
                        required=["function_name"],
                    ),
                ),

                # ── 7. find_vulnerabilities ──────────────────────────────
                types.FunctionDeclaration(
                    name="find_vulnerabilities",
                    description=(
                        "Find all functions flagged as buggy by the vulnerability scanner. "
                        "Returns each function's name, file, severity, impact score, and summary. "
                        "Results are sorted by severity then impact score — most dangerous first. "
                        "Use when the user asks: 'what bugs exist?', 'show me vulnerabilities', "
                        "'what are the critical security issues?', 'is this codebase safe?', "
                        "'what is the most dangerous bug?'. "
                        "Pass a severity_filter to narrow results (CRITICAL/HIGH/MEDIUM/LOW)."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "severity_filter": types.Schema(
                                type=types.Type.STRING,
                                description=(
                                    "Optional severity filter. One of: CRITICAL, HIGH, MEDIUM, LOW. "
                                    "Leave empty to return all vulnerabilities."
                                ),
                            ),
                        },
                        required=[],
                    ),
                ),

                # ── 8. find_vulnerable_paths ─────────────────────────────
                types.FunctionDeclaration(
                    name="find_vulnerable_paths",
                    description=(
                        "Find all entry points that eventually lead to a vulnerable (buggy) "
                        "function through the call graph — direct or indirect. "
                        "Returns each entry point paired with the buggy functions it can reach "
                        "and their severity. "
                        "Use when the user asks: 'which entry points lead to bugs?', "
                        "'what public APIs expose vulnerable code?', "
                        "'what is the attack surface of this codebase?', "
                        "'which callers are affected by vulnerabilities?'."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={},
                        required=[],
                    ),
                ),

                # ── 6. run_cypher ─────────────────────────────────────────
                types.FunctionDeclaration(
                    name="run_cypher",
                    description=(
                        "Execute a read-only Cypher query against the Neo4j knowledge graph. "
                        "Use for complex structural questions: finding all classes in a layer, "
                        "listing entry points, finding high-impact functions, inheritance chains, "
                        "or any custom graph traversal the other tools cannot answer. "
                        "Node labels: File, Class, Enum, Struct, Function, Field, Tag. "
                        "All nodes also have :CodeEntity label and a uid property. "
                        "Relationships: DEFINES, HAS_METHOD, HAS_FIELD, CONTAINS, "
                        "INHERITS_FROM, IMPLEMENTS, CALLS, TAGGED_WITH, SIMILAR_TO."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "cypher_query": types.Schema(
                                type=types.Type.STRING,
                                description=(
                                    "A valid read-only Cypher query. "
                                    "Example: MATCH (f:Function) WHERE f.layer = 'service' "
                                    "RETURN f.name, f.file ORDER BY f.impact_score DESC"
                                ),
                            ),
                        },
                        required=["cypher_query"],
                    ),
                ),

            ]
        )
    ]
