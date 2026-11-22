import type { ReactNode } from 'react'
import { Badge, cx, useReveal } from '../../ui'
import styles from './Detail.module.css'
import type { Status } from './status'

export function Summary({ name, address, details }: { name: string; address: string; details: string }) {
  return (
    <div className={styles.summary}>
      <h2 className={styles.name}>{name}</h2>
      <p className={styles.muted}>{address}</p>
      <p className={styles.muted}>{details}</p>
    </div>
  )
}

export function StatusLine({ status }: { status: Status }) {
  const reveal = useReveal(status.label)

  return (
    <p key={status.label} className={cx(styles.status, reveal)}>
      <Badge tone={status.tone}>{status.label}</Badge>
      {status.action && <span className={styles.action}>{status.action}</span>}
    </p>
  )
}

export function Facts({ children }: { children: ReactNode }) {
  return <dl className={styles.facts}>{children}</dl>
}

export function Fact({ label, value, wide = false }: { label: string; value: ReactNode; wide?: boolean }) {
  return (
    <div className={cx(styles.fact, wide && styles.wide)}>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  )
}
