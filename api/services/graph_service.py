"""
GraphService — queries Neo4j to produce graph data for the frontend visualiser
and the scan-results panel.

All methods return plain Python dicts/lists (no Neo4j driver objects) so they
can be serialised directly into Pydantic response models.

Design notes:
  - Nodes are capped at `node_limit` (default 200) ordered by impact_score DESC
    to keep the front-end graph manageable while showing the most important code.
  - Edges are collected only for the returned set of nodes (no dangling edges).
  - Every Cypher query is wrapped in try/except; partial results are preferred
    over a hard failure so the UI always has something to show.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class GraphService:
    """Wraps Neo4jClient for graph visualisation and scan-results queries."""

    def __init__(self, neo4j_client) -> None:
        self._db = neo4j_client

    # ── Graph visualisation ───────────────────────────────────────────────────

    # Every label the extraction pipeline can produce
    ALL_LABELS = [
        "Function", "Class", "Struct", "Enum", "Interface",
        "File", "Package", "Namespace", "ExternalFunction",
        "Field", "Import", "Include", "Tag",
    ]

    def get_graph_data(
        self,
        node_limit: int = 200,
        include_labels: Optional[list[str]] = None,
        min_impact_score: float = 0.0,
        bugs_only: bool = False,
    ) -> dict[str, Any]:
        """
        Return nodes + edges suitable for the frontend graph renderer.

        Args:
            node_limit        : max number of nodes (ordered by impact_score DESC)
            include_labels    : which node labels to fetch (default: all code entity types)
            min_impact_score  : filter out low-impact nodes
            bugs_only         : if True, return only buggy nodes and their call-neighbours

        Returns:
            {"nodes": [...], "edges": [...], "stats": {...}}
        """
        if include_labels is None:
            include_labels = self.ALL_LABELS

        nodes = self._fetch_nodes(node_limit, include_labels, min_impact_score, bugs_only)
        if not nodes:
            return {"nodes": [], "edges": [], "stats": {"total_nodes": 0, "total_edges": 0}}

        node_ids = {n["id"] for n in nodes}
        edges = self._fetch_edges(node_ids)

        stats = self._compute_stats(nodes, edges)
        return {"nodes": nodes, "edges": edges, "stats": stats}

    def _fetch_nodes(
        self,
        limit: int,
        labels: list[str],
        min_impact: float,
        bugs_only: bool,
    ) -> list[dict]:
        label_filter = " OR ".join(f"n:{lbl}" for lbl in labels)
        bug_clause   = "AND n.is_buggy = true" if bugs_only else ""

        query = f"""
            MATCH (n)
            WHERE ({label_filter})
              AND coalesce(n.impact_score, 0) >= $min_impact
              {bug_clause}
            RETURN
                n.uid           AS id,
                [x IN labels(n) WHERE x <> 'CodeEntity'][0] AS label,
                n.name          AS name,
                n.file          AS file,
                n.summary       AS summary,
                n.layer         AS layer,
                coalesce(n.impact_score, 0)   AS impact_score,
                coalesce(n.is_entry_point, false) AS is_entry_point,
                coalesce(n.is_buggy, false)   AS is_buggy,
                n.severity      AS severity,
                n.bug_confidence AS bug_confidence,
                coalesce(n.fan_in,  0)  AS fan_in,
                coalesce(n.fan_out, 0)  AS fan_out,
                coalesce(n.tags, [])    AS tags,
                n.language      AS language
            ORDER BY n.impact_score DESC
            LIMIT $limit
        """
        try:
            rows = self._db.run_query(query, {"min_impact": min_impact, "limit": limit})
            return [_normalize_node(r) for r in rows]
        except Exception as exc:
            logger.error("Failed to fetch graph nodes: %s", exc)
            return []

    def _fetch_edges(self, node_ids: set[str]) -> list[dict]:
        """Fetch all edges where BOTH endpoints are in node_ids."""
        query = """
            MATCH (a)-[r]->(b)
            WHERE a.uid IN $ids AND b.uid IN $ids
              AND type(r) IN [
                'CALLS', 'INHERITS_FROM', 'IMPLEMENTS', 'SIMILAR_TO',
                'DEFINES', 'CONTAINS', 'HAS_METHOD', 'HAS_FIELD',
                'IMPORTS', 'INCLUDES', 'TAGGED_WITH'
              ]
            RETURN a.uid AS source, b.uid AS target, type(r) AS relation
        """
        try:
            rows = self._db.run_query(query, {"ids": list(node_ids)})
            # Deduplicate by (source, target, relation)
            seen: set[tuple] = set()
            edges: list[dict] = []
            for r in rows:
                key = (r["source"], r["target"], r["relation"])
                if key not in seen:
                    seen.add(key)
                    edges.append({"source": r["source"], "target": r["target"],
                                  "relation": r["relation"]})
            return edges
        except Exception as exc:
            logger.error("Failed to fetch graph edges: %s", exc)
            return []

    def _compute_stats(self, nodes: list[dict], edges: list[dict]) -> dict:
        buggy     = [n for n in nodes if n.get("is_buggy")]
        entry_pts = [n for n in nodes if n.get("is_entry_point")]
        sev_counts: dict[str, int] = {}
        for n in buggy:
            sev = n.get("severity") or "UNKNOWN"
            sev_counts[sev] = sev_counts.get(sev, 0) + 1

        return {
            "total_nodes":    len(nodes),
            "total_edges":    len(edges),
            "buggy_nodes":    len(buggy),
            "entry_points":   len(entry_pts),
            "severity_counts": sev_counts,
        }

    # ── Scan results ──────────────────────────────────────────────────────────

    def get_scan_results(
        self,
        severity_filter: Optional[str] = None,
        limit: int = 500,
    ) -> dict[str, Any]:
        """
        Return all vulnerability annotations from Neo4j.

        Args:
            severity_filter : optional — "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
            limit           : max number of results

        Returns:
            {"total_functions": N, "bugs_found": M, ..., "vulnerabilities": [...]}
        """
        sev_clause = "AND f.severity = $severity" if severity_filter else ""
        query = f"""
            MATCH (f:Function:CodeEntity)
            WHERE f.is_buggy = true
              {sev_clause}
            RETURN
                f.uid            AS uid,
                f.name           AS name,
                f.file           AS file,
                f.severity       AS severity,
                coalesce(f.bug_confidence, 0.0) AS confidence,
                f.summary        AS summary,
                f.layer          AS layer,
                coalesce(f.impact_score, 0)     AS impact_score,
                coalesce(f.fan_in, 0)           AS fan_in,
                f.line_start     AS line_start,
                f.body           AS body,
                f.bug_reason     AS bug_reason
            ORDER BY
                CASE f.severity
                    WHEN 'CRITICAL' THEN 1
                    WHEN 'HIGH'     THEN 2
                    WHEN 'MEDIUM'   THEN 3
                    WHEN 'LOW'      THEN 4
                    ELSE 5
                END,
                f.impact_score DESC
            LIMIT $limit
        """
        params: dict = {"limit": limit}
        if severity_filter:
            params["severity"] = severity_filter.upper()

        try:
            rows = self._db.run_query(query, params)
        except Exception as exc:
            logger.error("Failed to fetch scan results: %s", exc)
            rows = []

        # Count totals from Neo4j for accuracy
        totals = self._fetch_scan_totals()

        return {
            "total_functions": totals.get("total", 0),
            "bugs_found":      totals.get("bugs",  0),
            "critical":        totals.get("CRITICAL", 0),
            "high":            totals.get("HIGH",     0),
            "medium":          totals.get("MEDIUM",   0),
            "low":             totals.get("LOW",      0),
            "vulnerabilities": [_normalize_vuln(r) for r in rows],
        }

    def _fetch_scan_totals(self) -> dict:
        query = """
            MATCH (f:Function:CodeEntity)
            RETURN
                count(f)                              AS total,
                sum(CASE WHEN f.is_buggy = true THEN 1 ELSE 0 END) AS bugs,
                sum(CASE WHEN f.severity = 'CRITICAL' THEN 1 ELSE 0 END) AS CRITICAL,
                sum(CASE WHEN f.severity = 'HIGH'     THEN 1 ELSE 0 END) AS HIGH,
                sum(CASE WHEN f.severity = 'MEDIUM'   THEN 1 ELSE 0 END) AS MEDIUM,
                sum(CASE WHEN f.severity = 'LOW'      THEN 1 ELSE 0 END) AS LOW
        """
        try:
            rows = self._db.run_query(query)
            return rows[0] if rows else {}
        except Exception as exc:
            logger.error("Failed to fetch scan totals: %s", exc)
            return {}

    # ── Graph overview stats ──────────────────────────────────────────────────

    def get_overview_stats(self) -> dict[str, Any]:
        """
        Lightweight summary of the graph for the frontend dashboard header.
        Returns node/edge counts, bug totals, and top entry points.
        """
        queries = {
            "node_count": "MATCH (n:CodeEntity) RETURN count(n) AS n",
            "edge_count": "MATCH ()-[r]->() RETURN count(r) AS n",
            "bug_count":  "MATCH (f:Function) WHERE f.is_buggy = true RETURN count(f) AS n",
            "file_count": "MATCH (f:File:CodeEntity) RETURN count(f) AS n",
        }
        result: dict[str, Any] = {}
        for key, q in queries.items():
            try:
                rows = self._db.run_query(q)
                result[key] = rows[0]["n"] if rows else 0
            except Exception as exc:
                logger.warning("get_overview_stats query '%s' failed: %s", key, exc)
                result[key] = 0

        return result


# ── Normalisers ───────────────────────────────────────────────────────────────

def _normalize_node(row: dict) -> dict:
    return {
        "id":            row.get("id") or "",
        "label":         row.get("label") or "Function",
        "name":          row.get("name") or "",
        "file":          row.get("file"),
        "summary":       row.get("summary"),
        "layer":         row.get("layer"),
        "impact_score":  float(row.get("impact_score") or 0),
        "is_entry_point": bool(row.get("is_entry_point")),
        "is_buggy":      bool(row.get("is_buggy")),
        "severity":      row.get("severity"),
        "bug_confidence": row.get("bug_confidence"),
        "fan_in":        int(row.get("fan_in") or 0),
        "fan_out":       int(row.get("fan_out") or 0),
        "tags":          row.get("tags") or [],
        "language":      row.get("language"),
    }


def _normalize_vuln(row: dict) -> dict:
    return {
        "uid":          row.get("uid") or "",
        "name":         row.get("name") or "",
        "file":         row.get("file"),
        "severity":     row.get("severity") or "UNKNOWN",
        "confidence":   float(row.get("confidence") or 0),
        "summary":      row.get("summary"),
        "layer":        row.get("layer"),
        "impact_score": float(row.get("impact_score") or 0),
        "fan_in":       int(row.get("fan_in") or 0),
        "line_start":   row.get("line_start"),
        "body":         row.get("body") or None,
        "bug_reason":   row.get("bug_reason") or None,
    }
