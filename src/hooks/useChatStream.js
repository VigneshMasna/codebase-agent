import { useCallback } from 'react'
import useChatStore from '../store/useChatStore'
import useAppStore from '../store/useAppStore'
import { getChatSessions } from '../api/client'

/**
 * Encapsulates the full SSE streaming flow for a single chat turn:
 *   send(message) → POST /chat/stream → parse SSE events → update store
 *
 * Returns { send, streaming } so the caller only needs to wire up the UI.
 */
export function useChatStream() {
  const {
    streaming,
    activeSessionId,
    setSessions,
    addMessage,
    appendChunk,
    appendToolCall,
    finalizeStream,
    setStreaming,
  } = useChatStore()

  const { addToast } = useAppStore()

  const send = useCallback(async (message) => {
    const msg = message.trim()
    if (!msg || streaming) return

    addMessage({ role: 'user', content: msg })
    addMessage({ role: 'assistant', content: '', isStreaming: true, toolCalls: [] })
    setStreaming(true)

    try {
      const res = await fetch('/chat/stream', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ message: msg, session_id: activeSessionId || undefined }),
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }

      const reader  = res.body.getReader()
      const decoder = new TextDecoder()
      let   buffer  = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() ?? ''

        for (const part of parts) {
          for (const line of part.split('\n')) {
            if (!line.startsWith('data: ')) continue
            const raw = line.slice(6).trim()
            if (!raw || raw === '[DONE]') continue
            try {
              const evt = JSON.parse(raw)
              if (evt.type === 'chunk')     appendChunk(evt.text ?? '')
              if (evt.type === 'tool_call') appendToolCall({ tool: evt.tool, args: evt.args ?? {} })
              if (evt.type === 'error')     addToast({ type: 'error', title: 'Agent error', message: evt.message })
              if (evt.type === 'done') {
                if (evt.session_id) useChatStore.setState({ activeSessionId: evt.session_id })
                getChatSessions().then(({ data }) => setSessions(data || [])).catch(() => {})
              }
            } catch { /* skip malformed SSE event */ }
          }
        }
      }
    } catch (e) {
      addToast({ type: 'error', title: 'Chat error', message: e.message })
    } finally {
      finalizeStream()
    }
  }, [streaming, activeSessionId, addMessage, appendChunk, appendToolCall, finalizeStream, setStreaming, setSessions, addToast])

  return { send, streaming }
}
