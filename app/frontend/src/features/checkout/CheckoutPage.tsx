import { Link, useParams } from 'react-router'
import { paths } from '../../app/paths'
import { Button, Card, EmptyState, Loading, Page, formatPrice, formatTime, formatWindow } from '../../ui'
import styles from './CheckoutPage.module.css'
import { useAccessCodes, useOrder, usePay, type Order, type OrderStatus } from './orders'

const CLOSED_TITLES: Partial<Record<OrderStatus, string>> = {
  EXPIRED: 'Termin płatności minął.',
  CANCELLED: 'Rezerwacja została anulowana.',
}

export function CheckoutPage() {
  const id = Number(useParams().orderId)

  if (!Number.isSafeInteger(id) || id <= 0) {
    return (
      <Page title="Płatność">
        <EmptyState title="Nie znaleziono rezerwacji.">
          <Link to={paths.lockers}>Wróć do listy punktów</Link>
        </EmptyState>
      </Page>
    )
  }
  return <Checkout id={id} />
}

function Checkout({ id }: { id: number }) {
  const order = useOrder(id)

  if (!order.data) {
    return (
      <Page title="Płatność">
        {order.isError ? (
          <EmptyState title="Nie udało się wczytać rezerwacji.">
            <Link to={paths.lockers}>Wróć do listy punktów</Link>
          </EmptyState>
        ) : (
          <Loading />
        )}
      </Page>
    )
  }
  if (order.data.status === 'AWAITING_PAYMENT') {
    return <Payment order={order.data} />
  }
  if (order.data.status === 'PAID' && order.data.reservationStatus === 'BOOKED') {
    return <Paid order={order.data} />
  }
  return (
    <Page title="Płatność">
      <EmptyState title={CLOSED_TITLES[order.data.status] ?? 'Ta rezerwacja jest już opłacona.'}>
        <Link to={paths.order(id)}>Przejdź do rezerwacji</Link>
      </EmptyState>
    </Page>
  )
}

function Payment({ order }: { order: Order }) {
  const pay = usePay(order.id)

  return (
    <Page title="Płatność">
      <Card className={styles.card}>
        <Summary order={order} />
        <div className={styles.total}>
          <p>Do zapłaty</p>
          <p className={styles.amount}>{formatPrice(order.price)}</p>
        </div>
        <div className={styles.actions}>
          <Button onClick={() => pay.mutate()} disabled={pay.isPending}>
            Zapłać (symulacja)
          </Button>
          <p className={styles.muted}>Zapłać do {formatTime(order.paymentDeadline)}</p>
        </div>
      </Card>
    </Page>
  )
}

function Paid({ order }: { order: Order }) {
  const codes = useAccessCodes(order.id)
  const dropOff = codes.data?.find(code => code.purpose === 'DROP_OFF')

  return (
    <Page title="Rezerwacja opłacona">
      <Card className={styles.card}>
        <Summary order={order} />
        <dl className={styles.facts}>
          <div className={styles.fact}>
            <dt>Skrytka</dt>
            <dd>{order.cellNumber}</dd>
          </div>
          <div className={styles.fact}>
            <dt>PIN</dt>
            <dd>{dropOff?.pin ?? '…'}</dd>
          </div>
        </dl>
        <p className={styles.muted}>Ten PIN otworzy skrytkę, gdy zostawisz bagaż. Znajdziesz go też w „Moje rezerwacje”.</p>
        <Link to={paths.order(order.id)} className={styles.link}>
          Przejdź do rezerwacji
        </Link>
      </Card>
    </Page>
  )
}

function Summary({ order }: { order: Order }) {
  return (
    <div className={styles.summary}>
      <h2 className={styles.name}>{order.lockermatName}</h2>
      <p className={styles.muted}>{order.lockermatAddress}</p>
      <p className={styles.muted}>
        Rozmiar {order.size} · {formatWindow(order.from, order.to)}
      </p>
    </div>
  )
}
