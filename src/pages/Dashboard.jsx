import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { ZoomIn, ZoomOut, Maximize2, Columns2 } from 'lucide-react'
import StatCard from '../components/dashboard/StatCard'
import LanguageDonut from '../components/dashboard/LanguageDonut'
import UploadSection from '../components/dashboard/UploadSection'
import VisGraph from '../components/graph/VisGraph'
import DotsIcon from '../components/ui/DotsIcon'
import { getStats, getGraph } from '../api/client'
import { useIngest } from '../context/IngestContext'
import { labelColor } from '../constants/graph'

/* ── Results Overview panel ───────────────────────────────────── */
function ResultsOverview({ nodes, edges, onClose }) {
  // Count nodes by label
  const nodeCounts = {}
  let totalNodes = 0
  nodes.forEach(n => {
    const key = n.label || 'Unknown'
    nodeCounts[key] = (nodeCounts[key] || 0) + 1
    totalNodes++
  })

  // Count edges by type
  const edgeCounts = {}
  let totalEdges = 0
  edges.forEach(e => {
    const key = e.type || 'RELATED'
    edgeCounts[key] = (edgeCounts[key] || 0) + 1
    totalEdges++
  })

  const nodeEntries = [
    ['*', totalNodes],
    ...Object.entries(nodeCounts).sort((a, b) => b[1] - a[1]),
  ]
  const edgeEntries = [
    ['*', totalEdges],
    ...Object.entries(edgeCounts).sort((a, b) => b[1] - a[1]),
  ]

  return (
    <div style={{
      position: 'absolute', top: 0, right: 0, bottom: 0,
      width: 210,
      background: 'rgba(15,16,20,0.97)',
      borderLeft: '1px solid rgba(255,255,255,0.08)',
      display: 'flex',
      flexDirection: 'column',
      zIndex: 20,
      overflowY: 'auto',
      backdropFilter: 'blur(12px)',
    }}>
      {/* Header */}
      <div style={{
        padding: '12px 14px 10px',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        flexShrink: 0,
      }}>
        <span style={{ fontSize: '13px', fontWeight: 700, color: '#fff' }}>
          Results overview
        </span>
        <button
          onClick={onClose}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'rgba(255,255,255,0.40)', fontSize: '16px', lineHeight: 1,
            padding: '2px 4px', borderRadius: '4px',
          }}
          onMouseEnter={e => e.currentTarget.style.color = '#fff'}
          onMouseLeave={e => e.currentTarget.style.color = 'rgba(255,255,255,0.40)'}
        >
          ✕
        </button>
      </div>

      {/* Content */}
      <div style={{ padding: '12px 14px', overflowY: 'auto' }}>

        {/* Nodes section */}
        <p style={{
          fontSize: '13px', fontWeight: 600, color: 'rgba(255,255,255,0.85)',
          marginBottom: '8px',
        }}>
          Nodes ({totalNodes})
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '18px' }}>
          {nodeEntries.map(([label, count]) => {
            const color = label === '*' ? '#a78bfa' : labelColor(label)
            return (
              <span key={label} style={{
                display: 'inline-flex', alignItems: 'center', gap: '4px',
                padding: '3px 9px', borderRadius: '999px',
                background: `${color}20`,
                border: `1px solid ${color}55`,
                fontSize: '12px', fontWeight: 600,
                color,
                cursor: 'default',
                whiteSpace: 'nowrap',
              }}>
                {label === '*' ? '* ' : ''}{label === '*' ? `(${count})` : `${label} (${count})`}
              </span>
            )
          })}
        </div>

        {/* Relationships section */}
        <p style={{
          fontSize: '13px', fontWeight: 600, color: 'rgba(255,255,255,0.85)',
          marginBottom: '8px',
        }}>
          Relationships ({totalEdges})
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
          {edgeEntries.map(([type, count]) => (
            <span key={type} style={{
              display: 'inline-flex', alignItems: 'center',
              padding: '3px 9px', borderRadius: '999px',
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.14)',
              fontSize: '12px', fontWeight: 600,
              color: 'rgba(255,255,255,0.75)',
              cursor: 'default',
              whiteSpace: 'nowrap',
            }}>
              {type === '*' ? `* (${count})` : `${type} (${count})`}
            </span>
          ))}
        </div>

      </div>
    </div>
  )
}

/* ── Shared panel constants ───────────────────────────────────── */
const PANEL_BG     = '#18191d'
const PANEL_BORDER = '1px solid rgba(255,255,255,0.08)'
const PANEL_RADIUS = '10px'

/* ── Small icon button ────────────────────────────────────────── */
function IconBtn({ onClick, title, children, active = false }) {
  return (
    <button
      onClick={onClick}
      title={title}
      style={{
        width: 30, height: 30, borderRadius: '7px',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: active ? 'rgba(167,139,250,0.15)' : 'rgba(255,255,255,0.05)',
        border: active ? '1px solid rgba(167,139,250,0.35)' : '1px solid rgba(255,255,255,0.09)',
        color: active ? '#a78bfa' : 'rgba(255,255,255,0.45)',
        cursor: 'pointer',
        transition: 'background 0.15s, color 0.15s, border-color 0.15s',
      }}
      onMouseEnter={e => {
        if (!active) {
          e.currentTarget.style.background = 'rgba(255,255,255,0.10)'
          e.currentTarget.style.color = 'rgba(255,255,255,0.85)'
        }
      }}
      onMouseLeave={e => {
        if (!active) {
          e.currentTarget.style.background = 'rgba(255,255,255,0.05)'
          e.currentTarget.style.color = 'rgba(255,255,255,0.45)'
        }
      }}
    >
      {children}
    </button>
  )
}

/* ── Dashboard ───────────────────────────────────────────────── */
export default function Dashboard() {
  const graphRef = useRef(null)
  const { registerOnComplete } = useIngest()

  const [stats,         setStats]        = useState(null)
  const [langData,      setLangData]     = useState([])
  const [allNodes,      setAllNodes]     = useState([])   // full dataset → Results Overview
  const [allEdges,      setAllEdges]     = useState([])
  const [previewNodes,  setPreviewNodes] = useState([])   // top-80 subset → graph render
  const [previewEdges,  setPreviewEdges] = useState([])
  const [loadingGraph,  setLoadingGraph] = useState(true)
  const [showOverview,  setShowOverview] = useState(false)

  const refreshData = useCallback(() => {
    getStats().then(({ data }) => setStats(data)).catch(() => {})

    setLoadingGraph(true)
    getGraph({ node_limit: 2000 }).then(({ data }) => {
      const ns = data.nodes || []
      const es = data.edges || []

      setAllNodes(ns)
      setAllEdges(es)

      const sorted  = [...ns].sort((a, b) => (b.impact_score || 0) - (a.impact_score || 0))
      const preview = sorted.slice(0, 80)
      const pSet    = new Set(preview.map((n) => n.uid))

      setPreviewNodes(preview)
      setPreviewEdges(es.filter((e) => pSet.has(e.source_uid) && pSet.has(e.target_uid)))

      const langMap = {}
      ns.forEach((n) => { if (n.language) langMap[n.language] = (langMap[n.language] || 0) + 1 })
      const entries = Object.entries(langMap)
      if (entries.length) setLangData(entries.map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value))
      setLoadingGraph(false)
    }).catch(() => setLoadingGraph(false))
  }, [])

  useEffect(() => { refreshData() }, [])
  useLayoutEffect(() => { registerOnComplete(refreshData) }, [refreshData, registerOnComplete])

  const STAT_CARDS = [
    { label: 'Total Code Entities', value: stats?.node_count },
    { label: 'Total Edges',         value: stats?.edge_count },
    { label: 'Total Bugs',          value: stats?.bug_count  },
    { label: 'Total Files',         value: stats?.file_count },
  ]

  return (
    <div style={{
      padding: '14px',
      display: 'flex',
      flexDirection: 'column',
      gap: '12px',
      height: '100%',
      boxSizing: 'border-box',
      overflowY: 'auto',
      background: '#111215',
    }}>

      {/* ── Upload section ────────────────────────────────────── */}
      <UploadSection />

      {/* ── Stat cards row ────────────────────────────────────── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: '12px',
        flexShrink: 0,
      }}>
        {STAT_CARDS.map((s) => <StatCard key={s.label} {...s} />)}
      </div>

      {/* ── Bottom panels row ─────────────────────────────────── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 390px',
        gap: '12px',
        flex: 1,
        minHeight: 0,
      }}>

        {/* ── Graph panel ─────────────────────────────────────── */}
        <div style={{
          background: PANEL_BG,
          border: PANEL_BORDER,
          borderRadius: PANEL_RADIUS,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          minHeight: 380,
        }}>
          {/* Panel header */}
          <div style={{
            padding: '14px 16px 13px',
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexShrink: 0,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '9px' }}>
              <DotsIcon />
              <span style={{
                fontSize: '14px', fontWeight: 600,
                color: '#ffffff',
                fontFamily: 'Inter, system-ui, sans-serif',
              }}>
                Overall Code Structure Overview
              </span>
            </div>
            <IconBtn
              title="Results overview"
              onClick={() => setShowOverview(v => !v)}
              active={showOverview}
            >
              <Columns2 size={13} />
            </IconBtn>
          </div>

          {/* Graph canvas */}
          <div style={{ flex: 1, position: 'relative', minHeight: 0 }}>
            {loadingGraph ? (
              <div style={{
                position: 'absolute', inset: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <div style={{
                  width: 28, height: 28, borderRadius: '50%',
                  border: '2px solid rgba(255,255,255,0.08)',
                  borderTopColor: 'rgba(255,255,255,0.45)',
                  animation: 'spin 0.8s linear infinite',
                }} />
              </div>
            ) : previewNodes.length > 0 ? (
              <VisGraph ref={graphRef} nodes={previewNodes} edges={previewEdges} />
            ) : (
              <div style={{
                position: 'absolute', inset: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <p style={{ fontSize: '13px', color: 'rgba(255,255,255,0.28)' }}>
                  No graph data — ingest a codebase first
                </p>
              </div>
            )}

            {/* Results overview slide-in — uses full dataset, not preview subset */}
            {showOverview && (
              <ResultsOverview
                nodes={allNodes}
                edges={allEdges}
                onClose={() => setShowOverview(false)}
              />
            )}

            {/* Zoom controls — bottom-right (shifts left when overview open) */}
            <div style={{
              position: 'absolute',
              right: showOverview ? 222 : 12,
              bottom: 12,
              display: 'flex', flexDirection: 'column', gap: '4px',
              transition: 'right 0.2s ease',
            }}>
              <IconBtn onClick={() => graphRef.current?.zoomIn()}    title="Zoom in">    <ZoomIn    size={13} /></IconBtn>
              <IconBtn onClick={() => graphRef.current?.zoomOut()}   title="Zoom out">   <ZoomOut   size={13} /></IconBtn>
              <IconBtn onClick={() => graphRef.current?.fitScreen()} title="Fit screen"> <Maximize2 size={13} /></IconBtn>
            </div>
          </div>
        </div>

        {/* ── Pie chart panel ─────────────────────────────────── */}
        <div style={{
          background: PANEL_BG,
          border: PANEL_BORDER,
          borderRadius: PANEL_RADIUS,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          minHeight: 380,
        }}>
          {/* Panel header */}
          <div style={{
            padding: '14px 16px 13px',
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            display: 'flex',
            alignItems: 'center',
            gap: '9px',
            flexShrink: 0,
          }}>
            <DotsIcon />
            <span style={{
              fontSize: '14px', fontWeight: 600,
              color: '#ffffff',
              fontFamily: 'Inter, system-ui, sans-serif',
            }}>
              Code Entity Count by Language
            </span>
          </div>

          {/* Pie chart — absolutely-positioned inner div gives Recharts a real pixel height */}
          <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
            <div style={{ position: 'absolute', inset: 0, padding: '8px 8px 4px', display: 'flex', flexDirection: 'column' }}>
              <LanguageDonut data={langData} />
            </div>
          </div>
        </div>

      </div>

      {/* Scroll breathing room — sits after flex:1 grid, forces 24px overflow */}
      <div style={{ height: 24, flexShrink: 0 }} />
    </div>
  )
}
