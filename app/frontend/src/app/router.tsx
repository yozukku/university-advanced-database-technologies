import { Link, createBrowserRouter } from 'react-router'
import { CheckoutPage } from '../features/checkout/CheckoutPage'
import { LockersPage } from '../features/lockers/LockersPage'
import { EmptyState, Page } from '../ui'
import { paths } from './paths'
import { Shell } from './Shell'

export const router = createBrowserRouter([
  {
    element: <Shell />,
    children: [
      { index: true, element: <LockersPage /> },
      { path: 'rezerwacje', element: <Placeholder title="Moje rezerwacje" /> },
      { path: 'rezerwacje/:orderId', element: <Placeholder title="Rezerwacja" /> },
      { path: 'rezerwacje/:orderId/platnosc', element: <CheckoutPage /> },
      { path: 'rezerwacje/do-odbioru/:reservationId', element: <Placeholder title="Do odbioru" /> },
      { path: '*', element: <NotFound /> },
    ],
  },
])

function Placeholder({ title }: { title: string }) {
  return (
    <Page title={title}>
      <EmptyState title="Ten widok jest w przygotowaniu." />
    </Page>
  )
}

function NotFound() {
  return (
    <Page title="Nie znaleziono strony">
      <EmptyState title="Ta strona nie istnieje.">
        <Link to={paths.lockers}>Wróć do listy punktów</Link>
      </EmptyState>
    </Page>
  )
}
