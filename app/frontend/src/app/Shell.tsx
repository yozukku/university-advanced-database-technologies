import { useQuery } from '@tanstack/react-query'
import { Link, NavLink, Outlet } from 'react-router'
import { useAuth } from 'react-oidc-context'
import { Button, Loading, cx } from '../ui'
import { useApi } from './api'
import { paths } from './paths'
import styles from './Shell.module.css'

type Me = { sub: string; name: string; email: string }

export function Shell() {
  const auth = useAuth()

  if (auth.isLoading || auth.activeNavigator) {
    return <Loading />
  }
  if (!auth.isAuthenticated) {
    return <SignIn />
  }
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.bar}>
          <Link to={paths.lockers} className={styles.brand}>
            Bagażomat
          </Link>
          <nav aria-label="Menu główne" className={styles.nav}>
            <NavLink to={paths.lockers} end className={navClass}>
              Punkty
            </NavLink>
            <NavLink to={paths.orders} className={navClass}>
              Moje rezerwacje
            </NavLink>
          </nav>
          <Account />
        </div>
      </header>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}

function navClass({ isActive }: { isActive: boolean }) {
  return cx(styles.link, isActive && styles.active)
}

function Account() {
  const auth = useAuth()
  const api = useApi()
  const me = useQuery({ queryKey: ['me'], queryFn: ({ signal }) => api<Me>('/api/me', { signal }) })

  return (
    <div className={styles.account}>
      {me.data && <span className={styles.name}>{me.data.name}</span>}
      <Button variant="ghost" onClick={() => void auth.signoutRedirect({ post_logout_redirect_uri: window.location.origin + paths.lockers })}>
        Wyloguj
      </Button>
    </div>
  )
}

function SignIn() {
  const auth = useAuth()

  return (
    <main className={styles.signIn}>
      <div className={styles.signInCard}>
        <h1 className={styles.signInTitle}>Bagażomat</h1>
        <p className={styles.signInText}>Zaloguj się, aby zarezerwować skrytkę i zobaczyć swoje rezerwacje.</p>
        <Button onClick={() => void auth.signinRedirect()}>Zaloguj się</Button>
        {auth.error && <p role="alert" className={styles.signInError}>Nie udało się zalogować. Spróbuj ponownie.</p>}
      </div>
    </main>
  )
}
