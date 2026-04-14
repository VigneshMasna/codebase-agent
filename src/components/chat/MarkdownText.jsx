import React from 'react'
import { FONT, MONO } from '../../constants/chat'

/** Renders inline backtick code and **bold** spans. */
function renderInline(text) {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/)
  return parts.map((part, i) => {
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={i} style={{
          fontFamily: MONO, fontSize: 12, borderRadius: 4, padding: '1px 5px',
          background: 'rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.70)',
        }}>
          {part.slice(1, -1)}
        </code>
      )
    }
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} style={{ color: 'rgba(255,255,255,0.88)', fontWeight: 600 }}>{part.slice(2, -2)}</strong>
    }
    return <span key={i}>{part}</span>
  })
}

/** Extracts fenced code blocks (```lang\n...\n```) and renders them as <pre>. */
function renderCodeBlocks(content) {
  const blocks = []
  const re = /```(\w*)\n([\s\S]*?)```/g
  let m, key = 0
  while ((m = re.exec(content)) !== null) {
    blocks.push(
      <pre key={key++} style={{
        borderRadius: 8, padding: '10px 14px', overflowX: 'auto',
        fontFamily: MONO, fontSize: 12, margin: '6px 0',
        background: '#0e1014', border: '1px solid rgba(255,255,255,0.06)',
        color: 'rgba(255,255,255,0.60)', whiteSpace: 'pre', lineHeight: 1.65,
      }}>
        {m[1] && (
          <div style={{ color: 'rgba(255,255,255,0.22)', marginBottom: 6, fontSize: 10, fontFamily: MONO }}>
            {m[1]}
          </div>
        )}
        {m[2]}
      </pre>
    )
  }
  return blocks.length ? <div>{blocks}</div> : null
}

/**
 * Renders a subset of Markdown:
 * ##/### headings, bullet/numbered lists, inline code, bold, fenced code blocks.
 */
export default function MarkdownText({ content, isStreaming }) {
  if (!content && !isStreaming) return null

  return (
    <div style={{ fontSize: 13, lineHeight: 1.75, color: 'rgba(255,255,255,0.72)', fontFamily: FONT }}>
      {content.split('\n').map((line, i) => {
        if (line.startsWith('## '))
          return <p key={i} style={{ fontWeight: 600, fontSize: 14, margin: '10px 0 4px', color: 'rgba(255,255,255,0.88)' }}>{line.slice(3)}</p>
        if (line.startsWith('### '))
          return <p key={i} style={{ fontWeight: 600, fontSize: 13, margin: '8px 0 2px', color: 'rgba(255,255,255,0.75)' }}>{line.slice(4)}</p>
        if (line.startsWith('```')) return null
        if (line.startsWith('- ') || line.startsWith('* '))
          return (
            <div key={i} style={{ display: 'flex', gap: 8, margin: '2px 0' }}>
              <span style={{ color: 'rgba(255,255,255,0.25)', flexShrink: 0, marginTop: 2 }}>▸</span>
              <span>{renderInline(line.slice(2))}</span>
            </div>
          )
        const numMatch = line.match(/^(\d+)\. (.+)/)
        if (numMatch)
          return (
            <div key={i} style={{ display: 'flex', gap: 8, margin: '2px 0' }}>
              <span style={{ fontFamily: MONO, fontSize: 11, fontWeight: 700, flexShrink: 0, color: 'rgba(255,255,255,0.35)', minWidth: 18, marginTop: 1 }}>
                {numMatch[1]}.
              </span>
              <span>{renderInline(numMatch[2])}</span>
            </div>
          )
        if (!line.trim()) return <div key={i} style={{ height: 6 }} />
        return <p key={i} style={{ margin: '2px 0' }}>{renderInline(line)}</p>
      })}
      {renderCodeBlocks(content)}
      {isStreaming && (
        <span style={{
          display: 'inline-block', width: 2, height: '0.9em',
          background: 'rgba(255,255,255,0.62)', marginLeft: 3,
          borderRadius: 1, verticalAlign: 'text-bottom',
        }} />
      )}
    </div>
  )
}
