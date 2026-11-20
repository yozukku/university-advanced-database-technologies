import { Link, createBrowserRouter } from 'react-router'
import { CheckoutPage } from '../features/checkout/CheckoutPage'
import { LockersPage } from '../features/lockers/LockersPage'
import { IncomingPage } from '../features/orders/IncomingPage'
import { OrderPage } from '../features/orders/OrderPage'
import { OrdersPage } from '../features/orders/OrdersPage'
import { EmptyState, Page } from '../ui'
import { paths } from './paths'
import { Shell } from './Shell'

export const router = createBrowserRouter([
  {
    element: <Shell />,
    children: [
      { index: true, element: <LockersPage /> },
      { path: 'rezerwacje', element: <OrdersPage /> },
      { path: 'rezerwacje/:orderId', element: <OrderPage /> },
      { path: 'rezerwacje/:orderId/platnosc', element: <CheckoutPage /> },
      { path: 'rezerwacje/do-odbioru/:reservationId', element: <IncomingPage /> },
      { path: '*', element: <NotFound /> },
    ],
  },
])

function NotFound() {
  return (
    <Page title="Nie znaleziono strony">
      <EmptyState title="Ta strona nie istnieje.">
        <Link to={paths.lockers}>Wróć do listy punktów</Link>
      </EmptyState>
    </Page>
  )
}
