import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Bot, User } from 'lucide-react'
import ToolCallCard from './ToolCallCard'
import MarkdownText from './MarkdownText'
import { FONT, BUBBLE_AI, BUBBLE_U, BORDER, BORDER_MD } from '../../constants/chat'

function ThinkingDots() {
  const [step, setStep] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setStep(s => (s + 1) % 3), 480)
    return () => clearInterval(id)
  }, [])
  return (
    <span style={{ display: 'inline-flex', gap: 4, marginLeft: 4, verticalAlign: 'middle', alignItems: 'center' }}>
      {[0, 1, 2].map(i => (
        <motion.span
          key={i}
          animate={{ opacity: i <= step ? 0.88 : 0.18 }}
          transition={{ duration: 0.24, ease: 'easeInOut' }}
          style={{ display: 'inline-block', width: 4, height: 4, borderRadius: '50%', background: 'rgba(255,255,255,0.60)' }}
        />
      ))}
    </span>
  )
}

export default function MessageBubble({ msg }) {
  const isUser = msg.role === 'user'

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.20, ease: [0.16, 1, 0.3, 1] }}
      style={{ display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start', gap: 10 }}
    >
      {/* AI avatar */}
      {!isUser && (
        <div style={{
          width: 32, height: 32, borderRadius: 9, flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginTop: 1,
          background: 'rgba(255,255,255,0.06)',
          border: '1px solid rgba(255,255,255,0.10)',
        }}>
          <Bot size={16} color="rgba(255,255,255,0.62)" strokeWidth={1.6} />
        </div>
      )}

      <div style={{ maxWidth: '78%', display: 'flex', flexDirection: 'column', gap: 6, alignItems: isUser ? 'flex-end' : 'flex-start' }}>

        {/* Tool call cards */}
        {msg.toolCalls?.map((tc, i) => (
          <ToolCallCard key={i} tool={tc.tool} args={tc.args} />
        ))}

        {/* Thinking indicator — shown only while streaming with no content yet */}
        <AnimatePresence>
          {msg.isStreaming && !msg.content && !msg.toolCalls?.length && (
            <motion.div
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -2 }}
              transition={{ duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
              style={{
                display: 'inline-flex', alignItems: 'center',
                padding: '10px 18px', borderRadius: 12,
                background: BUBBLE_AI, border: `1px solid ${BORDER}`,
              }}
            >
              <span style={{ fontSize: 13, fontFamily: FONT, color: 'rgba(255,255,255,0.60)', letterSpacing: '0.03em', display: 'flex', alignItems: 'center' }}>
                Thinking<ThinkingDots />
              </span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Content bubble */}
        {(msg.content || (msg.isStreaming && msg.toolCalls?.length > 0)) && (
          <motion.div
            initial={{ opacity: 0, y: 3 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            style={isUser ? {
              padding: '9px 15px', borderRadius: 13, borderBottomRightRadius: 4,
              background: BUBBLE_U, border: `1px solid ${BORDER_MD}`,
            } : {
              padding: '11px 15px', borderRadius: 13, borderBottomLeftRadius: 4,
              background: BUBBLE_AI, border: `1px solid ${BORDER}`,
            }}
          >
            {isUser
              ? <p style={{ fontSize: 14, fontFamily: FONT, color: 'rgba(255,255,255,0.82)', margin: 0, lineHeight: 1.65 }}>{msg.content}</p>
              : <MarkdownText content={msg.content} isStreaming={msg.isStreaming} />
            }
          </motion.div>
        )}
      </div>

      {/* User avatar */}
      {isUser && (
        <div style={{
          width: 32, height: 32, borderRadius: 10, flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginTop: 1,
          background: 'rgba(255,255,255,0.05)',
          border: '1px solid rgba(255,255,255,0.09)',
        }}>
          <User size={14} color="rgba(255,255,255,0.50)" strokeWidth={1.8} />
        </div>
      )}
    </motion.div>
  )
}
