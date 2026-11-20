import type { Page } from '@playwright/test'
import { bookStorage, findCodes, findLockermats, findOrder } from '../api'
import { expect, test } from '../fixtures'
import { login } from '../login'

const CHECKOUT_PATH = /^\/rezerwacje\/(\d+)\/platnosc$/
const NO_FREE_CELL = 'Brak wolnej skrytki w tym rozmiarze i terminie. Wybierz inny termin lub punkt.'
const warsawTime = new Intl.DateTimeFormat('pl-PL', { timeZone: 'Europe/Warsaw', hour: '2-digit', minute: '2-digit' })

function card(page: Page, name: string) {
  return page.getByRole('list', { name: 'Punkty' }).getByRole('listitem').filter({ has: page.getByRole('heading', { name, exact: true }) })
}

function bookButtons(page: Page) {
  return page.getByRole('button', { name: 'Zarezerwuj' })
}

function payButton(page: Page) {
  return page.getByRole('button', { name: 'Zapłać (symulacja)' })
}

function fact(page: Page, label: string) {
  return page.locator(`dt:text-is("${label}") + dd`)
}

function isCheckout(url: URL) {
  return CHECKOUT_PATH.test(url.pathname)
}

function orderIdOf(page: Page) {
  return Number(CHECKOUT_PATH.exec(new URL(page.url()).pathname)?.[1])
}

test('rezerwacja i płatność: kwota, termin i PIN zostają po odświeżeniu', async ({ page }) => {
  await login(page, 'anna')
  const krakowGlowny = card(page, 'Kraków Główny')
  await expect(krakowGlowny).toContainText('20,00 zł')
  await expect(bookButtons(page)).toHaveCount(0)

  await krakowGlowny.getByRole('button', { name: 'Kraków Główny', exact: true }).click()
  await expect(bookButtons(page)).toHaveCount(1)
  await krakowGlowny.getByRole('button', { name: 'Zarezerwuj' }).click()

  await expect(page).toHaveURL(isCheckout)
  const order = await findOrder('anna', orderIdOf(page))
  const deadline = `Zapłać do ${warsawTime.format(new Date(order.paymentDeadline))}`
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Płatność')
  await expect(page.getByText('20,00 zł')).toBeVisible()
  await expect(page.getByText(deadline)).toBeVisible()
  await expect(payButton(page)).toHaveCount(1)

  await page.reload()

  await expect(page.getByText('20,00 zł')).toBeVisible()
  await expect(page.getByText(deadline)).toBeVisible()

  await payButton(page).click()

  await expect(fact(page, 'PIN')).toHaveText(/^\d{6}$/)
  const codes = await findCodes('anna', order.id)
  const dropOff = codes.find(code => code.purpose === 'DROP_OFF')!
  const pickUp = codes.find(code => code.purpose === 'PICK_UP')!
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Rezerwacja opłacona')
  await expect(fact(page, 'PIN')).toHaveText(dropOff.pin)
  await expect(fact(page, 'Skrytka')).toHaveText(String(order.cellNumber))
  await expect(page.getByText(/^\d{6}$/)).toHaveCount(1)
  await expect(page.getByText(pickUp.pin)).toHaveCount(0)

  await page.reload()

  await expect(fact(page, 'PIN')).toHaveText(dropOff.pin)
  await expect(fact(page, 'Skrytka')).toHaveText(String(order.cellNumber))
  await expect(page.getByText(/^\d{6}$/)).toHaveCount(1)
  await expect(payButton(page)).toHaveCount(0)
})

test('druga rezerwacja ostatniej skrytki pokazuje polski komunikat błędu', async ({ page }) => {
  await login(page, 'anna')
  await page.getByRole('radio', { name: 'L', exact: true }).check()
  await expect(page).toHaveURL(/rozmiar=L/)
  const params = new URL(page.url()).searchParams
  const slot = { size: 'L' as const, from: params.get('od') ?? '', to: params.get('do') ?? '' }
  const krakowGlowny = (await findLockermats('jan', slot.from, slot.to)).find(lockermat => lockermat.name === 'Kraków Główny')!
  await bookStorage('jan', { lockermatId: krakowGlowny.id, ...slot })
  await page.reload()
  const row = card(page, 'Kraków Główny')
  await expect(row).toContainText('1 wolna skrytka')
  await row.getByRole('button', { name: 'Kraków Główny', exact: true }).click()

  await bookStorage('jan', { lockermatId: krakowGlowny.id, ...slot })
  await row.getByRole('button', { name: 'Zarezerwuj' }).click()

  await expect(page.getByRole('alert')).toContainText(NO_FREE_CELL)
  expect(new URL(page.url()).pathname).toBe('/')
  await expect(row).toContainText('Brak wolnych skrytek')
  await expect(bookButtons(page)).toHaveCount(0)
})

test.describe('375 px', () => {
  test.use({ viewport: { width: 375, height: 812 } })

  test('na mapie karta zaznaczonego punktu prowadzi do płatności', async ({ page }) => {
    await login(page, 'anna')
    await page.getByRole('searchbox', { name: 'Szukaj punktu' }).fill('Gdańsk')
    await expect(page.getByRole('list', { name: 'Punkty' }).getByRole('listitem')).toHaveCount(3)
    await page.getByRole('group', { name: 'Widok' }).getByRole('button', { name: 'Mapa', exact: true }).click()
    const map = page.getByRole('region', { name: 'Mapa punktów' })
    await map.getByRole('button', { name: 'Lotnisko Gdańsk', exact: true }).click()

    await map.getByRole('button', { name: 'Zarezerwuj' }).click()

    await expect(page).toHaveURL(isCheckout)
    await expect(page.getByRole('heading', { name: 'Lotnisko Gdańsk', exact: true })).toBeVisible()
    await expect(payButton(page)).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  })
})
