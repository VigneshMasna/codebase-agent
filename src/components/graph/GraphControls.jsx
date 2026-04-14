import React from 'react'

const FONT = 'Inter, system-ui, sans-serif'

const FILTERS = [
  { value: 'all',      label: 'All'       },
  { value: 'Function', label: 'Functions' },
  { value: 'Class',    label: 'Classes'   },
  { value: 'buggy',    label: 'Bugs'      },
]

/* ── Shared floating panel surface ───────────────────────────── */
const FLOAT_BG     = 'rgba(18,19,23,0.94)'
const FLOAT_BORDER = '1px solid rgba(255,255,255,0.08)'
const FLOAT_SHADOW = '0 4px 20px rgba(0,0,0,0.50)'
const FLOAT_BLUR   = 'blur(14px)'

export function FilterBar({ filterLabel, onFilterChange }) {
  return (
    <div
      style={{
        position: 'absolute', top: 14, left: 14,
        display: 'flex', alignItems: 'center', gap: 2,
        zIndex: 20,
        padding: 4, borderRadius: 10,
        background: FLOAT_BG,
        border: FLOAT_BORDER,
        backdropFilter: FLOAT_BLUR,
        WebkitBackdropFilter: FLOAT_BLUR,
        boxShadow: FLOAT_SHADOW,
        fontFamily: FONT,
      }}
    >
      {FILTERS.map((f) => {
        const isActive = filterLabel === f.value
        return (
          <button
            key={f.value}
            onClick={() => onFilterChange(f.value)}
            style={{
              padding: '5px 12px',
              borderRadius: 7,
              fontSize: 12,
              fontWeight: isActive ? 500 : 400,
              fontFamily: FONT,
              background: isActive ? 'rgba(255,255,255,0.08)' : 'transparent',
              border: isActive ? '1px solid rgba(255,255,255,0.10)' : '1px solid transparent',
              color: isActive ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.40)',
              cursor: 'pointer',
              transition: 'background 0.15s, color 0.15s, border-color 0.15s',
              whiteSpace: 'nowrap',
            }}
            onMouseEnter={e => {
              if (!isActive) {
                e.currentTarget.style.background = 'rgba(255,255,255,0.04)'
                e.currentTarget.style.color = 'rgba(255,255,255,0.62)'
              }
            }}
            onMouseLeave={e => {
              if (!isActive) {
                e.currentTarget.style.background = 'transparent'
                e.currentTarget.style.color = 'rgba(255,255,255,0.40)'
              }
            }}
          >
            {f.label}
          </button>
        )
      })}
    </div>
  )
}

export function GraphLegend() {
  // Colors taken directly from NODE_HUE in VisGraph.jsx
  const nodeItems = [
    { label: 'Function',  color: '#e29480' },  // soft coral
    { label: 'Class',     color: '#d8a48f' },  // muted peach
    { label: 'Enum',      color: '#bda978' },  // muted gold
    { label: 'File',      color: '#55c4e5' },  // calm blue
    { label: 'Entry Pt',  color: '#b5ce9e' },  // soft green  (_entry)
    { label: 'Buggy',     color: '#e29480' },  // soft coral  (_buggy — same as Function)
    { label: 'External',  color: '#c2d3cd' },  // soft gray-green
  ]
  return (
    <div style={{
      position: 'absolute', bottom: 14, left: 14, zIndex: 20,
      padding: '11px 13px',
      borderRadius: 10,
      background: FLOAT_BG,
      border: FLOAT_BORDER,
      backdropFilter: FLOAT_BLUR,
      WebkitBackdropFilter: FLOAT_BLUR,
      boxShadow: FLOAT_SHADOW,
      fontFamily: FONT,
      minWidth: 130,
    }}>

      {/* Nodes */}
      <p style={{
        fontSize: 9, fontWeight: 600, letterSpacing: '0.08em',
        textTransform: 'uppercase', color: 'rgba(255,255,255,0.22)',
        margin: '0 0 7px',
      }}>
        Nodes
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
        {nodeItems.map(it => (
          <div key={it.label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{
              width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
              background: it.color,
            }} />
            <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.48)', fontFamily: FONT }}>
              {it.label}
            </span>
          </div>
        ))}
      </div>


    </div>
  )
}
