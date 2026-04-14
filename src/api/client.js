import axios from 'axios'

const api = axios.create({
  baseURL: '',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

export default api

// ── Health ────────────────────────────────────────────────────
export const getHealth = () => api.get('/health')

// ── Stats ─────────────────────────────────────────────────────
// Backend: { node_count, edge_count, bug_count, file_count }
export const getStats = () => api.get('/api/stats')

// ── Graph ─────────────────────────────────────────────────────
// Backend nodes use `id` as the unique key. Normalised to `uid`
// so all frontend consumers have a single stable field name.
export const getGraph = (params = {}) =>
  api.get('/api/graph', {
    params: {
      node_limit: 2000,  // request the maximum allowed by the API
      ...params,
    },
  }).then((res) => {
    const data = res.data
    // Normalise: copy `id` → `uid` on every node
    const nodes = (data.nodes || []).map((n) => ({
      ...n,
      uid: n.uid ?? n.id,   // prefer existing uid, fall back to id
    }))
    // Normalise: ensure edges have source_uid / target_uid aliases
    const edges = (data.edges || []).map((e) => ({
      ...e,
      source_uid: e.source_uid ?? e.source,
      target_uid: e.target_uid ?? e.target,
      type:       e.type       ?? e.relation,
    }))
    return { ...res, data: { ...data, nodes, edges } }
  })

export const getNode = (uid) =>
  api.get(`/api/node/${encodeURIComponent(uid)}`)
    .then((res) => ({
      ...res,
      data: { ...res.data, uid: res.data.uid ?? res.data.id },
    }))

// ── Scan results ──────────────────────────────────────────────
// Backend: { total_functions, bugs_found, vulnerabilities: [{uid,name,file,severity,confidence,...}] }
// We normalise so callers see `results[]` with `function_name` and `bug_confidence`.
export const getScanResults = () =>
  api.get('/api/scan-results').then((res) => {
    const data  = res.data
    const items = (data.vulnerabilities || data.results || []).map((v) => ({
      ...v,
      function_name:   v.function_name   ?? v.name,
      bug_confidence:  v.bug_confidence  ?? v.confidence,
      bug_explanation: v.bug_explanation ?? v.bug_reason ?? v.explanation ?? null,
      is_buggy:        true,
      fan_out:         v.fan_out ?? null,
    }))
    return { ...res, data: { ...data, results: items } }
  })

// ── Ingest ────────────────────────────────────────────────────
// Backend expects `clear_first` (not `clear`)
export const ingestFolder = (folder_path, clear_first = false) =>
  api.post('/ingest', { folder_path, clear_first })

export const uploadIngest = (file, { clear_first = false, skip_enrich = false, skip_scan = false } = {}) => {
  const form = new FormData()
  form.append('file', file)
  form.append('clear_first',  String(clear_first))
  form.append('skip_enrich',  String(skip_enrich))
  form.append('skip_scan',    String(skip_scan))
  return api.post('/ingest/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 0,   // uploads can take a while
  })
}

export const getIngestStatus = (job_id) => api.get(`/ingest/status/${job_id}`)
export const getIngestJobs   = ()        => api.get('/ingest/jobs')

// ── Chat ──────────────────────────────────────────────────────
export const sendChat = (message, session_id) =>
  api.post('/chat', { message, session_id: session_id || undefined })

export const getChatSessions = () => api.get('/chat/sessions')
export const clearSession    = (session_id) => api.delete(`/chat/session/${session_id}`)

// ── Scan (direct) ─────────────────────────────────────────────
export const scanCode   = (code, language)   => api.post('/scan/code',   { code, language })
export const scanFolder = (folder_path)      => api.post('/scan/folder', { folder_path })
