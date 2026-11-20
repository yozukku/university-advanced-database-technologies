import { Button } from '../../ui'
import { useBookStorage, type NewOrder } from './orders'

export function BookButton({ order }: { order: NewOrder }) {
  const book = useBookStorage()

  return (
    <Button onClick={() => book.mutate(order)} disabled={book.isPending}>
      Zarezerwuj
    </Button>
  )
}
