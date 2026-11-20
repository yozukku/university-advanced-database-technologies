import { test as base } from '@playwright/test'
import { resetData } from './api'

export const test = base.extend<{ resetBeforeEach: void }>({
  resetBeforeEach: [
    async ({}, use) => {
      await resetData()
      await use()
    },
    { auto: true },
  ],
})

export { expect } from '@playwright/test'
