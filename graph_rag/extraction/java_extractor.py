"""
Java AST → CodeGraph extractor.

Extracts:
  Nodes   : File, Package, Class, Interface, Function (methods + constructors)
  Edges   : DEFINES, IMPORTS, CONTAINS, HAS_METHOD, INHERITS_FROM, IMPLEMENTS
  Calls   : recorded as UnresolvedCall objects (resolved later by CallResolver)

Scope tracking uses explicit stacks so nested classes are handled correctly.
"""
from __future__ import annotations

from extraction.symbol_models import CodeGraph, Edge, Node, UnresolvedCall
from extraction.symbol_index import SymbolIndex


def _text(node) -> str:
    """Decode a Tree-Sitter node's text safely."""
    return node.text.decode("utf-8", errors="ignore").strip() if node.text else ""


def _child_text(node, field_name: str) -> str:
    child = node.child_by_field_name(field_name)
    return _text(child) if child else ""


def _modifiers_text(node) -> str:
    for child in node.children:
        if child.type == "modifiers":
            return _text(child)
    return ""


def _get_visibility(node) -> str:
    mods = _modifiers_text(node)
    for vis in ("public", "private", "protected"):
        if vis in mods:
            return vis
    return "package"


def _is_static(node) -> bool:
    return "static" in _modifiers_text(node)


def _is_abstract(node) -> bool:
    return "abstract" in _modifiers_text(node)


def _get_superclass(class_node) -> str:
    superclass = class_node.child_by_field_name("superclass")
    if superclass:
        # "extends TypeName"  — the type_identifier is the child of superclass
        for child in superclass.children:
            if child.type in ("type_identifier", "scoped_type_identifier"):
                return _text(child)
    return ""


def _get_interfaces(class_node) -> list[str]:
    interfaces_node = class_node.child_by_field_name("interfaces")
    if not interfaces_node:
        return []
    result = []
    for child in interfaces_node.children:
        if child.type in ("type_identifier", "scoped_type_identifier"):
            result.append(_text(child))
    return result


def _get_return_type(method_node) -> str:
    type_node = method_node.child_by_field_name("type")
    return _text(type_node) if type_node else "void"


def _get_params_signature(method_node) -> str:
    """Build a readable parameter signature like '(String user, int age)'."""
    params_node = method_node.child_by_field_name("parameters")
    if not params_node:
        return "()"
    parts = []
    for p in params_node.children:
        if p.type in ("formal_parameter", "spread_parameter"):
            ptype = _child_text(p, "type")
            pname = _child_text(p, "name")
            if not pname:
                # fallback: last identifier in the param node
                for c in reversed(p.children):
                    if c.type == "identifier":
                        pname = _text(c)
                        break
            parts.append(f"{ptype} {pname}".strip())
    return "(" + ", ".join(parts) + ")"


class JavaExtractor:

    def __init__(self, symbol_index: SymbolIndex, embedder=None) -> None:
        self.symbol_index = symbol_index
        self.embedder = embedder

    def _embed(self, text: str) -> list:
        if self.embedder and text:
            return self.embedder.generate(text)
        return []

    def extract(self, root_node, file_name: str) -> CodeGraph:
        graph = CodeGraph()

        # Add the File node itself
        file_node = Node(
            uid=file_name,
            label="File",
            name=file_name.split("/")[-1],
            file=file_name,
            language="java",
        )
        graph.add_node(file_node)

        # Scope stacks (enter on open, pop on close)
        class_stack: list[tuple[str, str]] = []   # (class_name, class_uid)
        method_stack: list[tuple[str, str]] = []  # (method_name, method_uid)
        current_package: list[str] = [""]         # mutable single-item list

        def traverse(node):
            pushed_class = None
            pushed_method = None

            ntype = node.type

            # ── PACKAGE ──────────────────────────────────────────────────────
            if ntype == "package_declaration":
                pkg_name = ""
                for child in node.children:
                    if child.type in ("identifier", "scoped_identifier"):
                        pkg_name = _text(child)
                        break

                if pkg_name:
                    current_package[0] = pkg_name
                    pkg_uid = pkg_name
                    graph.add_node(Node(
                        uid=pkg_uid, label="Package",
                        name=pkg_name, file=file_name,
                    ))
                    graph.add_edge(Edge(
                        source_uid=file_name,
                        target_uid=pkg_uid,
                        relation="IMPORTS",
                    ))

            # ── IMPORT ───────────────────────────────────────────────────────
            elif ntype == "import_declaration":
                imp_name = ""
                for child in node.children:
                    if child.type in ("identifier", "scoped_identifier"):
                        imp_name = _text(child)
                        break
                if imp_name:
                    imp_uid = f"import::{imp_name}"
                    graph.add_node(Node(
                        uid=imp_uid, label="Import",
                        name=imp_name, file=file_name,
                    ))
                    graph.add_edge(Edge(
                        source_uid=file_name,
                        target_uid=imp_uid,
                        relation="IMPORTS",
                    ))

            # ── CLASS ────────────────────────────────────────────────────────
            elif ntype == "class_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    cls_name = _text(name_node)
                    cls_uid = f"{file_name}::{cls_name}"

                    superclass = _get_superclass(node)
                    interfaces = _get_interfaces(node)

                    cls_node = Node(
                        uid=cls_uid,
                        label="Class",
                        name=cls_name,
                        file=file_name,
                        visibility=_get_visibility(node),
                        is_abstract=_is_abstract(node),
                        is_static=_is_static(node),
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        body=_text(node),
                        language="java",
                        embedding=self._embed(_text(node)),
                    )
                    graph.add_node(cls_node)
                    self.symbol_index.add_class(cls_name, cls_uid)

                    # File → Class
                    graph.add_edge(Edge(
                        source_uid=file_name,
                        target_uid=cls_uid,
                        relation="DEFINES",
                    ))

                    # Package → Class
                    pkg = current_package[0]
                    if pkg:
                        graph.add_edge(Edge(
                            source_uid=pkg,
                            target_uid=cls_uid,
                            relation="CONTAINS",
                        ))

                    # Inheritance: Class → superclass  (resolved by name later)
                    if superclass:
                        # Target uid will be resolved after full extraction;
                        # store as a provisional Edge using the raw class name as target_uid.
                        # The graph builder tolerates missing targets gracefully.
                        super_uid = self.symbol_index.resolve_class(superclass) or f"unresolved::{superclass}"
                        graph.add_edge(Edge(
                            source_uid=cls_uid,
                            target_uid=super_uid,
                            relation="INHERITS_FROM",
                        ))

                    # Implements — resolve via index; fallback to unresolved:: for
                    # cross-file interfaces (resolved later by InheritanceResolver)
                    for iface in interfaces:
                        iface_uid = (
                            self.symbol_index.resolve_class(iface)
                            or f"unresolved::{iface}"
                        )
                        graph.add_edge(Edge(
                            source_uid=cls_uid,
                            target_uid=iface_uid,
                            relation="IMPLEMENTS",
                        ))

                    class_stack.append((cls_name, cls_uid))
                    pushed_class = (cls_name, cls_uid)

            # ── INTERFACE ────────────────────────────────────────────────────
            elif ntype == "interface_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    iface_name = _text(name_node)
                    iface_uid = f"{file_name}::{iface_name}"
                    graph.add_node(Node(
                        uid=iface_uid,
                        label="Interface",
                        name=iface_name,
                        file=file_name,
                        visibility=_get_visibility(node),
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        language="java",
                        embedding=self._embed(iface_name),
                    ))
                    graph.add_edge(Edge(
                        source_uid=file_name,
                        target_uid=iface_uid,
                        relation="DEFINES",
                    ))

                    class_stack.append((iface_name, iface_uid))
                    pushed_class = (iface_name, iface_uid)

            # ── METHOD ───────────────────────────────────────────────────────
            elif ntype == "method_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    method_name = _text(name_node)
                    ret_type = _get_return_type(node)
                    params_sig = _get_params_signature(node)
                    signature = f"{ret_type} {method_name}{params_sig}"

                    # Qualified uid: file::Class::method (or file::method if top-level)
                    if class_stack:
                        parent_cls_name, parent_cls_uid = class_stack[-1]
                        method_uid = f"{parent_cls_uid}::{method_name}"
                        qualified = f"{parent_cls_name}.{method_name}"
                    else:
                        method_uid = f"{file_name}::{method_name}"
                        qualified = method_name

                    method_node_obj = Node(
                        uid=method_uid,
                        label="Function",
                        name=method_name,
                        file=file_name,
                        qualified_name=qualified,
                        signature=signature,
                        return_type=ret_type,
                        visibility=_get_visibility(node),
                        is_static=_is_static(node),
                        is_abstract=_is_abstract(node),
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        body=_text(node),
                        language="java",
                        embedding=self._embed(_text(node)),
                    )
                    graph.add_node(method_node_obj)
                    self.symbol_index.add_function(method_name, method_uid)

                    # Class → Method edge
                    if class_stack:
                        _, parent_cls_uid = class_stack[-1]
                        graph.add_edge(Edge(
                            source_uid=parent_cls_uid,
                            target_uid=method_uid,
                            relation="HAS_METHOD",
                        ))
                    else:
                        graph.add_edge(Edge(
                            source_uid=file_name,
                            target_uid=method_uid,
                            relation="DEFINES",
                        ))

                    method_stack.append((method_name, method_uid))
                    pushed_method = (method_name, method_uid)

            # ── CONSTRUCTOR ──────────────────────────────────────────────────
            elif ntype == "constructor_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    ctor_name = _text(name_node)
                    params_sig = _get_params_signature(node)
                    signature = f"{ctor_name}{params_sig}"

                    if class_stack:
                        _, parent_cls_uid = class_stack[-1]
                        ctor_uid = f"{parent_cls_uid}::<init>({ctor_name})"
                        qualified = f"{ctor_name}.<init>"
                    else:
                        ctor_uid = f"{file_name}::<init>({ctor_name})"
                        qualified = ctor_name

                    ctor_node_obj = Node(
                        uid=ctor_uid,
                        label="Function",
                        name=f"<init>",
                        file=file_name,
                        qualified_name=qualified,
                        signature=signature,
                        return_type="void",
                        visibility=_get_visibility(node),
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        body=_text(node),
                        language="java",
                        embedding=self._embed(_text(node)),
                    )
                    graph.add_node(ctor_node_obj)
                    self.symbol_index.add_function(f"<init>", ctor_uid)

                    if class_stack:
                        _, parent_cls_uid = class_stack[-1]
                        graph.add_edge(Edge(
                            source_uid=parent_cls_uid,
                            target_uid=ctor_uid,
                            relation="HAS_METHOD",
                        ))

                    method_stack.append((ctor_name, ctor_uid))
                    pushed_method = (ctor_name, ctor_uid)

            # ── ENUM ─────────────────────────────────────────────────────────
            elif ntype == "enum_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    enum_name = _text(name_node)
                    enum_uid = f"{file_name}::{enum_name}"

                    # Collect constant names from enum_body before recursing
                    constants = []
                    for child in node.children:
                        if child.type == "enum_body":
                            for body_child in child.children:
                                if body_child.type == "enum_constant":
                                    cname = body_child.child_by_field_name("name")
                                    if cname:
                                        constants.append(_text(cname))

                    graph.add_node(Node(
                        uid=enum_uid,
                        label="Enum",
                        name=enum_name,
                        file=file_name,
                        visibility=_get_visibility(node),
                        # signature reused to store comma-separated constant names
                        signature=", ".join(constants),
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        body=_text(node),
                        language="java",
                        embedding=self._embed(
                            f"enum {enum_name} constants: {', '.join(constants)}"
                        ),
                    ))
                    self.symbol_index.add_class(enum_name, enum_uid)

                    graph.add_edge(Edge(
                        source_uid=file_name,
                        target_uid=enum_uid,
                        relation="DEFINES",
                    ))
                    pkg = current_package[0]
                    if pkg:
                        graph.add_edge(Edge(
                            source_uid=pkg,
                            target_uid=enum_uid,
                            relation="CONTAINS",
                        ))

                    # Push so methods inside the enum get HAS_METHOD edges
                    class_stack.append((enum_name, enum_uid))
                    pushed_class = (enum_name, enum_uid)

            # ── FIELD ─────────────────────────────────────────────────────────
            elif ntype == "field_declaration" and class_stack:
                type_node = node.child_by_field_name("type")
                field_type = _text(type_node) if type_node else "unknown"
                visibility = _get_visibility(node)
                is_static_field = _is_static(node)
                is_final = "final" in _modifiers_text(node)

                _, parent_uid = class_stack[-1]

                # Java allows multiple declarators: int x, y, z;
                for child in node.children:
                    if child.type == "variable_declarator":
                        fname_node = child.child_by_field_name("name")
                        if fname_node:
                            field_name = _text(fname_node)
                            field_uid = f"{parent_uid}::field::{field_name}"
                            graph.add_node(Node(
                                uid=field_uid,
                                label="Field",
                                name=field_name,
                                file=file_name,
                                return_type=field_type,
                                visibility=visibility,
                                is_static=is_static_field,
                                line_start=node.start_point[0] + 1,
                                language="java",
                                signature=f"{field_type} {field_name}",
                            ))
                            graph.add_edge(Edge(
                                source_uid=parent_uid,
                                target_uid=field_uid,
                                relation="HAS_FIELD",
                            ))

            # ── METHOD CALL ──────────────────────────────────────────────────
            elif ntype == "method_invocation":
                name_node = node.child_by_field_name("name")
                if name_node and method_stack:
                    callee_name = _text(name_node)
                    _, caller_uid = method_stack[-1]
                    graph.add_unresolved_call(UnresolvedCall(
                        caller_uid=caller_uid,
                        callee_name=callee_name,
                        caller_file=file_name,
                    ))

            # ── Recurse ──────────────────────────────────────────────────────
            for child in node.children:
                traverse(child)

            # Pop scope on exit
            if pushed_class:
                if class_stack and class_stack[-1] == pushed_class:
                    class_stack.pop()
            if pushed_method:
                if method_stack and method_stack[-1] == pushed_method:
                    method_stack.pop()

        traverse(root_node)
        return graph
