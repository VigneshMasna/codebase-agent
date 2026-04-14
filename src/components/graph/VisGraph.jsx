/**
 * VisGraph — Production-grade Neo4j Browser-style graph.
 *
 * Architecture (hybrid canvas + SVG):
 *   <canvas>  — edges, arrowheads, edge labels  (fast, no DOM per edge)
 *   <svg>     — nodes only                       (keeps full interactivity)
 *
 * Performance:
 *   • Canvas edges: O(1) DOM regardless of edge count
 *   • RAF-throttled canvas redraws (never more than 60 fps)
 *   • Simulation auto-tunes strength/distance for node count
 *   • Circular initial placement → shorter settling time
 *   • Edge labels hidden when zoom < 0.45 or node count > 120
 *   • Physics disabled after stabilisation; re-enabled only on drag
 *
 * Interactions:
 *   • Hover  — dims unrelated nodes (opacity 0.28) + subtle scale on active node
 *   • Click  — white ring on selected; fires onNodeClick
 *   • Drag   — pins fx/fy during drag; releases cleanly
 *   • Zoom   — d3.zoom, smooth transitions
 */

import React, { useEffect, useRef, useImperativeHandle, forwardRef } from 'react'
import * as d3 from 'd3'
import dagre from 'dagre'
import { NODE_HUE, EDGE_COLOR } from '../../constants/graph'

/* ── Constants ───────────────────────────────────────────────────── */
const R    = 30      // node circle radius (px)
const FONT = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

/* ── Pure helpers ────────────────────────────────────────────────── */
const nodeHue  = n   => n.is_buggy ? NODE_HUE._buggy : n.is_entry_point ? NODE_HUE._entry : (NODE_HUE[n.label] || NODE_HUE._default)
const trunc    = (s, n) => (!s ? '' : s.length > n ? s.slice(0, n - 1) + '…' : s)

const AH = 8   // arrowhead length (px)

/** Straight line geometry for a directed edge.
 *  Returns null for self-loops (handled separately by drawSelfLoop).
 *  d._offset: perpendicular px shift (non-zero for bidirectional pairs). */
function linePath(d) {
  const { x: sx, y: sy } = d.source
  const { x: tx, y: ty } = d.target
  if (d.source.id === d.target.id) return null   // self-loop — skip here
  const dx = tx - sx, dy = ty - sy
  const len = Math.sqrt(dx * dx + dy * dy)
  if (len < 1) return null
  const ux = dx / len, uy = dy / len
  // Perpendicular unit vector (rotate 90°): (-uy, ux)
  const off = d._offset || 0
  const px = -uy * off, py = ux * off
  const p0x = sx + ux * R          + px,  p0y = sy + uy * R          + py
  const p1x = tx - ux * (R + AH)   + px,  p1y = ty - uy * (R + AH)   + py
  const tipX = tx - ux * R         + px,  tipY = ty - uy * R          + py
  const angle = Math.atan2(dy, dx)
  return { p0x, p0y, p1x, p1y, tipX, tipY, angle,
    midX: (p0x + p1x) / 2, midY: (p0y + p1y) / 2 }
}

/** Filter helper (pure, no side effects). */
function filterGraph(allNodes, allEdges, filter, vulnOnly) {
  if (!vulnOnly && (!filter || filter === 'all'))
    return { fn: allNodes, fe: allEdges }

  let fn
  if (vulnOnly || filter === 'buggy')
    fn = allNodes.filter(n => n.is_buggy)
  else if (filter === 'Function')
    fn = allNodes.filter(n => n.label === 'Function')
  else if (filter === 'Class')
    fn = allNodes.filter(n => ['Class', 'Interface', 'Struct', 'Enum'].includes(n.label))
  else
    fn = allNodes.filter(n => n.label === filter)

  const ids = new Set(fn.map(n => n.uid))
  return { fn, fe: allEdges.filter(e => ids.has(e.source_uid) && ids.has(e.target_uid)) }
}

/* ── VisGraph component ──────────────────────────────────────────── */
const VisGraph = forwardRef(function VisGraph(
  { nodes: apiNodes, edges: apiEdges, onNodeClick, onNodeHover, filterLabel = 'all', showVulnOnly = false },
  ref,
) {
  const wrapRef        = useRef(null)
  const canvasRef      = useRef(null)
  const svgRef         = useRef(null)
  const gRef           = useRef(null)
  const zoomRef        = useRef(null)
  const simRef         = useRef(null)
  const txRef          = useRef(d3.zoomIdentity)
  const linksRef       = useRef([])
  const hoveredRef     = useRef(null)
  const rafRef         = useRef(null)
  // Callback refs — always hold the latest prop without needing them in deps
  const onClickRef     = useRef(onNodeClick)
  const onHoverRef     = useRef(onNodeHover)
  onClickRef.current   = onNodeClick
  onHoverRef.current   = onNodeHover

  /* ── Expose zoom/fit controls ──────────────────────────────── */
  useImperativeHandle(ref, () => ({
    zoomIn   () { zoom(1.3) },
    zoomOut  () { zoom(0.77) },
    fitScreen() { fitAll() },
  }))

  function zoom(factor) {
    const svgEl = svgRef.current
    if (svgEl && zoomRef.current)
      d3.select(svgEl).transition().duration(280).call(zoomRef.current.scaleBy, factor)
  }

  function fitAll() {
    const svgEl = svgRef.current
    const gEl   = gRef.current
    if (!svgEl || !gEl || !zoomRef.current) return
    try {
      const b = gEl.getBBox()
      if (b.width < 1 || b.height < 1) return
      const W = svgEl.clientWidth  || 900
      const H = svgEl.clientHeight || 600
      const scale = Math.min(0.88 * W / (b.width + 80), 0.88 * H / (b.height + 80), 2.5)
      const tx    = W / 2 - scale * (b.x + b.width  / 2)
      const ty    = H / 2 - scale * (b.y + b.height / 2)
      d3.select(svgEl)
        .transition().duration(700).ease(d3.easeCubicInOut)
        .call(zoomRef.current.transform, d3.zoomIdentity.translate(tx, ty).scale(scale))
    } catch (_) {}
  }

  /* ── Canvas draw (called via RAF) ──────────────────────────── */
  function scheduleRedraw() {
    cancelAnimationFrame(rafRef.current)
    rafRef.current = requestAnimationFrame(drawCanvas)
  }

  function drawCanvas() {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const { x: tx, y: ty, k } = txRef.current
    const W = canvas.width, H = canvas.height

    ctx.clearRect(0, 0, W, H)
    ctx.save()
    ctx.translate(tx, ty)
    ctx.scale(k, k)

    const links = linksRef.current
    const hov   = hoveredRef.current
    // Show labels at moderate zoom OR on hover
    const showLabelsZoom = k >= 0.75

    links.forEach(d => {
      if (!d.source?.x) return

      const isHovEdge = !!(hov && (d.source.id === hov.id || d.target.id === hov.id))
      const isNbr     = !hov || (hov.nbr.has(d.source.id) && hov.nbr.has(d.target.id))
      const alpha     = isNbr ? 0.72 : 0.28
      const color     = isHovEdge ? '#B8C8D0' : EDGE_COLOR

      // ── Self-loop (recursive call) ──────────────────────────
      if (d.source.id === d.target.id) {
        const cx = d.source.x, cy = d.source.y
        const loopW = R * 1.1, loopH = R * 2.0
        // Two attachment points on the top of the circle
        const ax1 = cx - R * 0.45, ay1 = cy - R * 0.88
        const ax2 = cx + R * 0.45, ay2 = cy - R * 0.88
        // Control points forming the loop above the node
        const cp1x = cx - loopW, cp1y = cy - loopH
        const cp2x = cx + loopW, cp2y = cy - loopH

        ctx.save()
        ctx.globalAlpha = alpha
        ctx.strokeStyle = color
        ctx.lineWidth   = isHovEdge ? 1.8 : 1.4
        ctx.beginPath()
        ctx.moveTo(ax1, ay1)
        ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, ax2, ay2)
        ctx.stroke()

        // Arrowhead at ax2,ay2 — tangent from cp2 to end
        const tDx = ax2 - cp2x, tDy = ay2 - cp2y
        const tAngle = Math.atan2(tDy, tDx)
        ctx.save()
        ctx.translate(ax2, ay2)
        ctx.rotate(tAngle)
        ctx.fillStyle = color
        ctx.globalAlpha = isNbr ? 0.85 : 0.28
        ctx.beginPath()
        ctx.moveTo(0, 0)
        ctx.lineTo(-AH, AH * 0.42)
        ctx.lineTo(-AH, -AH * 0.42)
        ctx.closePath()
        ctx.fill()
        ctx.restore()

        // Label above the loop
        if ((showLabelsZoom || isHovEdge) && d.type) {
          ctx.font         = `400 8.5px ${FONT}`
          ctx.textAlign    = 'center'
          ctx.textBaseline = 'middle'
          ctx.globalAlpha  = isHovEdge ? Math.min(alpha * 1.3, 1) : alpha * 0.85
          ctx.fillStyle    = isHovEdge ? '#D0E4EA' : '#B0BEC5'
          ctx.fillText(d.type, cx, cy - loopH - 6)
        }
        ctx.restore()
        return
      }

      // ── Normal straight edge ─────────────────────────────────
      const line = linePath(d)
      if (!line) return

      const lw = isHovEdge ? 2.0 : 1.5

      ctx.save()
      ctx.globalAlpha = alpha

      ctx.beginPath()
      ctx.moveTo(line.p0x, line.p0y)
      ctx.lineTo(line.p1x, line.p1y)
      ctx.strokeStyle = color
      ctx.lineWidth   = lw
      ctx.stroke()

      // Arrowhead
      ctx.save()
      ctx.translate(line.tipX, line.tipY)
      ctx.rotate(line.angle)
      ctx.fillStyle = color
      ctx.globalAlpha = isNbr ? 0.85 : 0.28
      ctx.beginPath()
      ctx.moveTo(0, 0)
      ctx.lineTo(-AH, AH * 0.42)
      ctx.lineTo(-AH, -AH * 0.42)
      ctx.closePath()
      ctx.fill()
      ctx.restore()

      // Edge label
      if ((showLabelsZoom || isHovEdge) && d.type) {
        ctx.font         = `400 8.5px ${FONT}`
        ctx.textAlign    = 'center'
        ctx.textBaseline = 'middle'
        ctx.globalAlpha  = isHovEdge ? Math.min(alpha * 1.3, 1) : alpha * 0.85
        ctx.fillStyle    = isHovEdge ? '#D0E4EA' : '#B0BEC5'
        ctx.fillText(d.type, line.midX, line.midY - 9)
      }

      ctx.restore()
    })

    ctx.restore()
  }

  /* ── Main render effect ─────────────────────────────────────── */
  useEffect(() => {
    const wrap = wrapRef.current
    if (!wrap || !apiNodes?.length) return

    simRef.current?.stop()
    simRef.current = null
    cancelAnimationFrame(rafRef.current)
    txRef.current = d3.zoomIdentity   // reset transform on data change

    const W = wrap.clientWidth  || 900
    const H = wrap.clientHeight || 600

    /* Filter */
    const { fn: rawNodes, fe: rawEdges } = filterGraph(apiNodes, apiEdges, filterLabel, showVulnOnly)

    /* ── Setup canvas ──────────────────────────────────────────── */
    const canvas = canvasRef.current
    canvas.width  = wrap.clientWidth
    canvas.height = wrap.clientHeight

    /* ── Clear old SVG content ───────────────────────────────── */
    const svgEl = svgRef.current
    const svg   = d3.select(svgEl)
    svg.selectAll('*').remove()

    /* ── SVG defs: glow filters ──────────────────────────────── */
    const defs = svg.append('defs')

    // Very subtle radial shading — barely noticeable depth, no glow/blur
    const rg = defs.append('radialGradient')
      .attr('id', 'nodeShine')
      .attr('cx', '38%').attr('cy', '32%').attr('r', '58%')
    rg.append('stop').attr('offset', '0%')  .attr('stop-color', '#ffffff').attr('stop-opacity', '0.10')
    rg.append('stop').attr('offset', '100%').attr('stop-color', '#000000').attr('stop-opacity', '0.07')

    /* ── Zoom behaviour ──────────────────────────────────────── */
    const zoomBeh = d3.zoom().scaleExtent([0.04, 8])
      .on('zoom', ev => {
        txRef.current = ev.transform
        // Apply to SVG node group
        d3.select(gRef.current).attr('transform', ev.transform)
        scheduleRedraw()
      })
    svg.call(zoomBeh).on('dblclick.zoom', null)
    zoomRef.current = zoomBeh

    /* ── Main node group ─────────────────────────────────────── */
    const g = svg.append('g')
    gRef.current = g.node()

    /* ── Process edges ───────────────────────────────────────── */
    // Detect bidirectional pairs so we can shift each edge to one side
    const edgeKeys = new Set(rawEdges.map(e => `${e.source_uid}→${e.target_uid}`))
    const linkData = rawEdges.map(e => {
      const hasBidi = edgeKeys.has(`${e.target_uid}→${e.source_uid}`)
      return {
        ...e,
        source  : e.source_uid,
        target  : e.target_uid,
        _offset : hasBidi ? 7 : 0,   // shift bidi edges 7 px off-center
      }
    })
    linksRef.current = linkData

    /* ── Dagre hierarchical layout ───────────────────────────── */
    const dg = new dagre.graphlib.Graph()
    dg.setDefaultEdgeLabel(() => ({}))
    dg.setGraph({
      rankdir  : 'TB',    // top → bottom hierarchy
      nodesep  : 90,      // horizontal gap between nodes in same rank
      ranksep  : 130,     // vertical gap between ranks/layers
      marginx  : 60,
      marginy  : 60,
    })

    const nodeSet = new Set(rawNodes.map(n => n.uid))
    rawNodes.forEach(n => dg.setNode(n.uid, { width: R * 2 + 24, height: R * 2 + 24 }))
    rawEdges.forEach(e => {
      if (nodeSet.has(e.source_uid) && nodeSet.has(e.target_uid))
        dg.setEdge(e.source_uid, e.target_uid)
    })
    dagre.layout(dg)

    // Centre the dagre layout on the canvas
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    rawNodes.forEach(n => {
      const p = dg.node(n.uid)
      if (p) { minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x)
               minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y) }
    })
    const offsetX = W / 2 - (minX + (maxX - minX) / 2)
    const offsetY = H / 2 - (minY + (maxY - minY) / 2)

    const nodeData = rawNodes.map(n => {
      const p = dg.node(n.uid)
      const tx = p ? p.x + offsetX : W / 2
      const ty = p ? p.y + offsetY : H / 2
      return { ...n, id: n.uid, x: tx, y: ty, tx, ty }
    })

    /* ── Light simulation: dagre-anchored + collision only ───── */
    // forceX/Y pull each node back to its dagre position;
    // collision prevents circles from overlapping.
    // No charge or link forces — dagre already handles structure.
    const sim = d3.forceSimulation(nodeData)
      .force('link', d3.forceLink(linkData).id(d => d.id).strength(0))  // resolves source/target IDs → objects
      .force('collision', d3.forceCollide(R + 14).strength(0.85).iterations(2))
      .force('x', d3.forceX(d => d.tx).strength(0.45))
      .force('y', d3.forceY(d => d.ty).strength(0.45))
      .alphaDecay(0.08)    // fast settling (~40 ticks)
      .alphaMin(0.001)
      .velocityDecay(0.65)
    simRef.current = sim

    /* ── Render nodes ────────────────────────────────────────── */
    const nGroup = g.selectAll('g.nv')
      .data(nodeData, d => d.id)
      .join('g').attr('class', 'nv').style('cursor', 'grab')

    // Main circle — flat, crisp, no blur/glow/filter
    nGroup.append('circle').attr('class', 'body')
      .attr('r', R)
      .attr('fill',         d => nodeHue(d))
      .attr('stroke',       d => d3.color(nodeHue(d)).darker(0.4).formatHex())
      .attr('stroke-width', 1)

    // Very subtle inner shading overlay (barely noticeable)
    nGroup.append('circle').attr('class', 'shine')
      .attr('r', R)
      .attr('fill', 'url(#nodeShine)')
      .style('pointer-events', 'none')

    // Name only — centered, single line
    nGroup.append('text').attr('class', 'lname')
      .text(d => trunc(d.name || d.label || '', 11))
      .attr('y', 0)
      .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
      .attr('fill', '#1a1a1a')
      .attr('font-size', '9px').attr('font-weight', '600')
      .attr('font-family', FONT)
      .style('pointer-events', 'none').style('user-select', 'none')

    /* ── Drag ────────────────────────────────────────────────── */
    nGroup.call(
      d3.drag()
        .on('start', (ev, d) => {
          if (!ev.active) sim.alphaTarget(0.15).restart()
          d.fx = d.x; d.fy = d.y
          d3.select(ev.sourceEvent.target.parentNode).style('cursor', 'grabbing')
        })
        .on('drag', (ev, d) => {
          d.fx = ev.x; d.fy = ev.y
          d.tx = ev.x; d.ty = ev.y
        })
        .on('end',  (ev, d) => {
          if (!ev.active) sim.alphaTarget(0)
          d.fx = null; d.fy = null
          d3.select(ev.sourceEvent.target.parentNode).style('cursor', 'grab')
        }),
    )

    /* ── Hover helpers ───────────────────────────────────────── */
    function buildNbr(d) {
      const nbr = new Set([d.id])
      linkData.forEach(e => {
        const s = typeof e.source === 'object' ? e.source.id : e.source
        const t = typeof e.target === 'object' ? e.target.id : e.target
        if (s === d.id) nbr.add(t)
        if (t === d.id) nbr.add(s)
      })
      return nbr
    }

    nGroup
      .on('mouseenter', (ev, d) => {
        const nbr = buildNbr(d)
        hoveredRef.current = { id: d.id, nbr }

        nGroup.each(function(nd) {
          const sel = d3.select(this)
          if (nd.id === d.id) {
            sel.select('.body').attr('transform', 'scale(1.05)')
              .attr('stroke', d3.color(nodeHue(nd)).darker(0.6).formatHex())
              .attr('stroke-width', 1.5)
            sel.select('.shine').attr('transform', 'scale(1.05)')
          } else if (!nbr.has(nd.id)) {
            sel.attr('opacity', 0.55)   // was 0.28 — keep context visible
          }
        })
        scheduleRedraw()
        onHoverRef.current?.(d)
        ev.stopPropagation()
      })
      .on('mouseleave', () => {
        hoveredRef.current = null
        nGroup.attr('opacity', 1)
        nGroup.each(function(nd) {
          d3.select(this).select('.body')
            .attr('transform', null)
            .attr('stroke', d3.color(nodeHue(nd)).darker(0.4).formatHex())
            .attr('stroke-width', 1)
          d3.select(this).select('.shine').attr('transform', null)
        })
        scheduleRedraw()
        onHoverRef.current?.(null)
      })

    /* ── Click ───────────────────────────────────────────────── */
    nGroup.on('click', (ev, d) => {
      ev.stopPropagation()
      nGroup.select('.body')
        .attr('stroke', nd => nd.id === d.id ? d3.color(nodeHue(nd)).darker(1.2).formatHex() : d3.color(nodeHue(nd)).darker(0.4).formatHex())
        .attr('stroke-width', nd => nd.id === d.id ? 2 : 1)
      onClickRef.current?.(d)
    })

    svg.on('click', () => {
      nGroup.select('.body')
        .attr('stroke', nd => d3.color(nodeHue(nd)).darker(0.4).formatHex())
        .attr('stroke-width', 1)
    })

    /* ── Simulation tick ─────────────────────────────────────── */
    sim.on('tick', () => {
      nGroup.attr('transform', d => `translate(${d.x},${d.y})`)
      scheduleRedraw()
    })

    /* ── Fit only on initial stabilisation, never again ─────── */
    let initialFitDone = false
    sim.on('end', () => {
      sim.stop()
      if (!initialFitDone) {
        initialFitDone = true
        setTimeout(fitAll, 80)
      }
    })

    /* ── Handle canvas resize ────────────────────────────────── */
    const ro = new ResizeObserver(() => {
      if (!canvas || !wrap) return
      canvas.width  = wrap.clientWidth
      canvas.height = wrap.clientHeight
      scheduleRedraw()
    })
    ro.observe(wrap)

    return () => {
      sim.stop()
      ro.disconnect()
      cancelAnimationFrame(rafRef.current)
    }
  }, [apiNodes, apiEdges, filterLabel, showVulnOnly])

  return (
    <div ref={wrapRef} style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      {/* Canvas: edges drawn here — zero SVG DOM per edge */}
      <canvas
        ref={canvasRef}
        style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}
      />
      {/* SVG: interactive nodes only */}
      <svg
        ref={svgRef}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', overflow: 'visible' }}
      />
    </div>
  )
})

export default VisGraph
