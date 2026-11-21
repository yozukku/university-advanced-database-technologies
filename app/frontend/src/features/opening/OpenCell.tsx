import { Button } from '../../ui'
import { useOpenCell } from './opening'

export function OpenCell({ reservationId, cellNumber }: { reservationId: number; cellNumber: number }) {
  const open = useOpenCell(reservationId, cellNumber)

  return (
    <Button onClick={() => open.mutate()} disabled={open.isPending} aria-busy={open.isPending}>
      Otwórz skrytkę
    </Button>
  )
}
