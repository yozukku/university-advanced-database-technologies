import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { useApi } from '../../app/api'
import { paths } from '../../app/paths'
import type { Size } from '../lockers/filters'

export type OrderStatus = 'AWAITING_PAYMENT' | 'PAID' | 'COMPLETED' | 'CANCELLED' | 'EXPIRED'

export type ReservationStatus = 'BOOKED' | 'OCCUPIED' | 'COMPLETED' | 'CANCELLED' | 'NO_SHOW'

export type NewOrder = { lockermatId: number; size: Size; from: string; to: string }

export type Order = {
  id: number
  number: string
  status: OrderStatus
  size: Size
  price: number
  paymentDeadline: string
  createdAt: string
  reservationId: number
  reservationStatus: ReservationStatus
  from: string
  to: string
  lockermatName: string
  lockermatAddress: string
  cellNumber: number
}

export type AccessCode = { purpose: 'DROP_OFF' | 'PICK_UP'; pin: string; validFrom: string; validTo: string }

export function useBookStorage() {
  const api = useApi()
  const client = useQueryClient()
  const navigate = useNavigate()
  return useMutation({
    mutationFn: (order: NewOrder) => api<Order>('/api/orders', { method: 'POST', body: order }),
    onSuccess: order => navigate(paths.checkout(order.id)),
    onError: () => client.invalidateQueries({ queryKey: ['lockermats'] }),
  })
}

export function useOrder(id: number) {
  const api = useApi()
  return useQuery({
    queryKey: ['orders', id],
    queryFn: ({ signal }) => api<Order>(`/api/orders/${id}`, { signal }),
  })
}

export function useAccessCodes(id: number) {
  const api = useApi()
  return useQuery({
    queryKey: ['orders', id, 'codes'],
    queryFn: ({ signal }) => api<AccessCode[]>(`/api/orders/${id}/codes`, { signal }),
  })
}

export function usePay(id: number) {
  const api = useApi()
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => api<unknown>(`/api/orders/${id}/payments`, { method: 'POST', body: { result: 'SUCCESS' } }),
    onSettled: () => client.invalidateQueries({ queryKey: ['orders', id] }),
  })
}
