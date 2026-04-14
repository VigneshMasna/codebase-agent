import { create } from 'zustand'

const STORAGE_KEY = 'codebase-agent-chat'

/* ── Helpers ──────────────────────────────────────────────────── */
function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch { return {} }
}

function saveToStorage(messages, activeSessionId) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      messages:        messages.map((m) => ({ ...m, isStreaming: false })),
      activeSessionId: activeSessionId ?? null,
    }))
  } catch {}
}

/* ── Load persisted state once at module init ─────────────────── */
const saved = loadFromStorage()

/* ── Store ────────────────────────────────────────────────────── */
const useChatStore = create((set, get) => ({
  sessions:        [],
  activeSessionId: saved.activeSessionId ?? null,
  messages:        (saved.messages || []).map((m) => ({ ...m, isStreaming: false })),
  streaming:       false,
  needsReset:      false,

  setSessions: (s) => set({ sessions: s }),

  setActiveSession: (id) => set((s) => ({
    activeSessionId: id,
    messages: !s.streaming && s.activeSessionId && s.activeSessionId !== id
      ? []
      : s.messages,
  })),

  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages, msg] })),

  appendToolCall: (toolCall) =>
    set((s) => {
      const msgs = [...s.messages]
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].isStreaming) {
          msgs[i] = { ...msgs[i], toolCalls: [...(msgs[i].toolCalls || []), toolCall] }
          break
        }
      }
      return { messages: msgs }
    }),

  appendChunk: (chunk) =>
    set((s) => {
      const msgs = [...s.messages]
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].isStreaming) {
          msgs[i] = { ...msgs[i], content: msgs[i].content + chunk }
          break
        }
      }
      return { messages: msgs }
    }),

  // Called when streaming ends — strip flags, drop empties, then persist
  finalizeStream: () =>
    set((s) => {
      const messages = s.messages
        .map((m) => m.isStreaming ? { ...m, isStreaming: false } : m)
        .filter((m) => m.role === 'user' || m.content || m.toolCalls?.length)
      // Persist completed conversation to localStorage
      saveToStorage(messages, s.activeSessionId)
      return { messages, streaming: false }
    }),

  setStreaming: (v) => set({ streaming: v }),

  // Hard reset — wipes localStorage synchronously, then clears in-memory state
  // Sets needsReset: true so Chat.jsx reacts immediately even if already mounted
  clearMessages: () => {
    try { localStorage.removeItem(STORAGE_KEY) } catch {}
    set({ messages: [], streaming: false, activeSessionId: null, needsReset: true })
  },

  ackReset: () => set({ needsReset: false }),
}))

export default useChatStore
