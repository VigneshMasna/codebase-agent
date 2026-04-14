"""
Neo4j graph builder — production-level.

Root-cause fix for "nodes inserted but zero relationships" bug:
  Every node gets a secondary label :CodeEntity in addition to its primary label.
  Constraints are created on BOTH the primary label and :CodeEntity.
  All MATCH queries in edge insertion use MATCH (a:CodeEntity {uid: ...}) which
  hits the :CodeEntity constraint index reliably instead of doing a label-free
  full-node-scan that silently returns 0 rows on Neo4j Aura.

Node labels stored (primary + secondary :CodeEntity on all):
  File, Package, Import, Namespace, Class, Interface, Struct,
  Function, Include, ExternalFunction, Tag

Relationship types stored:
  DEFINES, IMPORTS, INCLUDES, CONTAINS, HAS_METHOD,
  INHERITS_FROM, IMPLEMENTS, CALLS, TAGGED_WITH, SIMILAR_TO
"""
from __future__ import annotations

from collections import defaultdict

from extraction.symbol_models import CodeGraph, Edge, Node


_NODE_LABELS = [
    "File", "Package", "Import", "Namespace",
    "Class", "Interface", "Struct", "Enum",
    "Function", "Field", "Include", "ExternalFunction", "Tag",
    "CodeEntity",   # secondary label — added to ALL nodes for indexed cross-label MATCH
]

_RELATION_TYPES = [
    "DEFINES", "IMPORTS", "INCLUDES", "CONTAINS",
    "HAS_METHOD", "HAS_FIELD", "INHERITS_FROM", "IMPLEMENTS",
    "CALLS", "TAGGED_WITH", "SIMILAR_TO",
]


class Neo4jGraphBuilder:

    def __init__(self, client) -> None:
        self.client = client

    # ── Setup ─────────────────────────────────────────────────────────────────

    def create_constraints(self) -> None:
        """
        Create uniqueness constraints on uid for every primary label AND
        for :CodeEntity (the shared secondary label used in MATCH queries).
        Safe to call multiple times — uses IF NOT EXISTS.
        """
        for label in _NODE_LABELS:
            try:
                self.client.run_query(
                    f"CREATE CONSTRAINT IF NOT EXISTS "
                    f"FOR (n:{label}) REQUIRE n.uid IS UNIQUE"
                )
            except Exception:
                try:
                    self.client.run_query(
                        f"CREATE CONSTRAINT ON (n:{label}) ASSERT n.uid IS UNIQUE"
                    )
                except Exception:
                    pass  # constraint already exists

    def clear_graph(self) -> None:
        self.client.run_query("MATCH (n) DETACH DELETE n")

    # ── Main entry point ──────────────────────────────────────────────────────

    def insert_graph(self, graph: CodeGraph) -> dict:
        nodes_created  = self._insert_nodes(graph.get_nodes())
        tag_stats      = self._insert_tags(graph.get_nodes())
        edges_created  = self._insert_edges(graph.edges)
        edges_created += self._insert_tagged_with_edges(graph.get_nodes())

        # ── Recompute metrics from actual graph edges ─────────────────────────
        # Must run AFTER edges are committed so CALLS relationships exist.
        # This is more accurate than the in-memory pre-push computation.
        self.recompute_metrics_from_graph()

        # ── Verification: query Neo4j for actual counts ───────────────────────
        actual = self._verify()
        print(f"\n  Neo4j verification:")
        print(f"    Nodes in DB     : {actual['nodes']}")
        print(f"    Relationships   : {actual['relationships']}")

        return {
            "nodes_created":  nodes_created + tag_stats["tags_created"],
            "edges_created":  edges_created,
            "tags_created":   tag_stats["tags_created"],
            "db_nodes":       actual["nodes"],
            "db_relations":   actual["relationships"],
        }

    # ── Node insertion ────────────────────────────────────────────────────────

    def _insert_nodes(self, nodes: list[Node]) -> int:
        by_label: dict[str, list[Node]] = defaultdict(list)
        for n in nodes:
            by_label[n.label].append(n)

        total = 0
        for label, label_nodes in by_label.items():
            params_list = [_node_to_params(n) for n in label_nodes]

            # SET n:CodeEntity adds the shared secondary label used for MATCH in edges
            query = f"""
            UNWIND $nodes AS p
            MERGE (n:{label} {{uid: p.uid}})
            SET n:CodeEntity,
                n.label             = p.label,
                n.name              = p.name,
                n.file              = p.file,
                n.qualified_name    = p.qualified_name,
                n.signature         = p.signature,
                n.return_type       = p.return_type,
                n.visibility        = p.visibility,
                n.is_static         = p.is_static,
                n.is_virtual        = p.is_virtual,
                n.is_abstract       = p.is_abstract,
                n.is_override       = p.is_override,
                n.line_start        = p.line_start,
                n.line_end          = p.line_end,
                n.body              = p.body,
                n.language          = p.language,
                n.summary           = p.summary,
                n.core_functionality = p.core_functionality,
                n.tags              = p.tags,
                n.layer             = p.layer,
                n.fan_in            = p.fan_in,
                n.fan_out           = p.fan_out,
                n.is_entry_point    = p.is_entry_point,
                n.is_leaf           = p.is_leaf,
                n.is_recursive      = p.is_recursive,
                n.impact_score      = p.impact_score,
                n.embedding         = p.embedding
            """
            self.client.run_query(query, {"nodes": params_list})
            total += len(params_list)
            print(f"  Inserted {len(params_list):>4} {label} nodes")

        return total

    # ── Tag nodes ─────────────────────────────────────────────────────────────

    def _insert_tags(self, nodes: list[Node]) -> dict:
        all_tags: set[str] = set()
        for n in nodes:
            for tag in (n.tags or []):
                if tag:
                    all_tags.add(tag.lower().strip())

        if not all_tags:
            return {"tags_created": 0}

        tag_params = [
            {"uid": f"tag::{tag}", "name": tag}
            for tag in sorted(all_tags)
        ]

        query = """
        UNWIND $tags AS t
        MERGE (tag:Tag:CodeEntity {uid: t.uid})
        SET tag.name = t.name
        """
        self.client.run_query(query, {"tags": tag_params})
        print(f"  Inserted {len(tag_params):>4} Tag nodes")
        return {"tags_created": len(tag_params)}

    def _insert_tagged_with_edges(self, nodes: list[Node]) -> int:
        pairs = []
        for n in nodes:
            if n.tags and n.label in ("Function", "Class", "Struct"):
                for tag in n.tags:
                    if tag:
                        pairs.append({
                            "source_uid": n.uid,
                            "target_uid": f"tag::{tag.lower().strip()}",
                        })
        if not pairs:
            return 0

        # Both MATCH use :CodeEntity index — guaranteed to find nodes
        query = """
        UNWIND $pairs AS p
        MATCH (src:CodeEntity {uid: p.source_uid})
        MATCH (tag:CodeEntity {uid: p.target_uid})
        MERGE (src)-[r:TAGGED_WITH]->(tag)
        ON CREATE SET r._new = true
        """
        self.client.run_query(query, {"pairs": pairs})
        created = self._count_new_relation("TAGGED_WITH")
        self.client.run_query(
            "MATCH ()-[r:TAGGED_WITH]->() WHERE r._new = true REMOVE r._new"
        )
        print(f"  Inserted {created:>4} TAGGED_WITH edges  (attempted {len(pairs)})")
        return created

    # ── Structural + similarity edges ─────────────────────────────────────────

    def _insert_edges(self, edges: list[Edge]) -> int:
        by_relation: dict[str, list[Edge]] = defaultdict(list)
        for e in edges:
            by_relation[e.relation].append(e)

        total = 0
        for relation, rel_edges in by_relation.items():
            valid = [
                {"source_uid": e.source_uid, "target_uid": e.target_uid}
                for e in rel_edges
                if not e.target_uid.startswith("unresolved::")
            ]
            if not valid:
                continue

            # Use :CodeEntity on BOTH sides — uses the constraint index,
            # never falls back to a full-node-scan that silently returns 0 rows.
            # ON CREATE SET r._new = true allows counting only newly created edges.
            query = f"""
            UNWIND $pairs AS p
            MATCH (a:CodeEntity {{uid: p.source_uid}})
            MATCH (b:CodeEntity {{uid: p.target_uid}})
            MERGE (a)-[r:{relation}]->(b)
            ON CREATE SET r._new = true
            """
            try:
                self.client.run_query(query, {"pairs": valid})
                created = self._count_new_relation(relation)
                # Strip the temporary marker
                self.client.run_query(
                    f"MATCH ()-[r:{relation}]->() WHERE r._new = true REMOVE r._new"
                )
                total += created
                print(f"  Inserted {created:>4} {relation} edges  (attempted {len(valid)})")
            except Exception as exc:
                print(f"  WARNING: {relation} edges failed — {exc}")

        return total

    # ── Post-ingestion metric recomputation ───────────────────────────────────

    def recompute_metrics_from_graph(self) -> None:
        """
        Recompute fan_in, fan_out, impact_score, is_entry_point, and is_leaf
        for all Function nodes directly from CALLS relationships in Neo4j.

        This is called automatically after insert_graph() so the stored values
        always reflect the actual committed graph structure — not the pre-push
        in-memory estimate.

        Both fan_in and fan_out exclude external:: nodes (stdlib / framework
        calls) so the metrics represent coupling within the codebase only.
        """
        print("  Recomputing fan-in/fan-out from committed CALLS edges...")
        query = """
            MATCH (f:Function:CodeEntity)
            OPTIONAL MATCH (caller:CodeEntity)-[:CALLS]->(f)
                WHERE NOT caller.uid STARTS WITH 'external::'
            OPTIONAL MATCH (f)-[:CALLS]->(callee:CodeEntity)
                WHERE NOT callee.uid STARTS WITH 'external::'
            WITH f,
                 count(DISTINCT caller) AS fi,
                 count(DISTINCT callee) AS fo
            SET f.fan_in        = fi,
                f.fan_out       = fo,
                f.impact_score  = round(fi * 2.0 + fo * 1.0, 2),
                f.is_entry_point = (
                    fi = 0
                    AND NOT f.name STARTS WITH '<init>'
                    AND NOT f.name STARTS WITH '~'
                ),
                f.is_leaf = (fo = 0)
        """
        try:
            self.client.run_query(query)
            print("  Metrics recomputed.")
        except Exception as exc:
            print(f"  WARNING: metrics recomputation failed — {exc}")

    # ── Verification ──────────────────────────────────────────────────────────

    def _verify(self) -> dict:
        """Query Neo4j directly for actual node + relationship counts."""
        nodes = self.client.run_query(
            "MATCH (n:CodeEntity) RETURN count(n) AS c"
        )
        rels = self.client.run_query(
            "MATCH ()-[r]->() RETURN count(r) AS c"
        )
        return {
            "nodes":         nodes[0]["c"] if nodes else 0,
            "relationships": rels[0]["c"] if rels else 0,
        }

    def _count_new_relation(self, relation: str) -> int:
        """Count only relationships tagged with _new=true (just created in this batch)."""
        result = self.client.run_query(
            f"MATCH ()-[r:{relation}]->() WHERE r._new = true RETURN count(r) AS c"
        )
        return result[0]["c"] if result else 0

    def _count_relation(self, relation: str) -> int:
        result = self.client.run_query(
            f"MATCH ()-[r:{relation}]->() RETURN count(r) AS c"
        )
        return result[0]["c"] if result else 0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _node_to_params(n: Node) -> dict:
    return {
        "uid":                n.uid,
        "label":              n.label,
        "name":               n.name,
        "file":               n.file,
        "qualified_name":     n.qualified_name,
        "signature":          n.signature,
        "return_type":        n.return_type,
        "visibility":         n.visibility,
        "is_static":          n.is_static,
        "is_virtual":         n.is_virtual,
        "is_abstract":        n.is_abstract,
        "is_override":        n.is_override,
        "line_start":         n.line_start,
        "line_end":           n.line_end,
        "body":               n.body[:4000] if n.body else "",
        "language":           n.language,
        "summary":            n.summary,
        "core_functionality": n.core_functionality,
        "tags":               n.tags if n.tags else [],
        "layer":              n.layer,
        "fan_in":             n.fan_in,
        "fan_out":            n.fan_out,
        "is_entry_point":     n.is_entry_point,
        "is_leaf":            n.is_leaf,
        "is_recursive":       n.is_recursive,
        "impact_score":       n.impact_score,
        "embedding":          n.embedding if n.embedding else [],
    }
