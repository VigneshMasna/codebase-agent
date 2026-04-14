import { create } from 'zustand'

const useAppStore = create((set, get) => ({
  // ── Health ───────────────────────────────────────────────────
  health: { neo4j: null, scanner: null, agent: null },
  setHealth: (h) => set({ health: h }),

  // ── Stats ────────────────────────────────────────────────────
  stats: null,
  setStats: (s) => set({ stats: s }),

  // ── Ingest ───────────────────────────────────────────────────
  ingestJob: null,           // { job_id, status, progress, events[] }
  ingestLogs: [],
  setIngestJob: (j)      => set({ ingestJob: j }),
  addIngestLog: (entry)  => set((s) => ({ ingestLogs: [...s.ingestLogs, entry] })),
  clearIngest: ()        => set({ ingestJob: null, ingestLogs: [] }),

  // ── UI ───────────────────────────────────────────────────────
  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),

  commandOpen: false,
  setCommandOpen: (v) => set({ commandOpen: v }),

  toasts: [],
  addToast: (toast) => {
    const id = Date.now()
    set((s) => ({ toasts: [...s.toasts, { id, ...toast }] }))
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), 4000)
  },
  removeToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))

export default useAppStore
