import React, { useEffect, useRef } from 'react'
import useChatStore from '../store/useChatStore'
import { getChatSessions } from '../api/client'
import { useChatStream } from '../hooks/useChatStream'
import MessageBubble from '../components/chat/MessageBubble'
import EmptyState from '../components/chat/EmptyState'
import ChatInput from '../components/chat/ChatInput'
import { BG_GRAD, FONT } from '../constants/chat'

export default function Chat() {
  const bottomRef = useRef(null)
  const { messages, streaming, setSessions, needsReset, ackReset } = useChatStore()
  const { send } = useChatStream()

  // Load session list on mount
  useEffect(() => {
    getChatSessions()
      .then(({ data }) => setSessions(data || []))
      .catch(() => {})
  }, [])

  // Acknowledge reset triggered by a new codebase upload
  useEffect(() => {
    if (needsReset) ackReset()
  }, [needsReset])

  // Auto-scroll to newest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: streaming ? 'instant' : 'smooth' })
  }, [messages, streaming])

  const hasMessages = messages.length > 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: BG_GRAD, fontFamily: FONT }}>

      {/* Message thread / empty state */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', padding: hasMessages ? '28px 0' : 0 }}>
        <div style={{ width: '100%', maxWidth: 860, margin: '0 auto', padding: '0 32px', display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
          {!hasMessages && <EmptyState onSend={send} />}
          {messages.map((msg, i) => <MessageBubble key={i} msg={msg} />)}
          <div ref={bottomRef} />
        </div>
      </div>

      <ChatInput onSend={send} streaming={streaming} />
    </div>
  )
}
