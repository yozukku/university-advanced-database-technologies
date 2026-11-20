import { useState } from 'react'
import { Button, Sheet, formatPrice, useToast } from '../../ui'
import type { Order } from '../checkout/orders'
import styles from './Detail.module.css'
import { useCancelOrder } from './queries'

export function CancelOrder({ order }: { order: Order }) {
  const [open, setOpen] = useState(false)
  const toast = useToast()
  const cancel = useCancelOrder(order.id, cancelled => {
    setOpen(false)
    toast(`Rezerwacja anulowana. Zwrot ${formatPrice(cancelled.refund)}.`)
  })

  return (
    <>
      <Button variant="secondary" onClick={() => setOpen(true)}>
        Anuluj
      </Button>
      <Sheet open={open} title="Anulować rezerwację?" onClose={() => setOpen(false)}>
        <p className={styles.muted}>Skrytka zostanie zwolniona, a pełna kwota wróci na Twoje konto.</p>
        <div className={styles.total}>
          <p>Zwrot</p>
          <p className={styles.amount}>{formatPrice(order.price)}</p>
        </div>
        <Button onClick={() => cancel.mutate()} disabled={cancel.isPending}>
          Anuluj rezerwację
        </Button>
      </Sheet>
    </>
  )
}
