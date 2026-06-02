/**
 * Проверка доступности API (запускайте при работающем backend).
 * API_URL=http://127.0.0.1:8000 npm run verify
 */
const base = (process.env.API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

async function main() {
  const checks = [
    ['/api/readiness', [200]],
    ['/openapi.json', [200]],
  ];
  for (const [path, okStatuses] of checks) {
    const url = base + path;
    let res;
    try {
      res = await fetch(url, { signal: AbortSignal.timeout(8000) });
    } catch (e) {
      console.error(`FAIL ${url}:`, e.message || e);
      process.exit(1);
    }
    if (!okStatuses.includes(res.status)) {
      console.error(`FAIL ${url}: HTTP ${res.status}`);
      process.exit(1);
    }
    console.log(`OK ${path} -> ${res.status}`);
  }

  const spec = await (await fetch(base + '/openapi.json')).json();
  const pathKeys = Object.keys(spec.paths || {});
  const hasBoard = pathKeys.some((p) => p.includes('board-columns'));
  if (!hasBoard) {
    console.warn('Предупреждение: в OpenAPI нет board-columns — перезапустите backend с актуальным кодом.');
  } else {
    console.log('OK OpenAPI содержит маршруты board-columns');
  }
  console.log('verify: готово');
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
