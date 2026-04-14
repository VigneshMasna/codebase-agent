import React, { useCallback, useRef } from 'react'
import { Upload, X, CheckCircle, AlertCircle, FileArchive, FileCode, ArrowRight } from 'lucide-react'
import { useIngest } from '../../context/IngestContext'
import DotsIcon from '../ui/DotsIcon'

const CARD_BG     = '#18191d'
const CARD_BORDER = '1px solid rgba(255,255,255,0.08)'
const CARD_RADIUS = '10px'
const FONT        = 'Inter, system-ui, sans-serif'

function Spinner() {
  return (
    <span style={{
      display: 'inline-block', width: 13, height: 13,
      borderRadius: '50%',
      border: '2px solid rgba(255,255,255,0.10)',
      borderTopColor: 'rgba(255,255,255,0.55)',
      animation: 'spin 0.75s linear infinite',
      flexShrink: 0,
    }} />
  )
}

function ProgressBar({ pct }) {
  return (
    <div style={{ height: 2, borderRadius: 99, background: 'rgba(255,255,255,0.07)', overflow: 'hidden' }}>
      <div style={{
        height: '100%', width: `${pct}%`, borderRadius: 99,
        background: 'rgba(255,255,255,0.38)',
        transition: 'width 0.4s ease',
      }} />
    </div>
  )
}

function LogLine({ status, text }) {
  const color = status === 'done' ? '#86efac' : status === 'error' ? '#fca5a5' : 'rgba(255,255,255,0.50)'
  const dot   = status === 'done' ? '✓' : status === 'error' ? '✗' : '·'
  return (
    <div style={{
      display: 'flex', gap: 7, fontSize: 11,
      fontFamily: 'JetBrains Mono, monospace',
      lineHeight: '1.6', color,
      animation: 'fadeSlideIn 0.15s ease both',
    }}>
      <span style={{ flexShrink: 0, opacity: 0.65 }}>{dot}</span>
      <span>{text}</span>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════ */
export default function UploadSection() {
  const {
    phase, fileName, fileSize, logs, progress, successFile,
    pickFile, startUpload, reset, clearSuccess,
  } = useIngest()

  // The actual File object — survives re-renders within the same session,
  // but if the user navigated away and came back mid-upload, the file is
  // already uploaded so we don't need it again.
  const fileObjRef = useRef(null)
  const inputRef   = useRef(null)
  const logBoxRef  = useRef(null)

  const isExpanded = phase !== 'idle' && phase !== 'collapsing'
  const isActive   = phase === 'uploading' || phase === 'processing'
  const isDone     = phase === 'done'
  const isError    = phase === 'error'

  /* ── Auto-scroll log box (never the page) ───────────────────── */
  const prevLogLen = useRef(0)
  if (logs.length !== prevLogLen.current) {
    prevLogLen.current = logs.length
    setTimeout(() => {
      const el = logBoxRef.current
      if (el) el.scrollTop = el.scrollHeight
    }, 40)
  }

  /* ── File picking ────────────────────────────────────────────── */
  function handleFile(f) {
    if (!f) return
    fileObjRef.current = f
    pickFile(f)
  }

  const onDragOver  = useCallback((e) => { e.preventDefault() }, [])
  const onDrop      = useCallback((e) => {
    e.preventDefault()
    const f = e.dataTransfer.files?.[0]
    if (f) handleFile(f)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  function handleAnalyze() {
    if (fileObjRef.current) {
      startUpload(fileObjRef.current)
    }
  }

  /* ── Subtitle text ───────────────────────────────────────────── */
  const subtitle =
    isDone   ? `✓ ${logs.findLast?.(l => l.status === 'done')?.text ?? 'Processed successfully'}` :
    isError  ? 'Something went wrong — try again' :
    isActive ? 'Processing…' :
    phase === 'selected' ? `${fileName ?? ''} — ready to analyze` :
               'Upload a .zip archive or a code file (.java .c .cpp .h)'

  const subtitleColor =
    isDone  ? '#86efac' : isError ? '#fca5a5' :
    isActive ? 'rgba(255,255,255,0.45)' : 'rgba(255,255,255,0.38)'

  /* ── File icon colour ────────────────────────────────────────── */
  const isZip  = /\.(zip|tar|tgz|gz)$/i.test(fileName || '')
  const fileColor = isZip ? '#bda978' : '#a0dde6'
  const FileTypeIcon = isZip ? FileArchive : FileCode

  return (
    <>
    <div
      style={{
        background: CARD_BG,
        border: CARD_BORDER,
        borderRadius: CARD_RADIUS,
        overflow: 'hidden',
        flexShrink: 0,
        transition: 'border-color 0.15s, background 0.15s',
      }}
      onDragOver={phase === 'idle' ? onDragOver : undefined}
      onDrop={phase === 'idle' ? onDrop : undefined}
    >

      {/* ── Always-visible top bar ──────────────────────────────── */}
      <div style={{
        padding: '13px 16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
        borderBottom: isExpanded ? '1px solid rgba(255,255,255,0.06)' : 'none',
        transition: 'border-color 0.25s',
      }}>

        {/* Left — icon + title + subtitle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 0, flex: 1 }}>
          <DotsIcon />
          <span style={{ fontSize: 14, fontWeight: 600, color: '#fff', fontFamily: FONT, flexShrink: 0 }}>
            Upload Codebase
          </span>
          <span style={{
            fontSize: 12, color: subtitleColor, fontFamily: FONT,
            marginLeft: 4,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            transition: 'color 0.2s',
          }}>
            {subtitle}
          </span>
        </div>

        {/* Right — controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          {isActive  && <Spinner />}
          {isDone    && <CheckCircle  size={14} color="#86efac" />}
          {isError   && <AlertCircle  size={14} color="#fca5a5" />}

          {/* Upload button — idle only */}
          {phase === 'idle' && (
            <>
              <button
                onClick={() => inputRef.current?.click()}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '5px 12px', borderRadius: 7,
                  background: 'rgba(255,255,255,0.07)',
                  border: '1px solid rgba(255,255,255,0.11)',
                  color: 'rgba(255,255,255,0.80)',
                  fontSize: 12, fontWeight: 600, fontFamily: FONT,
                  cursor: 'pointer',
                  transition: 'background 0.15s, color 0.15s',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.12)'; e.currentTarget.style.color = '#fff' }}
                onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.07)'; e.currentTarget.style.color = 'rgba(255,255,255,0.80)' }}
              >
                <Upload size={11} />
                Upload
              </button>
              <input
                ref={inputRef}
                type="file"
                accept=".zip,.java,.c,.cpp,.h"
                style={{ display: 'none' }}
                onChange={e => handleFile(e.target.files?.[0])}
              />
            </>
          )}

          {/* Dismiss — when expanded and not actively running */}
          {isExpanded && !isActive && (
            <button
              onClick={reset}
              style={{
                width: 26, height: 26, borderRadius: 6,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                color: 'rgba(255,255,255,0.35)',
                cursor: 'pointer',
                transition: 'color 0.15s, background 0.15s',
              }}
              onMouseEnter={e => { e.currentTarget.style.color = '#fff'; e.currentTarget.style.background = 'rgba(255,255,255,0.10)' }}
              onMouseLeave={e => { e.currentTarget.style.color = 'rgba(255,255,255,0.35)'; e.currentTarget.style.background = 'rgba(255,255,255,0.04)' }}
            >
              <X size={12} />
            </button>
          )}
        </div>
      </div>

      {/* ── Expandable body (smooth CSS height transition) ──────── */}
      <div style={{
        maxHeight: isExpanded ? '320px' : '0px',
        overflow: 'hidden',
        transition: 'max-height 0.30s cubic-bezier(0.4,0,0.2,1)',
      }}>
        <div style={{ padding: '12px 16px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>

          {/* ── Selected: file chip + analyze button ─────────── */}
          {phase === 'selected' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {/* File chip */}
              <div
                onClick={() => inputRef.current?.click()}
                style={{
                  flex: 1, display: 'flex', alignItems: 'center', gap: 8,
                  padding: '8px 12px', borderRadius: 8,
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px dashed rgba(255,255,255,0.11)',
                  cursor: 'pointer',
                  minWidth: 0,
                }}
              >
                <span style={{
                  width: 26, height: 26, borderRadius: 6, flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: `${fileColor}18`, border: `1px solid ${fileColor}35`,
                }}>
                  <FileTypeIcon size={12} color={fileColor} />
                </span>
                <span style={{ fontSize: 12, fontWeight: 600, color: '#fff', fontFamily: FONT, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {fileName}
                </span>
                <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', fontFamily: FONT, flexShrink: 0 }}>
                  {fileSize ? (fileSize / 1024).toFixed(1) + ' KB' : ''}
                </span>
              </div>
              <input
                ref={inputRef}
                type="file"
                accept=".zip,.java,.c,.cpp,.h"
                style={{ display: 'none' }}
                onChange={e => handleFile(e.target.files?.[0])}
              />
              {/* Analyze button */}
              <button
                onClick={handleAnalyze}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0,
                  padding: '8px 16px', borderRadius: 7,
                  background: 'rgba(255,255,255,0.08)',
                  border: '1px solid rgba(255,255,255,0.14)',
                  color: '#fff', fontSize: 12, fontWeight: 600,
                  fontFamily: FONT, cursor: 'pointer',
                  transition: 'background 0.15s',
                }}
                onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.14)'}
                onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.08)'}
              >
                <ArrowRight size={12} /> Analyze
              </button>
            </div>
          )}

          {/* ── Processing / done / error: progress + log ────── */}
          {(isActive || isDone || isError) && (
            <>
              <ProgressBar pct={progress} />
              <div
                ref={logBoxRef}
                style={{
                  borderRadius: 8,
                  background: 'rgba(0,0,0,0.22)',
                  border: '1px solid rgba(255,255,255,0.06)',
                  padding: '8px 12px',
                  maxHeight: 160, overflowY: 'auto',
                  display: 'flex', flexDirection: 'column', gap: 1,
                }}
              >
                {logs.length === 0 && (
                  <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.25)', fontFamily: 'JetBrains Mono, monospace' }}>· waiting…</span>
                )}
                {logs.map((l, i) => <LogLine key={i} status={l.status} text={l.text} />)}
              </div>
              {isError && (
                <button
                  onClick={reset}
                  style={{
                    alignSelf: 'flex-start', padding: '5px 12px', borderRadius: 6,
                    background: 'rgba(252,165,165,0.08)', border: '1px solid rgba(252,165,165,0.18)',
                    color: '#fca5a5', fontSize: 11, fontWeight: 600, fontFamily: FONT, cursor: 'pointer',
                  }}
                >
                  Try again
                </button>
              )}
            </>
          )}

        </div>
      </div>

    </div>

    {/* ── Persistent success strip — shown after collapse ─────── */}
    {successFile && (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 8,
        padding: '7px 14px',
        borderRadius: 8,
        background: 'rgba(134,239,172,0.06)',
        border: '1px solid rgba(134,239,172,0.18)',
        animation: 'fadeSlideIn 0.25s ease both',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <CheckCircle size={13} color="#86efac" style={{ flexShrink: 0 }} />
          <span style={{ fontSize: 12, fontFamily: FONT, color: '#86efac', fontWeight: 500 }}>
            <strong style={{ fontWeight: 700 }}>{successFile}</strong> processed completely
          </span>
        </div>
        <button
          onClick={clearSuccess}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'rgba(134,239,172,0.40)', padding: '2px 4px',
            display: 'flex', alignItems: 'center', transition: 'color 0.15s',
          }}
          onMouseEnter={e => e.currentTarget.style.color = '#86efac'}
          onMouseLeave={e => e.currentTarget.style.color = 'rgba(134,239,172,0.40)'}
        >
          <X size={11} />
        </button>
      </div>
    )}
    </>
  )
}
