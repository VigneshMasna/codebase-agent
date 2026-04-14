import React from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Workflow, ShieldCheck, Bot,
  ChevronLeft, ChevronRight, Waypoints,
} from 'lucide-react'
import useAppStore from '../../store/useAppStore'
import { motion, AnimatePresence } from 'framer-motion'

/* ── Nav groups ──────────────────────────────────────────────── */
const NAV_GROUPS = [
  {
    label: 'Main',
    items: [
      { to: '/',      icon: LayoutDashboard, label: 'Dashboard' },
      { to: '/graph', icon: Workflow,         label: 'Graph'     },
    ],
  },
  {
    label: 'Tools',
    items: [
      { to: '/scan', icon: ShieldCheck, label: 'Scan' },
      { to: '/chat', icon: Bot,         label: 'Chat' },
    ],
  },
]

const FONT        = 'Inter, system-ui, sans-serif'
const W_EXPANDED  = 220
const W_COLLAPSED = 56
// Fixed-width icon column — the icon never moves regardless of sidebar state
const ICON_COL    = 40

export default function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useAppStore()

  return (
    <motion.aside
      initial={false}
      animate={{ width: sidebarCollapsed ? W_COLLAPSED : W_EXPANDED }}
      transition={{ duration: 0.28, ease: [0.4, 0, 0.2, 1] }}
      style={{
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        flexShrink: 0,
        overflow: 'hidden',
        background: 'linear-gradient(180deg, #0f1013 0%, #0c0d10 100%)',
        borderRight: '1px solid rgba(255,255,255,0.10)',
        boxShadow: '1px 0 12px rgba(0,0,0,0.45)',
        fontFamily: FONT,
        willChange: 'width',
        transform: 'translateZ(0)',
        backfaceVisibility: 'hidden',
      }}
    >

      {/* ── Logo row ──────────────────────────────────────────── */}
      <div style={{
        height: 56,
        display: 'flex',
        alignItems: 'center',
        // Fixed padding — never changes during animation
        padding: '0 8px',
        gap: 0,
        flexShrink: 0,
        borderBottom: '1px solid rgba(255,255,255,0.055)',
        overflow: 'hidden',
      }}>
        {/* Brand mark lives inside the fixed icon column so it never jumps */}
        <div style={{
          width: ICON_COL, height: ICON_COL,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
          willChange: 'transform',
          transform: 'translateZ(0)',
          backfaceVisibility: 'hidden',
        }}>
          <div style={{
            width: 30, height: 30, borderRadius: 8,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'linear-gradient(135deg, #7c3aed 0%, #0ea5e9 100%)',
            boxShadow: '0 0 14px rgba(124,58,237,0.32)',
          }}>
            <Waypoints size={16} strokeWidth={1.9} color="#fff" />
          </div>
        </div>

        {/* Title fades out — never repositions the icon */}
        <AnimatePresence initial={false}>
          {!sidebarCollapsed && (
            <motion.div
              key="logo-text"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.16, ease: 'easeInOut' }}
              style={{ overflow: 'hidden', whiteSpace: 'nowrap', paddingRight: 8 }}
            >
              <div style={{
                fontSize: 15, fontWeight: 700, lineHeight: 1.25,
                color: 'rgba(255,255,255,0.92)',
                letterSpacing: '-0.015em',
              }}>
                GraphRAG Agent
              </div>
              <div style={{
                fontSize: 12, fontWeight: 400, lineHeight: 1.2,
                color: 'rgba(255,255,255,0.30)',
                marginTop: 2,
              }}>
                AI-powered analysis
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Nav ───────────────────────────────────────────────── */}
      <nav style={{
        flex: 1,
        padding: '12px 8px',
        display: 'flex',
        flexDirection: 'column',
        gap: 0,
        overflowY: 'auto',
        overflowX: 'hidden',
      }}>
        {NAV_GROUPS.map((group, gi) => (
          <div key={group.label} style={{ marginBottom: gi < NAV_GROUPS.length - 1 ? 20 : 0 }}>

            {/* Section label — fixed height container prevents layout shift */}
            <div style={{ height: 20, overflow: 'hidden', marginBottom: 4 }}>
              <AnimatePresence initial={false}>
                {!sidebarCollapsed && (
                  <motion.span
                    key={`grp-${group.label}`}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.14, ease: 'easeInOut' }}
                    style={{
                      display: 'block',
                      // Left indent aligns with icon center
                      paddingLeft: ICON_COL / 2 - 4,
                      fontSize: 10, fontWeight: 600,
                      letterSpacing: '0.08em',
                      textTransform: 'uppercase',
                      color: 'rgba(255,255,255,0.22)',
                      userSelect: 'none',
                      whiteSpace: 'nowrap',
                      lineHeight: '20px',
                    }}
                  >
                    {group.label}
                  </motion.span>
                )}
              </AnimatePresence>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {group.items.map(({ to, icon: Icon, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  style={{ textDecoration: 'none' }}
                  title={sidebarCollapsed ? label : undefined}
                >
                  {({ isActive }) => (
                    <NavItem
                      icon={Icon}
                      label={label}
                      isActive={isActive}
                      collapsed={sidebarCollapsed}
                    />
                  )}
                </NavLink>
              ))}
            </div>

          </div>
        ))}
      </nav>

      {/* ── Bottom: collapse toggle ────────────────────────────── */}
      <div style={{
        borderTop: '1px solid rgba(255,255,255,0.08)',
        padding: '9px 8px 11px',
        display: 'flex',
        // Fixed alignment — button sits inside icon column, never jumps
        justifyContent: 'flex-start',
        background: 'rgba(0,0,0,0.18)',
      }}>
        <div style={{
          width: ICON_COL,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
        }}>
          <button
            onClick={toggleSidebar}
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            style={{
              width: 30, height: 26, borderRadius: 6,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.12)',
              color: 'rgba(255,255,255,0.45)',
              cursor: 'pointer',
              transition: 'background 0.15s ease, color 0.15s ease, border-color 0.15s ease',
              flexShrink: 0,
              boxShadow: '0 1px 4px rgba(0,0,0,0.30)',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = 'rgba(255,255,255,0.12)'
              e.currentTarget.style.color = 'rgba(255,255,255,0.80)'
              e.currentTarget.style.borderColor = 'rgba(255,255,255,0.20)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'rgba(255,255,255,0.06)'
              e.currentTarget.style.color = 'rgba(255,255,255,0.45)'
              e.currentTarget.style.borderColor = 'rgba(255,255,255,0.12)'
            }}
          >
            {sidebarCollapsed
              ? <ChevronRight size={13} strokeWidth={2} />
              : <ChevronLeft  size={13} strokeWidth={2} />
            }
          </button>
        </div>
      </div>

    </motion.aside>
  )
}

/* ── NavItem ──────────────────────────────────────────────────── */
function NavItem({ icon: Icon, label, isActive, collapsed }) {
  return (
    <div
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        // Fixed padding — NEVER changes during animation (eliminates reflow)
        padding: '3px 0',
        // Fixed alignment — icon column handles centering in collapsed state
        justifyContent: 'flex-start',
        borderRadius: 8,
        background: isActive ? 'rgba(255,255,255,0.06)' : 'transparent',
        border: isActive
          ? '1px solid rgba(255,255,255,0.09)'
          : '1px solid transparent',
        cursor: 'pointer',
        transition: 'background 0.15s ease, border-color 0.15s ease',
        userSelect: 'none',
        minHeight: 34,
        overflow: 'hidden',
      }}
      onMouseEnter={e => {
        if (!isActive) e.currentTarget.style.background = 'rgba(255,255,255,0.04)'
      }}
      onMouseLeave={e => {
        if (!isActive) e.currentTarget.style.background = 'transparent'
      }}
    >
      {/* Left accent bar — absolute, zero layout impact */}
      {isActive && (
        <span style={{
          position: 'absolute',
          left: 0, top: '50%', transform: 'translateY(-50%)',
          width: 2, height: 14,
          borderRadius: '0 2px 2px 0',
          background: 'rgba(255,255,255,0.48)',
        }} />
      )}

      {/* Fixed icon column — icon position is completely independent of text */}
      <div style={{
        width: ICON_COL, height: 28,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
        // Own compositor layer so width animation doesn't touch this subtree
        willChange: 'transform',
        transform: 'translateZ(0)',
        backfaceVisibility: 'hidden',
      }}>
        <Icon
          size={18}
          strokeWidth={isActive ? 1.9 : 1.6}
          color={isActive ? 'rgba(255,255,255,0.82)' : 'rgba(255,255,255,0.38)'}
          style={{ transition: 'color 0.15s ease' }}
        />
      </div>

      {/* Label — opacity-only fade (no x-slide = zero layout recalculation) */}
      <AnimatePresence initial={false}>
        {!collapsed && (
          <motion.span
            key="nav-label"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.14, ease: 'easeInOut' }}
            style={{
              fontSize: 15,
              fontWeight: isActive ? 500 : 400,
              color: isActive ? 'rgba(255,255,255,0.88)' : 'rgba(255,255,255,0.50)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              transition: 'color 0.15s ease',
              fontFamily: FONT,
              letterSpacing: '-0.008em',
              paddingRight: 8,
            }}
          >
            {label}
          </motion.span>
        )}
      </AnimatePresence>
    </div>
  )
}
