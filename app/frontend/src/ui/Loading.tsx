import styles from './State.module.css'

export function Loading({ label = 'Ładowanie…' }: { label?: string }) {
  return (
    <p role="status" className={styles.loading}>
      {label}
    </p>
  )
}
