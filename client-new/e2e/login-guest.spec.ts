import { test, expect } from '@playwright/test';

test.describe('Login page (guest)', () => {
  test('forgot password and register toggles', async ({ page }) => {
    const safeGoto = async (url: string) => {
      try {
        await page.goto(url, { waitUntil: 'commit', timeout: 30_000 });
      } catch (e: any) {
        // SPA-роутер иногда отменяет навигацию, что даёт net::ERR_ABORTED.
        // Дальше мы всё равно ждём нужные элементы, поэтому можно игнорировать.
        const msg = String(e?.message || e);
        const benign =
          msg.includes('ERR_ABORTED') ||
          msg.includes('interrupted by another navigation') ||
          (msg.includes('Navigation to ') && msg.includes(' is interrupted'));
        if (!benign) throw e;
      }
    };

    await safeGoto('/login?mode=forgot');
    await expect(page.locator('input[type="email"]').first()).toBeVisible({ timeout: 10_000 });

    // SPA-переход может отменяться React Router'ом, поэтому для goto используем более мягкий критерий ожидания.
    await safeGoto('/login?mode=register');
    const registerNameInput = page.locator('input[type="text"]').first();
    // В full suite SPA иногда откатывает URL/состояние, поэтому делаем 1-2 попытки.
    let lastError: unknown = null;
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        await expect(registerNameInput).toBeVisible({ timeout: 10_000 });
        lastError = null;
        break;
      } catch (e) {
        lastError = e;
        await safeGoto('/login?mode=register');
      }
    }
    if (lastError) throw lastError;
  });
});
