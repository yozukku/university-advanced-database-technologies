import type { Locator, Page } from '@playwright/test'
import { bookStorage, findLockermats, payOrder } from '../api'
import { expect, test } from '../fixtures'
import { login } from '../login'

const HOUR_MS = 3_600_000
const MINUTE_MS = 60_000
const REDUCED = process.env.REDUCED_MOTION === '1'

function runningAnimations(page: Page) {
  return page.evaluate(() => document.getAnimations().filter(animation => animation.playState === 'running').length)
}

function animationName(locator: Locator) {
  return locator.evaluate(element => getComputedStyle(element).animationName)
}

async function expectMotion(page: Page, animated: Locator) {
  if (REDUCED) {
    expect(await runningAnimations(page)).toBe(0)
    expect(await animationName(animated)).toBe('none')
  } else {
    expect(await animationName(animated)).not.toBe('none')
  }
}

test('ruch tylko dla zmian stanu, bez animacji przy prefers-reduced-motion', async ({ page }) => {
  const from = new Date(Math.floor(Date.now() / MINUTE_MS) * MINUTE_MS)
  const slot = { size: 'M' as const, from: from.toISOString(), to: new Date(from.getTime() + 4 * HOUR_MS).toISOString() }
  const krakowGlowny = (await findLockermats('anna', slot.from, slot.to)).find(lockermat => lockermat.name === 'Kraków Główny')!
  const order = await bookStorage('anna', { lockermatId: krakowGlowny.id, ...slot })
  await payOrder('anna', order.id)
  await login(page, 'anna')
  expect(await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches)).toBe(REDUCED)
  await page.goto(`/rezerwacje/${order.id}`)

  await page.getByText('Historia zamówienia', { exact: true }).click()
  await expectMotion(page, page.getByRole('list', { name: 'Historia zamówienia' }))

  await page.getByRole('button', { name: 'Anuluj', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Anulować rezerwację?' })
  await expect(dialog).toBeVisible()
  await expectMotion(page, dialog)
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)

  await page.getByRole('button', { name: 'Otwórz skrytkę', exact: true }).click()
  const opened = page.getByRole('status').filter({ hasText: `Skrytka nr ${order.cellNumber} jest otwarta.` })
  await expect(opened).toBeVisible()
  await expectMotion(page, opened.locator('svg').first())
  await expect(page.getByText('Bagaż w skrytce', { exact: true })).toBeVisible()
  if (REDUCED) {
    expect(await runningAnimations(page)).toBe(0)
  }
})
