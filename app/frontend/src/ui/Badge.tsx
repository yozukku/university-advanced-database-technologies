import type { ReactNode } from 'react'
import styles from './Badge.module.css'
import { cx } from './cx'

type Tone = 'neutral' | 'accent' | 'danger'

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return <span className={cx(styles.badge, styles[tone])}>{children}</span>
}
