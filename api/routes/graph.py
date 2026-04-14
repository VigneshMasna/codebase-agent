"""
Graph routes — expose Neo4j graph data for the frontend visualiser and
vulnerability dashboard.

Endpoints:
  GET  /api/graph           — nodes + edges for the interactive graph panel
  GET  /api/scan-results    — all vulnerability annotations from Neo4j
  GET  /api/stats           — lightweight overview stats for the dashboard header
  GET  /api/node/{uid}      — full details of a single node (for click-to-inspect)
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies import require_neo4j
from api.models.responses import (
    GraphData,
    GraphEdge,
    GraphNode,
    ScanResultsResponse,
    VulnFunction,
)
from api.services.graph_service import GraphService

router = APIRouter()


# ── GET /api/graph ────────────────────────────────────────────────────────────

@router.get(
    "/graph",
    response_model=GraphData,
    summary="Get graph nodes and edges for visualisation",
    description=(
        "Returns the top-N most impactful code nodes and their relationships. "
        "Suitable for rendering with React Force Graph, Neovis.js, or similar."
    ),
)
def get_graph(
    node_limit: int = Query(200, ge=1, le=2000, description="Max number of nodes"),
    include_labels: str = Query(
        "Function,Class,Struct,Enum,Interface,File,Package,Namespace,ExternalFunction,Field,Import,Include,Tag",
        description="Comma-separated node labels to include",
    ),
    min_impact_score: float = Query(0.0, ge=0.0, description="Minimum impact score"),
    bugs_only: bool = Query(False, description="Return only buggy nodes and their edges"),
    neo4j=Depends(require_neo4j),
) -> GraphData:
    service = GraphService(neo4j)
    labels  = [lbl.strip() for lbl in include_labels.split(",") if lbl.strip()]

    data = service.get_graph_data(
        node_limit=node_limit,
        include_labels=labels,
        min_impact_score=min_impact_score,
        bugs_only=bugs_only,
    )

    nodes = [GraphNode(**n) for n in data["nodes"]]
    edges = [GraphEdge(**e) for e in data["edges"]]

    return GraphData(nodes=nodes, edges=edges, stats=data["stats"])


# ── GET /api/scan-results ─────────────────────────────────────────────────────

@router.get(
    "/scan-results",
    response_model=ScanResultsResponse,
    summary="Get all vulnerability annotations from the graph",
    description=(
        "Returns all Function nodes annotated as buggy by the ingest pipeline, "
        "ordered by severity (CRITICAL → HIGH → MEDIUM → LOW) then impact score."
    ),
)
def get_scan_results(
    severity: Optional[str] = Query(
        None,
        description="Filter by severity: CRITICAL | HIGH | MEDIUM | LOW",
    ),
    limit: int = Query(500, ge=1, le=5000, description="Max results"),
    neo4j=Depends(require_neo4j),
) -> ScanResultsResponse:
    # Validate severity filter
    if severity:
        severity = severity.upper()
        if severity not in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid severity '{severity}'. Use: CRITICAL, HIGH, MEDIUM, or LOW.",
            )

    service = GraphService(neo4j)
    data    = service.get_scan_results(severity_filter=severity, limit=limit)

    return ScanResultsResponse(
        total_functions= data["total_functions"],
        bugs_found=      data["bugs_found"],
        critical=        data["critical"],
        high=            data["high"],
        medium=          data["medium"],
        low=             data["low"],
        vulnerabilities= [VulnFunction(**v) for v in data["vulnerabilities"]],
    )


# ── GET /api/stats ────────────────────────────────────────────────────────────

@router.get(
    "/stats",
    summary="Graph overview statistics",
    description=(
        "Returns lightweight counts (nodes, edges, bugs, files) for the "
        "dashboard header without fetching full node data."
    ),
)
def get_stats(neo4j=Depends(require_neo4j)) -> dict:
    service = GraphService(neo4j)
    return service.get_overview_stats()


# ── GET /api/node/{uid} ───────────────────────────────────────────────────────

@router.get(
    "/node/{uid:path}",
    response_model=GraphNode,
    summary="Get full details of a single graph node",
    description=(
        "Returns all stored properties of a node by its UID. "
        "Used by the frontend when a user clicks on a node in the graph."
    ),
)
def get_node(uid: str, neo4j=Depends(require_neo4j)) -> GraphNode:
    try:
        rows = neo4j.run_query(
            """
            MATCH (n:CodeEntity {uid: $uid})
            RETURN
                n.uid           AS id,
                [x IN labels(n) WHERE x <> 'CodeEntity'][0] AS label,
                n.name          AS name,
                n.file          AS file,
                n.summary       AS summary,
                n.layer         AS layer,
                coalesce(n.impact_score, 0)      AS impact_score,
                coalesce(n.is_entry_point, false) AS is_entry_point,
                coalesce(n.is_buggy, false)       AS is_buggy,
                n.severity      AS severity,
                n.bug_confidence AS bug_confidence,
                coalesce(n.fan_in,  0) AS fan_in,
                coalesce(n.fan_out, 0) AS fan_out,
                coalesce(n.tags, [])   AS tags,
                n.language      AS language
            LIMIT 1
            """,
            {"uid": uid},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query failed: {exc}",
        )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node with uid '{uid}' not found in graph.",
        )

    row = rows[0]
    return GraphNode(
        id=            row.get("id") or "",
        label=         row.get("label") or "Function",
        name=          row.get("name") or "",
        file=          row.get("file"),
        summary=       row.get("summary"),
        layer=         row.get("layer"),
        impact_score=  float(row.get("impact_score") or 0),
        is_entry_point=bool(row.get("is_entry_point")),
        is_buggy=      bool(row.get("is_buggy")),
        severity=      row.get("severity"),
        bug_confidence=row.get("bug_confidence"),
        fan_in=        int(row.get("fan_in") or 0),
        fan_out=       int(row.get("fan_out") or 0),
        tags=          row.get("tags") or [],
        language=      row.get("language"),
    )
