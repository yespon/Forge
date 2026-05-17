import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { X, CheckCircle2, AlertCircle, Info } from 'lucide-react'

// ---- types ----
type ToastVariant = 'default' | 'success' | 'error' | 'info'

interface Toast {
  id: number
  message: string
  variant: ToastVariant
}

interface ToastContextValue {
  toast: (message: string, variant?: ToastVariant) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

let _nextId = 0

// ---- provider ----
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const addToast = useCallback((message: string, variant: ToastVariant = 'default') => {
    const id = ++_nextId
    setToasts((prev) => [...prev, { id, message, variant }])
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000)
  }, [])

  const remove = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ toast: addToast }}>
      {children}
      <ToastContainer toasts={toasts} onRemove={remove} />
    </ToastContext.Provider>
  )
}

// ---- hook ----
export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}

// ---- standalone Toaster component (import into App) ----
export function Toaster() {
  // Intentionally empty – the actual rendering is in ToastProvider above.
  // This exists so App.tsx can import `<Toaster />` which acts as a no-op
  // when the ToastProvider is mounted higher in the tree (see below pattern).
  return null
}

// ---- container UI ----
const variantStyles: Record<ToastVariant, string> = {
  default: 'bg-popover border text-popover-foreground',
  success: 'bg-green-50 border-green-200 text-green-900 dark:bg-green-950 dark:border-green-800 dark:text-green-100',
  error: 'bg-red-50 border-red-200 text-red-900 dark:bg-red-950 dark:border-red-800 dark:text-red-100',
  info: 'bg-blue-50 border-blue-200 text-blue-900 dark:bg-blue-950 dark:border-blue-800 dark:text-blue-100',
}

const variantIcons: Record<ToastVariant, ReactNode> = {
  default: null,
  success: <CheckCircle2 className="h-4 w-4 shrink-0 text-green-600 dark:text-green-400" />,
  error: <AlertCircle className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />,
  info: <Info className="h-4 w-4 shrink-0 text-blue-600 dark:text-blue-400" />,
}

function ToastContainer({ toasts, onRemove }: { toasts: Toast[]; onRemove: (id: number) => void }) {
  if (toasts.length === 0) return null
  return (
    <div className="fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 max-w-sm">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`flex items-center gap-2 rounded-lg border px-4 py-3 shadow-lg text-sm animate-in slide-in-from-bottom-2 ${variantStyles[t.variant]}`}
        >
          {variantIcons[t.variant]}
          <span className="flex-1">{t.message}</span>
          <button onClick={() => onRemove(t.id)} className="shrink-0 opacity-50 hover:opacity-100">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
    </div>
  )
}
