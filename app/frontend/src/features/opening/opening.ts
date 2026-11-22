import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useApi } from '../../app/api'
import { useToast } from '../../ui'

export type Opening = { id: number; purpose: 'DROP_OFF' | 'PICK_UP'; result: 'OPENED' | 'DOOR_FAILED' | 'PENDING' }

const DOOR_FAILED = 'Nie udało się otworzyć skrytki. Spróbuj ponownie.'
const PENDING = 'Czekamy na potwierdzenie otwarcia skrytki.'

export function useOpenCell(reservationId: number, cellNumber: number) {
  const api = useApi()
  const client = useQueryClient()
  const toast = useToast()
  return useMutation({
    mutationFn: () => api<Opening>(`/api/reservations/${reservationId}/open`, { method: 'POST' }),
    onSuccess: opening => {
      if (opening.result === 'DOOR_FAILED') {
        toast(DOOR_FAILED, 'error')
      } else if (opening.result === 'PENDING') {
        toast(PENDING)
      } else {
        toast(`Skrytka nr ${cellNumber} jest otwarta.`, 'success')
      }
    },
    onSettled: () =>
      Promise.all([client.invalidateQueries({ queryKey: ['orders'] }), client.invalidateQueries({ queryKey: ['shipments'] })]),
  })
}
