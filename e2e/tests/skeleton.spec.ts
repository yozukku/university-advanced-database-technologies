import { expect, test } from '@playwright/test'
import { login } from '../login'

test('Anna loguje się i widzi swoje imię', async ({ page }) => {
  await login(page, 'anna')
  await expect(page.getByText('Witaj, Anna Kowalska')).toBeVisible()
})

test('Chromium obsługuje WebGL2', async ({ page }) => {
  await page.goto('/')
  const supported = await page.evaluate(() => document.createElement('canvas').getContext('webgl2') !== null)
  expect(supported).toBe(true)
})
