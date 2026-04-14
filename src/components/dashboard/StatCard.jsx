import React from 'react'
import DotsIcon from '../ui/DotsIcon'
import useCountUp from '../../hooks/useCountUp'

export default function StatCard({ label, value }) {
  const count = useCountUp(value ?? 0)

  return (
    <div style={{
      borderRadius: '10px',
      padding: '20px 22px 22px',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between',
      background: '#18191d',
      border: '1px solid rgba(255,255,255,0.08)',
      height: '172px',
      boxSizing: 'border-box',
    }}>
      {/* Top row: grip icon + label */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '9px' }}>
        <DotsIcon />
        <span style={{
          fontSize: '14px',
          fontWeight: 500,
          color: '#ffffff',
          letterSpacing: '0',
          fontFamily: 'Inter, system-ui, sans-serif',
        }}>
          {label}
        </span>
      </div>

      {/* Huge number */}
      <p style={{
        fontSize: '80px',
        fontWeight: 800,
        lineHeight: 1,
        color: '#ffffff',
        fontFamily: 'Inter, system-ui, sans-serif',
        margin: 0,
        letterSpacing: '-0.02em',
      }}>
        {count.toLocaleString()}
      </p>
    </div>
  )
}
