"""
Context Builder — queries Neo4j at agent startup to build the dynamic system prompt.

The system prompt tells the agent what's in the graph BEFORE the first user message,
so it doesn't waste tool calls just discovering what exists.
"""
from __future__ import annotations

from graph.neo4j_client import Neo4jClient


def build_graph_context(client: Neo4jClient) -> str:
    """
    Query the graph for a high-level overview and return it as a formatted string
    ready to be embedded in the agent system prompt.
    """
    try:
        files      = _get_files(client)
        types_info = _get_types(client)
        top_funcs  = _get_top_functions(client)
        entries    = _get_entry_points(client)
        layers     = _get_layers(client)
        stats      = _get_stats(client)
        vuln_stats = _get_vuln_stats(client)
    except Exception as exc:
        return f"[Graph context unavailable: {exc}]"

    lines = ["=== CODEBASE KNOWLEDGE GRAPH OVERVIEW ===\n"]

    # ── Stats ─────────────────────────────────────────────────────────────────
    if stats:
        lines.append(f"Total nodes : {stats.get('nodes', '?')}")
        lines.append(f"Total edges : {stats.get('edges', '?')}\n")

    # ── Files ─────────────────────────────────────────────────────────────────
    if files:
        java = [f["name"] for f in files if f.get("language") == "java"]
        cpp  = [f["name"] for f in files if f.get("language") == "cpp"]
        c    = [f["name"] for f in files if f.get("language") == "c"]
        lines.append(f"SOURCE FILES ({len(files)}):")
        if java: lines.append(f"  Java : {', '.join(java)}")
        if cpp:  lines.append(f"  C++  : {', '.join(cpp)}")
        if c:    lines.append(f"  C    : {', '.join(c)}")
        lines.append("")

    # ── Types ─────────────────────────────────────────────────────────────────
    if types_info:
        classes = [n for n in types_info if n["label"] == "Class"]
        enums   = [n for n in types_info if n["label"] == "Enum"]
        structs = [n for n in types_info if n["label"] == "Struct"]

        if classes:
            lines.append(f"CLASSES ({len(classes)}): {', '.join(n['name'] for n in classes)}")
        if enums:
            sigs = [
                f"{n['name']} [{n['signature']}]" if n.get("signature") else n["name"]
                for n in enums
            ]
            lines.append(f"ENUMS ({len(enums)}): {', '.join(sigs)}")
        if structs:
            lines.append(f"STRUCTS ({len(structs)}): {', '.join(n['name'] for n in structs)}")
        lines.append("")

    # ── Top functions ─────────────────────────────────────────────────────────
    if top_funcs:
        lines.append(f"TOP FUNCTIONS BY IMPACT (top {len(top_funcs)}):")
        for f in top_funcs:
            impact = f.get("impact_score") or 0
            layer  = f.get("layer") or "unknown"
            fan_in = f.get("fan_in") or 0
            is_ep  = " [ENTRY POINT]" if f.get("is_entry_point") else ""
            lines.append(
                f"  {f['name']:<28} impact={impact:<5} layer={layer:<12} "
                f"callers={fan_in}{is_ep}"
            )
        lines.append("")

    # ── Entry points ──────────────────────────────────────────────────────────
    if entries:
        lines.append(f"ENTRY POINTS: {', '.join(e['name'] for e in entries)}\n")

    # ── Layers ────────────────────────────────────────────────────────────────
    if layers:
        lines.append(f"ARCHITECTURAL LAYERS: {', '.join(layers)}\n")

    # ── Vulnerability summary ─────────────────────────────────────────────────
    if vuln_stats and vuln_stats.get("scanned", 0) > 0:
        total_bugs = vuln_stats.get("bugs", 0)
        scanned    = vuln_stats.get("scanned", 0)
        lines.append("VULNERABILITY SCAN RESULTS:")
        if total_bugs == 0:
            lines.append(f"  No bugs detected across {scanned} functions scanned.")
        else:
            lines.append(f"  {total_bugs} bug(s) found in {scanned} functions scanned:")
            for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
                count = vuln_stats.get(sev, 0)
                if count:
                    lines.append(f"    {sev:<8} : {count}")
            # Full bug list — exact data so agent never has to guess
            all_bugs = vuln_stats.get("all_bugs", [])
            if all_bugs:
                lines.append("  Confirmed buggy functions (use find_vulnerabilities for full details):")
                for b in all_bugs:
                    lines.append(
                        f"    [{b['severity']}] {b['name']}()  "
                        f"file={b['file']}  layer={b['layer']}  impact={b['impact']}"
                    )
        lines.append("")

    lines.append("=== END OVERVIEW ===")
    return "\n".join(lines)


# ── Private query helpers ──────────────────────────────────────────────────────

def _get_files(client: Neo4jClient) -> list[dict]:
    # Use :File label directly — avoids relying on a 'label' property
    return client.run_query("""
        MATCH (f:File)
        RETURN f.name AS name, f.language AS language
        ORDER BY f.language, f.name
    """)


def _get_types(client: Neo4jClient) -> list[dict]:
    # Use node label predicates; extract primary label via labels() function
    return client.run_query("""
        MATCH (n:CodeEntity)
        WHERE n:Class OR n:Enum OR n:Struct OR n:Interface
        RETURN n.name AS name,
               [l IN labels(n) WHERE l <> 'CodeEntity'][0] AS label,
               n.signature AS signature
        ORDER BY label, n.name
    """)


def _get_top_functions(client: Neo4jClient) -> list[dict]:
    return client.run_query("""
        MATCH (f:Function)
        RETURN f.name AS name, f.layer AS layer,
               f.impact_score AS impact_score,
               f.fan_in AS fan_in, f.is_entry_point AS is_entry_point
        ORDER BY coalesce(f.impact_score, 0) DESC
        LIMIT 20
    """)


def _get_entry_points(client: Neo4jClient) -> list[dict]:
    return client.run_query("""
        MATCH (f:Function)
        WHERE f.is_entry_point = true
        RETURN f.name AS name, f.file AS file
        ORDER BY f.name
    """)


def _get_layers(client: Neo4jClient) -> list[str]:
    rows = client.run_query("""
        MATCH (n:CodeEntity)
        WHERE n.layer IS NOT NULL AND n.layer <> '' AND n.layer <> 'unknown'
        RETURN DISTINCT n.layer AS layer
        ORDER BY n.layer
    """)
    return [r["layer"] for r in rows]


def _get_stats(client: Neo4jClient) -> dict:
    node_row = client.run_query("MATCH (n:CodeEntity) RETURN count(n) AS c")
    edge_row = client.run_query("MATCH ()-[r]->() RETURN count(r) AS c")
    return {
        "nodes": node_row[0]["c"] if node_row else 0,
        "edges": edge_row[0]["c"] if edge_row else 0,
    }


def _get_vuln_stats(client: Neo4jClient) -> dict:
    """Query vulnerability scan results stored on Function nodes."""
    # Check if scan has been run (is_buggy property exists on any node)
    check = client.run_query("""
        MATCH (f:Function)
        WHERE f.is_buggy IS NOT NULL
        RETURN count(f) AS c
    """)
    scanned = check[0]["c"] if check else 0
    if scanned == 0:
        return {}

    rows = client.run_query("""
        MATCH (f:Function)
        WHERE f.is_buggy IS NOT NULL
        RETURN
            count(f) AS scanned,
            count(CASE WHEN f.is_buggy = true THEN 1 END) AS bugs,
            count(CASE WHEN f.severity = 'CRITICAL' AND f.is_buggy = true THEN 1 END) AS critical,
            count(CASE WHEN f.severity = 'HIGH'     AND f.is_buggy = true THEN 1 END) AS high,
            count(CASE WHEN f.severity = 'MEDIUM'   AND f.is_buggy = true THEN 1 END) AS medium,
            count(CASE WHEN f.severity = 'LOW'      AND f.is_buggy = true THEN 1 END) AS low
    """)

    all_bugs_rows = client.run_query("""
        MATCH (f:Function)
        WHERE f.is_buggy = true
        RETURN f.name AS name, f.severity AS severity,
               f.file AS file, f.layer AS layer,
               coalesce(f.impact_score, 0) AS impact
        ORDER BY
            CASE f.severity
                WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2
                WHEN 'MEDIUM'   THEN 3 WHEN 'LOW'  THEN 4
                ELSE 5
            END,
            f.impact_score DESC
    """)

    r = rows[0] if rows else {}
    return {
        "scanned":  r.get("scanned", 0),
        "bugs":     r.get("bugs", 0),
        "CRITICAL": r.get("critical", 0),
        "HIGH":     r.get("high", 0),
        "MEDIUM":   r.get("medium", 0),
        "LOW":      r.get("low", 0),
        "all_bugs": [
            {
                "name":     row["name"],
                "severity": row["severity"],
                "file":     row["file"] or "?",
                "layer":    row["layer"] or "unknown",
                "impact":   row["impact"],
            }
            for row in all_bugs_rows
        ],
    }
