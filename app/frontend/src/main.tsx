import { createRoot } from 'react-dom/client'
import { AuthProvider } from 'react-oidc-context'
import { App } from './app/App'
import { paths } from './app/paths'
import { router } from './app/router'
import './ui/global.css'

const authority = import.meta.env.VITE_KEYCLOAK_ISSUER ?? 'http://localhost:8081/realms/bagazomat'

createRoot(document.getElementById('root')!).render(
  <AuthProvider
    authority={authority}
    client_id="bagazomat-web"
    redirect_uri={new URL('/', window.location.origin).href}
    response_type="code"
    scope="openid profile email"
    automaticSilentRenew={false}
    onSigninCallback={() => void router.navigate(paths.lockers, { replace: true })}
  >
    <App />
  </AuthProvider>,
)
