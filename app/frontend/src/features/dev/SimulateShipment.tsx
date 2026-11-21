import { Button } from '../../ui'
import { useSimulateShipment } from './shipments'

export function SimulateShipment() {
  const simulate = useSimulateShipment()

  return (
    <Button variant="secondary" onClick={() => simulate.mutate()} disabled={simulate.isPending}>
      Symuluj przesyłkę
    </Button>
  )
}
