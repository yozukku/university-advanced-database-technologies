import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useApi } from '../../app/api'
import type { IncomingShipment } from '../orders/queries'

export function useSimulateShipment() {
  const api = useApi()
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => api<IncomingShipment>('/api/dev/shipments', { method: 'POST' }),
    onSettled: () => client.invalidateQueries({ queryKey: ['shipments'] }),
  })
}
