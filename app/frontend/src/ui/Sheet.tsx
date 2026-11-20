import { useEffect, useEffectEvent, useId, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { CloseButton } from './CloseButton'
import styles from './Sheet.module.css'

type SheetProps = {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
}

export function Sheet({ open, title, onClose, children }: SheetProps) {
  const panel = useRef<HTMLDivElement>(null)
  const titleId = useId()
  const close = useEffectEvent(onClose)

  useEffect(() => {
    if (!open) {
      return
    }
    const root = document.getElementById('root')
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        close()
      }
    }
    root?.setAttribute('inert', '')
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', onKeyDown)
    panel.current?.focus()
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = ''
      root?.removeAttribute('inert')
      previous?.focus()
    }
  }, [open])

  if (!open) {
    return null
  }
  return createPortal(
    <div className={styles.overlay} onClick={event => event.target === event.currentTarget && onClose()}>
      <div ref={panel} className={styles.panel} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}>
        <div className={styles.header}>
          <h2 id={titleId} className={styles.title}>{title}</h2>
          <CloseButton onClick={onClose} />
        </div>
        {children}
      </div>
    </div>,
    document.body,
  )
}
