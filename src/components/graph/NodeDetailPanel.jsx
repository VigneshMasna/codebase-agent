import React, { useRef, useEffect } from 'react'
import { X, Lock, AlertTriangle, Globe, FileCode, Tag } from 'lucide-react'

const FONT = 'Inter, system-ui, sans-serif'
const MONO = 'JetBrains Mono, monospace'

/* ── hex → rgba helper ────────────────────────────────────────── */
function rgba(hex, a) {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${a})`
}

/* ── Node type → color (mirrors graph node colors) ───────────── */
const TYPE_COLOR = {
  Function:         '#e29480',
  Class:            '#d8a48f',
  Interface:        '#d8a48f',
  Struct:           '#d8a48f',
  Enum:             '#bda978',
  File:             '#55c4e5',
  Package:          '#b5ce9e',
  Tag:              '#bda978',
  Include:          '#a0dde6',
  Import:           '#a0dde6',
  ExternalFunction: '#c2d3cd',
  Field:            '#c2d3cd',
}

/* ── Severity — muted ─────────────────────────────────────────── */
const SEV_COLOR = {
  CRITICAL: { fg: 'rgba(248,113,113,0.70)', bg: 'rgba(248,113,113,0.06)', border: 'rgba(248,113,113,0.14)' },
  HIGH:     { fg: 'rgba(251,146,60,0.70)',  bg: 'rgba(251,146,60,0.06)',  border: 'rgba(251,146,60,0.14)'  },
  MEDIUM:   { fg: 'rgba(215,170,50,0.75)',  bg: 'rgba(215,170,50,0.06)',  border: 'rgba(215,170,50,0.14)'  },
  LOW:      { fg: 'rgba(74,222,128,0.62)',  bg: 'rgba(74,222,128,0.05)',  border: 'rgba(74,222,128,0.12)'  },
}

function TypeChip({ label }) {
  const hex   = TYPE_COLOR[label] || '#9FA8DA'
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      fontSize: 11, fontWeight: 500, fontFamily: FONT,
      padding: '2px 9px', borderRadius: 999,
      color:       rgba(hex, 0.60),
      background:  rgba(hex, 0.06),
      border:      `1px solid ${rgba(hex, 0.14)}`,
      letterSpacing: '0.01em',
    }}>
      {label}
    </span>
  )
}

function SevBadge({ sev }) {
  const s = SEV_COLOR[sev?.toUpperCase()] || {
    fg: 'rgba(255,255,255,0.35)',
    bg: 'rgba(255,255,255,0.05)',
    border: 'rgba(255,255,255,0.10)',
  }
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center',
      fontSize: 10, fontWeight: 600, fontFamily: FONT,
      padding: '2px 8px', borderRadius: 999,
      color: s.fg, background: s.bg, border: `1px solid ${s.border}`,
      letterSpacing: '0.04em', textTransform: 'uppercase',
    }}>
      {sev}
    </span>
  )
}

/* ── Single info row ──────────────────────────────────────────── */
function InfoRow({ icon: Icon, label, value, mono = false }) {
  if (value == null || value === '') return null
  return (
    <div style={{
      display: 'flex', gap: 10, alignItems: 'flex-start',
      padding: '5px 0',
      borderBottom: '1px solid rgba(255,255,255,0.04)',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 5,
        width: 68, flexShrink: 0, paddingTop: 1,
      }}>
        {Icon && <Icon size={11} color="rgba(255,255,255,0.28)" strokeWidth={1.6} />}
        <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.32)', fontFamily: FONT }}>
          {label}
        </span>
      </div>
      <span style={{
        fontSize: 11, flex: 1, lineHeight: 1.55,
        color: 'rgba(255,255,255,0.65)',
        wordBreak: 'break-all',
        fontFamily: mono ? MONO : FONT,
      }}>
        {String(value)}
      </span>
    </div>
  )
}

/* ── Section heading ──────────────────────────────────────────── */
function SectionLabel({ children }) {
  return (
    <p style={{
      fontSize: 10, fontWeight: 600, fontFamily: FONT,
      letterSpacing: '0.07em', textTransform: 'uppercase',
      color: 'rgba(255,255,255,0.22)',
      margin: '14px 0 6px',
    }}>
      {children}
    </p>
  )
}

/* ═══════════════════════════════════════════════════════════════ */
export default function NodeDetailPanel({ node, locked, onClose }) {
  const visible = !!node

  /* Keep last node data alive during the fade-out so content
     doesn't vanish before the transition completes.           */
  const displayRef = useRef(node)
  if (node) displayRef.current = node
  const display = displayRef.current

  return (
    <div style={{
      position: 'absolute', top: 14, right: 14,
      width: 272,
      maxHeight: 'calc(100% - 28px)',
      zIndex: 30,
      borderRadius: 12,
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      background: 'rgba(16,17,21,0.97)',
      border: '1px solid rgba(255,255,255,0.07)',
      backdropFilter: 'blur(18px)',
      WebkitBackdropFilter: 'blur(18px)',
      boxShadow: '0 8px 32px rgba(0,0,0,0.60)',
      opacity: visible ? 1 : 0,
      transform: visible ? 'translateX(0) scale(1)' : 'translateX(12px) scale(0.95)',
      pointerEvents: visible ? 'all' : 'none',
      transition: 'opacity 0.55s cubic-bezier(0.16,1,0.3,1), transform 0.55s cubic-bezier(0.16,1,0.3,1)',
      fontFamily: FONT,
    }}>
      {display && (
        <>
          {/* ── Header ────────────────────────────────────────── */}
          <div style={{
            padding: '13px 13px 11px',
            borderBottom: '1px solid rgba(255,255,255,0.06)',
            flexShrink: 0,
          }}>
            {/* Name row */}
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
              <p style={{
                fontSize: 13, fontWeight: 600, fontFamily: MONO,
                color: 'rgba(255,255,255,0.88)',
                wordBreak: 'break-all', lineHeight: 1.35, flex: 1,
                margin: 0,
              }}>
                {display.name || display.label}
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0, paddingTop: 2 }}>
                {locked && <Lock size={11} color="rgba(255,255,255,0.25)" strokeWidth={1.6} />}
                <button
                  onClick={onClose}
                  style={{
                    background: 'none', border: 'none', cursor: 'pointer',
                    padding: 3, display: 'flex', borderRadius: 5,
                    color: 'rgba(255,255,255,0.28)',
                    transition: 'background 0.12s, color 0.12s',
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.background = 'rgba(255,255,255,0.07)'
                    e.currentTarget.style.color = 'rgba(255,255,255,0.65)'
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background = 'none'
                    e.currentTarget.style.color = 'rgba(255,255,255,0.28)'
                  }}
                >
                  <X size={13} strokeWidth={1.8} />
                </button>
              </div>
            </div>

            {/* Badge row */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 8 }}>
              <TypeChip label={display.label} />
              {display.is_entry_point && (
                <span style={{
                  display: 'inline-flex', alignItems: 'center',
                  fontSize: 11, fontWeight: 500, fontFamily: FONT,
                  padding: '2px 9px', borderRadius: 999,
                  color: 'rgba(74,222,128,0.62)',
                  background: 'rgba(74,222,128,0.06)',
                  border: '1px solid rgba(74,222,128,0.14)',
                }}>
                  Entry Point
                </span>
              )}
              {display.is_buggy && <SevBadge sev={display.severity || 'BUG'} />}
            </div>
          </div>

          {/* ── Body ──────────────────────────────────────────── */}
          <div style={{ padding: '8px 13px 14px', overflowY: 'auto', flex: 1 }}>

            <InfoRow icon={Globe}    label="Language" value={display.language} />
            <InfoRow icon={FileCode} label="File"     value={display.file}     mono />

            {/* Summary */}
            {display.summary && (
              <>
                <SectionLabel>Description</SectionLabel>
                <p style={{
                  fontSize: 12, lineHeight: 1.65,
                  color: 'rgba(255,255,255,0.48)',
                  fontFamily: FONT,
                  paddingLeft: 10,
                  borderLeft: '2px solid rgba(255,255,255,0.07)',
                  margin: 0,
                }}>
                  {display.summary}
                </p>
              </>
            )}

            {/* Vulnerability block */}
            {display.is_buggy && (
              <div style={{
                marginTop: 14, borderRadius: 9, padding: '10px 11px',
                background: 'rgba(248,113,113,0.05)',
                border: '1px solid rgba(248,113,113,0.12)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                  <AlertTriangle size={12} color="rgba(248,113,113,0.70)" strokeWidth={1.8} />
                  <span style={{ fontSize: 11, fontWeight: 600, fontFamily: FONT, color: 'rgba(248,113,113,0.70)' }}>
                    Vulnerability Detected
                  </span>
                </div>
                {display.severity && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8 }}>
                    <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.30)', fontFamily: FONT }}>Severity</span>
                    <SevBadge sev={display.severity} />
                  </div>
                )}
                {display.bug_confidence != null && (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.30)', fontFamily: FONT }}>Confidence</span>
                      <span style={{ fontSize: 11, fontFamily: MONO, color: 'rgba(248,113,113,0.65)' }}>
                        {Math.round(display.bug_confidence * 100)}%
                      </span>
                    </div>
                    <div style={{
                      height: 3, borderRadius: 999,
                      background: 'rgba(255,255,255,0.06)', overflow: 'hidden',
                    }}>
                      <div style={{
                        height: '100%', borderRadius: 999,
                        background: 'rgba(248,113,113,0.55)',
                        width: `${Math.round(display.bug_confidence * 100)}%`,
                        transition: 'width 0.4s ease',
                      }} />
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Tags */}
            {display.tags?.length > 0 && (
              <>
                <SectionLabel>
                  <Tag size={9} style={{ display: 'inline', marginRight: 4 }} />
                  Tags
                </SectionLabel>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                  {display.tags.map(t => (
                    <span key={t} style={{
                      fontSize: 11, fontFamily: FONT,
                      padding: '2px 8px', borderRadius: 999,
                      color: 'rgba(255,255,255,0.42)',
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.08)',
                    }}>
                      {t}
                    </span>
                  ))}
                </div>
              </>
            )}

            {/* Hint */}
            {!locked && (
              <p style={{
                marginTop: 16, fontSize: 10, textAlign: 'center',
                color: 'rgba(255,255,255,0.16)', fontFamily: FONT,
              }}>
                click node to lock · hover to preview
              </p>
            )}
          </div>
        </>
      )}
    </div>
  )
}
