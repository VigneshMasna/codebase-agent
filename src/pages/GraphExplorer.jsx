import React, { useEffect, useRef, useState, useCallback } from 'react'
import { AlertCircle, ZoomIn, ZoomOut, Maximize2, RefreshCw } from 'lucide-react'
import VisGraph from '../components/graph/VisGraph'
import { GraphLegend, FilterBar } from '../components/graph/GraphControls'
import NodeDetailPanel from '../components/graph/NodeDetailPanel'
import { getGraph } from '../api/client'

const FONT        = 'Inter, system-ui, sans-serif'
const FLOAT_BG    = 'rgba(18,19,23,0.94)'
const FLOAT_BLUR  = 'blur(14px)'
const FLOAT_STYLE = {
  background:          FLOAT_BG,
  border:              '1px solid rgba(255,255,255,0.08)',
  backdropFilter:      FLOAT_BLUR,
  WebkitBackdropFilter: FLOAT_BLUR,
  boxShadow:           '0 4px 20px rgba(0,0,0,0.50)',
}

export default function GraphExplorer() {
  const graphRef = useRef(null)

  const [nodes,        setNodes]    = useState([])
  const [edges,        setEdges]    = useState([])
  const [loading,      setLoading]  = useState(true)
  const [error,        setError]    = useState(null)
  const [filterLabel,  setFilter]   = useState('all')
  const [selectedNode, setSelected] = useState(null)
  const [hoveredNode,  setHovered]  = useState(null)
  const hoverTimerRef               = useRef(null)

  const handleNodeHover = useCallback((node) => {
    clearTimeout(hoverTimerRef.current)
    if (node) {
      hoverTimerRef.current = setTimeout(() => setHovered(node), 150)
    } else {
      hoverTimerRef.current = setTimeout(() => setHovered(null), 320)
    }
  }, [])

  const panelNode = selectedNode || hoveredNode

  const fetchGraph = useCallback(() => {
    setLoading(true)
    setError(null)
    getGraph({ node_limit: 2000 })
      .then(({ data }) => {
        setNodes(data.nodes || [])
        setEdges(data.edges || [])
        setLoading(false)
      })
      .catch((e) => {
        setError(e.response?.data?.detail || e.message)
        setLoading(false)
      })
  }, [])

  useEffect(() => { fetchGraph() }, [fetchGraph])

  const vulnCount  = nodes.filter(n => n.is_buggy).length
  const entryCount = nodes.filter(n => n.is_entry_point).length
  const ready      = !loading && !error && nodes.length > 0

  const filteredCount = !ready ? 0
    : filterLabel === 'all'   ? nodes.length
    : filterLabel === 'buggy' ? nodes.filter(n => n.is_buggy).length
    : filterLabel === 'Class' ? nodes.filter(n => ['Class', 'Interface', 'Struct', 'Enum'].includes(n.label)).length
    : nodes.filter(n => n.label === filterLabel).length

  return (
    <div style={{
      position: 'relative', width: '100%', height: '100%',
      display: 'flex', flexDirection: 'column',
      background: '#111215',
      fontFamily: FONT,
    }}>

      {/* ── Loading spinner ───────────────────────────────────── */}
      {loading && (
        <div style={{
          position: 'absolute', inset: 0, zIndex: 30,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          pointerEvents: 'none',
        }}>
          <div style={{
            width: 28, height: 28, borderRadius: '50%',
            border: '2px solid rgba(255,255,255,0.08)',
            borderTopColor: 'rgba(255,255,255,0.45)',
            animation: 'spin 0.8s linear infinite',
          }} />
        </div>
      )}

      {/* ── Error state ───────────────────────────────────────── */}
      {error && !loading && (
        <div style={{
          position: 'absolute', inset: 0, zIndex: 30,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 10,
        }}>
          <AlertCircle size={24} color="#f87171" />
          <p style={{ fontSize: 13, color: '#f87171', maxWidth: 340, textAlign: 'center', padding: '0 20px' }}>
            {error}
          </p>
          <button
            onClick={fetchGraph}
            style={{
              marginTop: 4, padding: '6px 16px', borderRadius: 7,
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.10)',
              color: 'rgba(255,255,255,0.70)',
              fontSize: 12, fontWeight: 500, fontFamily: FONT, cursor: 'pointer',
              transition: 'background 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.10)'}
            onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.06)'}
          >
            Retry
          </button>
        </div>
      )}

      {/* ── Empty state ───────────────────────────────────────── */}
      {!loading && !error && nodes.length === 0 && (
        <div style={{
          position: 'absolute', inset: 0, zIndex: 30,
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 8,
        }}>
          <p style={{
            fontSize: 14, fontWeight: 500,
            color: 'rgba(255,255,255,0.35)',
            fontFamily: FONT,
          }}>
            Graph is not available
          </p>
          <p style={{
            fontSize: 12,
            color: 'rgba(255,255,255,0.20)',
            fontFamily: FONT,
          }}>
            Ingest a codebase from the Dashboard to get started
          </p>
        </div>
      )}

      {/* ── Filter bar — only when data is ready ─────────────── */}
      {ready && (
        <FilterBar filterLabel={filterLabel} onFilterChange={setFilter} />
      )}

      {/* ── Graph canvas ──────────────────────────────────────── */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {ready && (
          <VisGraph
            ref={graphRef}
            nodes={nodes}
            edges={edges}
            onNodeClick={d => setSelected(prev => prev?.uid === d.uid ? null : d)}
            onNodeHover={handleNodeHover}
            filterLabel={filterLabel}
          />
        )}

        {/* ── Filter-empty state ────────────────────────────── */}
        {ready && filteredCount === 0 && (
          <div style={{
            position: 'absolute', inset: 0, zIndex: 25,
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 8,
            pointerEvents: 'none',
          }}>
            <p style={{
              fontSize: 14, fontWeight: 500,
              color: 'rgba(255,255,255,0.35)',
              fontFamily: FONT, margin: 0,
            }}>
              No {filterLabel === 'buggy' ? 'buggy' : filterLabel.toLowerCase()} nodes found
            </p>
            <p style={{
              fontSize: 12,
              color: 'rgba(255,255,255,0.20)',
              fontFamily: FONT, margin: 0,
            }}>
              Try a different filter
            </p>
          </div>
        )}

        {/* ── Zoom + controls — only when ready ─────────────── */}
        {ready && (
          <div style={{
            position: 'absolute', top: 14, zIndex: 20,
            right: panelNode ? 'calc(18rem + 14px)' : 14,
            display: 'flex', flexDirection: 'column', gap: 6,
            transition: 'right 0.20s ease',
          }}>
            {/* Zoom cluster */}
            <div style={{
              ...FLOAT_STYLE,
              borderRadius: 10,
              padding: 4,
              display: 'flex', flexDirection: 'column', gap: 1,
            }}>
              {[
                [() => graphRef.current?.zoomIn(),    'Zoom in',     ZoomIn],
                [() => graphRef.current?.zoomOut(),   'Zoom out',    ZoomOut],
                [() => graphRef.current?.fitScreen(), 'Fit all',     Maximize2],
                [fetchGraph,                           'Reload data', RefreshCw],
              ].map(([onClick, title, Icon]) => (
                <button
                  key={title}
                  onClick={onClick}
                  title={title}
                  style={{
                    width: 30, height: 30, borderRadius: 7,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: 'transparent', border: 'none',
                    color: 'rgba(255,255,255,0.38)',
                    cursor: 'pointer',
                    transition: 'background 0.15s, color 0.15s',
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.background = 'rgba(255,255,255,0.06)'
                    e.currentTarget.style.color = 'rgba(255,255,255,0.80)'
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background = 'transparent'
                    e.currentTarget.style.color = 'rgba(255,255,255,0.38)'
                  }}
                >
                  <Icon size={14} strokeWidth={1.7} />
                </button>
              ))}
            </div>

          </div>
        )}

        {/* ── Legend — only when ready ──────────────────────── */}
        {ready && <GraphLegend />}

        <NodeDetailPanel
          node={panelNode}
          locked={!!selectedNode}
          onClose={() => { setSelected(null); setHovered(null) }}
        />
      </div>

      {/* ── Stats strip — only when ready ─────────────────────── */}
      {ready && (
        <div style={{
          flexShrink: 0,
          display: 'flex', alignItems: 'center', gap: 20,
          padding: '7px 20px',
          borderTop: '1px solid rgba(255,255,255,0.06)',
          fontFamily: FONT,
        }}>
          <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.35)' }}>
            <b style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 600, color: 'rgba(255,255,255,0.75)', marginRight: 4 }}>{nodes.length}</b>
            nodes
          </span>
          <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.35)' }}>
            <b style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 600, color: 'rgba(255,255,255,0.75)', marginRight: 4 }}>{edges.length}</b>
            edges
          </span>
          <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.35)' }}>
            <b style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 600, color: '#f87171', marginRight: 4 }}>{vulnCount}</b>
            bugs
          </span>
          <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.35)' }}>
            <b style={{ fontFamily: 'JetBrains Mono, monospace', fontWeight: 600, color: '#4ade80', marginRight: 4 }}>{entryCount}</b>
            entries
          </span>
          <span style={{
            marginLeft: 'auto', fontSize: 10,
            fontFamily: 'JetBrains Mono, monospace',
            color: 'rgba(255,255,255,0.18)',
          }}>
            vis-network · {nodes.length} / 2000
          </span>
        </div>
      )}
    </div>
  )
}
