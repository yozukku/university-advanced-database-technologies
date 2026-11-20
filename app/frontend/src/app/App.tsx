import { RouterProvider } from 'react-router/dom'
import { ToastProvider } from '../ui'
import { QueryProvider } from './QueryProvider'
import { router } from './router'

export function App() {
  return (
    <ToastProvider>
      <QueryProvider>
        <RouterProvider router={router} />
      </QueryProvider>
    </ToastProvider>
  )
}
