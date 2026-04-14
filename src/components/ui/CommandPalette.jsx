import React, { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Search, LayoutDashboard, GitFork, ShieldAlert, MessageSquare } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import useAppStore from '../../store/useAppStore'

const COMMANDS = [
  { label: 'Go to Dashboard',      icon: LayoutDashboard, action: '/'      },
  { label: 'Go to Graph Explorer', icon: GitFork,         action: '/graph'  },
  { label: 'Go to Scan Results',   icon: ShieldAlert,     action: '/scan'   },
  { label: 'Go to Chat Agent',     icon: MessageSquare,   action: '/chat'   },
]

export default function CommandPalette() {
  const { commandOpen, setCommandOpen } = useAppStore()
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)
  const inputRef = useRef(null)
  const navigate = useNavigate()

  const filtered = COMMANDS.filter((c) =>
    c.label.toLowerCase().includes(query.toLowerCase())
  )

  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setCommandOpen(true)
      }
      if (e.key === 'Escape') setCommandOpen(false)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  useEffect(() => {
    if (commandOpen) {
      setQuery('')
      setSelected(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [commandOpen])

  const run = (cmd) => {
    navigate(cmd.action)
    setCommandOpen(false)
  }

  const handleKey = (e) => {
    if (e.key === 'ArrowDown') setSelected((s) => Math.min(s + 1, filtered.length - 1))
    if (e.key === 'ArrowUp')   setSelected((s) => Math.max(s - 1, 0))
    if (e.key === 'Enter' && filtered[selected]) run(filtered[selected])
  }

  return (
    <AnimatePresence>
      {commandOpen && (
        <>
          <motion.div
            className="fixed inset-0 z-40"
            style={{ background: 'rgba(7,7,15,0.75)', backdropFilter: 'blur(8px)' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setCommandOpen(false)}
          />
          <motion.div
            className="fixed top-[28%] left-1/2 z-50 w-full max-w-md -translate-x-1/2"
            initial={{ opacity: 0, y: -20, scale: 0.97 }}
            animate={{ opacity: 1, y: 0,   scale: 1    }}
            exit={{    opacity: 0, y: -20, scale: 0.97 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          >
            <div
              className="overflow-hidden rounded-2xl"
              style={{
                background: 'rgba(12,12,26,0.95)',
                border: '1px solid rgba(139,92,246,0.22)',
                boxShadow: '0 24px 80px rgba(0,0,0,0.80), 0 0 0 1px rgba(139,92,246,0.08)',
                backdropFilter: 'blur(20px)',
              }}
            >
              {/* Input */}
              <div className="flex items-center gap-3 px-4 py-3.5"
                style={{ borderBottom: '1px solid rgba(139,92,246,0.10)' }}>
                <Search size={15} style={{ color: 'var(--violet-light)' }} />
                <input
                  ref={inputRef}
                  value={query}
                  onChange={(e) => { setQuery(e.target.value); setSelected(0) }}
                  onKeyDown={handleKey}
                  placeholder="Search commands…"
                  className="flex-1 bg-transparent outline-none text-sm text-white placeholder:text-[var(--text-3)]"
                />
                <kbd
                  className="text-[10px] px-1.5 py-0.5 rounded font-mono"
                  style={{ background: 'rgba(139,92,246,0.10)', color: 'var(--text-3)', border: '1px solid rgba(139,92,246,0.16)' }}
                >
                  ESC
                </kbd>
              </div>

              {/* Results */}
              <ul className="py-1 max-h-60 overflow-y-auto">
                {filtered.length === 0 && (
                  <li className="px-4 py-3 text-sm" style={{ color: 'var(--text-3)' }}>
                    No results
                  </li>
                )}
                {filtered.map((cmd, i) => (
                  <li
                    key={cmd.label}
                    className="flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-smooth"
                    style={{
                      background: i === selected ? 'rgba(139,92,246,0.12)' : 'transparent',
                      color: i === selected ? 'var(--violet-light)' : 'var(--text-1)',
                    }}
                    onMouseEnter={() => setSelected(i)}
                    onClick={() => run(cmd)}
                  >
                    <cmd.icon size={15} />
                    <span className="text-sm">{cmd.label}</span>
                  </li>
                ))}
              </ul>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
