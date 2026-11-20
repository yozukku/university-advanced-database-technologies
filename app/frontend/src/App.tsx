import { useEffect, useState } from 'react'
import { useAuth } from 'react-oidc-context'

type Profile = { sub: string; name: string; email: string }
type ProfileState = { profile?: Profile; failed?: boolean }

export function App() {
  const auth = useAuth()

  return (
    <main>
      <h1>Bagażomat</h1>
      {auth.isLoading || auth.activeNavigator
        ? <p role="status">Trwa logowanie…</p>
        : auth.isAuthenticated && auth.user
          ? <Account key={auth.user.profile.sub} token={auth.user.access_token} />
          : <button type="button" onClick={() => void auth.signinRedirect()}>Zaloguj się</button>}
      {auth.error && <p role="alert">Nie udało się zalogować. Spróbuj ponownie.</p>}
    </main>
  )
}

function Account({ token }: { token: string }) {
  const [state, setState] = useState<ProfileState>({})

  useEffect(() => {
    const controller = new AbortController()

    async function loadProfile() {
      try {
        const response = await fetch('/api/me', {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        })
        if (!response.ok) {
          setState({ failed: true })
          return
        }
        const profile: Profile = await response.json()
        setState({ profile })
      } catch {
        if (!controller.signal.aborted) {
          setState({ failed: true })
        }
      }
    }

    void loadProfile()
    return () => controller.abort()
  }, [token])

  if (state.failed) {
    return <p role="alert">Nie udało się pobrać danych konta.</p>
  }
  if (!state.profile) {
    return <p role="status">Pobieranie danych konta…</p>
  }
  return <p>Witaj, {state.profile.name}</p>
}
