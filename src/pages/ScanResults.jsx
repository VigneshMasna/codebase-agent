import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  AlertCircle, AlertTriangle, Info, CheckCircle,
  ChevronDown, Search, ShieldCheck, Radar, FileCode,
} from 'lucide-react'
import { getScanResults } from '../api/client'
import DotsIcon from '../components/ui/DotsIcon'
import useCountUp from '../hooks/useCountUp'

const FONT = 'Inter, system-ui, sans-serif'
const MONO = 'JetBrains Mono, monospace'

/* ── Dashboard tokens ─────────────────────────────────────────── */
const CARD_BG     = '#18191d'
const CARD_BORDER = '1px solid rgba(255,255,255,0.08)'
const CARD_RADIUS = 10

const SEV_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3, SAFE: 4 }

const SEV = {
  CRITICAL: { fg: 'rgba(248,113,113,0.72)', accent: 'rgba(248,113,113,0.30)', Icon: AlertCircle  },
  HIGH:     { fg: 'rgba(251,146,60,0.72)',  accent: 'rgba(251,146,60,0.30)',  Icon: AlertTriangle },
  MEDIUM:   { fg: 'rgba(215,170,50,0.75)',  accent: 'rgba(215,170,50,0.30)', Icon: Info          },
  LOW:      { fg: 'rgba(74,222,128,0.62)',  accent: 'rgba(74,222,128,0.25)', Icon: CheckCircle   },
}


/* ── Severity stat card ─────────────────────────────────────────
   Always neutral background (never tinted) — active state shown
   only via colored number + thin bottom accent line.             */
function SevCard({ sev, count, active, onClick, index }) {
  const cfg   = SEV[sev]
  const shown = useCountUp(count)

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05, duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
      onClick={onClick}
      style={{
        borderRadius: CARD_RADIUS,
        padding: '20px 22px 18px',
        display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
        background: CARD_BG,
        border: CARD_BORDER,
        borderBottom: active ? `2px solid ${cfg.accent}` : CARD_BORDER,
        height: 148,
        boxSizing: 'border-box',
        cursor: 'pointer',
        transition: 'border-bottom-color 0.18s ease',
        userSelect: 'none',
        position: 'relative', overflow: 'hidden',
      }}
    >
      {/* Top: grip + label + icon */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <DotsIcon />
          <span style={{
            fontSize: 15, fontWeight: 500, fontFamily: FONT,
            color: 'rgba(255,255,255,0.85)',
          }}>
            {sev.charAt(0) + sev.slice(1).toLowerCase()}
          </span>
        </div>
        <cfg.Icon size={13} color={cfg.fg} strokeWidth={1.8} style={{ opacity: active ? 1 : 0.5 }} />
      </div>

      {/* Big number */}
      <p style={{
        fontSize: 64, fontWeight: 800, lineHeight: 1,
        fontFamily: FONT, letterSpacing: '-0.02em',
        color: active ? cfg.fg : '#ffffff',
        margin: 0,
        transition: 'color 0.18s ease',
      }}>
        {shown}
      </p>
    </motion.div>
  )
}

/* ── Severity badge pill ───────────────────────────────────────── */
function SevBadge({ sev }) {
  const cfg = SEV[sev?.toUpperCase()] || {
    fg: 'rgba(255,255,255,0.32)', accent: 'rgba(255,255,255,0.08)',
  }
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      fontSize: 10, fontWeight: 600, fontFamily: FONT,
      padding: '2px 7px', borderRadius: 999,
      color: cfg.fg,
      background: cfg.fg.replace(/[\d.]+\)$/, '0.08)'),
      border: `1px solid ${cfg.fg.replace(/[\d.]+\)$/, '0.15)')}`,
      letterSpacing: '0.05em', textTransform: 'uppercase', flexShrink: 0,
    }}>
      {sev}
    </span>
  )
}

/* ── Mini stat block ───────────────────────────────────────────── */
function StatBlock({ label, value }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      padding: '6px 16px', borderRadius: 8,
      background: 'rgba(255,255,255,0.025)',
      border: '1px solid rgba(255,255,255,0.06)',
      minWidth: 56,
    }}>
      <span style={{
        fontSize: 15, fontWeight: 700, fontFamily: MONO,
        color: 'rgba(255,255,255,0.62)', lineHeight: 1,
      }}>
        {value}
      </span>
      <span style={{
        fontSize: 11, fontFamily: FONT,
        color: 'rgba(255,255,255,0.30)',
        marginTop: 4, whiteSpace: 'nowrap',
      }}>
        {label}
      </span>
    </div>
  )
}

/* ── Result card ───────────────────────────────────────────────── */
function VulnCard({ vuln, index }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = SEV[vuln.severity?.toUpperCase()] || SEV.LOW

  const hasBody    = !!vuln.body?.trim()
  const hasDesc    = !!(vuln.bug_explanation || vuln.summary)
  const hasDetails = hasDesc || hasBody

  const stats = [
    vuln.impact_score > 0 && { label: 'Impact', value: typeof vuln.impact_score === 'number' ? vuln.impact_score.toFixed(1) : vuln.impact_score },
    vuln.layer != null    && { label: 'Layer',  value: vuln.layer },
  ].filter(Boolean)

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.26, ease: [0.16, 1, 0.3, 1] }}
      style={{
        background: CARD_BG,
        border: CARD_BORDER,
        borderLeft: `2px solid ${cfg.fg.replace(/[\d.]+\)$/, '0.35)')}`,
        borderRadius: CARD_RADIUS,
        overflow: 'hidden',
        transition: 'box-shadow 0.18s ease',
      }}
    >
      {/* Header */}
      <button
        onClick={() => hasDetails && setExpanded(s => !s)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 12,
          padding: '13px 16px', textAlign: 'left',
          cursor: hasDetails ? 'pointer' : 'default',
          background: 'transparent', border: 'none',
          borderBottom: expanded ? '1px solid rgba(255,255,255,0.06)' : '1px solid transparent',
          transition: 'background 0.15s ease, border-color 0.18s ease',
          fontFamily: FONT,
        }}
        onMouseEnter={e => { if (hasDetails) e.currentTarget.style.background = 'rgba(255,255,255,0.02)' }}
        onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Badge + name */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <SevBadge sev={vuln.severity} />
            <span style={{
              fontSize: 15, fontWeight: 600, fontFamily: MONO,
              color: 'rgba(255,255,255,0.88)',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {vuln.function_name || vuln.name}
            </span>
          </div>

          {/* File + line */}
          {vuln.file && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 6 }}>
              <FileCode size={11} color="rgba(255,255,255,0.22)" strokeWidth={1.6} />
              <span style={{
                fontSize: 12, fontFamily: MONO, color: 'rgba(255,255,255,0.32)',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {vuln.file}
                {vuln.line_start != null && (
                  <span style={{ color: 'rgba(255,255,255,0.18)', marginLeft: 3 }}>
                    :{vuln.line_start}
                  </span>
                )}
              </span>
            </div>
          )}
        </div>

        {/* Chevron */}
        {hasDetails && (
          <div style={{
            flexShrink: 0, color: 'rgba(255,255,255,0.22)',
            transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.22s cubic-bezier(0.16,1,0.3,1)',
          }}>
            <ChevronDown size={13} strokeWidth={1.8} />
          </div>
        )}
      </button>

      {/* Expanded body */}
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.26, ease: [0.16, 1, 0.3, 1] }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{
              padding: '16px 18px 18px',
              display: 'flex', flexDirection: 'column', gap: 14,
            }}>

              {/* Description */}
              {hasDesc && (
                <div>
                  <p style={{
                    fontSize: 11, fontWeight: 600, fontFamily: FONT,
                    letterSpacing: '0.06em', textTransform: 'uppercase',
                    color: 'rgba(255,255,255,0.25)', margin: '0 0 8px',
                  }}>
                    {vuln.bug_explanation ? 'Analysis' : 'Description'}
                  </p>
                  <p style={{
                    fontSize: 13, lineHeight: 1.75, fontFamily: FONT,
                    color: 'rgba(255,255,255,0.62)', margin: 0,
                    paddingLeft: 12,
                    borderLeft: '2px solid rgba(255,255,255,0.08)',
                  }}>
                    {vuln.bug_explanation || vuln.summary}
                  </p>
                </div>
              )}

              {/* Code block */}
              {hasBody && (
                <div style={{
                  borderRadius: 8, overflow: 'hidden',
                  background: '#111215',
                  border: '1px solid rgba(255,255,255,0.06)',
                }}>
                  <div style={{
                    padding: '6px 13px',
                    borderBottom: '1px solid rgba(255,255,255,0.05)',
                    display: 'flex', alignItems: 'center', gap: 6,
                    background: 'rgba(255,255,255,0.015)',
                  }}>
                    <FileCode size={11} color="rgba(255,255,255,0.22)" strokeWidth={1.6} />
                    <span style={{ fontSize: 11, fontFamily: MONO, color: 'rgba(255,255,255,0.30)' }}>
                      {vuln.file || 'source'}{vuln.line_start != null && `:${vuln.line_start}`}
                    </span>
                  </div>
                  <pre style={{
                    margin: 0, padding: '12px 16px',
                    fontSize: 13, fontFamily: MONO, lineHeight: 1.68,
                    color: 'rgba(255,255,255,0.65)',
                    overflowX: 'auto', whiteSpace: 'pre',
                    maxHeight: 300, overflowY: 'auto',
                  }}>
                    {vuln.body}
                  </pre>
                </div>
              )}

              {/* Stat blocks */}
              {stats.length > 0 && (
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {stats.map(s => <StatBlock key={s.label} label={s.label} value={s.value} />)}
                </div>
              )}

            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

/* ═══════════════════════════════════════════════════════════════ */
export default function ScanResults() {
  const [results,   setResults]   = useState([])
  const [loading,   setLoading]   = useState(true)
  const [search,    setSearch]    = useState('')
  const [sevFilter, setSevFilter] = useState('all')

  useEffect(() => {
    getScanResults()
      .then(({ data }) => setResults(data.results || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const counts = {
    CRITICAL: results.filter(r => r.severity === 'CRITICAL').length,
    HIGH:     results.filter(r => r.severity === 'HIGH').length,
    MEDIUM:   results.filter(r => r.severity === 'MEDIUM').length,
    LOW:      results.filter(r => r.severity === 'LOW').length,
  }

  const filtered = results
    .filter(r => {
      if (sevFilter !== 'all' && r.severity !== sevFilter) return false
      if (search) {
        const q = search.toLowerCase()
        return (r.function_name || r.name || '').toLowerCase().includes(q)
            || (r.file || '').toLowerCase().includes(q)
      }
      return true
    })
    .sort((a, b) => (SEV_ORDER[a.severity] ?? 9) - (SEV_ORDER[b.severity] ?? 9))

  const FILTER_TABS = ['all', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW']

  const activeSummary = Object.entries(counts)
    .filter(([, n]) => n > 0)
    .map(([s, n]) => `${s.charAt(0) + s.slice(1).toLowerCase()}: ${n}`)
    .join(' · ')

  return (
    <div style={{
      padding: 14,
      display: 'flex', flexDirection: 'column', gap: 12,
      height: '100%', boxSizing: 'border-box',
      overflowY: 'auto', background: '#111215',
      fontFamily: FONT,
    }}>

      {/* ── Severity stat cards ───────────────────────────────── */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
        gap: 12, flexShrink: 0,
      }}>
        {Object.entries(counts).map(([sev, count], i) => (
          <SevCard
            key={sev} sev={sev} count={count} index={i}
            active={sevFilter === sev}
            onClick={() => setSevFilter(sevFilter === sev ? 'all' : sev)}
          />
        ))}
      </div>

      {/* ── Search + filter ───────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0, flexWrap: 'wrap' }}>
        <div style={{
          flex: 1, minWidth: 180,
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '0 14px', height: 38,
          background: CARD_BG, border: CARD_BORDER, borderRadius: CARD_RADIUS,
        }}>
          <Search size={13} color="rgba(255,255,255,0.22)" strokeWidth={1.8} style={{ flexShrink: 0 }} />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search functions or files…"
            style={{
              flex: 1, background: 'transparent', border: 'none', outline: 'none',
              fontSize: 13, fontFamily: FONT, color: 'rgba(255,255,255,0.72)',
            }}
          />
        </div>

        <div style={{
          display: 'flex', alignItems: 'center', gap: 2,
          padding: 4, borderRadius: CARD_RADIUS,
          background: CARD_BG, border: CARD_BORDER,
        }}>
          {FILTER_TABS.map(tab => {
            const isActive = sevFilter === tab
            return (
              <button
                key={tab}
                onClick={() => setSevFilter(tab)}
                style={{
                  padding: '5px 13px', borderRadius: 7,
                  fontSize: 13, fontWeight: isActive ? 500 : 400, fontFamily: FONT,
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
                {tab === 'all' ? 'All' : tab.charAt(0) + tab.slice(1).toLowerCase()}
              </button>
            )
          })}
        </div>
      </div>

      {/* ── Results list ──────────────────────────────────────── */}
      {loading ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{
            width: 26, height: 26, borderRadius: '50%',
            border: '2px solid rgba(255,255,255,0.08)',
            borderTopColor: 'rgba(255,255,255,0.40)',
            animation: 'spin 0.8s linear infinite',
          }} />
        </div>

      ) : filtered.length === 0 ? (
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 14,
        }}>
          <div style={{
            width: 56, height: 56, borderRadius: 14,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'rgba(74,222,128,0.05)',
            border: '1px solid rgba(74,222,128,0.12)',
          }}>
            <ShieldCheck size={26} color="rgba(74,222,128,0.48)" strokeWidth={1.5} />
          </div>
          <p style={{ fontSize: 17, fontWeight: 500, color: 'rgba(255,255,255,0.40)', margin: 0, fontFamily: FONT, textAlign: 'center' }}>
            {results.length === 0 ? 'No scan results yet' : 'No matching results'}
          </p>
          <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.22)', margin: 0, fontFamily: FONT, textAlign: 'center' }}>
            {results.length === 0 ? 'Ingest a codebase first to run vulnerability analysis' : 'Try adjusting your search or filter'}
          </p>
        </div>

      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '0 2px',
          }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 5,
              fontSize: 13, fontFamily: FONT, color: 'rgba(255,255,255,0.30)',
            }}>
              <Radar size={12} strokeWidth={1.6} />
              <span>
                Showing{' '}
                <b style={{ color: 'rgba(255,255,255,0.55)', fontWeight: 600 }}>{filtered.length}</b>
                {' '}of{' '}
                <b style={{ color: 'rgba(255,255,255,0.55)', fontWeight: 600 }}>{results.length}</b>
                {' '}results
              </span>
            </div>
            {activeSummary && sevFilter === 'all' && (
              <span style={{ fontSize: 12, fontFamily: FONT, color: 'rgba(255,255,255,0.25)' }}>
                {activeSummary}
              </span>
            )}
          </div>

          {filtered.map((v, i) => <VulnCard key={v.uid || i} vuln={v} index={i} />)}

          <div style={{ height: 20, flexShrink: 0 }} />
        </div>
      )}

    </div>
  )
}
