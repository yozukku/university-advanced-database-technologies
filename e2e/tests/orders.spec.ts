import type { Locator, Page } from '@playwright/test'
import { bookStorage, findCodes, findHistory, findLockermats, findOrder, openCell, payOrder, simulateShipment, type Order, type OrderEvent, type User } from '../api'
import { expect, test } from '../fixtures'
import { login } from '../login'

const HOUR_MS = 3_600_000
const MINUTE_MS = 60_000
const warsawTime = new Intl.DateTimeFormat('pl-PL', { timeZone: 'Europe/Warsaw', hour: '2-digit', minute: '2-digit' })

function slotFromNow() {
  const from = new Date(Math.floor(Date.now() / MINUTE_MS) * MINUTE_MS)
  return { size: 'M' as const, from: from.toISOString(), to: new Date(from.getTime() + 4 * HOUR_MS).toISOString() }
}

async function bookKrakow(user: User, paid: boolean, slot = slotFromNow()) {
  const krakowGlowny = (await findLockermats(user, slot.from, slot.to)).find(lockermat => lockermat.name === 'Kraków Główny')!
  const order = await bookStorage(user, { lockermatId: krakowGlowny.id, ...slot })
  if (paid) {
    await payOrder(user, order.id)
  }
  return order
}

async function pinOf(user: User, order: Order, purpose: 'DROP_OFF' | 'PICK_UP') {
  return (await findCodes(user, order.id)).find(code => code.purpose === purpose)!.pin
}

function rows(page: Page, list: string) {
  return page.getByRole('list', { name: list }).getByRole('listitem')
}

function fact(page: Page, label: string) {
  return page.locator(`dt:text-is("${label}") + dd`)
}

function pathIs(path: string) {
  return (url: URL) => url.pathname === path
}

function windowText(page: Page, from: string, to: string) {
  return page.evaluate(
    ([start, end]) =>
      new Intl.DateTimeFormat('pl-PL', { timeZone: 'Europe/Warsaw', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).formatRange(
        new Date(start),
        new Date(end),
      ),
    [from, to],
  )
}

async function expectHistory(page: Page, events: OrderEvent[], labels: string[], actors: string[]) {
  const list = page.getByRole('list', { name: 'Historia zamówienia' })
  await expect(list).toHaveCount(0)
  await expect(page.locator('details')).not.toHaveAttribute('open')
  await page.getByText('Historia zamówienia', { exact: true }).click()
  const times = await page.evaluate(
    instants =>
      instants.map(at =>
        new Intl.DateTimeFormat('pl-PL', { timeZone: 'Europe/Warsaw', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(at)),
      ),
    events.map(event => event.at),
  )
  await expect(list.getByRole('listitem')).toHaveText(labels.map((label, index) => `${times[index]}${label}${actors[index]}`))
}

async function expectNoButtonOrPin(list: Locator, pins: string[]) {
  await expect(list.getByRole('button')).toHaveCount(0)
  for (const pin of pins) {
    await expect(list).not.toContainText(pin)
  }
}

test('wiersz listy pokazuje tylko punkt, okno i status, bez przycisku i PIN-u', async ({ page }) => {
  const slot = slotFromNow()
  const unpaid = await bookKrakow('anna', false, slot)
  const booked = await bookKrakow('anna', true, slot)
  const occupied = await bookKrakow('anna', true, slot)
  const pins = [await pinOf('anna', booked, 'DROP_OFF'), await pinOf('anna', booked, 'PICK_UP'), await pinOf('anna', occupied, 'PICK_UP')]
  await openCell('anna', occupied.reservationId)

  await login(page, 'anna')
  await page.getByRole('navigation', { name: 'Menu główne' }).getByRole('link', { name: 'Moje rezerwacje' }).click()

  const active = rows(page, 'Rezerwacje')
  await expect(active).toHaveCount(3)
  const window = await windowText(page, booked.from, booked.to)
  await expect(active).toHaveText([`Kraków Główny${window}Bagaż w skrytce`, `Kraków Główny${window}Opłacona`, `Kraków Główny${window}Do zapłaty`])
  await expectNoButtonOrPin(page.getByRole('list', { name: 'Rezerwacje' }), pins)
  await expect(active.nth(0).getByRole('link')).toHaveAttribute('href', `/rezerwacje/${occupied.id}`)
  await expect(active.nth(1).getByRole('link')).toHaveAttribute('href', `/rezerwacje/${booked.id}`)
  await expect(active.nth(2).getByRole('link')).toHaveAttribute('href', `/rezerwacje/${unpaid.id}/platnosc`)

  await page.getByRole('tab', { name: 'Zakończone' }).click()
  await expect(page.getByText('Nie masz zakończonych rezerwacji.')).toBeVisible()
})

test('jan nie widzi rezerwacji anny', async ({ page }) => {
  const order = await bookKrakow('anna', true)
  await bookKrakow('anna', false)

  await login(page, 'jan')
  await page.goto('/rezerwacje')
  await expect(page.getByText('Nie masz aktywnych rezerwacji.')).toBeVisible()
  await page.getByRole('tab', { name: 'Zakończone' }).click()
  await expect(page.getByText('Nie masz zakończonych rezerwacji.')).toBeVisible()
  await page.getByRole('tab', { name: 'Do odbioru' }).click()
  await expect(page.getByText('Nie masz przesyłek do odbioru.')).toBeVisible()

  await page.goto(`/rezerwacje/${order.id}`)
  await expect(page.getByText('Nie udało się wczytać rezerwacji.')).toBeVisible()
  await expect(page.getByText('Kraków Główny')).toHaveCount(0)
  await expect(page.getByText(/^\d{6}$/)).toHaveCount(0)
})

test('anulowanie pokazuje kwotę zwrotu', async ({ page }) => {
  const order = await bookKrakow('anna', true)
  const dropOff = await pinOf('anna', order, 'DROP_OFF')

  await login(page, 'anna')
  await page.goto('/rezerwacje')
  await rows(page, 'Rezerwacje').getByRole('link').click()
  await expect(page).toHaveURL(pathIs(`/rezerwacje/${order.id}`))
  await expect(page.getByText('Opłacona', { exact: true })).toBeVisible()
  await expect(page.getByText('Zostaw bagaż', { exact: true })).toBeVisible()
  await expect(fact(page, 'PIN')).toHaveText(dropOff)
  await expect(page.getByText(/^\d{6}$/)).toHaveCount(1)

  await page.getByRole('button', { name: 'Anuluj', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Anulować rezerwację?' })
  await expect(dialog).toContainText('Zwrot')
  await expect(dialog).toContainText('20,00 zł')
  await dialog.getByRole('button', { name: 'Anuluj rezerwację' }).click()

  await expect(page.getByRole('status').filter({ hasText: 'Zwrot' })).toHaveText('Rezerwacja anulowana. Zwrot 20,00 zł.')
  await expect(dialog).toHaveCount(0)
  await expect(page.getByText('Anulowana', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Anuluj', exact: true })).toHaveCount(0)
  await expect(fact(page, 'PIN')).toHaveCount(0)
  expect((await findOrder('anna', order.id)).status).toBe('CANCELLED')

  await page.goto('/rezerwacje')
  await expect(page.getByText('Nie masz aktywnych rezerwacji.')).toBeVisible()
  await page.getByRole('tab', { name: 'Zakończone' }).click()
  await expect(page).toHaveURL(url => url.searchParams.get('zakladka') === 'zakonczone')
  await expect(rows(page, 'Rezerwacje')).toHaveCount(1)
  await expect(rows(page, 'Rezerwacje')).toContainText(['Anulowana'])
})

test('po zostawieniu bagażu jest PIN odbioru bez „Anuluj”, zakończona rezerwacja nie ma PIN-u, historia jest zwinięta', async ({ page }) => {
  const order = await bookKrakow('anna', true)
  expect((await openCell('anna', order.reservationId)).result).toBe('OPENED')
  const pickUp = await pinOf('anna', order, 'PICK_UP')

  await login(page, 'anna')
  await page.goto(`/rezerwacje/${order.id}`)
  await expect(page.getByText('Bagaż w skrytce', { exact: true })).toBeVisible()
  await expect(page.getByText('Odbierz bagaż', { exact: true })).toBeVisible()
  await expect(fact(page, 'PIN')).toHaveText(pickUp)
  await expect(page.getByText(/^\d{6}$/)).toHaveCount(1)
  await expect(page.getByRole('button', { name: 'Anuluj', exact: true })).toHaveCount(0)

  expect((await openCell('anna', order.reservationId)).result).toBe('OPENED')
  await page.reload()

  await expect(page.getByText('Zakończona', { exact: true })).toBeVisible()
  await expect(fact(page, 'Skrytka')).toHaveText(String(order.cellNumber))
  await expect(fact(page, 'PIN')).toHaveCount(0)
  await expect(page.getByText(/^\d{6}$/)).toHaveCount(0)
  await expect(page.getByRole('button')).toHaveText(['Wyloguj'])

  const events = await findHistory('anna', order.id)
  expect(events.map(event => `${event.entity}:${event.action}:${event.actorKind}`)).toEqual([
    'ORDER:CREATED:CUSTOMER',
    'ORDER:PAID:CUSTOMER',
    'RESERVATION:DEPOSITED:CUSTOMER',
    'RESERVATION:COLLECTED:CUSTOMER',
  ])
  await expectHistory(page, events, ['Zamówienie utworzone', 'Zamówienie opłacone', 'Bagaż zostawiony', 'Bagaż odebrany'], Array(4).fill('Klient'))

  await page.goto('/rezerwacje?zakladka=zakonczone')
  await expect(rows(page, 'Rezerwacje')).toContainText(['Zakończona'])
})

test('nieopłacona rezerwacja otwiera płatność z tą samą kwotą i terminem', async ({ page }) => {
  const order = await bookKrakow('anna', false)
  const deadline = `Zapłać do ${warsawTime.format(new Date(order.paymentDeadline))}`

  await login(page, 'anna')
  await page.goto('/rezerwacje')
  await expect(rows(page, 'Rezerwacje')).toContainText(['Do zapłaty'])
  await rows(page, 'Rezerwacje').getByRole('link').click()

  await expect(page).toHaveURL(pathIs(`/rezerwacje/${order.id}/platnosc`))
  await expect(page.getByText('20,00 zł')).toBeVisible()
  await expect(page.getByText(deadline)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Zapłać (symulacja)' })).toHaveCount(1)

  await page.goto(`/rezerwacje/${order.id}`)
  await expect(page).toHaveURL(pathIs(`/rezerwacje/${order.id}/platnosc`))
  await expect(page.getByText(deadline)).toBeVisible()
})

test('„Do odbioru”: szczegóły z pozycji listy, bez PIN-u i bez zapytania o zamówienie', async ({ page }) => {
  const shipment = await simulateShipment('jan')
  const orderRequests: string[] = []
  page.on('request', request => {
    const path = new URL(request.url()).pathname
    if (/^\/api\/orders\/\d+(\/codes)?$/.test(path)) {
      orderRequests.push(path)
    }
  })

  await login(page, 'jan')
  await page.goto('/rezerwacje')
  await page.getByRole('tab', { name: 'Do odbioru' }).click()
  await expect(page).toHaveURL(url => url.searchParams.get('zakladka') === 'do-odbioru')
  const incoming = rows(page, 'Przesyłki')
  await expect(incoming).toHaveText([`${shipment.lockermatName}${await windowText(page, shipment.from, shipment.to)}Czeka na odbiór`])
  await expect(page.getByRole('list', { name: 'Przesyłki' }).getByRole('button')).toHaveCount(0)
  await incoming.getByRole('link').click()

  await expect(page).toHaveURL(pathIs(`/rezerwacje/do-odbioru/${shipment.reservationId}`))
  await expect(page.getByRole('heading', { name: shipment.lockermatName })).toBeVisible()
  await expect(page.getByText('Czeka na odbiór', { exact: true })).toBeVisible()
  await expect(page.getByText('Odbierz bagaż', { exact: true })).toBeVisible()
  await expect(fact(page, 'Skrytka')).toHaveText(String(shipment.cellNumber))
  await expect(fact(page, 'PIN')).toHaveCount(0)
  await expect(page.getByText(/^\d{6}$/)).toHaveCount(0)

  await page.reload()
  await expect(fact(page, 'Skrytka')).toHaveText(String(shipment.cellNumber))
  const events = await findHistory('jan', shipment.orderId)
  await expectHistory(
    page,
    events,
    ['Zamówienie utworzone', 'Zamówienie opłacone', 'Bagaż zostawiony', 'Bagaż odebrany', 'Bagaż zostawiony'],
    Array(5).fill('System'),
  )
  expect(orderRequests).toEqual([])
})
