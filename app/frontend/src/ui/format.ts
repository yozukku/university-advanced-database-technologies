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
const dateTimeYear = new Intl.DateTimeFormat(LOCALE, {
  timeZone: TIME_ZONE,
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})
const year = new Intl.DateTimeFormat(LOCALE, { timeZone: TIME_ZONE, year: 'numeric' })

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
  const start = new Date(from)
  const end = new Date(to)
  const now = year.format(new Date())
  const format = year.format(start) === now && year.format(end) === now ? dateTime : dateTimeYear
  return format.formatRange(start, end)
}
