import { useState } from 'react'
import { Loading, cx, formatDateTime, reveal } from '../../ui'
import styles from './Detail.module.css'
import { useOrderHistory } from './queries'
import { actorLabel, eventLabel } from './status'

export function OrderHistory({ orderId }: { orderId: number }) {
  const [open, setOpen] = useState(false)

  return (
    <details className={styles.history} onToggle={event => setOpen(event.currentTarget.open)}>
      <summary className={styles.toggle}>Historia zamówienia</summary>
      {open && <Events orderId={orderId} />}
    </details>
  )
}

function Events({ orderId }: { orderId: number }) {
  const history = useOrderHistory(orderId)

  if (!history.data) {
    return history.isError ? <p className={styles.muted}>Nie udało się wczytać historii.</p> : <Loading />
  }
  return (
    <ol aria-label="Historia zamówienia" className={cx(styles.events, reveal)}>
      {history.data.map(event => (
        <li key={event.id} className={styles.event}>
          <time dateTime={event.at} className={styles.time}>
            {formatDateTime(event.at)}
          </time>
          <span>{eventLabel(event)}</span>
          <span className={styles.who}>{actorLabel(event.actorKind)}</span>
        </li>
      ))}
    </ol>
  )
}
