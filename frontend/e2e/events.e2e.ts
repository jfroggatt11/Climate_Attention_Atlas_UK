import { expect, test } from '@playwright/test'

test('event menu groups hazards and cleans provider country labels', async ({ page }) => {
  await page.goto('/timeline?release=candidate')
  await page.getByText('Browse and select events', { exact: true }).click()
  await expect(page.locator('.atlas-event-group-heading').getByText('Weather and hazards', { exact: true })).toBeVisible()
  await expect(page.getByText('Flood in the United Kingdom (also listed for Ireland)', { exact: true })).toHaveCount(1)
  await expect(page.getByText('Flood affecting Portugal and the United Kingdom', { exact: true })).toHaveCount(0)
  await expect(page.getByText(/Iran’s direct attack on Israel/)).toHaveCount(1)
  await expect(page.getByText(/Strait of Hormuz oil-supply risk/)).toHaveCount(1)
  const weatherGroup = page.locator('details.atlas-event-group').filter({ hasText: 'Weather and hazards' })
  await expect(weatherGroup.locator('.atlas-event-option')).not.toHaveCount(0)
  await weatherGroup.locator('summary').click()
  await expect(weatherGroup).not.toHaveAttribute('open', '')
  await weatherGroup.locator('summary').click()
  await expect(weatherGroup).toHaveAttribute('open', '')
  await page.getByLabel('Event type').selectOption('weather')
  await expect.poll(() => page.locator('.atlas-event-option').count()).toBeGreaterThan(20)
  await expect(page.getByText('Storm Eunice', { exact: true })).toBeVisible()
  await expect(page.getByText('UN Climate Change Conference COP26 (Glasgow)', { exact: true })).toHaveCount(0)
  await page.locator('.atlas-event-filters select').nth(1).selectOption('local')
  await expect(page.locator('.atlas-event-subgroup h4').getByText('Global / regional', { exact: true })).toHaveCount(0)
})

for (const plot of ['lines']) {
  test(`event tooltips show original dates in ${plot}`, async ({ page }, testInfo) => {
    await page.goto(`/timeline?left=physical:desnz_fuel_prices:uk_diesel&right=physical:market_prices:tsla&events=all&plot=${plot}`)
    const tooltip = page.getByRole('tooltip')
    const range = page.locator('[data-event-id="gdacs:FL:1103066"]')
    await range.hover({ force: plot === 'layers' })
    await expect(tooltip).toContainText('Flood in the United Kingdom')
    await expect(tooltip).toContainText('Start: 01 Jan 2025')
    await expect(tooltip).toContainText('End: 08 Jan 2025')
    await page.screenshot({ path: testInfo.outputPath('event-tooltip.png') })
    await page.getByRole('heading', { name: 'Attention timeline' }).hover()
    await expect(tooltip).toHaveCount(0)

    await page.locator('[data-event-id="gdacs:FL:1103661"]').focus()
    await expect(tooltip).toContainText('Flood in the United Kingdom (also listed for Ireland)')
    await expect(tooltip).toContainText('Start: 09 Dec 2025')
    await expect(tooltip).toContainText('End: 13 Dec 2025')

    // Clip the range at both sides; tooltip must retain provider dates.
    await page.getByLabel('From', { exact: true }).fill('2025-01-03')
    await page.getByLabel('To', { exact: true }).fill('2025-01-06')
    await range.hover()
    await expect(tooltip).toContainText('Start: 01 Jan 2025')
    await expect(tooltip).toContainText('End: 08 Jan 2025')
    await page.getByRole('button', { name: 'Hide events', exact: true }).click()
    await expect(tooltip).toHaveCount(0)
  })
}

for (const left of ['physical:desnz_fuel_prices:uk_diesel', 'unavailable']) {
  test(`event spans render with ${left}`, async ({ page }, testInfo) => {
    await page.goto(`/timeline?left=${left}&right=physical:market_prices:tsla&events=all`)
    const areas = page.locator('.recharts-reference-area-rect')
    const lines = page.locator('.recharts-reference-line-line')
    await expect.poll(() => areas.count()).toBeGreaterThan(20)
    await expect.poll(() => lines.count()).toBeGreaterThan(10)
    for (const area of await areas.all()) {
      await expect(area).toBeVisible()
      const box = await area.boundingBox()
      expect(box!.width).toBeGreaterThan(0)
      expect(box!.height).toBeGreaterThan(100)
    }
    await page.locator('.atlas-chart-shell').screenshot({ path: testInfo.outputPath('events.png') })
    await page.getByRole('button', { name: 'Hide events', exact: true }).click()
    await expect(areas).toHaveCount(0)
    await expect(lines).toHaveCount(0)
    await page.getByRole('button', { name: 'Show all events', exact: true }).click()
    await expect.poll(() => areas.count()).toBeGreaterThan(20)
    await expect.poll(() => lines.count()).toBeGreaterThan(10)
  })
}
