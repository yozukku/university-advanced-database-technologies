import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { CloseButton } from './CloseButton'
import styles from './Toast.module.css'
import { cx } from './cx'

type Tone = 'neutral' | 'success' | 'error'
type Toast = { id: number; message: string; tone: Tone }
type ShowToast = (message: string, tone?: Tone) => void

const DURATION_MS = 6000

const ToastContext = createContext<ShowToast | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const lastId = useRef(0)

  const dismiss = useCallback((id: number) => {
    setToasts(current => current.filter(toast => toast.id !== id))
  }, [])

  const show = useCallback<ShowToast>((message, tone = 'neutral') => {
    const id = ++lastId.current
    setToasts(current => current.some(toast => toast.message === message) ? current : [...current, { id, message, tone }])
  }, [])

  return (
    <ToastContext value={show}>
      {children}
      {createPortal(
        <div className={styles.region}>
          {toasts.map(toast => <ToastItem key={toast.id} toast={toast} onDismiss={dismiss} />)}
        </div>,
        document.body,
      )}
    </ToastContext>
  )
}

export function useToast() {
  const show = useContext(ToastContext)
  if (!show) {
    throw new Error('useToast wymaga ToastProvider')
  }
  return show
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: (id: number) => void }) {
  useEffect(() => {
    const timer = window.setTimeout(() => onDismiss(toast.id), DURATION_MS)
    return () => window.clearTimeout(timer)
  }, [toast.id, onDismiss])

  return (
    <div role={toast.tone === 'error' ? 'alert' : 'status'} className={cx(styles.toast, styles[toast.tone])}>
      {toast.tone === 'success' && (
        <svg className={styles.check} viewBox="0 0 16 16" aria-hidden="true">
          <path d="M3 8.5l3.5 3.5L13 4.5" pathLength={1} />
        </svg>
      )}
      <p className={styles.message}>{toast.message}</p>
      <CloseButton onClick={() => onDismiss(toast.id)} />
    </div>
  )
}
