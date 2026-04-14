import React, { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Workflow, ShieldCheck, Bot,
} from 'lucide-react'
import useAppStore from '../../store/useAppStore'
import { getHealth } from '../../api/client'

const FONT = 'Inter, system-ui, sans-serif'

const PAGE_META = {
  '/':      { label: 'Dashboard',      sub: 'Overview & codebase ingestion',     icon: LayoutDashboard },
  '/graph': { label: 'Graph Explorer', sub: 'Interactive call graph',            icon: Workflow        },
  '/scan':  { label: 'Scan Results',   sub: 'Security analysis & bug detection', icon: ShieldCheck     },
  '/chat':  { label: 'AI Chat',        sub: 'Ask questions about your code',     icon: Bot             },
}

/* ── Status dot ──────────────────────────────────────────────── */
function StatusDot({ status, label }) {
  const isOnline  = status === true
  const isOffline = status === false
  const dotColor  = isOnline ? '#4ade80' : isOffline ? '#f87171' : 'rgba(255,255,255,0.18)'

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontFamily: FONT }}>
      <span style={{
        width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
        background: dotColor,
        boxShadow: isOnline ? `0 0 5px ${dotColor}88` : 'none',
        animation: isOnline ? 'statusPulse 3s ease-in-out infinite' : 'none',
      }} />
      <span style={{
        fontSize: 13, fontWeight: 400, letterSpacing: '0.01em',
        color: isOnline
          ? 'rgba(255,255,255,0.58)'
          : isOffline
          ? 'rgba(248,113,113,0.72)'
          : 'rgba(255,255,255,0.22)',
      }}>
        {label}
      </span>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════ */
export default function TopBar() {
  const location = useLocation()
  const { health, setHealth } = useAppStore()
  const page     = PAGE_META[location.pathname] || PAGE_META['/']
  const PageIcon = page.icon

  const fetchHealth = async () => {
    try {
      const { data } = await getHealth()
      setHealth({
        neo4j:   data?.neo4j   === 'ok',
        scanner: data?.scanner === 'ok',
        agent:   data?.agent   === 'ok',
      })
    } catch {
      setHealth({ neo4j: false, scanner: false, agent: false })
    }
  }

  useEffect(() => {
    fetchHealth()
    const id = setInterval(fetchHealth, 30_000)
    return () => clearInterval(id)
  }, [])

  return (
    <>
      <style>{`
        @keyframes statusPulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.38; }
        }
      `}</style>

      <header style={{
        height: 56,
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 22px',
        background: 'rgba(10,11,14,0.96)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        borderBottom: '1px solid rgba(255,255,255,0.10)',
        boxShadow: '0 1px 12px rgba(0,0,0,0.50)',
        fontFamily: FONT,
        position: 'relative',
        zIndex: 10,
      }}>

        {/* ── Left: page icon + title ──────────────────────────── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
          <div style={{
            width: 30, height: 30, borderRadius: 8, flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.09)',
          }}>
            <PageIcon size={15} strokeWidth={1.8} color="rgba(255,255,255,0.52)" />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <span style={{
              fontSize: 15, fontWeight: 700, lineHeight: 1,
              color: 'rgba(255,255,255,0.92)',
              letterSpacing: '-0.015em',
            }}>
              {page.label}
            </span>
            <span style={{
              fontSize: 12, fontWeight: 400, lineHeight: 1,
              color: 'rgba(255,255,255,0.30)',
            }}>
              {page.sub}
            </span>
          </div>
        </div>

        {/* ── Right: grouped status indicators ────────────────── */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 16,
          padding: '7px 14px', borderRadius: 9,
          background: 'rgba(255,255,255,0.025)',
          border: '1px solid rgba(255,255,255,0.055)',
        }}>
          <StatusDot status={health.neo4j}   label="Neo4j"   />
          <span style={{ width: 1, height: 13, background: 'rgba(255,255,255,0.07)', flexShrink: 0 }} />
          <StatusDot status={health.scanner} label="Scanner" />
          <span style={{ width: 1, height: 13, background: 'rgba(255,255,255,0.07)', flexShrink: 0 }} />
          <StatusDot status={health.agent}   label="Agent"   />
        </div>

      </header>
    </>
  )
}
