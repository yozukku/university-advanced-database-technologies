const LOCALE = 'pl-PL'
const TIME_ZONE = 'Europe/Warsaw'

const price = new Intl.NumberFormat(LOCALE, { style: 'currency', currency: 'PLN' })
const time = new Intl.DateTimeFormat(LOCALE, { timeZone: TIME_ZONE, hour: '2-digit', minute: '2-digit' })
const dateTime = new Intl.DateTimeFormat(LOCALE, {
  timeZone: TIME_ZONE,
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
})

type Instant = string | Date

export function formatPrice(value: number | string) {
  return price.format(Number(value))
}

export function formatTime(value: Instant) {
  return time.format(new Date(value))
}

export function formatDateTime(value: Instant) {
  return dateTime.format(new Date(value))
}

export function formatWindow(from: Instant, to: Instant) {
  return dateTime.formatRange(new Date(from), new Date(to))
}
