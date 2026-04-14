import React from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { X, CheckCircle, AlertTriangle, Info, AlertCircle } from 'lucide-react'
import useAppStore from '../../store/useAppStore'

const ICONS = {
  success: <CheckCircle  size={16} color="#34D399" />,
  error:   <AlertCircle size={16} color="#F87171" />,
  warning: <AlertTriangle size={16} color="#FBBF24" />,
  info:    <Info         size={16} color="#8B5CF6" />,
}

export default function ToastContainer() {
  const { toasts, removeToast } = useAppStore()

  return (
    <div className="fixed top-5 right-5 z-50 flex flex-col gap-2 pointer-events-none">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, x: 40, scale: 0.95 }}
            animate={{ opacity: 1, x: 0,  scale: 1    }}
            exit={{    opacity: 0, x: 40, scale: 0.95 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl shadow-card min-w-[280px] max-w-xs"
            style={{
              background: 'rgba(17,17,40,0.95)',
              border: '1px solid rgba(139,92,246,0.22)',
              backdropFilter: 'blur(12px)',
              boxShadow: '0 8px 32px rgba(0,0,0,0.50)',
            }}
          >
            <span className="mt-0.5 flex-shrink-0">{ICONS[t.type] || ICONS.info}</span>
            <div className="flex-1 min-w-0">
              {t.title && <p className="text-sm font-semibold text-white">{t.title}</p>}
              <p className="text-xs" style={{ color: 'var(--text-2)' }}>{t.message}</p>
            </div>
            <button
              className="flex-shrink-0 mt-0.5 transition-smooth hover:text-white"
              style={{ color: 'var(--text-3)' }}
              onClick={() => removeToast(t.id)}
            >
              <X size={13} />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
