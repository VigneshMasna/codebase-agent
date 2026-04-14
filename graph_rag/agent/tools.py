"""
GraphTools — 6 tool implementations that query the Neo4j knowledge graph.

Each method returns a formatted string (not raw dicts) so the LLM can directly
reason over the result without any further parsing.

Tools:
  1. search_by_concept   — semantic search via tags + embedding similarity
  2. get_node_details    — full properties of a node by name or UID
  3. trace_callers       — who calls this function (N hops upstream)
  4. trace_callees       — what this function calls (N hops downstream)
  5. get_impact_analysis — blast radius: callers, callees, metrics, similar
  6. run_cypher          — direct read-only Cypher for structural questions
"""
from __future__ import annotations

import re

import numpy as np

from graph.neo4j_client import Neo4jClient
from embedding.embedding_generator import EmbeddingGenerator

# Write-op keywords blocked in run_cypher
_WRITE_RE = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP)\b", re.IGNORECASE
)


class GraphTools:

    def __init__(self, client: Neo4jClient, embedder: EmbeddingGenerator) -> None:
        self.client  = client
        self.embedder = embedder

    # ── 1. search_by_concept ──────────────────────────────────────────────────

    def search_by_concept(self, query: str, top_k: int = 5) -> str:
        """
        Two-phase semantic search:
          Phase 1 — tag-based (fast exact/contains match against Tag nodes)
          Phase 2 — embedding cosine similarity (semantic, Python-side)
        Results are merged and deduplicated.
        """
        top_k = max(1, min(top_k, 15))
        found: dict[str, dict] = {}  # uid -> node dict

        # ── Phase 1: tag search ────────────────────────────────────────────
        _STOPWORDS = {
            "all", "and", "the", "for", "are", "this", "that", "with",
            "find", "show", "list", "what", "does", "code", "related",
            "functions", "function", "handling", "related", "give", "me",
            "how", "any", "have", "which",
        }
        keywords = [
            w.lower() for w in query.split()
            if len(w) > 3 and w.lower() not in _STOPWORDS
        ]
        for kw in keywords[:4]:  # limit to 4 keywords to avoid slow queries
            rows = self.client.run_query(
                """
                MATCH (t:Tag)<-[:TAGGED_WITH]-(n:CodeEntity)
                WHERE toLower(t.name) CONTAINS $kw
                RETURN n.uid AS uid, n.name AS name,
                       [l IN labels(n) WHERE l <> 'CodeEntity'][0] AS label,
                       n.summary AS summary, n.core_functionality AS core_functionality,
                       n.file AS file, n.layer AS layer,
                       n.impact_score AS impact_score,
                       collect(t.name) AS tags
                ORDER BY coalesce(n.impact_score, 0) DESC
                LIMIT 10
                """,
                {"kw": kw},
            )
            for r in rows:
                if r["uid"] not in found:
                    r["_score"] = 1.0  # tag match = high confidence
                    found[r["uid"]] = r

        # ── Phase 2: embedding similarity ─────────────────────────────────
        try:
            q_vec = self.embedder.generate(query)
            if q_vec:
                rows = self.client.run_query(
                    """
                    MATCH (n:CodeEntity)
                    WHERE n.embedding IS NOT NULL
                      AND (n:Function OR n:Class OR n:Struct OR n:Enum)
                    RETURN n.uid AS uid, n.name AS name,
                           [l IN labels(n) WHERE l <> 'CodeEntity'][0] AS label,
                           n.embedding AS embedding,
                           n.summary AS summary,
                           n.core_functionality AS core_functionality,
                           n.file AS file, n.layer AS layer,
                           n.impact_score AS impact_score
                    LIMIT 200
                    """
                )
                scored = []
                for r in rows:
                    emb = r.get("embedding")
                    if emb:
                        sim = _cosine_sim(q_vec, emb)
                        scored.append((sim, r))
                scored.sort(key=lambda x: -x[0])
                for sim, r in scored[:top_k]:
                    if sim > 0.52 and r["uid"] not in found:
                        r["_score"] = round(sim, 3)
                        found[r["uid"]] = r
        except Exception:
            pass  # embedding search is best-effort

        if not found:
            return f"No nodes found matching concept: '{query}'"

        # Sort by impact_score, then _score
        results = sorted(
            found.values(),
            key=lambda n: (n.get("impact_score") or 0, n.get("_score") or 0),
            reverse=True,
        )[:top_k]

        lines = [f"Search results for '{query}' ({len(results)} found):\n"]
        for i, n in enumerate(results, 1):
            lines.append(f"{i}. [{n['label']}] {n['name']}")
            lines.append(f"   File  : {n.get('file', '?')}")
            lines.append(f"   Layer : {n.get('layer') or 'unknown'}")
            if n.get("core_functionality"):
                lines.append(f"   Core  : {n['core_functionality']}")
            elif n.get("summary"):
                lines.append(f"   About : {n['summary'][:120]}")
            lines.append("")

        return "\n".join(lines)

    # ── 7. find_vulnerabilities ───────────────────────────────────────────────

    def find_vulnerabilities(self, severity_filter: str = "") -> str:
        """
        Query Neo4j for all Function nodes flagged as buggy.
        Optionally filter by severity (CRITICAL / HIGH / MEDIUM / LOW).
        Results are sorted by impact_score so the most dangerous bugs appear first.
        """
        severity_filter = severity_filter.strip().upper()
        valid_severities = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}

        if severity_filter and severity_filter in valid_severities:
            rows = self.client.run_query(
                """
                MATCH (f:Function)
                WHERE f.is_buggy = true AND f.severity = $sev
                RETURN f.name AS name, f.file AS file, f.layer AS layer,
                       f.severity AS severity, f.bug_confidence AS confidence,
                       f.impact_score AS impact_score, f.fan_in AS fan_in,
                       f.summary AS summary
                ORDER BY coalesce(f.impact_score, 0) DESC
                LIMIT 30
                """,
                {"sev": severity_filter},
            )
            header = f"Vulnerable functions with severity={severity_filter}"
        else:
            rows = self.client.run_query(
                """
                MATCH (f:Function)
                WHERE f.is_buggy = true
                RETURN f.name AS name, f.file AS file, f.layer AS layer,
                       f.severity AS severity, f.bug_confidence AS confidence,
                       f.impact_score AS impact_score, f.fan_in AS fan_in,
                       f.summary AS summary
                ORDER BY
                    CASE f.severity
                        WHEN 'CRITICAL' THEN 1
                        WHEN 'HIGH'     THEN 2
                        WHEN 'MEDIUM'   THEN 3
                        WHEN 'LOW'      THEN 4
                        ELSE 5
                    END,
                    coalesce(f.impact_score, 0) DESC
                LIMIT 30
                """
            )
            header = "All vulnerable functions"

        if not rows:
            msg = "No vulnerabilities found"
            if severity_filter:
                msg += f" with severity={severity_filter}"
            return msg + ". The codebase appears clean."

        # Summary counts
        by_sev: dict[str, int] = {}
        for r in rows:
            s = r.get("severity") or "UNKNOWN"
            by_sev[s] = by_sev.get(s, 0) + 1

        lines = [f"{header} ({len(rows)} found):\n"]
        summary_parts = [f"{s}={c}" for s, c in sorted(by_sev.items())]
        lines.append(f"  Severity breakdown: {', '.join(summary_parts)}\n")

        for r in rows:
            sev      = r.get("severity") or "?"
            name     = r.get("name") or "?"
            file_    = r.get("file") or "?"
            layer    = r.get("layer") or "unknown"
            impact   = r.get("impact_score") or 0
            fan_in   = r.get("fan_in") or 0
            conf     = r.get("confidence") or 0.0
            summary  = r.get("summary") or ""

            lines.append(f"  [{sev}] {name}()")
            lines.append(f"    File    : {file_}  (layer: {layer})")
            lines.append(f"    Impact  : score={impact}, callers={fan_in}, confidence={conf:.2f}")
            if summary:
                lines.append(f"    Summary : {summary[:120]}")
            lines.append("")

        return "\n".join(lines)

    # ── 8. find_vulnerable_paths ──────────────────────────────────────────────

    def find_vulnerable_paths(self) -> str:
        """
        Traverses the call graph to find every entry point that leads (directly
        or indirectly) to a buggy function. Groups results by entry point and
        lists the vulnerable functions reachable from it, with severity.
        """
        rows = self.client.run_query(
            """
            MATCH (ep:Function)
            WHERE ep.is_entry_point = true
            MATCH path = (ep)-[:CALLS*1..6]->(vuln:Function)
            WHERE vuln.is_buggy = true
            RETURN
                ep.name      AS entry_point,
                ep.file      AS ep_file,
                ep.layer     AS ep_layer,
                ep.impact_score AS ep_impact,
                vuln.name    AS vuln_name,
                vuln.severity AS severity,
                vuln.file    AS vuln_file,
                length(path) AS hops
            ORDER BY
                CASE vuln.severity
                    WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
                    WHEN 'MEDIUM'   THEN 3 WHEN 'LOW'  THEN 4
                    ELSE 5
                END,
                ep.impact_score DESC
            """
        )

        if not rows:
            return (
                "No entry points found that lead to vulnerable code. "
                "Either no vulnerabilities exist or they are unreachable from any entry point."
            )

        # Group by entry point
        grouped: dict[str, dict] = {}
        for r in rows:
            ep = r["entry_point"]
            if ep not in grouped:
                grouped[ep] = {
                    "ep_file":   r.get("ep_file", "?"),
                    "ep_layer":  r.get("ep_layer", "?"),
                    "ep_impact": r.get("ep_impact", 0),
                    "vulns":     [],
                }
            grouped[ep]["vulns"].append({
                "name":     r["vuln_name"],
                "severity": r.get("severity", "?"),
                "file":     r.get("vuln_file", "?"),
                "hops":     r.get("hops", "?"),
            })

        lines = [
            f"Entry points leading to vulnerable code ({len(grouped)} found):\n"
        ]
        for ep_name, info in grouped.items():
            lines.append(f"  ENTRY POINT: {ep_name}()")
            lines.append(f"    File   : {info['ep_file']}  (layer: {info['ep_layer']})")
            lines.append(f"    Impact : {info['ep_impact']}")
            lines.append(f"    Reaches {len(info['vulns'])} vulnerable function(s):")
            for v in info["vulns"]:
                lines.append(
                    f"      [{v['severity']}] {v['name']}()  "
                    f"in {v['file']}  ({v['hops']} hop(s) away)"
                )
            lines.append("")

        return "\n".join(lines)

    # ── 2. get_node_details ───────────────────────────────────────────────────

    def get_node_details(self, name_or_uid: str) -> str:
        """
        Returns full properties for a node identified by name or UID.
        Returns up to 3 matches if the name is ambiguous.
        """
        rows = self.client.run_query(
            """
            MATCH (n:CodeEntity)
            WHERE n.name = $val OR n.uid = $val
            OPTIONAL MATCH (n)-[:TAGGED_WITH]->(tag:Tag)
            WITH n, collect(tag.name) AS tags
            RETURN n.uid AS uid, n.name AS name,
                   [l IN labels(n) WHERE l <> 'CodeEntity'][0] AS label,
                   n.file AS file, n.language AS language,
                   n.signature AS signature, n.return_type AS return_type,
                   n.visibility AS visibility, n.is_static AS is_static,
                   n.is_virtual AS is_virtual, n.is_abstract AS is_abstract,
                   n.is_recursive AS is_recursive,
                   n.layer AS layer,
                   n.summary AS summary,
                   n.core_functionality AS core_functionality,
                   n.fan_in AS fan_in, n.fan_out AS fan_out,
                   n.impact_score AS impact_score,
                   n.is_entry_point AS is_entry_point, n.is_leaf AS is_leaf,
                   n.line_start AS line_start, n.line_end AS line_end,
                   n.body AS body,
                   n.is_buggy AS is_buggy, n.severity AS severity,
                   n.bug_confidence AS bug_confidence,
                   tags
            LIMIT 3
            """,
            {"val": name_or_uid},
        )

        if not rows:
            # Try fuzzy name match to suggest alternatives
            keyword = name_or_uid.lower().replace(" ", "")
            similar = self.client.run_query(
                """
                MATCH (n:CodeEntity)
                WHERE n:Function OR n:Class OR n:Struct OR n:Enum
                  AND toLower(n.name) CONTAINS $kw
                RETURN n.name AS name,
                       [l IN labels(n) WHERE l <> 'CodeEntity'][0] AS label
                LIMIT 5
                """,
                {"kw": keyword},
            )
            if similar:
                suggestions = ", ".join(
                    f"{r['name']} ({r['label']})" for r in similar
                )
                return (
                    f"No exact match for '{name_or_uid}'. "
                    f"Did you mean one of these? {suggestions}"
                )
            return f"No node found with name or UID: '{name_or_uid}'"

        sections = []
        for r in rows:
            body = r.get("body") or ""
            if len(body) > 1500:
                body = body[:1500] + "\n... [truncated]"

            flags = []
            if r.get("is_entry_point"): flags.append("ENTRY_POINT")
            if r.get("is_leaf"):        flags.append("LEAF")
            if r.get("is_recursive"):   flags.append("RECURSIVE")
            if r.get("is_virtual"):     flags.append("VIRTUAL")
            if r.get("is_abstract"):    flags.append("ABSTRACT")
            if r.get("is_static"):      flags.append("STATIC")

            lines = [
                f"{'-'*60}",
                f"[{r['label']}] {r['name']}",
                f"  UID       : {r['uid']}",
                f"  File      : {r.get('file', '?')}  (lines {r.get('line_start','?')}–{r.get('line_end','?')})",
                f"  Language  : {r.get('language', '?')}",
            ]
            if r.get("signature"):
                lines.append(f"  Signature : {r['signature']}")
            if r.get("layer"):
                lines.append(f"  Layer     : {r['layer']}")
            if r.get("visibility"):
                lines.append(f"  Visibility: {r['visibility']}")
            if flags:
                lines.append(f"  Flags     : {', '.join(flags)}")
            # Bug detection results (if scan has been run)
            if r.get("is_buggy"):
                lines.append(f"  *** BUG DETECTED: severity={r.get('severity','?')}, "
                             f"confidence={r.get('bug_confidence', 0):.2f} ***")
            if r.get("summary"):
                lines.append(f"  Summary   : {r['summary']}")
            if r.get("core_functionality"):
                lines.append(f"  Core      : {r['core_functionality']}")
            if r.get("tags"):
                lines.append(f"  Tags      : {', '.join(r['tags'])}")

            fan_in  = r.get("fan_in")  or 0
            fan_out = r.get("fan_out") or 0
            impact  = r.get("impact_score") or 0
            if fan_in or fan_out or impact:
                lines.append(
                    f"  Metrics   : fan_in={fan_in}, fan_out={fan_out}, impact={impact}"
                )
            if body:
                lines.append(f"\n  Source:\n{_indent(body, 4)}")

            sections.append("\n".join(lines))

        return "\n\n".join(sections)

    # ── 3. trace_callers ──────────────────────────────────────────────────────

    def trace_callers(self, function_name: str, depth: int = 2) -> str:
        """
        Find all functions that directly or transitively call `function_name`.
        Depth controls how many hops upstream to traverse (max 4).
        """
        depth = max(1, min(int(depth), 4))

        # Find the function first to confirm it exists
        exists = self.client.run_query(
            "MATCH (n:CodeEntity {name: $name}) RETURN n.uid AS uid LIMIT 1",
            {"name": function_name},
        )
        if not exists:
            return f"Function '{function_name}' not found in graph."

        rows = self.client.run_query(
            f"""
            MATCH path = (caller:CodeEntity)-[:CALLS*1..{depth}]->(n:CodeEntity)
            WHERE n.name = $name
            RETURN [node IN nodes(path) | node.name] AS chain,
                   length(path) AS hops
            ORDER BY hops
            LIMIT 30
            """,
            {"name": function_name},
        )

        if not rows:
            return f"No callers found for '{function_name}' (depth={depth}). It may be an entry point."

        # Group by hop depth
        by_depth: dict[int, list[str]] = {}
        for r in rows:
            h = r["hops"]
            by_depth.setdefault(h, [])
            chain = r["chain"]
            # chain[-1] is the target function; everything before is the caller chain
            caller_path = " -> ".join(chain)
            if caller_path not in by_depth[h]:
                by_depth[h].append(caller_path)

        lines = [f"Callers of '{function_name}' (depth={depth}):\n"]
        for h in sorted(by_depth):
            hop_label = f"{h}-hop {'callers' if h == 1 else 'chains'}"
            lines.append(f"  {hop_label}:")
            for chain in by_depth[h]:
                lines.append(f"    • {chain}")
            lines.append("")

        return "\n".join(lines)

    # ── 4. trace_callees ──────────────────────────────────────────────────────

    def trace_callees(self, function_name: str, depth: int = 2) -> str:
        """
        Trace what `function_name` calls, and what those functions call.
        Depth controls how many hops downstream (max 4).
        """
        depth = max(1, min(int(depth), 4))

        exists = self.client.run_query(
            "MATCH (n:CodeEntity {name: $name}) RETURN n.uid AS uid LIMIT 1",
            {"name": function_name},
        )
        if not exists:
            return f"Function '{function_name}' not found in graph."

        rows = self.client.run_query(
            f"""
            MATCH path = (n:CodeEntity)-[:CALLS*1..{depth}]->(callee:CodeEntity)
            WHERE n.name = $name
            RETURN [node IN nodes(path) | node.name] AS chain,
                   length(path) AS hops
            ORDER BY hops
            LIMIT 30
            """,
            {"name": function_name},
        )

        if not rows:
            return f"'{function_name}' makes no calls (it's a leaf function)."

        by_depth: dict[int, list[str]] = {}
        for r in rows:
            h = r["hops"]
            by_depth.setdefault(h, [])
            chain = " -> ".join(r["chain"])
            if chain not in by_depth[h]:
                by_depth[h].append(chain)

        lines = [f"Call tree from '{function_name}' (depth={depth}):\n"]
        for h in sorted(by_depth):
            hop_label = f"{h}-hop {'callees' if h == 1 else 'chains'}"
            lines.append(f"  {hop_label}:")
            for chain in by_depth[h]:
                lines.append(f"    • {chain}")
            lines.append("")

        return "\n".join(lines)

    # ── 5. get_impact_analysis ────────────────────────────────────────────────

    def get_impact_analysis(self, function_name: str) -> str:
        """
        Full blast-radius report: metrics, callers, callees, similar functions.
        Answers 'what breaks if we remove X?'
        """
        rows = self.client.run_query(
            """
            MATCH (n:CodeEntity {name: $name})
            OPTIONAL MATCH (caller:CodeEntity)-[:CALLS]->(n)
            OPTIONAL MATCH (n)-[:CALLS]->(callee:CodeEntity)
            OPTIONAL MATCH (n)-[:SIMILAR_TO]-(sim:CodeEntity)
            WITH n,
                 collect(DISTINCT caller.name) AS callers,
                 collect(DISTINCT callee.name) AS callees,
                 collect(DISTINCT sim.name)    AS similar
            RETURN n.uid AS uid, n.name AS name,
                   [l IN labels(n) WHERE l <> 'CodeEntity'][0] AS label,
                   n.file AS file, n.layer AS layer,
                   n.summary AS summary,
                   n.fan_in AS fan_in, n.fan_out AS fan_out,
                   n.impact_score AS impact_score,
                   n.is_entry_point AS is_entry_point,
                   n.is_leaf AS is_leaf, n.is_recursive AS is_recursive,
                   callers, callees, similar
            LIMIT 1
            """,
            {"name": function_name},
        )

        if not rows:
            return f"Function '{function_name}' not found in graph."

        r = rows[0]
        callers  = r.get("callers") or []
        callees  = r.get("callees") or []
        similar  = r.get("similar") or []
        fan_in   = r.get("fan_in")  or len(callers)
        fan_out  = r.get("fan_out") or len(callees)
        impact   = r.get("impact_score") or round(fan_in * 2 + fan_out, 1)

        lines = [
            f"Impact Analysis: {r['name']}",
            "-" * 50,
            f"  File   : {r.get('file', '?')}",
            f"  Layer  : {r.get('layer') or 'unknown'}",
            "",
            "  Metrics:",
            f"    fan_in        = {fan_in}  (functions that call this)",
            f"    fan_out       = {fan_out}  (functions this calls)",
            f"    impact_score  = {impact}",
            f"    entry_point   = {bool(r.get('is_entry_point'))}",
            f"    leaf          = {bool(r.get('is_leaf'))}",
            f"    recursive     = {bool(r.get('is_recursive'))}",
            "",
        ]

        if r.get("summary"):
            lines += [f"  What it does: {r['summary']}", ""]

        if callers:
            lines.append(f"  Direct Callers ({len(callers)}): {', '.join(callers)}")
        else:
            lines.append("  Direct Callers: none (this is an entry point)")

        if callees:
            lines.append(f"  Direct Callees ({len(callees)}): {', '.join(callees)}")
        else:
            lines.append("  Direct Callees: none (this is a leaf function)")

        if similar:
            lines.append(f"  Similar Functions: {', '.join(similar)}")

        lines += [
            "",
            "  Blast Radius (removing this function breaks):",
        ]
        if callers:
            for c in callers:
                lines.append(f"    -> {c}")
        else:
            lines.append("    -> nothing (safe to remove structurally)")

        return "\n".join(lines)

    # ── 6. run_cypher ─────────────────────────────────────────────────────────

    def run_cypher(self, cypher_query: str) -> str:
        """
        Execute a read-only Cypher query directly against Neo4j.
        Write operations (CREATE, MERGE, DELETE, SET, etc.) are blocked.
        Results are capped at 30 rows.
        """
        if _WRITE_RE.search(cypher_query):
            return (
                "Blocked: query contains write operations. "
                "Only read queries (MATCH, RETURN, WITH, OPTIONAL MATCH) are allowed."
            )

        # Inject LIMIT 30 if not already limited
        q = cypher_query.strip().rstrip(";")
        if "LIMIT" not in q.upper():
            q += "\nLIMIT 30"

        try:
            rows = self.client.run_query(q)
        except Exception as exc:
            return f"Cypher error: {exc}"

        if not rows:
            return "Query returned no results."

        # Format rows as a table-like string
        lines = [f"Query returned {len(rows)} row(s):\n"]
        for i, row in enumerate(rows, 1):
            parts = [f"{k}={v}" for k, v in row.items() if v is not None]
            lines.append(f"  {i}. {', '.join(parts)}")

        return "\n".join(lines)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cosine_sim(a: list, b: list) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(np.dot(va, vb) / denom) if denom > 0 else 0.0


def _indent(text: str, spaces: int) -> str:
    pad = " " * spaces
    return "\n".join(pad + line for line in text.splitlines())
