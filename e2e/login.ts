import type { Page } from '@playwright/test'

export async function login(page: Page, username: 'anna' | 'jan') {
  await page.goto('/')
  await page.getByRole('button', { name: 'Zaloguj się' }).click()
  await page.locator('#username').fill(username)
  await page.locator('#password').fill('demo')
  await page.locator('#kc-login').click()
  await page.waitForURL('http://localhost:5173/')
}
