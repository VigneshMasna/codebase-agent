/**
 * IngestContext — global upload/ingest state that survives tab switches.
 *
 * State is stored in sessionStorage so React Router navigation
 * (unmount/remount of Dashboard) never loses it.
 *
 * On remount, if phase is 'uploading' or 'processing' and a jobId exists,
 * the SSE stream is automatically reconnected — the backend replays all
 * buffered events so the log catches up instantly.
 */
import React, {
  createContext, useCallback, useContext,
  useEffect, useRef, useState,
} from 'react'
import { uploadIngest } from '../api/client'
import useChatStore from '../store/useChatStore'

/* ── Storage key ─────────────────────────────────────────────── */
const SK = 'ingest_state'

const DEFAULT = {
  phase:       'idle',   // idle | selected | uploading | processing | done | collapsing | error
  fileName:    null,
  fileSize:    null,
  logs:        [],
  progress:    0,
  jobId:       null,
  successFile: null,
}

function load() {
  try {
    const raw = sessionStorage.getItem(SK)
    return raw ? { ...DEFAULT, ...JSON.parse(raw) } : { ...DEFAULT }
  } catch {
    return { ...DEFAULT }
  }
}

function save(state) {
  try { sessionStorage.setItem(SK, JSON.stringify(state)) } catch {}
}

function clear() {
  try { sessionStorage.removeItem(SK) } catch {}
}

/* ── Context ──────────────────────────────────────────────────── */
const IngestContext = createContext(null)

export function IngestProvider({ children }) {
  const [state, _setState] = useState(load)

  // Ref so SSE callbacks always close over latest state without re-subscribing
  const stateRef  = useRef(state)
  const esRef     = useRef(null)

  // Callbacks registered by consumers (e.g. Dashboard's refreshData)
  const onCompleteRef = useRef(null)

  /* setState + sessionStorage in one call */
  const setState = useCallback((updater) => {
    _setState(prev => {
      const next = typeof updater === 'function' ? updater(prev) : updater
      stateRef.current = next
      save(next)
      return next
    })
  }, [])

  /* ── SSE stream ─────────────────────────────────────────────── */
  const startStream = useCallback((jobId) => {
    esRef.current?.close()

    const es = new EventSource(`/ingest/progress/${jobId}`)
    esRef.current = es
    let ticks = 0

    es.onmessage = (e) => {
      try {
        const evt = JSON.parse(e.data)

        if (evt.type === 'progress') {
          const msg = evt.message || evt.step_name || 'Processing…'
          ticks++
          setState(prev => ({
            ...prev,
            logs:     [...prev.logs, { status: 'running', text: msg }],
            progress: Math.min(20 + ticks * 9, 90),
          }))
        }

        if (evt.type === 'done') {
          es.close()
          if (evt.status === 'complete' || evt.status === 'done') {
            const r = evt.result || {}
            const summary = r.nodes_created != null
              ? `${r.nodes_created} nodes · ${r.edges_created} edges · ${r.bugs_found ?? 0} bugs`
              : 'Ingestion complete'

            setState(prev => ({
              ...prev,
              logs:     [...prev.logs, { status: 'done', text: summary }],
              progress: 100,
              phase:    'done',
            }))

            // Step 1: show done for 1.2 s
            setTimeout(() => {
              setState(prev => ({ ...prev, phase: 'collapsing' }))

              // Step 2: after CSS transition (350 ms) → reset + show success strip
              setTimeout(() => {
                const name = stateRef.current.fileName ?? 'Codebase'
                setState({
                  ...DEFAULT,
                  successFile: name,
                })
                onCompleteRef.current?.()
              }, 350)
            }, 1200)

          } else {
            setState(prev => ({
              ...prev,
              logs:  [...prev.logs, { status: 'error', text: evt.error || 'Ingestion failed' }],
              phase: 'error',
            }))
          }
        }

        if (evt.type === 'error') {
          es.close()
          setState(prev => ({
            ...prev,
            logs:  [...prev.logs, { status: 'error', text: evt.message || 'Error' }],
            phase: 'error',
          }))
        }
      } catch {}
    }

    es.onerror = () => {
      es.close()
      setState(prev => ({
        ...prev,
        logs:  [...prev.logs, { status: 'error', text: 'Connection lost' }],
        phase: 'error',
      }))
    }
  }, [setState])

  /* ── On mount: reconnect SSE if a job was in-flight ─────────── */
  useEffect(() => {
    const s = stateRef.current
    if ((s.phase === 'uploading' || s.phase === 'processing') && s.jobId) {
      // Re-attach to the existing job; backend replays buffered events
      setState(prev => ({ ...prev, logs: [] }))  // clear stale logs before replay
      startStream(s.jobId)
    }
    return () => esRef.current?.close()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  /* ── Actions ─────────────────────────────────────────────────── */

  const pickFile = useCallback((file) => {
    if (!file) return
    setState({
      ...DEFAULT,
      phase:    'selected',
      fileName: file.name,
      fileSize: file.size,
    })
  }, [setState])

  const startUpload = useCallback(async (file) => {
    if (!file) return
    useChatStore.getState().clearMessages()
    setState(prev => ({
      ...prev,
      logs:     [{ status: 'running', text: `Uploading ${file.name} (${(file.size / 1024).toFixed(1)} KB)…` }],
      progress: 5,
      phase:    'uploading',
    }))
    try {
      const { data } = await uploadIngest(file, { clear_first: true })
      setState(prev => ({
        ...prev,
        logs:     [...prev.logs, { status: 'running', text: 'Upload complete — starting analysis…' }],
        progress: 20,
        phase:    'processing',
        jobId:    data.job_id,
      }))
      startStream(data.job_id)
    } catch (err) {
      setState(prev => ({
        ...prev,
        logs:  [...prev.logs, { status: 'error', text: err.response?.data?.detail || err.message || 'Upload failed' }],
        phase: 'error',
      }))
    }
  }, [setState, startStream])

  const reset = useCallback(() => {
    esRef.current?.close()
    setState({ ...DEFAULT })
    clear()
  }, [setState])

  const clearSuccess = useCallback(() => {
    setState(prev => ({ ...prev, successFile: null }))
  }, [setState])

  const registerOnComplete = useCallback((cb) => {
    onCompleteRef.current = cb
  }, [])

  const value = {
    ...state,
    pickFile,
    startUpload,
    reset,
    clearSuccess,
    registerOnComplete,
  }

  return (
    <IngestContext.Provider value={value}>
      {children}
    </IngestContext.Provider>
  )
}

export function useIngest() {
  const ctx = useContext(IngestContext)
  if (!ctx) throw new Error('useIngest must be used inside <IngestProvider>')
  return ctx
}
