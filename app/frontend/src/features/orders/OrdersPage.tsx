import { Link, useSearchParams } from 'react-router'
import { paths } from '../../app/paths'
import { Badge, Button, EmptyState, Loading, Page, Tabs, formatWindow } from '../../ui'
import type { Order } from '../checkout/orders'
import styles from './OrdersPage.module.css'
import { useIncoming, useOrders } from './queries'
import { incomingStatus, isActive, orderStatus, type Status } from './status'

type Tab = 'aktywne' | 'do-odbioru' | 'zakonczone'

const TAB_PARAM = 'zakladka'

const TABS: Array<{ value: Tab; label: string }> = [
  { value: 'aktywne', label: 'Aktywne' },
  { value: 'do-odbioru', label: 'Do odbioru' },
  { value: 'zakonczone', label: 'Zakończone' },
]

type Row = { key: number; href: string; name: string; from: string; to: string; status: Status }

export function OrdersPage() {
  const [params, setParams] = useSearchParams()
  const tab = TABS.find(candidate => candidate.value === params.get(TAB_PARAM))?.value ?? 'aktywne'

  return (
    <Page title="Moje rezerwacje">
      <Tabs<Tab>
        label="Rezerwacje"
        tabs={TABS}
        value={tab}
        onChange={next => setParams(next === 'aktywne' ? {} : { [TAB_PARAM]: next }, { replace: true })}
      >
        {tab === 'do-odbioru' ? <IncomingList /> : <OrderList active={tab === 'aktywne'} />}
      </Tabs>
    </Page>
  )
}

function OrderList({ active }: { active: boolean }) {
  const orders = useOrders()

  if (!orders.data) {
    return <Pending isError={orders.isError} retry={() => void orders.refetch()} />
  }
  const rows = orders.data.filter(order => isActive(order) === active).map(orderRow)
  if (rows.length === 0) {
    return active ? (
      <EmptyState title="Nie masz aktywnych rezerwacji.">
        <Link to={paths.lockers}>Znajdź punkt</Link>
      </EmptyState>
    ) : (
      <EmptyState title="Nie masz zakończonych rezerwacji." />
    )
  }
  return <RowList label="Rezerwacje" rows={rows} />
}

function IncomingList() {
  const incoming = useIncoming()

  if (!incoming.data) {
    return <Pending isError={incoming.isError} retry={() => void incoming.refetch()} />
  }
  if (incoming.data.length === 0) {
    return <EmptyState title="Nie masz przesyłek do odbioru." />
  }
  const rows = incoming.data.map(shipment => ({
    key: shipment.reservationId,
    href: paths.incoming(shipment.reservationId),
    name: shipment.lockermatName,
    from: shipment.from,
    to: shipment.to,
    status: incomingStatus(shipment),
  }))
  return <RowList label="Przesyłki" rows={rows} />
}

function orderRow(order: Order): Row {
  return {
    key: order.id,
    href: order.status === 'AWAITING_PAYMENT' ? paths.checkout(order.id) : paths.order(order.id),
    name: order.lockermatName,
    from: order.from,
    to: order.to,
    status: orderStatus(order),
  }
}

function RowList({ label, rows }: { label: string; rows: Row[] }) {
  return (
    <ul aria-label={label} className={styles.list}>
      {rows.map(row => (
        <li key={row.key}>
          <Link to={row.href} className={styles.row}>
            <span className={styles.place}>
              <span className={styles.name}>{row.name}</span>
              <span className={styles.window}>{formatWindow(row.from, row.to)}</span>
            </span>
            <Badge tone={row.status.tone}>{row.status.label}</Badge>
          </Link>
        </li>
      ))}
    </ul>
  )
}

function Pending({ isError, retry }: { isError: boolean; retry: () => void }) {
  if (!isError) {
    return <Loading />
  }
  return (
    <EmptyState title="Nie udało się wczytać rezerwacji.">
      <Button variant="secondary" onClick={retry}>
        Spróbuj ponownie
      </Button>
    </EmptyState>
  )
}
