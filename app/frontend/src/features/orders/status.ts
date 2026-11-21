import type { AccessCode, Order, OrderStatus } from '../checkout/orders'
import type { ActorKind, IncomingShipment, OrderEvent } from './queries'

export type Status = { label: string; tone: 'accent' | 'neutral'; action?: string }

const DROP_OFF = 'Zostaw bagaż'
const PICK_UP = 'Odbierz bagaż'

const CLOSED: Partial<Record<OrderStatus, string>> = {
  COMPLETED: 'Zakończona',
  CANCELLED: 'Anulowana',
  EXPIRED: 'Wygasła',
}

const EVENTS: Record<string, string> = {
  'ORDER:CREATED': 'Zamówienie utworzone',
  'ORDER:PAID': 'Zamówienie opłacone',
  'ORDER:CANCELLED': 'Zamówienie anulowane',
  'ORDER:EXPIRED': 'Termin płatności minął',
  'PAYMENT:REFUNDED': 'Zwrot płatności',
  'RESERVATION:DEPOSITED': 'Bagaż zostawiony',
  'RESERVATION:COLLECTED': 'Bagaż odebrany',
}

const ACTORS: Record<ActorKind, string> = {
  CUSTOMER: 'Klient',
  RECIPIENT: 'Odbiorca',
  SYSTEM: 'System',
}

export function isActive(order: Order) {
  return order.status === 'AWAITING_PAYMENT' || order.status === 'PAID'
}

export function orderStatus(order: Order): Status {
  if (order.status === 'AWAITING_PAYMENT') {
    return { label: 'Do zapłaty', tone: 'accent' }
  }
  if (order.status === 'PAID') {
    if (order.reservationStatus === 'BOOKED') {
      return { label: 'Opłacona', tone: 'accent', action: DROP_OFF }
    }
    if (order.reservationStatus === 'OCCUPIED') {
      return { label: 'Bagaż w skrytce', tone: 'accent', action: PICK_UP }
    }
    return { label: 'Opłacona', tone: 'accent' }
  }
  return { label: CLOSED[order.status] ?? order.status, tone: 'neutral' }
}

export function incomingStatus(shipment: IncomingShipment): Status {
  if (shipment.status === 'OCCUPIED') {
    return { label: 'Czeka na odbiór', tone: 'accent', action: PICK_UP }
  }
  return { label: 'Odebrana', tone: 'neutral' }
}

export function pinPurpose(order: Order): AccessCode['purpose'] | null {
  if (order.status !== 'PAID') {
    return null
  }
  if (order.reservationStatus === 'BOOKED') {
    return 'DROP_OFF'
  }
  return order.reservationStatus === 'OCCUPIED' ? 'PICK_UP' : null
}

export function canOpen(order: Order) {
  return order.status === 'PAID' && (order.reservationStatus === 'BOOKED' || order.reservationStatus === 'OCCUPIED')
}

export function canCollect(shipment: IncomingShipment) {
  return shipment.status === 'OCCUPIED'
}

export function canCancel(order: Order) {
  return order.status === 'PAID' && order.reservationStatus === 'BOOKED'
}

export function eventLabel(event: OrderEvent) {
  return EVENTS[`${event.entity}:${event.action}`] ?? 'Zmiana zamówienia'
}

export function actorLabel(kind: ActorKind) {
  return ACTORS[kind] ?? kind
}
