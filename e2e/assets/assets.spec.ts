import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { expect, test, type Locator, type Page } from '@playwright/test'

const ASSETS_DIR = resolve('../report/assets')
const MIN_WIDTH = 2000
const ERD_HTML = process.env.ERD_HTML
const ERD_VIEWS: Record<string, string> = {
  '.legend-wrap': 'legenda',
  '#zone-overview svg': 'przeglad',
  '#zone-net svg': 'siec-automatow',
  '#zone-money svg': 'klient-i-pieniadze',
  '#zone-booking svg': 'zamowienie-i-rezerwacja',
  '#zone-access svg': 'dostep-i-incydenty',
  '#zone-audit svg': 'dziennik-zdarzen',
}

test.use({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 })

async function shoot(page: Page, element: Locator, path: string) {
  await page.evaluate(() => document.fonts.ready)
  const png = await element.screenshot({ path })
  expect(png.readUInt32BE(16)).toBeGreaterThanOrEqual(MIN_WIDTH)
}

test('diagram ERD', async ({ page }) => {
  test.skip(!ERD_HTML, 'Ustaw ERD_HTML na ścieżkę strony ERD')
  await page.addInitScript(() => {
    localStorage.setItem('bagazomat-erd:theme', 'light')
    localStorage.setItem('bagazomat-erd:lang', 'pl')
  })
  await page.goto(pathToFileURL(resolve(ERD_HTML!)).href)
  await page.addStyleTag({ content: '.controls, .handle { display: none !important; } .legend-wrap { padding: 16px; }' })
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
  await expect(page.locator('html')).toHaveAttribute('lang', 'pl')
  for (const view of ['#zone-overview svg', '#zone-audit svg']) {
    await expect(page.locator(`${view} text`).filter({ hasText: /^audit_event_$/ }).first()).toBeVisible()
  }
  for (const [selector, name] of Object.entries(ERD_VIEWS)) {
    await shoot(page, page.locator(selector), `${ASSETS_DIR}/erd/${name}.png`)
  }
})

test('model grafowy', async ({ page }) => {
  await page.goto(pathToFileURL(`${ASSETS_DIR}/graph/model.svg`).href)
  await shoot(page, page.locator('svg').first(), `${ASSETS_DIR}/graph/model.png`)
})

test('potok make full', async ({ page }) => {
  await page.goto(pathToFileURL(`${ASSETS_DIR}/pipeline/pipeline.svg`).href)
  await shoot(page, page.locator('svg').first(), `${ASSETS_DIR}/pipeline/pipeline.png`)
})
