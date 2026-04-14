import React, { useState, useRef } from 'react'
import { Send, Loader } from 'lucide-react'
import { FONT, SURFACE } from '../../constants/chat'

// Single-line height: 15px padding-top + 22px line-height + 15px padding-bottom = 52px
// Must include padding because box-sizing is border-box.
const LINE_H = 52

/**
 * Chat input bar.
 * Manages its own textarea state internally.
 * Calls onSend(message) and resets itself when the user submits.
 */
export default function ChatInput({ onSend, streaming }) {
  const [input,       setInput]       = useState('')
  const [focused,     setFocused]     = useState(false)
  const [isMultiLine, setIsMultiLine] = useState(false)
  const inputRef = useRef(null)

  const handleInputChange = (e) => {
    setInput(e.target.value)
    const ta = e.target
    // Snap to auto first (no transition) to measure true scrollHeight
    ta.style.transition = 'none'
    ta.style.height = 'auto'
    const sh = ta.scrollHeight
    // Re-enable transition in next frame so browser animates from current → new height
    requestAnimationFrame(() => {
      ta.style.transition = 'height 0.18s cubic-bezier(0.4,0,0.2,1)'
      ta.style.height = Math.min(sh, 180) + 'px'
      ta.style.overflowY = sh > 180 ? 'auto' : 'hidden'
    })
    setIsMultiLine(sh > LINE_H + 8)
  }

  const resetHeight = () => {
    const ta = inputRef.current
    if (!ta) return
    ta.style.transition = 'height 0.18s cubic-bezier(0.4,0,0.2,1)'
    ta.style.height = LINE_H + 'px'
    ta.style.overflowY = 'hidden'
    setIsMultiLine(false)
  }

  const handleSend = (text) => {
    const msg = (text || input).trim()
    if (!msg || streaming) return
    setInput('')
    resetHeight()
    onSend(msg)
  }

  const canSend = !!input.trim() && !streaming

  return (
    <div style={{
      flexShrink: 0,
      padding: '12px 32px 22px',
      background: 'linear-gradient(0deg, #0f1115 70%, transparent)',
      borderTop: '1px solid rgba(255,255,255,0.06)',
    }}>
      <div style={{ maxWidth: 860, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 8 }}>

        {/* Focus ring — radius morphs pill ↔ rounded-rect with content */}
        <div style={{
          borderRadius: isMultiLine ? 22 : 999,
          padding: 1,
          background: focused ? 'rgba(255,255,255,0.07)' : 'transparent',
          transition: 'border-radius 0.25s cubic-bezier(0.4,0,0.2,1), background 0.18s ease',
        }}>
          {/* Container — position:relative so send button is absolutely anchored */}
          <div
            style={{
              position: 'relative',
              minHeight: LINE_H,
              borderRadius: isMultiLine ? 20 : 999,
              background: focused ? '#1c1f27' : SURFACE,
              border: `1px solid ${focused ? 'rgba(255,255,255,0.13)' : 'rgba(255,255,255,0.09)'}`,
              boxShadow: focused
                ? '0 4px 28px rgba(0,0,0,0.35), 0 1px 0 rgba(255,255,255,0.03) inset'
                : '0 2px 8px rgba(0,0,0,0.22)',
              overflow: 'hidden',
              transition: [
                'border-radius 0.25s cubic-bezier(0.4,0,0.2,1)',
                'background 0.18s ease',
                'border-color 0.18s ease',
                'box-shadow 0.18s ease',
              ].join(', '),
              cursor: 'text',
            }}
            onClick={() => inputRef.current?.focus()}
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() } }}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              placeholder="Ask about functions, vulnerabilities, call chains…"
              rows={1}
              disabled={streaming}
              className="chat-input"
              style={{
                display: 'block', width: '100%', boxSizing: 'border-box',
                background: 'transparent', border: 'none', outline: 'none',
                resize: 'none', fontSize: 14, fontFamily: FONT,
                color: 'rgba(255,255,255,0.85)', lineHeight: 1.6,
                caretColor: 'rgba(255,255,255,0.70)',
                padding: '15px 62px 15px 20px',
                height: LINE_H + 'px',
                overflowY: 'hidden',
              }}
            />

            {/* Send button — absolutely anchored so it never affects layout */}
            <button
              onClick={() => handleSend()}
              disabled={!canSend}
              style={{
                position: 'absolute', right: 12, bottom: 10,
                width: 32, height: 32, borderRadius: '50%',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: canSend ? 'rgba(255,255,255,0.10)' : 'rgba(255,255,255,0.05)',
                border: 'none',
                cursor: canSend ? 'pointer' : 'default',
                opacity: canSend ? 1 : 0.40,
                transition: 'background 0.15s ease, opacity 0.15s ease',
              }}
              onMouseEnter={e => { if (canSend) e.currentTarget.style.background = 'rgba(255,255,255,0.16)' }}
              onMouseLeave={e => { e.currentTarget.style.background = canSend ? 'rgba(255,255,255,0.10)' : 'rgba(255,255,255,0.05)' }}
            >
              {streaming
                ? <Loader size={15} color="rgba(255,255,255,0.50)" className="animate-spin" />
                : <Send   size={15} color="rgba(255,255,255,0.55)" strokeWidth={1.8} />
              }
            </button>
          </div>
        </div>

        <p style={{ textAlign: 'center', fontSize: 11, fontFamily: FONT, color: 'rgba(255,255,255,0.15)', margin: 0 }}>
          Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  )
}
