import type { Locator, Page } from '@playwright/test'
import { expect, test } from '../fixtures'
import { login } from '../login'

function list(page: Page) {
  return page.getByRole('list', { name: 'Punkty' })
}

function map(page: Page) {
  return page.getByRole('region', { name: 'Mapa punktów' })
}

function markers(page: Page) {
  return map(page).locator('.maplibregl-marker')
}

function viewButton(page: Page, name: 'Lista' | 'Mapa') {
  return page.getByRole('group', { name: 'Widok' }).getByRole('button', { name, exact: true })
}

async function centre(locator: Locator) {
  const box = await locator.boundingBox()
  return box ? { x: box.x + box.width / 2, y: box.y + box.height / 2 } : null
}

async function distanceFromMapCentre(page: Page, marker: Locator) {
  const [point, middle] = await Promise.all([centre(marker), centre(map(page).getByRole('region', { name: 'Mapa', exact: true }))])
  return point && middle ? Math.hypot(point.x - middle.x, point.y - middle.y) : Infinity
}

test.describe('1440 px', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('lista po lewej, mapa po prawej z 12 znacznikami', async ({ page }) => {
    await login(page, 'anna')

    await expect(list(page)).toBeVisible()
    await expect(map(page)).toBeVisible()
    await expect(markers(page)).toHaveCount(12)
    await expect(page.getByRole('group', { name: 'Widok' })).toBeHidden()
    const listBox = (await list(page).boundingBox())!
    const mapBox = (await map(page).boundingBox())!
    expect(listBox.x + listBox.width).toBeLessThanOrEqual(mapBox.x)
    expect(mapBox.y).toBeLessThan(listBox.y + listBox.height)
  })

  test('kliknięcie wiersza listy aktywuje jego znacznik', async ({ page }) => {
    await login(page, 'anna')
    const row = list(page).getByRole('button', { name: 'Kraków Główny', exact: true })
    const marker = map(page).getByRole('button', { name: 'Kraków Główny', exact: true })
    await expect(markers(page)).toHaveCount(12)
    await expect(marker).toHaveAttribute('aria-pressed', 'false')

    await row.click()

    await expect(row).toHaveAttribute('aria-pressed', 'true')
    await expect(marker).toHaveAttribute('aria-pressed', 'true')
    await expect(markers(page).and(page.locator('[aria-pressed="true"]'))).toHaveCount(1)
    await expect.poll(() => distanceFromMapCentre(page, marker)).toBeLessThan(4)
  })

  test('kliknięcie znacznika aktywuje jego wiersz, a wyszukiwanie zmienia znaczniki', async ({ page }) => {
    await login(page, 'anna')
    await page.getByRole('searchbox', { name: 'Szukaj punktu' }).fill('Gdańsk')
    await expect(markers(page)).toHaveCount(3)
    await expect(list(page).getByRole('listitem')).toHaveCount(3)

    await map(page).getByRole('button', { name: 'Lotnisko Gdańsk', exact: true }).click()

    await expect(list(page).getByRole('button', { name: 'Lotnisko Gdańsk', exact: true })).toHaveAttribute('aria-pressed', 'true')
    await expect(list(page).getByRole('button', { pressed: true })).toHaveCount(1)
  })
})

test.describe('375 px', () => {
  test.use({ viewport: { width: 375, height: 812 } })

  test('przełącznik „Lista / Mapa” pokazuje tylko jedno z nich', async ({ page }) => {
    await login(page, 'anna')

    await expect(viewButton(page, 'Lista')).toHaveAttribute('aria-pressed', 'true')
    await expect(list(page)).toBeVisible()
    await expect(map(page)).toBeHidden()

    await viewButton(page, 'Mapa').click()

    await expect(map(page)).toBeVisible()
    await expect(list(page)).toBeHidden()
    await expect(markers(page)).toHaveCount(12)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)

    await viewButton(page, 'Lista').click()

    await expect(list(page)).toBeVisible()
    await expect(map(page)).toBeHidden()
  })

  test('na mapie znacznik pokazuje kartę punktu', async ({ page }) => {
    await login(page, 'anna')
    await page.getByRole('searchbox', { name: 'Szukaj punktu' }).fill('Gdańsk')
    await expect(list(page).getByRole('listitem')).toHaveCount(3)
    await viewButton(page, 'Mapa').click()
    const marker = map(page).getByRole('button', { name: 'Lotnisko Gdańsk', exact: true })

    await marker.click()

    await expect(marker).toHaveAttribute('aria-pressed', 'true')
    await expect(map(page).getByRole('heading', { name: 'Lotnisko Gdańsk', exact: true })).toBeVisible()
    await expect(map(page).getByText(/zł/)).toHaveCount(1)
    await expect(list(page)).toBeHidden()
  })
})
