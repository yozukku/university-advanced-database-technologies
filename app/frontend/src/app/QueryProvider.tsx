import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { useAuth } from 'react-oidc-context'
import { useToast } from '../ui'
import { ApiError, errorMessage } from './api'

export function QueryProvider({ children }: { children: ReactNode }) {
  const toast = useToast()
  const { removeUser } = useAuth()
  const [client] = useState(() => {
    const onError = (error: Error) => {
      toast(errorMessage(error), 'error')
      if (error instanceof ApiError && error.status === 401) {
        void removeUser()
      }
    }
    return new QueryClient({
      queryCache: new QueryCache({ onError }),
      mutationCache: new MutationCache({ onError }),
      defaultOptions: { queries: { retry: false } },
    })
  })

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}
