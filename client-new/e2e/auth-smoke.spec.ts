import { test, expect } from '@playwright/test';

function randomEmail() {
  const n = Math.floor(Math.random() * 1_000_000);
  return `e2e_${Date.now()}_${n}@example.com`;
}

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

test.describe('Auth smoke (API + cookies)', () => {
  test('register -> wrong password -> login success', async ({ page }) => {
    const email = randomEmail();
    const password = 'E2E_pass_12345';
    const wrongPassword = 'wrong_password_123';
    const name = 'E2E User';

    // 1) Register (creates user; HttpOnly cookies are set only on /auth/login)
    const registerRes = await page.request.post(`${API_BASE}/api/auth/register`, {
      headers: { 'Content-Type': 'application/json' },
      data: { name, email, password },
    });
    expect(registerRes.status(), `register: ${await registerRes.text().catch(() => '')}`).toBe(201);

    // 2) Wrong password should fail
    const wrongLoginRes = await page.request.post(`${API_BASE}/api/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { email, password: wrongPassword },
    });
    expect(wrongLoginRes.status()).toBe(401);

    // 3) Correct login -> set cookies
    const loginRes = await page.request.post(`${API_BASE}/api/auth/login`, {
      headers: { 'Content-Type': 'application/json' },
      data: { email, password },
    });
    expect(loginRes.ok(), `login: ${await loginRes.text().catch(() => '')}`).toBeTruthy();

    const setCookie = loginRes.headers()['set-cookie'];
    const accessToken = getCookieValue(setCookie, 'access_token');
    const refreshToken = getCookieValue(setCookie, 'refresh_token');
    expect(accessToken).toBeTruthy();
    expect(refreshToken).toBeTruthy();

    await page.context().addCookies([
      {
        name: 'access_token',
        value: accessToken as string,
        domain: 'localhost',
        path: '/',
        httpOnly: true,
        secure: false,
        sameSite: 'Lax',
      },
      {
        name: 'refresh_token',
        value: refreshToken as string,
        domain: 'localhost',
        path: '/',
        httpOnly: true,
        secure: false,
        sameSite: 'Lax',
      },
    ]);

    await page.goto('/');
    const logoutBtn = page.getByRole('button', { name: /logout|выход|გასვლა/i }).first();
    await expect(logoutBtn).toBeVisible({ timeout: 10_000 });

    // 4) Logout
    await expect(logoutBtn).not.toBeDisabled({ timeout: 60_000 });
    await logoutBtn.click();
    await expect(page).toHaveURL(/\/login/, { timeout: 20_000 });
  });
});

