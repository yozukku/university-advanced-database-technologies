import { Link, Navigate, useParams } from 'react-router'
import { paths } from '../../app/paths'
import { Card, EmptyState, Loading, Page, formatWindow } from '../../ui'
import { useAccessCodes, useOrder, type AccessCode } from '../checkout/orders'
import { OpenCell } from '../opening/OpenCell'
import { CancelOrder } from './CancelOrder'
import { Fact, Facts, StatusLine, Summary } from './Detail'
import styles from './Detail.module.css'
import { OrderHistory } from './OrderHistory'
import { canCancel, canOpen, orderStatus, pinPurpose } from './status'

const TITLE = 'Rezerwacja'

export function OrderPage() {
  const id = Number(useParams().orderId)

  if (!Number.isSafeInteger(id) || id <= 0) {
    return <Missing />
  }
  return <OrderDetail id={id} />
}

function OrderDetail({ id }: { id: number }) {
  const order = useOrder(id)

  if (!order.data) {
    return order.isError ? <Missing /> : <Page title={TITLE}><Loading /></Page>
  }
  if (order.data.status === 'AWAITING_PAYMENT') {
    return <Navigate to={paths.checkout(id)} replace />
  }
  const purpose = pinPurpose(order.data)
  return (
    <Page title={TITLE}>
      <Card className={styles.card}>
        <Summary
          name={order.data.lockermatName}
          address={order.data.lockermatAddress}
          details={`Rozmiar ${order.data.size} · ${formatWindow(order.data.from, order.data.to)}`}
        />
        <StatusLine status={orderStatus(order.data)} />
        <Facts>
          <Fact label="Skrytka" value={order.data.cellNumber} />
          {purpose && <Pin orderId={id} purpose={purpose} />}
        </Facts>
        {canOpen(order.data) && (
          <div className={styles.actions}>
            <OpenCell reservationId={order.data.reservationId} cellNumber={order.data.cellNumber} />
            {canCancel(order.data) && <CancelOrder order={order.data} />}
          </div>
        )}
        <OrderHistory orderId={id} />
      </Card>
    </Page>
  )
}

function Pin({ orderId, purpose }: { orderId: number; purpose: AccessCode['purpose'] }) {
  const codes = useAccessCodes(orderId)

  return <Fact label="PIN" value={codes.data?.find(code => code.purpose === purpose)?.pin ?? '…'} wide />
}

function Missing() {
  return (
    <Page title={TITLE}>
      <EmptyState title="Nie udało się wczytać rezerwacji.">
        <Link to={paths.orders}>Wróć do listy rezerwacji</Link>
      </EmptyState>
    </Page>
  )
}
