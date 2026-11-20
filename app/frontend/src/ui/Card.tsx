import type { HTMLAttributes } from 'react'
import styles from './Card.module.css'
import { cx } from './cx'

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cx(styles.card, className)} {...props} />
}
