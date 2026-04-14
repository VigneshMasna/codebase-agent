import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search, Database, GitFork, TrendingUp, Bug, Terminal, Zap,
  ChevronDown, ChevronUp,
} from 'lucide-react'
import { SURFACE, BORDER, MONO, FONT } from '../../constants/chat'

const TOOL_META = {
  search_by_concept:     { icon: Search,     color: 'rgba(34,211,238,0.70)',  label: 'Concept Search'  },
  get_node_details:      { icon: Database,   color: 'rgba(148,163,184,0.70)', label: 'Node Details'    },
  trace_callers:         { icon: GitFork,    color: 'rgba(148,163,184,0.70)', label: 'Trace Callers'   },
  trace_callees:         { icon: GitFork,    color: 'rgba(148,163,184,0.70)', label: 'Trace Callees'   },
  get_impact_analysis:   { icon: TrendingUp, color: 'rgba(251,191,36,0.70)',  label: 'Impact Analysis' },
  find_vulnerabilities:  { icon: Bug,        color: 'rgba(248,113,113,0.70)', label: 'Find Vulns'      },
  find_vulnerable_paths: { icon: Bug,        color: 'rgba(248,113,113,0.70)', label: 'Vuln Paths'      },
  run_cypher:            { icon: Terminal,   color: 'rgba(52,211,153,0.70)',  label: 'Cypher Query'    },
}

export default function ToolCallCard({ tool, args }) {
  const [open, setOpen] = useState(false)
  const meta = TOOL_META[tool] || { icon: Zap, color: 'rgba(148,163,184,0.70)', label: tool }
  const Icon = meta.icon

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      style={{ borderRadius: 8, overflow: 'hidden', background: SURFACE, border: BORDER, fontSize: 12, fontFamily: FONT }}
    >
      <button
        onClick={() => setOpen(s => !s)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 8,
          padding: '6px 10px', textAlign: 'left',
          background: 'transparent', border: 'none', cursor: 'pointer',
        }}
      >
        <Icon size={11} color={meta.color} strokeWidth={1.8} style={{ flexShrink: 0 }} />
        <span style={{ color: meta.color, fontWeight: 600 }}>{meta.label}</span>
        {args && Object.keys(args).length > 0 && (
          <span style={{
            color: 'rgba(255,255,255,0.28)', fontFamily: MONO, fontSize: 11,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1,
          }}>
            {Object.values(args)[0]?.toString().slice(0, 52)}
          </span>
        )}
        <span style={{ color: 'rgba(255,255,255,0.20)', marginLeft: 'auto', flexShrink: 0 }}>
          {open ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
        </span>
      </button>

      <AnimatePresence>
        {open && args && (
          <motion.div
            initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }}
            transition={{ duration: 0.16 }}
            style={{ overflow: 'hidden' }}
          >
            <pre style={{
              margin: 0, padding: '4px 10px 8px',
              fontFamily: MONO, fontSize: 11,
              color: 'rgba(255,255,255,0.45)',
              whiteSpace: 'pre-wrap', wordBreak: 'break-all',
              borderTop: BORDER,
            }}>
              {JSON.stringify(args, null, 2)}
            </pre>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
