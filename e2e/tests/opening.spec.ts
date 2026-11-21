import type { Page, Route } from '@playwright/test'
import {
  bookStorage,
  cancelOrder,
  findCodes,
  findHistory,
  findIncoming,
  findLockermats,
  findOrder,
  openCell,
  payOrder,
  type AccessCode,
  type Opening,
  type Size,
} from '../api'
import { expect, test } from '../fixtures'
import { login } from '../login'

const HOUR_MS = 3_600_000
const MINUTE_MS = 60_000
const OPEN_ROUTE = '**/api/reservations/*/open'
const OPEN_PATH = /^\/api\/reservations\/\d+\/open$/
const DOOR_FAILED = 'Nie udało się otworzyć skrytki. Spróbuj ponownie.'
const PENDING = 'Czekamy na potwierdzenie otwarcia skrytki.'

function slotFromNow(size: Size) {
  const from = new Date(Math.floor(Date.now() / MINUTE_MS) * MINUTE_MS)
  return { size, from: from.toISOString(), to: new Date(from.getTime() + 4 * HOUR_MS).toISOString() }
}

async function bookKrakow(paid: boolean, slot = slotFromNow('M')) {
  const krakowGlowny = (await findLockermats('anna', slot.from, slot.to)).find(lockermat => lockermat.name === 'Kraków Główny')!
  const order = await bookStorage('anna', { lockermatId: krakowGlowny.id, ...slot })
  if (paid) {
    await payOrder('anna', order.id)
  }
  return order
}

function openButton(page: Page) {
  return page.getByRole('button', { name: 'Otwórz skrytkę', exact: true })
}

function simulateButton(page: Page) {
  return page.getByRole('button', { name: 'Symuluj przesyłkę', exact: true })
}

function fact(page: Page, label: string) {
  return page.locator(`dt:text-is("${label}") + dd`)
}

function rows(page: Page, list: string) {
  return page.getByRole('list', { name: list }).getByRole('listitem')
}

function toast(page: Page, message: string) {
  return page.getByRole('status').filter({ hasText: message })
}

function recordOpenings(page: Page) {
  const paths: string[] = []
  page.on('request', request => {
    const path = new URL(request.url()).pathname
    if (request.method() === 'POST' && OPEN_PATH.test(path)) {
      paths.push(path)
    }
  })
  return paths
}

function reply(result: Opening['result']) {
  return (route: Route) => route.fulfill({ json: { id: 1, purpose: 'DROP_OFF', result } })
}

test('pełna ścieżka w UI: rezerwacja, płatność, zostawienie i odbiór bagażu kończą się statusem „Zakończona”', async ({ page }) => {
  const openings = recordOpenings(page)
  await login(page, 'anna')
  const krakowGlowny = page
    .getByRole('list', { name: 'Punkty' })
    .getByRole('listitem')
    .filter({ has: page.getByRole('heading', { name: 'Kraków Główny', exact: true }) })
  await krakowGlowny.getByRole('button', { name: 'Kraków Główny', exact: true }).click()
  await krakowGlowny.getByRole('button', { name: 'Zarezerwuj' }).click()
  await page.getByRole('button', { name: 'Zapłać (symulacja)' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Rezerwacja opłacona')
  await expect(openButton(page)).toHaveCount(0)
  await page.getByRole('link', { name: 'Przejdź do rezerwacji' }).click()

  await expect(page).toHaveURL(url => /^\/rezerwacje\/\d+$/.test(url.pathname))
  const order = await findOrder('anna', Number(new URL(page.url()).pathname.split('/').at(-1)))
  const codes = await findCodes('anna', order.id)
  const pin = (purpose: AccessCode['purpose']) => codes.find(code => code.purpose === purpose)!.pin
  await expect(page.getByText('Opłacona', { exact: true })).toBeVisible()
  await expect(page.getByText('Zostaw bagaż', { exact: true })).toBeVisible()
  await expect(fact(page, 'PIN')).toHaveText(pin('DROP_OFF'))
  await expect(openButton(page)).toHaveCount(1)
  await expect(page.getByRole('button', { name: 'Anuluj', exact: true })).toHaveCount(1)

  await openButton(page).click()

  await expect(toast(page, `Skrytka nr ${order.cellNumber} jest otwarta.`)).toBeVisible()
  await expect(page.getByText('Bagaż w skrytce', { exact: true })).toBeVisible()
  await expect(page.getByText('Odbierz bagaż', { exact: true })).toBeVisible()
  await expect(fact(page, 'PIN')).toHaveText(pin('PICK_UP'))
  await expect(openButton(page)).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Anuluj', exact: true })).toHaveCount(0)

  await openButton(page).click()

  await expect(page.getByText('Zakończona', { exact: true })).toBeVisible()
  await expect(openButton(page)).toHaveCount(0)
  await expect(fact(page, 'PIN')).toHaveCount(0)
  expect(openings).toEqual(Array(2).fill(`/api/reservations/${order.reservationId}/open`))
  expect((await findOrder('anna', order.id)).status).toBe('COMPLETED')
  expect((await findHistory('anna', order.id)).map(event => `${event.entity}:${event.action}:${event.actorKind}`)).toEqual([
    'ORDER:CREATED:CUSTOMER',
    'ORDER:PAID:CUSTOMER',
    'RESERVATION:DEPOSITED:CUSTOMER',
    'RESERVATION:COLLECTED:CUSTOMER',
  ])

  await page.reload()
  await expect(page.getByText('Zakończona', { exact: true })).toBeVisible()
  await expect(openButton(page)).toHaveCount(0)
  await page.goto('/rezerwacje?zakladka=zakonczone')
  await expect(rows(page, 'Rezerwacje')).toContainText(['Zakończona'])
})

test('jan symuluje przesyłkę w „Do odbioru” i odbiera ją z rezerwacji DESTINATION', async ({ page }) => {
  const openings = recordOpenings(page)
  await login(page, 'jan')
  await expect(rows(page, 'Punkty')).toHaveCount(12)
  await expect(simulateButton(page)).toHaveCount(0)

  await page.getByRole('navigation', { name: 'Menu główne' }).getByRole('link', { name: 'Moje rezerwacje' }).click()
  await expect(page.getByText('Nie masz aktywnych rezerwacji.')).toBeVisible()
  await expect(simulateButton(page)).toHaveCount(0)
  await page.getByRole('tab', { name: 'Zakończone' }).click()
  await expect(page.getByText('Nie masz zakończonych rezerwacji.')).toBeVisible()
  await expect(simulateButton(page)).toHaveCount(0)
  await page.getByRole('tab', { name: 'Do odbioru' }).click()
  await expect(page.getByText('Nie masz przesyłek do odbioru.')).toBeVisible()

  await simulateButton(page).click()

  const incoming = rows(page, 'Przesyłki')
  await expect(incoming).toHaveCount(1)
  const [shipment] = await findIncoming('jan')
  await expect(incoming).toContainText([shipment.lockermatName])
  await expect(incoming).toContainText(['Czeka na odbiór'])
  await expect(page.getByRole('list', { name: 'Przesyłki' }).getByRole('button')).toHaveCount(0)
  await expect(simulateButton(page)).toHaveCount(1)
  await incoming.getByRole('link').click()

  await expect(page).toHaveURL(url => url.pathname === `/rezerwacje/do-odbioru/${shipment.reservationId}`)
  await expect(page.getByText('Czeka na odbiór', { exact: true })).toBeVisible()
  await expect(page.getByText('Odbierz bagaż', { exact: true })).toBeVisible()
  await expect(fact(page, 'PIN')).toHaveCount(0)
  await expect(simulateButton(page)).toHaveCount(0)
  await expect(openButton(page)).toHaveCount(1)

  await openButton(page).click()

  await expect(toast(page, `Skrytka nr ${shipment.cellNumber} jest otwarta.`)).toBeVisible()
  await expect(page.getByText('Odebrana', { exact: true })).toBeVisible()
  await expect(openButton(page)).toHaveCount(0)
  expect(openings).toEqual([`/api/reservations/${shipment.reservationId}/open`])
  expect((await findIncoming('jan')).map(item => item.status)).toEqual(['COMPLETED'])
  expect((await findHistory('jan', shipment.orderId)).at(-1)).toMatchObject({ entity: 'RESERVATION', action: 'COLLECTED', actorKind: 'RECIPIENT' })

  await page.reload()
  await expect(page.getByText('Odebrana', { exact: true })).toBeVisible()
  await expect(openButton(page)).toHaveCount(0)
  await page.goto('/rezerwacje?zakladka=do-odbioru')
  await expect(rows(page, 'Przesyłki')).toContainText(['Odebrana'])
})

test('„Otwórz skrytkę” jest tylko przy opłaconej rezerwacji BOOKED albo OCCUPIED', async ({ page }) => {
  const slot = slotFromNow('S')
  const unpaid = await bookKrakow(false, slot)
  const booked = await bookKrakow(true, slot)
  const occupied = await bookKrakow(true, slot)
  await openCell('anna', occupied.reservationId)
  const completed = await bookKrakow(true, slot)
  await openCell('anna', completed.reservationId)
  await openCell('anna', completed.reservationId)
  const cancelled = await bookKrakow(true, slot)
  await cancelOrder('anna', cancelled.id)

  await login(page, 'anna')
  const cases: Array<[number, string, number]> = [
    [booked.id, 'Opłacona', 1],
    [occupied.id, 'Bagaż w skrytce', 1],
    [completed.id, 'Zakończona', 0],
    [cancelled.id, 'Anulowana', 0],
  ]
  for (const [id, status, buttons] of cases) {
    await page.goto(`/rezerwacje/${id}`)
    await expect(page.getByText(status, { exact: true })).toBeVisible()
    await expect(openButton(page)).toHaveCount(buttons)
  }

  await page.goto(`/rezerwacje/${unpaid.id}`)
  await expect(page).toHaveURL(url => url.pathname === `/rezerwacje/${unpaid.id}/platnosc`)
  await expect(page.getByRole('button', { name: 'Zapłać (symulacja)' })).toBeVisible()
  await expect(openButton(page)).toHaveCount(0)

  await page.goto('/rezerwacje')
  await expect(rows(page, 'Rezerwacje')).toHaveCount(3)
  await expect(openButton(page)).toHaveCount(0)
  await page.getByRole('tab', { name: 'Zakończone' }).click()
  await expect(rows(page, 'Rezerwacje')).toHaveCount(2)
  await expect(openButton(page)).toHaveCount(0)
})

test('stany otwierania: DOOR_FAILED daje toast z błędem przy aktywnym przycisku, potem oczekiwanie i otwarcie', async ({ page }) => {
  const order = await bookKrakow(true)
  await login(page, 'anna')
  await page.goto(`/rezerwacje/${order.id}`)
  await expect(page.getByText('Zostaw bagaż', { exact: true })).toBeVisible()

  await page.route(OPEN_ROUTE, reply('DOOR_FAILED'))
  await openButton(page).click()
  await expect(page.getByRole('alert')).toContainText(DOOR_FAILED)
  await expect(openButton(page)).toBeEnabled()
  await expect(page.getByText('Opłacona', { exact: true })).toBeVisible()
  await page.unroute(OPEN_ROUTE)

  await page.route(OPEN_ROUTE, reply('PENDING'))
  await openButton(page).click()
  await expect(toast(page, PENDING)).toBeVisible()
  await expect(page.getByText('Opłacona', { exact: true })).toBeVisible()
  await page.unroute(OPEN_ROUTE)

  let release = () => {}
  const held = new Promise<void>(resolve => {
    release = resolve
  })
  await page.route(OPEN_ROUTE, async route => {
    await held
    await route.continue()
  })
  await openButton(page).click()
  await expect(openButton(page)).toBeDisabled()
  await expect(openButton(page)).toHaveAttribute('aria-busy', 'true')
  release()

  await expect(toast(page, `Skrytka nr ${order.cellNumber} jest otwarta.`)).toBeVisible()
  await expect(page.getByText('Bagaż w skrytce', { exact: true })).toBeVisible()
  await expect(openButton(page)).toBeEnabled()
  await expect(openButton(page)).toHaveAttribute('aria-busy', 'false')
  expect((await findHistory('anna', order.id)).map(event => event.action)).toEqual(['CREATED', 'PAID', 'DEPOSITED'])
})
