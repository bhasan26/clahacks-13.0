// Uses an existing Playwright installation. Run the API on port 8001 and a Vite
// test server on port 5174 whose /api proxy targets port 8001 (no request routing).
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  globalThis.checkPage = page;
  const errors = [];
  page.on('pageerror', error => { errors.push(error.message); console.error('Browser error:', error.message); });
  await page.goto(process.env.COVERAGEGUARD_TEST_URL || 'http://127.0.0.1:5174');
  assert.equal(await page.getByRole('navigation').getByRole('button').count(), 4);
  assert.equal(await page.locator('input[type=file]').count(), 2);
  await page.getByRole('button', { name: 'Check', exact: true }).click();
  await page.getByText('Missing: insurance card, prescription.', { exact: true }).waitFor();

  await page.locator('#insurance-card').setInputFiles({ name: 'card.txt', mimeType: 'text/plain', buffer: Buffer.from('UnitedHealthcare') });
  await page.locator('#prescription').setInputFiles({ name: 'prescription.txt', mimeType: 'text/plain', buffer: Buffer.from('NOT VALID FOR DISPENSING\nRx: Ozempic (semaglutide) 1 mg') });
  await page.getByRole('button', { name: 'Check', exact: true }).click();
  await page.getByText('Prescription assumed valid for this policy test. Insurer approval is not confirmed.', { exact: true }).waitFor({ timeout: 28000 });
  assert(await page.getByText('Needs policy review', { exact: true }).isVisible());
  assert(await page.getByText('Ozempic (semaglutide) 1 mg', { exact: true }).isVisible());
  assert(await page.getByText('If insurance does not cover the prescribed treatment, please consult the responsible physician.', { exact: true }).isVisible());
  await page.screenshot({ path: '/private/tmp/coverageguard-four-pages-check.png', fullPage: true });

  for (const [folder, ext] of [['output/pdf', 'pdf'], ['backend/tests/fixtures', 'png']]) {
    await page.locator('#insurance-card').setInputFiles(path.resolve(folder, `sample_unitedhealthcare_insurance_card.${ext}`));
    await page.locator('#prescription').setInputFiles(path.resolve(folder, `sample_prescription_avery_sample.${ext}`));
    await page.getByRole('button', { name: 'Check', exact: true }).click();
    await page.getByText('Prescription assumed valid for this policy test. Insurer approval is not confirmed.', { exact: true }).waitFor({ timeout: 28000 });
    assert(await page.getByText('Needs policy review', { exact: true }).isVisible());
    assert(await page.getByText('UnitedHealthcare', { exact: true }).isVisible());
  }
  // Live retrieved policy: matching clinical criteria and a specific policy mismatch.
  for (const [clinical, expected] of [
    ['Diagnosis: E11.9 Type 2 diabetes mellitus\nA1C: 7.2%', 'Accepted'],
    ['Diagnosis: Obesity, weight loss only', 'Policy mismatch'],
  ]) {
    await page.locator('#insurance-card').setInputFiles({ name: 'card.txt', mimeType: 'text/plain', buffer: Buffer.from('UnitedHealthcare') });
    await page.locator('#prescription').setInputFiles({ name: 'test-rx.txt', mimeType: 'text/plain', buffer: Buffer.from(`NOT VALID FOR DISPENSING\nRx: Ozempic\n${clinical}`) });
    await page.getByRole('button', { name: 'Check', exact: true }).click();
    await page.getByText(expected, { exact: true }).waitFor({ timeout: 28000 });
    assert(await page.getByRole('link', { name: 'Policy: 2026 P 1332-8', exact: true }).isVisible());
  }
  await page.getByRole('button', { name: 'All Requests', exact: true }).click();
  await page.getByRole('columnheader', { name: 'Request ID', exact: true }).waitFor();
  assert.equal(await page.getByRole('columnheader').count(), 6);
  await page.getByRole('button', { name: 'Open report', exact: true }).nth(3).waitFor();
  assert((await page.getByRole('button', { name: 'Open report', exact: true }).count()) >= 4);
  await page.getByRole('button', { name: 'Open report', exact: true }).first().click();
  await page.getByRole('dialog').waitFor();
  assert(await page.getByRole('dialog').getByText('UnitedHealthcare', { exact: true }).isVisible());
  await page.keyboard.press('Escape');
  assert.equal(await page.getByRole('dialog').count(), 0);
  await page.screenshot({ path: '/private/tmp/coverageguard-four-pages-requests.png', fullPage: true });

  await page.getByRole('button', { name: 'Insurance Database Connection', exact: true }).click();
  await page.getByText('READ ONLY — NO WRITE ACCESS', { exact: true }).waitFor();
  assert(await page.getByText('READ-ONLY', { exact: true }).isVisible());
  assert(await page.getByText('Application records connected. Direct insurer database access is not configured.', { exact: true }).isVisible());
  await page.getByRole('button', { name: 'Latest Insurance Updates', exact: true }).click();
  await page.getByRole('heading', { name: 'Latest Insurance Updates', exact: true }).waitFor();
  await page.reload();
  await page.getByRole('heading', { name: 'Latest Insurance Updates', exact: true }).waitFor();
  await page.getByRole('button', { name: 'New Insurance Check', exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: '/private/tmp/coverageguard-four-pages-mobile.png', fullPage: true });
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  assert.deepEqual(errors, []);
  console.log('PASS: four pages, missing uploads, assumed-valid sample prescriptions, policy acceptance and mismatch with citations, PDF/image OCR, history, report, connection permissions, reload, mobile layout; no browser errors.');
  await browser.close();
})().catch(async error => { console.error(error); if (globalThis.checkPage) { console.error((await checkPage.locator('body').innerText()).slice(-2500)); await checkPage.screenshot({ path: '/private/tmp/coverageguard-browser-failure.png', fullPage: true }); await checkPage.context().browser()?.close(); } process.exit(1); });
