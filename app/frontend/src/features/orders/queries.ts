import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useApi } from '../../app/api'
import type { Order, OrderStatus, ReservationStatus } from '../checkout/orders'

export type ActorKind = 'CUSTOMER' | 'RECIPIENT' | 'SYSTEM'

export type OrderEvent = {
  id: number
  at: string
  entity: 'ORDER' | 'RESERVATION' | 'PAYMENT'
  action: string
  actorKind: ActorKind
}

export type IncomingShipment = {
  orderId: number
  reservationId: number
  status: ReservationStatus
  lockermatName: string
  lockermatAddress: string
  cellNumber: number
  from: string
  to: string
}

export type CancelledOrder = { id: number; status: OrderStatus; refund: number }

export function useOrders() {
  const api = useApi()
  return useQuery({
    queryKey: ['orders'],
    queryFn: ({ signal }) => api<Order[]>('/api/orders', { signal }),
  })
}

export function useIncoming() {
  const api = useApi()
  return useQuery({
    queryKey: ['shipments', 'incoming'],
    queryFn: ({ signal }) => api<IncomingShipment[]>('/api/shipments/incoming', { signal }),
  })
}

export function useOrderHistory(id: number) {
  const api = useApi()
  return useQuery({
    queryKey: ['orders', id, 'history'],
    queryFn: ({ signal }) => api<OrderEvent[]>(`/api/orders/${id}/history`, { signal }),
  })
}

export function useCancelOrder(id: number, onSuccess: (cancelled: CancelledOrder) => void) {
  const api = useApi()
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => api<CancelledOrder>(`/api/orders/${id}/cancel`, { method: 'POST' }),
    onSuccess,
    onSettled: () => client.invalidateQueries({ queryKey: ['orders'] }),
  })
}
