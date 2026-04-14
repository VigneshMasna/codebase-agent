import React, { useState } from 'react'
import { PieChart, Pie, Cell, Sector, Tooltip, ResponsiveContainer } from 'recharts'

/* ── Language-aware colour palette ───────────────────────────── */
const LANG_COLORS = {
  // JVM
  java:       '#4DC9C8', Java:       '#4DC9C8',
  kotlin:     '#7F52FF', Kotlin:     '#7F52FF',
  scala:      '#DC322F', Scala:      '#DC322F',
  groovy:     '#4298B8', Groovy:     '#4298B8',
  // C-family
  c:          '#E07840', C:          '#E07840',
  'c++':      '#5B6EE0', 'C++':      '#5B6EE0',
  cpp:        '#5B6EE0', Cpp:        '#5B6EE0',
  'c#':       '#9B4F96', 'C#':       '#9B4F96',
  csharp:     '#9B4F96', CSharp:     '#9B4F96',
  // Scripting
  python:     '#F5D547', Python:     '#F5D547',
  ruby:       '#CC342D', Ruby:       '#CC342D',
  php:        '#777BB4', PHP:        '#777BB4',
  lua:        '#00007C', Lua:        '#00007C',
  perl:       '#39457E', Perl:       '#39457E',
  // Web
  javascript: '#F7CA18', JavaScript: '#F7CA18',
  js:         '#F7CA18', JS:         '#F7CA18',
  typescript: '#3178C6', TypeScript: '#3178C6',
  ts:         '#3178C6', TS:         '#3178C6',
  html:       '#E44D26', HTML:       '#E44D26',
  css:        '#264DE4', CSS:        '#264DE4',
  // Systems
  go:         '#00ADD8', Go:         '#00ADD8',
  golang:     '#00ADD8', Golang:     '#00ADD8',
  rust:       '#CE422B', Rust:       '#CE422B',
  zig:        '#F7A41D', Zig:        '#F7A41D',
  // Mobile
  swift:      '#FA7343', Swift:      '#FA7343',
  // Data / config
  r:          '#276DC3', R:          '#276DC3',
  matlab:     '#0076A8', Matlab:     '#0076A8',
  // Fallback
  unknown:    '#E054A4', Unknown:    '#E054A4',
}
const FALLBACK_PALETTE = [
  '#4DC9C8','#5B6EE0','#E07840','#E054A4',
  '#8B5CF6','#F472B6','#34D399','#FBBF24',
  '#60A5FA','#FB923C','#A78BFA','#4ADE80',
]

function getColor(name, i) {
  return LANG_COLORS[name] ?? FALLBACK_PALETTE[i % FALLBACK_PALETTE.length]
}

/* ── Active (expanded) slice shape ───────────────────────────── */
function ActiveSlice(props) {
  const { cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill } = props
  return (
    <g>
      <Sector
        cx={cx} cy={cy}
        innerRadius={innerRadius}
        outerRadius={outerRadius + 10}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
        opacity={1}
      />
      {/* Subtle outer ring */}
      <Sector
        cx={cx} cy={cy}
        innerRadius={outerRadius + 13}
        outerRadius={outerRadius + 16}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
        opacity={0.35}
      />
    </g>
  )
}

/* ── Number label outside each slice ─────────────────────────── */
function OuterLabel({ cx, cy, midAngle, outerRadius, value, percent, index, activeIndex }) {
  if (percent < 0.04) return null
  const RAD = Math.PI / 180
  const bump = index === activeIndex ? 10 : 0
  const r = outerRadius + 24 + bump
  const x = cx + r * Math.cos(-midAngle * RAD)
  const y = cy + r * Math.sin(-midAngle * RAD)
  const isActive = index === activeIndex
  return (
    <text
      x={x} y={y}
      textAnchor="middle" dominantBaseline="central"
      style={{
        fontSize: isActive ? '14px' : '12px',
        fontWeight: isActive ? 700 : 600,
        fill: isActive ? '#ffffff' : 'rgba(255,255,255,0.70)',
        fontFamily: 'Inter, system-ui, sans-serif',
        transition: 'font-size 0.15s',
      }}
    >
      {value}
    </text>
  )
}

/* ── Tooltip ──────────────────────────────────────────────────── */
function CustomTooltip({ active, payload, total }) {
  if (!active || !payload?.length) return null
  const { name, value, payload: entry } = payload[0]
  const pct = total > 0 ? ((value / total) * 100).toFixed(1) : 0
  const color = entry?.fill || '#fff'
  return (
    <div style={{
      padding: '10px 14px',
      background: '#1e1f26',
      border: `1px solid ${color}55`,
      borderRadius: '10px',
      boxShadow: `0 4px 20px rgba(0,0,0,0.5), 0 0 0 1px ${color}22`,
      minWidth: 140,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '7px', marginBottom: '6px' }}>
        <span style={{ width: 10, height: 10, borderRadius: '2px', background: color, flexShrink: 0 }} />
        <span style={{ fontSize: '13px', fontWeight: 700, color: '#fff' }}>{name}</span>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px' }}>
        <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.45)' }}>Entities</span>
        <span style={{ fontSize: '11px', fontWeight: 600, color: '#fff', fontFamily: 'monospace' }}>{value}</span>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', marginTop: '3px' }}>
        <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.45)' }}>Share</span>
        <span style={{ fontSize: '11px', fontWeight: 600, color, fontFamily: 'monospace' }}>{pct}%</span>
      </div>
    </div>
  )
}

/* ── Main component ───────────────────────────────────────────── */
export default function LanguageDonut({ data = [] }) {
  const [activeIndex, setActiveIndex] = useState(null)

  if (!data.length) {
    return (
      <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
        <p style={{ fontSize: '13px', color: 'rgba(255,255,255,0.35)' }}>
          No data yet — ingest a codebase first
        </p>
      </div>
    )
  }

  const total = data.reduce((s, d) => s + d.value, 0)

  // Attach color to each data entry so tooltip can read it
  const coloredData = data.map((d, i) => ({ ...d, fill: getColor(d.name, i) }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>

      {/* Pie chart — minHeight gives ResponsiveContainer a real pixel anchor */}
      <div style={{ flex: 1, minHeight: 200, minWidth: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={coloredData}
              cx="50%"
              cy="50%"
              outerRadius="62%"
              paddingAngle={0.5}
              dataKey="value"
              labelLine={false}
              label={(props) => <OuterLabel {...props} activeIndex={activeIndex} />}
              activeIndex={activeIndex}
              activeShape={ActiveSlice}
              stroke="none"
              startAngle={90}
              endAngle={-270}
              onMouseEnter={(_, i) => setActiveIndex(i)}
              onMouseLeave={() => setActiveIndex(null)}
              style={{ cursor: 'pointer', outline: 'none' }}
            >
              {coloredData.map((entry, i) => (
                <Cell
                  key={i}
                  fill={entry.fill}
                  opacity={activeIndex === null || activeIndex === i ? 1 : 0.40}
                  style={{ transition: 'opacity 0.18s ease' }}
                />
              ))}
            </Pie>
            <Tooltip content={(props) => <CustomTooltip {...props} total={total} />} />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '14px',
        paddingBottom: '14px',
        paddingTop: '4px',
        flexWrap: 'wrap',
        rowGap: '8px',
      }}>
        {coloredData.map((entry, i) => {
          const isActive = activeIndex === i
          const pct = ((entry.value / total) * 100).toFixed(0)
          return (
            <div
              key={i}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                cursor: 'pointer',
                padding: '3px 8px', borderRadius: '6px',
                background: isActive ? `${entry.fill}18` : 'transparent',
                border: `1px solid ${isActive ? entry.fill + '55' : 'transparent'}`,
                transition: 'background 0.15s, border-color 0.15s',
              }}
              onMouseEnter={() => setActiveIndex(i)}
              onMouseLeave={() => setActiveIndex(null)}
            >
              <span style={{
                width: 10, height: 10, borderRadius: '2px', flexShrink: 0,
                background: entry.fill,
                boxShadow: isActive ? `0 0 6px ${entry.fill}` : 'none',
                transition: 'box-shadow 0.15s',
              }} />
              <span style={{
                fontSize: '12px',
                color: isActive ? '#ffffff' : 'rgba(255,255,255,0.65)',
                fontFamily: 'Inter, system-ui, sans-serif',
                fontWeight: isActive ? 600 : 400,
                transition: 'color 0.15s',
              }}>
                {entry.name}
              </span>
              <span style={{
                fontSize: '11px',
                color: isActive ? entry.fill : 'rgba(255,255,255,0.35)',
                fontFamily: 'monospace',
                fontWeight: 600,
                transition: 'color 0.15s',
              }}>
                {pct}%
              </span>
            </div>
          )
        })}
      </div>

    </div>
  )
}
