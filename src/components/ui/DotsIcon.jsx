import React from 'react'

/** 2×3 dot grip icon used in panel headers across the dashboard. */
export default function DotsIcon() {
  return (
    <svg width="10" height="14" viewBox="0 0 10 14" fill="none" style={{ flexShrink: 0 }}>
      {[2, 7, 12].map((cy) =>
        [2, 8].map((cx) => (
          <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={1.4} fill="rgba(255,255,255,0.32)" />
        ))
      )}
    </svg>
  )
}
