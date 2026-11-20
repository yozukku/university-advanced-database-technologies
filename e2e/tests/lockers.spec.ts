import type { Page } from '@playwright/test'
import { bookStorage, findLockermats } from '../api'
import { expect, test } from '../fixtures'
import { login } from '../login'

const HOUR_MS = 3_600_000
const FREE_COUNT = /wolna skrytka|wolne skrytki|wolnych skrytek/

function cards(page: Page) {
  return page.getByRole('list', { name: 'Punkty' }).getByRole('listitem')
}

function card(page: Page, name: string) {
  return cards(page).filter({ has: page.getByRole('heading', { name, exact: true }) })
}

function windowParams(page: Page) {
  const params = new URL(page.url()).searchParams
  return { size: params.get('rozmiar'), from: params.get('od') ?? '', to: params.get('do') ?? '' }
}

test('„Kraków” zostawia tylko punkty z Krakowa', async ({ page }) => {
  await login(page, 'anna')
  await expect(cards(page)).toHaveCount(12)

  await page.getByRole('searchbox', { name: 'Szukaj punktu' }).fill('Kraków')

  await expect(cards(page)).toHaveText([/Kraków, /, /Kraków, /, /Kraków, /])
  await expect(cards(page).getByRole('heading')).toHaveText(['Rynek Główny', 'Lotnisko Kraków-Balice', 'Kraków Główny'])
})

test('rezerwacja przez API w domyślnym oknie zmniejsza liczbę wolnych skrytek o 1', async ({ page }) => {
  await login(page, 'anna')
  await expect(page.getByRole('radio', { name: 'M', exact: true })).toBeChecked()
  await expect(page.getByRole('radio', { name: '+ 4 h' })).toBeChecked()
  await expect(page).toHaveURL(/rozmiar=M/)
  const { from, to } = windowParams(page)
  expect(Date.parse(to) - Date.parse(from)).toBe(4 * HOUR_MS)
  await expect(card(page, 'Kraków Główny')).toContainText('4 wolne skrytki')
  await expect(card(page, 'Rynek Główny')).toContainText('4 wolne skrytki')

  const lockermats = await findLockermats('jan', from, to)
  const krakowGlowny = lockermats.find(lockermat => lockermat.name === 'Kraków Główny')
  await bookStorage('jan', { lockermatId: krakowGlowny!.id, size: 'M', from, to })
  await page.reload()

  expect(windowParams(page)).toEqual({ size: 'M', from, to })
  await expect(card(page, 'Kraków Główny')).toContainText('3 wolne skrytki')
  await expect(card(page, 'Rynek Główny')).toContainText('4 wolne skrytki')
})

test('każda karta pokazuje jedną cenę i jedną liczbę wolnych skrytek', async ({ page }) => {
  await login(page, 'anna')
  await expect(cards(page)).toHaveCount(12)
  for (const item of await cards(page).all()) {
    await expect(item.getByText(/zł/)).toHaveCount(1)
    await expect(item.getByText(FREE_COUNT)).toHaveCount(1)
  }
  const krakowGlowny = card(page, 'Kraków Główny')
  await expect(krakowGlowny).toContainText('20,00 zł')

  await page.getByRole('radio', { name: 'L', exact: true }).check()
  await expect(page).toHaveURL(/rozmiar=L/)
  await expect(krakowGlowny.getByText(/zł/)).toHaveText('30,00 zł')
  await expect(krakowGlowny.getByText(FREE_COUNT)).toHaveText('2 wolne skrytki')

  await page.getByRole('radio', { name: '+ 3 dni' }).check()
  await expect(krakowGlowny.getByText(/zł/)).toHaveText('90,00 zł')
  const { size, from, to } = windowParams(page)
  expect(size).toBe('L')
  expect(Date.parse(to) - Date.parse(from)).toBe(72 * HOUR_MS)
})
