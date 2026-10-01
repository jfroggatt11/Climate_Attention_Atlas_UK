import { expect, test } from '@playwright/test'

for (const left of ['physical:desnz_fuel_prices:uk_diesel', 'unavailable']) {
  test(`event spans and single-date markers render with ${left}`, async ({ page }, testInfo) => {
    await page.goto(`/timeline?left=${left}&right=physical:market_prices:tsla&events=all`)
    const areas = page.locator('.recharts-reference-area-rect')
    const lines = page.locator('.recharts-reference-line-line')
    await expect(areas).toHaveCount(5)
    await expect(lines).toHaveCount(1)
    for (const area of await areas.all()) {
      await expect(area).toBeVisible()
      const box = await area.boundingBox()
      expect(box!.width).toBeGreaterThan(0)
      expect(box!.height).toBeGreaterThan(100)
    }
    // A vertical SVG line has a zero-width bounding box; check its painted
    // coordinates instead of Playwright's box-based visibility assertion.
    const y1 = Number(await lines.getAttribute('y1'))
    const y2 = Number(await lines.getAttribute('y2'))
    expect(Math.abs(y2 - y1)).toBeGreaterThan(100)
    expect(Number(await lines.getAttribute('x1'))).toBeGreaterThan(0)
    await page.locator('.atlas-chart-shell').screenshot({ path: testInfo.outputPath('events.png') })
    await page.getByRole('button', { name: 'Hide events', exact: true }).click()
    await expect(areas).toHaveCount(0)
    await expect(lines).toHaveCount(0)
    await page.getByRole('button', { name: 'Show all events', exact: true }).click()
    await expect(areas).toHaveCount(5)
    await expect(lines).toHaveCount(1)
  })
}
