"""
C++ AST → CodeGraph extractor.

Extracts:
  Nodes   : File, Namespace, Class, Struct, Function (free + methods)
  Edges   : DEFINES, INCLUDES, CONTAINS, HAS_METHOD, INHERITS_FROM
  Calls   : recorded as UnresolvedCall objects

Scope tracking uses explicit stacks for namespaces, classes, and functions.
"""
from __future__ import annotations

from extraction.symbol_models import CodeGraph, Edge, Node, UnresolvedCall
from extraction.symbol_index import SymbolIndex


def _text(node) -> str:
    return node.text.decode("utf-8", errors="ignore").strip() if node.text else ""


def _extract_declarator_name(declarator_node) -> str:
    """
    Same recursive strategy as in c_extractor, extended for C++ qualified names.

      identifier               → "foo"
      function_declarator      → recurse into "declarator" field
      pointer_declarator       → recurse into "declarator" field
      reference_declarator     → recurse into "declarator" field
      qualified_identifier     → take the "name" field (e.g. DB::connect → "connect")
      destructor_name          → e.g. "~MyClass"
    """
    if declarator_node is None:
        return ""

    ntype = declarator_node.type

    if ntype in ("identifier", "field_identifier"):
        return _text(declarator_node)

    if ntype == "qualified_identifier":
        name_node = declarator_node.child_by_field_name("name")
        if name_node:
            return _text(name_node)

    if ntype == "destructor_name":
        # e.g.  ~MyClass
        for child in declarator_node.children:
            if child.type == "identifier":
                return "~" + _text(child)
        return _text(declarator_node)

    # function_declarator / pointer_declarator / reference_declarator
    inner = declarator_node.child_by_field_name("declarator")
    if inner:
        result = _extract_declarator_name(inner)
        if result:
            return result

    # Fallback
    for child in declarator_node.children:
        if child.type in ("identifier", "field_identifier"):
            return _text(child)

    return ""


def _get_return_type(func_node) -> str:
    type_node = func_node.child_by_field_name("type")
    return _text(type_node) if type_node else ""


def _get_params_signature(func_node) -> str:
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
        elif p.type in ("variadic_parameter", "variadic_parameter_declaration"):
            parts.append("...")

    return "(" + ", ".join(parts) + ")"


def _get_modifiers(func_node) -> dict:
    """Check for virtual, override, static in the function specifiers."""
    flags = {"is_virtual": False, "is_override": False, "is_static": False}
    for child in func_node.children:
        t = child.type
        if t == "virtual":
            flags["is_virtual"] = True
        elif t == "storage_class_specifier" and _text(child) == "static":
            flags["is_static"] = True
        elif t == "function_specifier" and _text(child) == "virtual":
            flags["is_virtual"] = True
        # "override" appears as a type_qualifier after the parameter list
        elif t == "type_qualifier" and _text(child) == "override":
            flags["is_override"] = True
    return flags


def _get_cpp_base_classes(class_node) -> list[str]:
    """
    Extract base class names from C++ class specifier.
    Example: class DB : public BaseDB, private ILogger
    """
    bases = []
    for child in class_node.children:
        if child.type == "base_class_clause":
            for sub in child.children:
                if sub.type in ("type_identifier", "qualified_identifier"):
                    bases.append(_text(sub))
    return bases


class CppExtractor:

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
            language="cpp",
        ))

        namespace_stack: list[tuple[str, str]] = []  # (ns_name, ns_uid)
        class_stack: list[tuple[str, str]] = []       # (class_name, class_uid)
        struct_stack: list[tuple[str, str]] = []      # (struct_name, struct_uid)
        function_stack: list[tuple[str, str]] = []    # (func_name, func_uid)

        def traverse(node):
            pushed_namespace = None
            pushed_class = None
            pushed_struct = None
            pushed_function = None
            ntype = node.type

            # ── INCLUDE ──────────────────────────────────────────────────────
            if ntype == "preproc_include":
                for child in node.children:
                    if child.type in ("string_literal", "system_lib_string"):
                        inc_text = _text(child)
                        inc_uid = inc_text.strip('"<> ')
                        graph.add_node(Node(
                            uid=inc_uid, label="Include",
                            name=inc_uid, file="",
                        ))
                        graph.add_edge(Edge(
                            source_uid=file_name,
                            target_uid=inc_uid,
                            relation="INCLUDES",
                        ))
                        break

            # ── NAMESPACE ────────────────────────────────────────────────────
            elif ntype == "namespace_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    ns_name = _text(name_node)
                    ns_uid = f"{file_name}::{ns_name}"
                    graph.add_node(Node(
                        uid=ns_uid,
                        label="Namespace",
                        name=ns_name,
                        file=file_name,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        language="cpp",
                        embedding=self._embed(ns_name),
                    ))
                    graph.add_edge(Edge(
                        source_uid=file_name,
                        target_uid=ns_uid,
                        relation="DEFINES",
                    ))
                    namespace_stack.append((ns_name, ns_uid))
                    pushed_namespace = (ns_name, ns_uid)

            # ── CLASS ────────────────────────────────────────────────────────
            elif ntype == "class_specifier":
                name_node = node.child_by_field_name("name")
                if name_node:
                    cls_name = _text(name_node)
                    cls_uid = f"{file_name}::{cls_name}"
                    base_classes = _get_cpp_base_classes(node)

                    graph.add_node(Node(
                        uid=cls_uid,
                        label="Class",
                        name=cls_name,
                        file=file_name,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        body=_text(node),
                        language="cpp",
                        embedding=self._embed(_text(node)),
                    ))
                    self.symbol_index.add_class(cls_name, cls_uid)

                    # Parent container: namespace > file
                    if namespace_stack:
                        _, ns_uid = namespace_stack[-1]
                        graph.add_edge(Edge(
                            source_uid=ns_uid,
                            target_uid=cls_uid,
                            relation="CONTAINS",
                        ))
                    graph.add_edge(Edge(
                        source_uid=file_name,
                        target_uid=cls_uid,
                        relation="DEFINES",
                    ))

                    # Inheritance
                    for base in base_classes:
                        # Resolve now if already indexed; otherwise store as provisional
                        base_uid = (
                            self.symbol_index.resolve_class(base)
                            or f"unresolved::{base}"
                        )
                        graph.add_edge(Edge(
                            source_uid=cls_uid,
                            target_uid=base_uid,
                            relation="INHERITS_FROM",
                        ))

                    class_stack.append((cls_name, cls_uid))
                    pushed_class = (cls_name, cls_uid)

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
                        language="cpp",
                        embedding=self._embed(_text(node)),
                    ))
                    self.symbol_index.add_struct(struct_name, struct_uid)
                    graph.add_edge(Edge(
                        source_uid=file_name,
                        target_uid=struct_uid,
                        relation="DEFINES",
                    ))
                    # Push so field_declaration children get HAS_FIELD edges
                    struct_stack.append((struct_name, struct_uid))
                    pushed_struct = (struct_name, struct_uid)

            # ── ENUM ─────────────────────────────────────────────────────────
            elif ntype == "enum_specifier":
                name_node = node.child_by_field_name("name")
                if name_node:
                    enum_name = _text(name_node)
                    enum_uid = f"{file_name}::{enum_name}"

                    # Collect enumerator names before recursing
                    constants = []
                    for child in node.children:
                        if child.type == "enumerator_list":
                            for sub in child.children:
                                if sub.type == "enumerator":
                                    cname = sub.child_by_field_name("name")
                                    if cname:
                                        constants.append(_text(cname))

                    graph.add_node(Node(
                        uid=enum_uid,
                        label="Enum",
                        name=enum_name,
                        file=file_name,
                        signature=", ".join(constants),
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        body=_text(node),
                        language="cpp",
                        embedding=self._embed(
                            f"enum {enum_name} constants: {', '.join(constants)}"
                        ),
                    ))
                    self.symbol_index.add_class(enum_name, enum_uid)

                    if namespace_stack:
                        _, ns_uid = namespace_stack[-1]
                        graph.add_edge(Edge(
                            source_uid=ns_uid,
                            target_uid=enum_uid,
                            relation="CONTAINS",
                        ))
                    graph.add_edge(Edge(
                        source_uid=file_name,
                        target_uid=enum_uid,
                        relation="DEFINES",
                    ))

            # ── FIELD (inside class or struct) ────────────────────────────────
            elif ntype == "field_declaration":
                parent_uid = None
                if class_stack:
                    _, parent_uid = class_stack[-1]
                elif struct_stack:
                    _, parent_uid = struct_stack[-1]

                if parent_uid:
                    type_node = node.child_by_field_name("type")
                    field_type = _text(type_node) if type_node else "unknown"

                    declarator = node.child_by_field_name("declarator")
                    if declarator:
                        field_name = _extract_declarator_name(declarator)
                        if field_name:
                            field_uid = f"{parent_uid}::field::{field_name}"
                            graph.add_node(Node(
                                uid=field_uid,
                                label="Field",
                                name=field_name,
                                file=file_name,
                                return_type=field_type,
                                line_start=node.start_point[0] + 1,
                                language="cpp",
                                signature=f"{field_type} {field_name}",
                            ))
                            graph.add_edge(Edge(
                                source_uid=parent_uid,
                                target_uid=field_uid,
                                relation="HAS_FIELD",
                            ))

            # ── FUNCTION ─────────────────────────────────────────────────────
            elif ntype == "function_definition":
                declarator = node.child_by_field_name("declarator")
                if declarator:
                    func_name = _extract_declarator_name(declarator)
                    if func_name:
                        ret_type = _get_return_type(node)
                        params_sig = _get_params_signature(node)
                        signature = f"{ret_type} {func_name}{params_sig}".strip()
                        modifiers = _get_modifiers(node)

                        # Determine parent scope
                        if class_stack:
                            parent_name, parent_uid = class_stack[-1]
                            func_uid = f"{parent_uid}::{func_name}"
                            qualified = f"{parent_name}::{func_name}"
                            parent_relation = "HAS_METHOD"
                        elif namespace_stack:
                            _, ns_uid = namespace_stack[-1]
                            func_uid = f"{ns_uid}::{func_name}"
                            qualified = func_name
                            parent_relation = "CONTAINS"
                        else:
                            func_uid = f"{file_name}::{func_name}"
                            qualified = func_name
                            parent_relation = "DEFINES"

                        graph.add_node(Node(
                            uid=func_uid,
                            label="Function",
                            name=func_name,
                            file=file_name,
                            qualified_name=qualified,
                            signature=signature,
                            return_type=ret_type,
                            is_virtual=modifiers["is_virtual"],
                            is_override=modifiers["is_override"],
                            is_static=modifiers["is_static"],
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            body=_text(node),
                            language="cpp",
                            embedding=self._embed(_text(node)),
                        ))
                        self.symbol_index.add_function(func_name, func_uid)

                        # Always add a DEFINES edge from file (for global discoverability)
                        graph.add_edge(Edge(
                            source_uid=file_name,
                            target_uid=func_uid,
                            relation="DEFINES",
                        ))
                        # Also add the scoped relationship
                        if parent_relation != "DEFINES":
                            _, parent_uid = (
                                class_stack[-1] if class_stack else namespace_stack[-1]
                            )
                            graph.add_edge(Edge(
                                source_uid=parent_uid,
                                target_uid=func_uid,
                                relation=parent_relation,
                            ))

                        function_stack.append((func_name, func_uid))
                        pushed_function = (func_name, func_uid)

            # ── FUNCTION CALL ────────────────────────────────────────────────
            elif ntype == "call_expression":
                func_node = node.child_by_field_name("function")
                if func_node and function_stack:
                    # Strip member access: obj.method() or obj->method()
                    raw = _text(func_node)
                    # For "std::cout << x" the call node type is different — skip
                    callee_name = raw.split("::")[-1].split("->")[-1].split(".")[-1].strip()
                    if callee_name and callee_name.isidentifier():
                        _, caller_uid = function_stack[-1]
                        graph.add_unresolved_call(UnresolvedCall(
                            caller_uid=caller_uid,
                            callee_name=callee_name,
                            caller_file=file_name,
                        ))

            # ── Recurse ──────────────────────────────────────────────────────
            for child in node.children:
                traverse(child)

            # Pop on exit
            if pushed_namespace and namespace_stack and namespace_stack[-1] == pushed_namespace:
                namespace_stack.pop()
            if pushed_class and class_stack and class_stack[-1] == pushed_class:
                class_stack.pop()
            if pushed_struct and struct_stack and struct_stack[-1] == pushed_struct:
                struct_stack.pop()
            if pushed_function and function_stack and function_stack[-1] == pushed_function:
                function_stack.pop()

        traverse(root_node)
        return graph
