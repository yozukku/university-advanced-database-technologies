import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useApi } from '../../app/api'
import type { Size, Window } from './filters'

export type Offer = { size: Size; free: number; price: number }

export type Lockermat = {
  id: number
  name: string
  address: string
  lng: number
  lat: number
  sizes: Offer[]
}

export function useLockermats(search: string, { from, to }: Window) {
  const api = useApi()
  return useQuery({
    queryKey: ['lockermats', search, from, to],
    queryFn: ({ signal }) => api<Lockermat[]>(`/api/lockermats?${new URLSearchParams({ q: search, from, to })}`, { signal }),
    placeholderData: keepPreviousData,
  })
}
