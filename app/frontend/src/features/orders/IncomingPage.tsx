import { Link, useParams } from 'react-router'
import { paths } from '../../app/paths'
import { Card, EmptyState, Loading, Page, formatWindow } from '../../ui'
import { Fact, Facts, StatusLine, Summary } from './Detail'
import styles from './Detail.module.css'
import { OrderHistory } from './OrderHistory'
import { useIncoming } from './queries'
import { incomingStatus } from './status'

const TITLE = 'Przesyłka'

export function IncomingPage() {
  const id = Number(useParams().reservationId)
  const incoming = useIncoming()
  const shipment = incoming.data?.find(item => item.reservationId === id)

  if (!shipment) {
    return (
      <Page title={TITLE}>
        {incoming.data || incoming.isError ? (
          <EmptyState title="Nie znaleziono przesyłki.">
            <Link to={paths.orders}>Wróć do listy rezerwacji</Link>
          </EmptyState>
        ) : (
          <Loading />
        )}
      </Page>
    )
  }
  return (
    <Page title={TITLE}>
      <Card className={styles.card}>
        <Summary name={shipment.lockermatName} address={shipment.lockermatAddress} details={formatWindow(shipment.from, shipment.to)} />
        <StatusLine status={incomingStatus(shipment)} />
        <Facts>
          <Fact label="Skrytka" value={shipment.cellNumber} />
        </Facts>
        <OrderHistory orderId={shipment.orderId} />
      </Card>
    </Page>
  )
}
