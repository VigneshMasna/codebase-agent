"""
C AST → CodeGraph extractor.

Extracts:
  Nodes   : File, Struct, Function (free functions only in C)
  Edges   : DEFINES, INCLUDES
  Calls   : recorded as UnresolvedCall objects

Key fix: function names are extracted by recursively traversing the declarator
sub-tree to find the identifier, instead of blindly stripping "()" from text.
"""
from __future__ import annotations

from extraction.symbol_models import CodeGraph, Edge, Node, UnresolvedCall
from extraction.symbol_index import SymbolIndex


def _text(node) -> str:
    return node.text.decode("utf-8", errors="ignore").strip() if node.text else ""


def _extract_declarator_name(declarator_node) -> str:
    """
    Recursively find the function/variable identifier inside a declarator chain.

    Handles:
      identifier                   → "foo"
      function_declarator          → recurse into declarator field
      pointer_declarator           → recurse into declarator field
      qualified_identifier (C++)   → take the "name" field
      abstract_function_declarator → recurse
    """
    if declarator_node is None:
        return ""

    ntype = declarator_node.type

    if ntype == "identifier":
        return _text(declarator_node)

    if ntype == "qualified_identifier":
        name_node = declarator_node.child_by_field_name("name")
        if name_node:
            return _text(name_node)

    # function_declarator, pointer_declarator, abstract_function_declarator, etc.
    inner = declarator_node.child_by_field_name("declarator")
    if inner:
        result = _extract_declarator_name(inner)
        if result:
            return result

    # Last resort: first identifier child
    for child in declarator_node.children:
        if child.type == "identifier":
            return _text(child)

    return ""


def _get_return_type(func_node) -> str:
    type_node = func_node.child_by_field_name("type")
    return _text(type_node) if type_node else ""


def _get_params_signature(func_node) -> str:
    """
    Walk declarator chain to find the function_declarator, then read its
    parameter_list.
    """
    def find_func_declarator(node):
        if node is None:
            return None
        if node.type == "function_declarator":
            return node
        inner = node.child_by_field_name("declarator")
        return find_func_declarator(inner)

    declarator = func_node.child_by_field_name("declarator")
    func_decl = find_func_declarator(declarator)
    if not func_decl:
        return "()"

    params_node = func_decl.child_by_field_name("parameters")
    if not params_node:
        return "()"

    parts = []
    for p in params_node.children:
        if p.type == "parameter_declaration":
            ptype = ""
            pname = ""
            type_node = p.child_by_field_name("type")
            if type_node:
                ptype = _text(type_node)
            decl_node = p.child_by_field_name("declarator")
            if decl_node:
                pname = _extract_declarator_name(decl_node)
            parts.append(f"{ptype} {pname}".strip())
        elif p.type == "variadic_parameter":
            parts.append("...")

    return "(" + ", ".join(parts) + ")"


class CExtractor:

    def __init__(self, symbol_index: SymbolIndex, embedder=None) -> None:
        self.symbol_index = symbol_index
        self.embedder = embedder

    def _embed(self, text: str) -> list:
        if self.embedder and text:
            return self.embedder.generate(text)
        return []

    def extract(self, root_node, file_name: str) -> CodeGraph:
        graph = CodeGraph()

        # File node
        graph.add_node(Node(
            uid=file_name,
            label="File",
            name=file_name.split("/")[-1],
            file=file_name,
            language="c",
        ))

        # function_stack: track which function body we're currently inside
        function_stack: list[tuple[str, str]] = []  # (name, uid)

        def traverse(node):
            pushed_function = None
            ntype = node.type

            # ── INCLUDE ──────────────────────────────────────────────────────
            if ntype == "preproc_include":
                # Get the raw include text: <stdio.h> or "myheader.h"
                for child in node.children:
                    if child.type in ("string_literal", "system_lib_string"):
                        inc_text = _text(child)
                        # Strip quotes/angle-brackets for the uid
                        inc_uid = inc_text.strip('"<> ')
                        graph.add_node(Node(
                            uid=inc_uid,
                            label="Include",
                            name=inc_uid,
                            file="",
                        ))
                        graph.add_edge(Edge(
                            source_uid=file_name,
                            target_uid=inc_uid,
                            relation="INCLUDES",
                        ))
                        break

            # ── STRUCT ───────────────────────────────────────────────────────
            elif ntype == "struct_specifier":
                name_node = node.child_by_field_name("name")
                if name_node:
                    struct_name = _text(name_node)
                    struct_uid = f"{file_name}::{struct_name}"
                    graph.add_node(Node(
                        uid=struct_uid,
                        label="Struct",
                        name=struct_name,
                        file=file_name,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        body=_text(node),
                        language="c",
                        embedding=self._embed(_text(node)),
                    ))
                    self.symbol_index.add_struct(struct_name, struct_uid)
                    graph.add_edge(Edge(
                        source_uid=file_name,
                        target_uid=struct_uid,
                        relation="DEFINES",
                    ))

            # ── FUNCTION ─────────────────────────────────────────────────────
            elif ntype == "function_definition":
                declarator = node.child_by_field_name("declarator")
                if declarator:
                    func_name = _extract_declarator_name(declarator)
                    if func_name:
                        func_uid = f"{file_name}::{func_name}"
                        ret_type = _get_return_type(node)
                        params_sig = _get_params_signature(node)
                        signature = f"{ret_type} {func_name}{params_sig}".strip()

                        graph.add_node(Node(
                            uid=func_uid,
                            label="Function",
                            name=func_name,
                            file=file_name,
                            qualified_name=func_name,
                            signature=signature,
                            return_type=ret_type,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            body=_text(node),
                            language="c",
                            embedding=self._embed(_text(node)),
                        ))
                        self.symbol_index.add_function(func_name, func_uid)

                        graph.add_edge(Edge(
                            source_uid=file_name,
                            target_uid=func_uid,
                            relation="DEFINES",
                        ))

                        function_stack.append((func_name, func_uid))
                        pushed_function = (func_name, func_uid)

            # ── FUNCTION CALL ────────────────────────────────────────────────
            elif ntype == "call_expression":
                func_node = node.child_by_field_name("function")
                if func_node and function_stack:
                    # Strip member/pointer access: obj->method or obj.method → method
                    raw = _text(func_node).split("(")[0].strip()
                    callee_name = raw.split("->")[-1].split(".")[-1].strip()
                    if callee_name and callee_name.replace("_", "").isalnum():
                        _, caller_uid = function_stack[-1]
                        graph.add_unresolved_call(UnresolvedCall(
                            caller_uid=caller_uid,
                            callee_name=callee_name,
                            caller_file=file_name,
                        ))

            # ── Recurse ──────────────────────────────────────────────────────
            for child in node.children:
                traverse(child)

            if pushed_function:
                if function_stack and function_stack[-1] == pushed_function:
                    function_stack.pop()

        traverse(root_node)
        return graph
