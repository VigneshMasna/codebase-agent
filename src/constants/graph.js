/**
 * Shared graph colour palette.
 * Single source of truth — used by VisGraph (canvas rendering) and
 * Dashboard (ResultsOverview label badges).
 */

export const NODE_HUE = {
  Function        : '#e29480',   // soft coral
  Class           : '#d8a48f',   // muted peach
  Interface       : '#d8a48f',
  Struct          : '#d8a48f',
  Enum            : '#bda978',   // muted gold
  File            : '#55c4e5',   // calm blue
  Package         : '#b5ce9e',   // soft green
  Namespace       : '#bda978',
  ExternalFunction: '#c2d3cd',   // soft gray-green
  Field           : '#c2d3cd',
  Import          : '#a0dde6',   // light cyan
  Include         : '#a0dde6',
  Tag             : '#bda978',
  CodeEntity      : '#9FA8DA',   // Neo4j base label
  // Extra labels some parsers emit
  Variable        : '#c2d3cd',
  Constant        : '#bda978',
  Method          : '#e29480',
  Module          : '#b5ce9e',
  Type            : '#d8a48f',
  // Special rendering states (VisGraph internal use)
  _buggy          : '#e29480',
  _entry          : '#b5ce9e',
  _default        : '#c2d3cd',
}

/** Unified soft edge colour — subtle, non-distracting. */
export const EDGE_COLOR = '#90A4AE'

/** Colour for a node label string (used in text badges). */
export function labelColor(label) {
  return NODE_HUE[label] || NODE_HUE.CodeEntity
}

/** Colour for a full node object (respects is_buggy / is_entry_point flags). */
export function nodeHue(node) {
  if (node.is_buggy) return NODE_HUE._buggy
  if (node.is_entry_point) return NODE_HUE._entry
  return NODE_HUE[node.label] || NODE_HUE._default
}
