/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['Fira Code', 'JetBrains Mono', 'monospace'],
        sans: ['Inter', 'Fira Sans', 'sans-serif'],
      },
      colors: {
        bg: {
          base:      '#070D1A',
          surface:   '#0C1629',
          elevated:  '#111E35',
          highlight: '#16243E',
        },
        accent: {
          cyan:   '#38BDF8',
          indigo: '#818CF8',
          purple: '#A78BFA',
        },
        node: {
          fn:       '#38BDF8',
          cls:      '#818CF8',
          struct:   '#A78BFA',
          external: '#4B5563',
          buggy:    '#F87171',
          entry:    '#34D399',
          tag:      '#FBBF24',
        },
        status: {
          success: '#34D399',
          danger:  '#F87171',
          warning: '#FBBF24',
          info:    '#38BDF8',
        },
        border: {
          DEFAULT: 'rgba(56,189,248,0.12)',
          strong:  'rgba(56,189,248,0.25)',
        },
      },
      boxShadow: {
        'glow-cyan':   '0 0 16px rgba(56,189,248,0.35)',
        'glow-indigo': '0 0 16px rgba(129,140,248,0.35)',
        'glow-red':    '0 0 16px rgba(248,113,113,0.40)',
        'glow-green':  '0 0 16px rgba(52,211,153,0.35)',
        'card':        '0 4px 24px rgba(0,0,0,0.45)',
      },
      animation: {
        'pulse-slow':  'pulse 3s cubic-bezier(0.4,0,0.6,1) infinite',
        'count-up':    'countUp 0.6s ease-out forwards',
        'slide-in-r':  'slideInRight 0.3s cubic-bezier(0.16,1,0.3,1) forwards',
        'slide-in-up': 'slideInUp 0.3s cubic-bezier(0.16,1,0.3,1) forwards',
        'fade-in':     'fadeIn 0.25s ease-out forwards',
      },
      keyframes: {
        slideInRight: {
          from: { transform: 'translateX(100%)', opacity: '0' },
          to:   { transform: 'translateX(0)',    opacity: '1' },
        },
        slideInUp: {
          from: { transform: 'translateY(16px)', opacity: '0' },
          to:   { transform: 'translateY(0)',    opacity: '1' },
        },
        fadeIn: {
          from: { opacity: '0' },
          to:   { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
