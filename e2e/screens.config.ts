import { defineConfig } from '@playwright/test'
import base from './playwright.config'

export default defineConfig(base, {
  testDir: './screens',
  timeout: 180_000,
})
