import React from 'react'
import { Sparkles, Search, GitFork, TrendingUp, Bug } from 'lucide-react'
import { FONT, BUBBLE_AI, BORDER } from '../../constants/chat'

const SUGGESTIONS = [
  { text: 'What are the most critical vulnerabilities?', icon: Search     },
  { text: 'Show all entry points in the codebase',       icon: GitFork    },
  { text: 'What functions have the highest impact score?',icon: TrendingUp },
  { text: 'Find vulnerable call paths from entry points', icon: Bug       },
]

/** Shown when there are no messages — icon, title, and suggestion cards. */
export default function EmptyState({ onSend }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, gap: 36 }}>

      {/* Icon + title */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18 }}>
        <div style={{
          width: 64, height: 64, borderRadius: 18,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'linear-gradient(135deg, rgba(139,92,246,0.14) 0%, rgba(34,211,238,0.07) 100%)',
          border: '1px solid rgba(139,92,246,0.20)',
          boxShadow: '0 0 28px rgba(139,92,246,0.14), 0 2px 10px rgba(0,0,0,0.35)',
        }}>
          <Sparkles size={29} color="rgba(167,139,250,0.78)" strokeWidth={1.5} />
        </div>
        <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <p style={{ fontSize: 20, fontWeight: 600, color: 'rgba(255,255,255,0.88)', margin: 0 }}>
            Ask your codebase anything
          </p>
          <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.46)', margin: 0 }}>
            Powered by Gemini + Neo4j knowledge graph
          </p>
        </div>
      </div>

      {/* Suggestion cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12, width: '100%', maxWidth: 560 }}>
        {SUGGESTIONS.map((s) => {
          const Icon = s.icon
          return (
            <button
              key={s.text}
              onClick={() => onSend(s.text)}
              style={{
                padding: '12px 16px', borderRadius: 12, textAlign: 'left',
                background: BUBBLE_AI, border: `1px solid ${BORDER}`,
                cursor: 'pointer', transition: 'background 0.15s, border-color 0.15s',
                display: 'flex', alignItems: 'flex-start', gap: 11,
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = 'rgba(255,255,255,0.07)'
                e.currentTarget.style.borderColor = 'rgba(255,255,255,0.13)'
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = BUBBLE_AI
                e.currentTarget.style.borderColor = BORDER
              }}
            >
              <Icon size={14} color="rgba(255,255,255,0.32)" strokeWidth={1.8} style={{ flexShrink: 0, marginTop: 2 }} />
              <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.65)', lineHeight: 1.58, fontFamily: FONT }}>
                {s.text}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
