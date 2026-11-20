import { createRoot } from 'react-dom/client'
import { AuthProvider } from 'react-oidc-context'
import { App } from './App'
import './style.css'

const authority = import.meta.env.VITE_KEYCLOAK_ISSUER ?? 'http://localhost:8081/realms/bagazomat'

createRoot(document.getElementById('root')!).render(
  <AuthProvider
    authority={authority}
    client_id="bagazomat-web"
    redirect_uri={new URL('/', window.location.origin).href}
    response_type="code"
    scope="openid profile email"
    automaticSilentRenew={false}
    onSigninCallback={() => window.history.replaceState(null, '', '/')}
  >
    <App />
  </AuthProvider>,
)
