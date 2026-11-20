import styles from './CloseButton.module.css'

export function CloseButton({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" className={styles.close} aria-label="Zamknij" onClick={onClick}>
      <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
        <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    </button>
  )
}
