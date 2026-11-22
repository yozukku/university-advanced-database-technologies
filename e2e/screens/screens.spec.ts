import type { Locator, Page } from '@playwright/test'
import { bookStorage, cancelOrder, findLockermats, openCell, payOrder, type Size } from '../api'
import { expect, test } from '../fixtures'
import { login } from '../login'

const SCREENS_DIR = process.env.SCREENS_DIR ?? '../out/screens'
const REPORT_DIR = '../report/assets/app'
const REPORT_SHOTS: Record<string, string> = {
  'punkty-wybrany-1440': 'punkty',
  'punkty-mapa-375': 'punkty-telefon',
  'platnosc-oplacona-1440': 'platnosc',
  'rezerwacje-aktywne-1440': 'rezerwacje',
  'rezerwacja-zakonczona-1440': 'historia',
  'przesylka-1440': 'przesylka',
}
const VIEWPORTS = [
  { width: 375, height: 812 },
  { width: 1440, height: 900 },
]
const HOUR_MS = 3_600_000
const MINUTE_MS = 60_000
const FAR_FUTURE = { from: '2036-06-01T08:00:00Z', to: '2036-06-01T12:00:00Z' }

function camera(page: Page) {
  let pending = 0
  page.on('request', () => {
    pending += 1
  })
  page.on('requestfinished', () => {
    pending -= 1
  })
  page.on('requestfailed', () => {
    pending -= 1
  })
  return async (name: string) => {
    await expect.poll(() => pending, { timeout: 30_000 }).toBe(0)
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.waitForTimeout(500)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
    const file = `${name}-${page.viewportSize()!.width}`
    await page.screenshot({ path: `${SCREENS_DIR}/${file}.png`, fullPage: true })
    if (REPORT_SHOTS[file]) {
      await page.screenshot({ path: `${REPORT_DIR}/${REPORT_SHOTS[file]}.png`, fullPage: true })
    }
  }
}

function slotFromNow(size: Size) {
  const from = new Date(Math.floor(Date.now() / MINUTE_MS) * MINUTE_MS)
  return { size, from: from.toISOString(), to: new Date(from.getTime() + 4 * HOUR_MS).toISOString() }
}

async function book(name: string, slot: { size: Size; from: string; to: string }, paid: boolean) {
  const lockermat = (await findLockermats('anna', slot.from, slot.to)).find(candidate => candidate.name === name)!
  const order = await bookStorage('anna', { lockermatId: lockermat.id, ...slot })
  if (paid) {
    await payOrder('anna', order.id)
  }
  return order
}

function rows(page: Page, list: string) {
  return page.getByRole('list', { name: list }).getByRole('listitem')
}

function button(page: Page, name: string) {
  return page.getByRole('button', { name, exact: true })
}

async function centre(locator: Locator) {
  const box = await locator.boundingBox()
  return box ? { x: box.x + box.width / 2, y: box.y + box.height / 2 } : null
}

async function expectCentred(page: Page, name: string) {
  const map = page.getByRole('region', { name: 'Mapa punktów' })
  const marker = map.getByRole('button', { name, exact: true })
  await expect
    .poll(async () => {
      const [point, middle] = await Promise.all([centre(marker), centre(map.getByRole('region', { name: 'Mapa', exact: true }))])
      return point && middle ? Math.hypot(point.x - middle.x, point.y - middle.y) : Infinity
    })
    .toBeLessThan(4)
}

for (const viewport of VIEWPORTS) {
  test.describe(`${viewport.width} px`, () => {
    test.use({ viewport })

    test('anna: od logowania do zakończonej rezerwacji', async ({ page }) => {
      const capture = camera(page)
      const phone = viewport.width < 960

      await page.goto('/')
      await expect(button(page, 'Zaloguj się')).toBeVisible()
      await capture('logowanie')

      await login(page, 'anna')
      await expect(rows(page, 'Punkty')).toHaveCount(12)
      await capture('punkty')

      await page.getByLabel('Szukaj punktu').fill('Zakopane')
      await expect(page.getByText('Nie znaleziono punktów.')).toBeVisible()
      await capture('punkty-brak-wynikow')
      await page.getByLabel('Szukaj punktu').fill('Kraków')
      await expect(rows(page, 'Punkty')).toHaveCount(3)

      await page.getByRole('list', { name: 'Punkty' }).getByRole('button', { name: 'Kraków Główny', exact: true }).click()
      await expect(button(page, 'Zarezerwuj')).toBeVisible()
      if (phone) {
        await capture('punkty-wybrany')
        await page.getByRole('group', { name: 'Widok' }).getByRole('button', { name: 'Mapa', exact: true }).click()
        await expectCentred(page, 'Kraków Główny')
        await capture('punkty-mapa')
      } else {
        await expectCentred(page, 'Kraków Główny')
        await capture('punkty-wybrany')
      }

      await button(page, 'Zarezerwuj').click()
      await expect(button(page, 'Zapłać (symulacja)')).toBeVisible()
      await capture('platnosc')

      await button(page, 'Zapłać (symulacja)').click()
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('Rezerwacja opłacona')
      await capture('platnosc-oplacona')

      await page.getByRole('link', { name: 'Przejdź do rezerwacji' }).click()
      await expect(page.getByText('Zostaw bagaż', { exact: true })).toBeVisible()
      await capture('rezerwacja-oplacona')

      await button(page, 'Anuluj').click()
      await expect(page.getByRole('dialog')).toBeVisible()
      await capture('rezerwacja-anulowanie')
      await page.keyboard.press('Escape')
      await expect(page.getByRole('dialog')).toHaveCount(0)

      await button(page, 'Otwórz skrytkę').click()
      await expect(page.getByText('Odbierz bagaż', { exact: true })).toBeVisible()
      await capture('rezerwacja-w-skrytce')

      await button(page, 'Otwórz skrytkę').click()
      await expect(page.getByText('Zakończona', { exact: true })).toBeVisible()
      await page.reload()
      await page.getByText('Historia zamówienia', { exact: true }).click()
      await expect(rows(page, 'Historia zamówienia')).toHaveCount(4)
      await capture('rezerwacja-zakonczona')

      const slot = slotFromNow('M')
      await book('Rynek Główny', slot, false)
      await book('Warszawa Centralna', slot, true)
      await openCell('anna', (await book('Lotnisko Gdańsk', slot, true)).reservationId)
      const farFuture = await book('Wrocław Główny', { size: 'M', ...FAR_FUTURE }, true)
      await page.goto(`/rezerwacje/${farFuture.id}`)
      await button(page, 'Otwórz skrytkę').click()
      await expect(page.getByRole('alert')).toContainText('Tej skrytki nie można teraz otworzyć.')
      await capture('rezerwacja-blad-otwarcia')
      await cancelOrder('anna', farFuture.id)

      await page.goto('/rezerwacje')
      await expect(rows(page, 'Rezerwacje')).toHaveCount(3)
      await capture('rezerwacje-aktywne')
      await page.getByRole('tab', { name: 'Zakończone' }).click()
      await expect(rows(page, 'Rezerwacje')).toHaveCount(2)
      await capture('rezerwacje-zakonczone')

      await page.goto(`/rezerwacje/${farFuture.id}`)
      await expect(page.getByText('Anulowana', { exact: true })).toBeVisible()
      await capture('rezerwacja-anulowana')

      await page.goto('/nie-ma-takiej-strony')
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('Nie znaleziono strony')
      await capture('nie-znaleziono')
    })

    test('jan: przesyłka od symulacji do odbioru', async ({ page }) => {
      const capture = camera(page)
      await login(page, 'jan')
      await page.goto('/rezerwacje')
      await expect(page.getByText('Nie masz aktywnych rezerwacji.')).toBeVisible()
      await capture('rezerwacje-puste')

      await page.getByRole('tab', { name: 'Do odbioru' }).click()
      await expect(page.getByText('Nie masz przesyłek do odbioru.')).toBeVisible()
      await capture('do-odbioru-puste')

      await button(page, 'Symuluj przesyłkę').click()
      await expect(rows(page, 'Przesyłki')).toHaveCount(1)
      await capture('do-odbioru')

      await rows(page, 'Przesyłki').getByRole('link').click()
      await expect(button(page, 'Otwórz skrytkę')).toBeVisible()
      await capture('przesylka')

      await button(page, 'Otwórz skrytkę').click()
      await expect(page.getByText('Odebrana', { exact: true })).toBeVisible()
      await capture('przesylka-odebrana')
    })
  })
}
