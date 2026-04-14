import { create } from 'zustand'

const useGraphStore = create((set) => ({
  nodes: [],
  edges: [],
  loading: false,
  error: null,
  selectedNode: null,
  filterLabel: 'all',        // 'all' | 'Function' | 'Class' | 'buggy'
  showVulnOnly: false,

  setGraphData: (nodes, edges) => set({ nodes, edges, loading: false, error: null }),
  setLoading:   (v) => set({ loading: v }),
  setError:     (e) => set({ error: e, loading: false }),
  setSelected:  (n) => set({ selectedNode: n }),
  setFilter:    (f) => set({ filterLabel: f }),
  toggleVulnOnly: () => set((s) => ({ showVulnOnly: !s.showVulnOnly })),
}))

export default useGraphStore
