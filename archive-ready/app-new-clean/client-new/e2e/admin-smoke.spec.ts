import { test, expect } from '@playwright/test';

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || 'admin@agile.com';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || 'Admin!Agile(Secured';
const ADMIN_PASSWORD_FALLBACK = 'Admin!Agile(Secured';

const API_BASE = process.env.E2E_API_BASE || 'http://127.0.0.1:8000';

function parseSetCookieHeader(setCookieHeaders: string[] | string | undefined) {
  const cookies = Array.isArray(setCookieHeaders) ? setCookieHeaders : setCookieHeaders ? [setCookieHeaders] : [];
  return cookies;
}

function getCookieValue(setCookieHeaders: string[] | string | undefined, name: string) {
  const headerStr = Array.isArray(setCookieHeaders) ? setCookieHeaders.join(',') : setCookieHeaders || '';
  const match = headerStr.match(new RegExp(`${name}=([^;]+)`));
  if (!match) return null;
  return decodeURIComponent(match[1]);
}

async function loginAsAdmin(page: import('@playwright/test').Page) {
  const passwordCandidates = ADMIN_PASSWORD && ADMIN_PASSWORD !== ADMIN_PASSWORD_FALLBACK
    ? [ADMIN_PASSWORD, ADMIN_PASSWORD_FALLBACK]
    : [ADMIN_PASSWORD_FALLBACK];

  let loginRes: import('@playwright/test').APIResponse | null = null;
  for (const pwd of passwordCandidates) {
    loginRes = await page.request.post(`${API_BASE}/api/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { email: ADMIN_EMAIL, password: pwd },
    });
    if (loginRes.ok()) break;
  }
  if (!loginRes) throw new Error('loginAsAdmin: no login response');

  if (!loginRes.ok()) {
    const body = await loginRes.text().catch(() => '');
    throw new Error(
      `POST /api/auth/login -> ${loginRes.status()}. ${body.slice(0, 200)} ` +
        `Check E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD (prod DB = prod admin password).`
    );
  }

  const setCookie = loginRes.headers()['set-cookie'];
  const accessToken = getCookieValue(setCookie, 'access_token');
  const refreshToken = getCookieValue(setCookie, 'refresh_token');
  if (!accessToken || !refreshToken) {
    throw new Error(`login did not return access_token/refresh_token cookies (set-cookie: ${String(setCookie)})`);
  }

  await page.context().addCookies([
    {
      name: 'access_token',
      value: accessToken,
      domain: 'localhost',
      path: '/',
      httpOnly: true,
      secure: false,
      sameSite: 'Lax',
    },
    {
      name: 'refresh_token',
      value: refreshToken,
      domain: 'localhost',
      path: '/',
      httpOnly: true,
      secure: false,
      sameSite: 'Lax',
    },
  ]);

  await page.goto('/');
  await expect(page).not.toHaveURL(/\/login/, { timeout: 10_000 });
}

test.describe('Admin UI smoke', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
  });

  test('core routes load without crash', async ({ page }) => {
    const paths = [
      '/',
      '/projects',
      '/events',
      '/places',
      '/music',
      '/shop',
      '/analytics',
      '/training',
      '/assessment',
      '/competency',
      '/kpi',
      '/leaderboard',
      '/profile',
      '/admin',
    ];

    for (const path of paths) {
      await page.goto(path);
      await page.waitForLoadState('domcontentloaded');
      await expect(page.locator('body')).toBeVisible();
      const fired = await page.getByText(/уволен|fired/i).count();
      expect(fired).toBe(0);
    }
  });

  test('header: search modal open/close', async ({ page }) => {
    await page.goto('/');
    const searchBtn = page.getByRole('button', { name: /search|поиск|ctrl\+k/i });
    await searchBtn.click();
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 5000 });
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toHaveCount(0, { timeout: 3000 });
  });

  test('header: theme toggle', async ({ page }) => {
    await page.goto('/');
    const themeBtn = page.getByRole('button', { name: /theme|dark|light|Switch/i });
    await themeBtn.click();
    await page.waitForTimeout(400);
    await themeBtn.click();
  });

  test('header: notifications bell', async ({ page }) => {
    await page.goto('/');
    const bell = page.getByRole('button', { name: /notification/i });
    await bell.click();
    await page.waitForTimeout(500);
    await page.keyboard.press('Escape').catch(() => {});
  });

  test('sidebar: new project from sidebar', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /новый проект|new project/i }).click();
    await expect(page).toHaveURL(/\/projects/, { timeout: 8000 });
    await expect(page.locator('.modal-overlay, [class*="modal"]').first()).toBeVisible({ timeout: 8000 });
    await page.locator('.modal-overlay').first().click({ position: { x: 2, y: 2 } }).catch(() => {});
  });

  test('projects: open first project if any', async ({ page }) => {
    await page.goto('/projects');
    const card = page.locator('[class*="quickCard"]').first();
    if (await card.isVisible().catch(() => false)) {
      await card.click();
      await expect(page).toHaveURL(/\/project\//, { timeout: 10_000 });
      await page.waitForLoadState('domcontentloaded');
    }
  });

  test('profile: tab or form visible', async ({ page }) => {
    await page.goto('/profile');
    await expect(page.locator('main, .page, [class*="page"]').first()).toBeVisible({ timeout: 10_000 });
  });

  test('logout returns to login', async ({ page }) => {
    await page.goto('/');
    const logout = page.getByRole('button', { name: /logout|выход|გასვლა/i });
    await logout.click();
    await expect(page).toHaveURL(/\/login/, { timeout: 15_000 });
  });
});
