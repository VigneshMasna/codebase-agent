import React, { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  FolderOpen, Upload, Play, CheckCircle, XCircle, Loader,
  FileArchive, FileCode, CloudUpload, Terminal
} from 'lucide-react'
import useAppStore from '../../store/useAppStore'
import useChatStore from '../../store/useChatStore'
import { ingestFolder, uploadIngest } from '../../api/client'

const STATUS_ICON = {
  done:    <CheckCircle size={12} color="#34D399" />,
  error:   <XCircle    size={12} color="#F87171" />,
  running: <Loader     size={12} color="#8B5CF6" className="animate-spin" />,
}

const TABS = [
  { id: 'folder', icon: FolderOpen,   label: 'Folder Path' },
  { id: 'zip',    icon: FileArchive,  label: 'ZIP Upload'  },
  { id: 'file',   icon: FileCode,     label: 'Code File'   },
]

export default function IngestPanel() {
  const [tab, setTab]           = useState('folder')
  const [folderPath, setFolderPath] = useState('')
  const [loading, setLoading]   = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [uploadFile, setUploadFile] = useState(null)
  const fileInputRef = useRef(null)
  const logsEndRef   = useRef(null)

  const { ingestJob, ingestLogs, setIngestJob, addIngestLog, clearIngest, addToast } = useAppStore()

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [ingestLogs])

  const streamProgress = (jobId) => {
    const es = new EventSource(`/ingest/progress/${jobId}`)
    es.onmessage = (e) => {
      try {
        const evt = JSON.parse(e.data)
        // Backend SSE types: "progress" | "error" | "done" (with status: "complete"|"error")
        if (evt.type === 'progress') {
          addIngestLog({ status: 'running', text: evt.message || evt.step_name || 'Processing…' })
        } else if (evt.type === 'done') {
          if (evt.status === 'complete' || evt.status === 'done') {
            const r = evt.result || {}
            const summary = r.nodes_created != null
              ? `✓ ${r.nodes_created} nodes, ${r.edges_created} edges, ${r.bugs_found ?? 0} bugs found`
              : '✓ Ingestion complete — graph is ready!'
            addIngestLog({ status: 'done', text: summary })
            setIngestJob((j) => ({ ...j, status: 'done' }))
            addToast({ type: 'success', title: 'Ingest complete', message: 'Graph is ready to explore' })
          } else {
            addIngestLog({ status: 'error', text: `✗ ${evt.error || 'Ingestion failed'}` })
            setIngestJob((j) => ({ ...j, status: 'error' }))
            addToast({ type: 'error', title: 'Ingest failed', message: evt.error || 'Unknown error' })
          }
          es.close()
          setLoading(false)
        } else if (evt.type === 'error') {
          addIngestLog({ status: 'error', text: `✗ ${evt.message || 'Error'}` })
          setIngestJob((j) => ({ ...j, status: 'error' }))
          es.close()
          setLoading(false)
        }
      } catch {}
    }
    es.onerror = () => {
      addIngestLog({ status: 'error', text: '✗ Connection lost' })
      es.close()
      setLoading(false)
    }
  }

  const startFolderIngest = async () => {
    if (!folderPath.trim()) {
      addToast({ type: 'error', title: 'Missing path', message: 'Enter an absolute folder path' })
      return
    }
    clearIngest()
    useChatStore.getState().clearMessages()
    setLoading(true)
    try {
      const { data } = await ingestFolder(folderPath.trim(), false)
      setIngestJob({ job_id: data.job_id, status: 'running' })
      addIngestLog({ status: 'running', text: `Ingesting: ${folderPath.trim()}` })
      streamProgress(data.job_id)
    } catch (e) {
      addToast({ type: 'error', title: 'Ingest failed', message: e.response?.data?.detail || e.message })
      setLoading(false)
    }
  }

  const startUploadIngest = async (file) => {
    if (!file) {
      addToast({ type: 'error', title: 'No file', message: 'Select a file to upload' })
      return
    }
    clearIngest()
    useChatStore.getState().clearMessages()
    setLoading(true)
    addIngestLog({ status: 'running', text: `Uploading: ${file.name} (${(file.size / 1024).toFixed(1)} KB)` })
    try {
      const { data } = await uploadIngest(file)
      setIngestJob({ job_id: data.job_id, status: 'running' })
      addIngestLog({ status: 'running', text: 'Upload complete — starting analysis…' })
      streamProgress(data.job_id)
    } catch (e) {
      addToast({ type: 'error', title: 'Upload failed', message: e.response?.data?.detail || e.message })
      addIngestLog({ status: 'error', text: `✗ ${e.response?.data?.detail || e.message}` })
      setLoading(false)
    }
  }

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (!file) return
    setUploadFile(file)
  }, [])

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    setDragOver(true)
  }, [])

  const handleDragLeave = useCallback(() => setDragOver(false), [])

  const acceptForTab = tab === 'zip' ? '.zip,.tar,.tar.gz,.tgz' : '.py,.js,.ts,.jsx,.tsx,.java,.cpp,.c,.go,.rs,.rb,.cs'

  return (
    <div
      className="flex flex-col gap-0 h-full rounded-2xl overflow-hidden"
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        boxShadow: 'var(--shadow-card)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 pt-4 pb-3"
        style={{ borderBottom: '1px solid rgba(139,92,246,0.10)' }}
      >
        <div className="flex items-center gap-2.5">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center"
            style={{ background: 'linear-gradient(135deg, #8B5CF6, #22D3EE)', boxShadow: 'var(--glow-violet)' }}
          >
            <CloudUpload size={14} color="#fff" />
          </div>
          <div>
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-1)' }}>Ingest Codebase</h3>
            <p className="text-[11px]" style={{ color: 'var(--text-3)' }}>Build the knowledge graph</p>
          </div>
        </div>

        {/* Tab switcher */}
        <div className="flex items-center gap-1 p-1 rounded-xl" style={{ background: 'rgba(255,255,255,0.04)' }}>
          {TABS.map(({ id, icon: TabIcon, label }) => (
            <button
              key={id}
              onClick={() => { setTab(id); setUploadFile(null) }}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-smooth"
              style={{
                background: tab === id ? 'rgba(139,92,246,0.18)' : 'transparent',
                color: tab === id ? 'var(--violet-light)' : 'var(--text-3)',
                border: tab === id ? '1px solid rgba(139,92,246,0.30)' : '1px solid transparent',
              }}
            >
              <TabIcon size={11} />
              <span className="hidden sm:block">{label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-3 px-5 py-4 flex-1">
        <AnimatePresence mode="wait">
          {/* ── Folder Path tab ── */}
          {tab === 'folder' && (
            <motion.div
              key="folder"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18 }}
              className="flex gap-2"
            >
              <div className="flex-1 flex items-center gap-2 px-3 py-2 rounded-xl input-base">
                <FolderOpen size={14} style={{ color: 'var(--text-3)', flexShrink: 0 }} />
                <input
                  value={folderPath}
                  onChange={(e) => setFolderPath(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && startFolderIngest()}
                  placeholder="/absolute/path/to/your/repo"
                  disabled={loading}
                  className="flex-1 bg-transparent outline-none text-sm"
                  style={{ color: 'var(--text-1)', fontFamily: 'JetBrains Mono, monospace' }}
                />
              </div>
              <button
                onClick={startFolderIngest}
                disabled={loading}
                className="btn-primary flex items-center gap-2 px-4 py-2 text-sm font-semibold"
                style={{ borderRadius: 10 }}
              >
                {loading ? <Loader size={13} className="animate-spin" /> : <Play size={13} />}
                {loading ? 'Running…' : 'Ingest'}
              </button>
            </motion.div>
          )}

          {/* ── ZIP Upload tab ── */}
          {tab === 'zip' && (
            <motion.div
              key="zip"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18 }}
              className="flex flex-col gap-3"
            >
              <div
                className={`drop-zone flex flex-col items-center justify-center gap-3 py-6 cursor-pointer ${dragOver ? 'drag-over' : ''}`}
                onClick={() => fileInputRef.current?.click()}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
              >
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center"
                  style={{ background: 'rgba(139,92,246,0.12)', border: '1px solid rgba(139,92,246,0.22)' }}
                >
                  <FileArchive size={18} style={{ color: 'var(--violet-light)' }} />
                </div>
                {uploadFile ? (
                  <div className="text-center">
                    <p className="text-sm font-medium" style={{ color: 'var(--text-1)' }}>{uploadFile.name}</p>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>
                      {(uploadFile.size / 1024).toFixed(1)} KB · Click to change
                    </p>
                  </div>
                ) : (
                  <div className="text-center">
                    <p className="text-sm font-medium" style={{ color: 'var(--text-2)' }}>
                      Drop ZIP here or <span style={{ color: 'var(--violet-light)' }}>browse</span>
                    </p>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>
                      .zip · .tar · .tar.gz · .tgz
                    </p>
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={acceptForTab}
                  className="hidden"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                />
              </div>

              <button
                onClick={() => startUploadIngest(uploadFile)}
                disabled={loading || !uploadFile}
                className="btn-primary flex items-center justify-center gap-2 py-2.5 text-sm font-semibold w-full"
                style={{ borderRadius: 10 }}
              >
                {loading ? <Loader size={14} className="animate-spin" /> : <Upload size={14} />}
                {loading ? 'Uploading & analysing…' : 'Upload & Ingest'}
              </button>
            </motion.div>
          )}

          {/* ── Single Code File tab ── */}
          {tab === 'file' && (
            <motion.div
              key="file"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18 }}
              className="flex flex-col gap-3"
            >
              <div
                className={`drop-zone flex flex-col items-center justify-center gap-3 py-6 cursor-pointer ${dragOver ? 'drag-over' : ''}`}
                onClick={() => fileInputRef.current?.click()}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
              >
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center"
                  style={{ background: 'rgba(34,211,238,0.10)', border: '1px solid rgba(34,211,238,0.20)' }}
                >
                  <FileCode size={18} style={{ color: 'var(--cyan)' }} />
                </div>
                {uploadFile ? (
                  <div className="text-center">
                    <p className="text-sm font-medium" style={{ color: 'var(--text-1)' }}>{uploadFile.name}</p>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>
                      {(uploadFile.size / 1024).toFixed(1)} KB · Click to change
                    </p>
                  </div>
                ) : (
                  <div className="text-center">
                    <p className="text-sm font-medium" style={{ color: 'var(--text-2)' }}>
                      Drop code file or <span style={{ color: 'var(--cyan)' }}>browse</span>
                    </p>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>
                      .py · .js · .ts · .java · .cpp · .go · .rs and more
                    </p>
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={acceptForTab}
                  className="hidden"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                />
              </div>

              <button
                onClick={() => startUploadIngest(uploadFile)}
                disabled={loading || !uploadFile}
                className="btn-primary flex items-center justify-center gap-2 py-2.5 text-sm font-semibold w-full"
                style={{ borderRadius: 10 }}
              >
                {loading ? <Loader size={14} className="animate-spin" /> : <Play size={14} />}
                {loading ? 'Analysing…' : 'Analyse File'}
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Terminal log */}
        <div
          className="flex-1 rounded-xl overflow-hidden"
          style={{
            background: 'rgba(0,0,0,0.45)',
            border: '1px solid rgba(139,92,246,0.10)',
            minHeight: 100,
            maxHeight: 150,
          }}
        >
          {/* Terminal title bar */}
          <div
            className="flex items-center gap-2 px-3 py-2"
            style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}
          >
            <Terminal size={11} style={{ color: 'var(--text-4)' }} />
            <span className="font-mono text-[10px]" style={{ color: 'var(--text-4)' }}>ingest.log</span>
            <div className="flex gap-1 ml-auto">
              {['#F87171', '#FBBF24', '#34D399'].map((c) => (
                <div key={c} className="w-2 h-2 rounded-full opacity-50" style={{ background: c }} />
              ))}
            </div>
          </div>

          <div className="p-3 overflow-y-auto font-mono text-[11px]" style={{ maxHeight: 110 }}>
            {ingestLogs.length === 0 && (
              <span style={{ color: 'var(--text-4)' }}>~ waiting for ingest job…</span>
            )}
            <AnimatePresence initial={false}>
              {ingestLogs.map((log, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="flex items-start gap-2 py-0.5"
                >
                  <span className="flex-shrink-0 mt-[1px]">{STATUS_ICON[log.status]}</span>
                  <span style={{
                    color: log.status === 'done' ? '#34D399'
                      : log.status === 'error' ? '#F87171'
                      : 'var(--text-2)',
                  }}>
                    {log.text}
                  </span>
                </motion.div>
              ))}
            </AnimatePresence>
            <div ref={logsEndRef} />
          </div>
        </div>
      </div>
    </div>
  )
}
