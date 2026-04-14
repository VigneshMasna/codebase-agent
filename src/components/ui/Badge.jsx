import React from 'react'

const MAP = {
  CRITICAL: 'badge-critical',
  HIGH:     'badge-high',
  MEDIUM:   'badge-medium',
  LOW:      'badge-low',
  SAFE:     'badge-safe',
  INFO:     'badge-info',
  Function: 'badge-info',
  Class:    'badge-info',
  Struct:   'badge-info',
  Entry:    'badge-safe',
  Buggy:    'badge-critical',
}

export default function Badge({ label, className = '' }) {
  const cls = MAP[label?.toUpperCase?.()] || MAP[label] || 'badge-info'
  return <span className={`badge ${cls} ${className}`}>{label}</span>
}
