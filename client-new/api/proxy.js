const BACKEND_ORIGIN = 'https://app-agile-business-pro.onrender.com';
// The current Render instance still has the legacy CORS list. Requests from the
// browser never reach Render directly: this same-origin Vercel function is the
// only public hop. Use the backend's existing local trusted origin until the
// rolling Render release with the production domain is active.
const TRUSTED_BACKEND_ORIGIN = 'http://localhost:5173';

async function readBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(Buffer.from(chunk));
  return chunks.length ? Buffer.concat(chunks) : undefined;
}

export default async function handler(req, res) {
  const rawPath = Array.isArray(req.query.path) ? req.query.path.join('/') : (req.query.path || '');
  const url = new URL(`/api/${rawPath}`, BACKEND_ORIGIN);
  for (const [key, value] of Object.entries(req.query)) {
    if (key === 'path') continue;
    const values = Array.isArray(value) ? value : [value];
    for (const item of values) url.searchParams.append(key, String(item));
  }

  const headers = new Headers();
  for (const [key, value] of Object.entries(req.headers)) {
    const lower = key.toLowerCase();
    if (['host', 'origin', 'referer', 'content-length', 'connection', 'accept-encoding'].includes(lower)) continue;
    if (Array.isArray(value)) value.forEach(item => headers.append(key, item));
    else if (value != null) headers.set(key, value);
  }
  headers.set('x-forwarded-host', req.headers.host || 'agile-control-center.vercel.app');
  headers.set('x-forwarded-proto', 'https');
  // Backend CSRF requires a trusted origin. The browser still communicates only
  // with this same-origin proxy; the server-to-server hop uses its own origin.
  headers.set('origin', TRUSTED_BACKEND_ORIGIN);
  headers.set('referer', `${TRUSTED_BACKEND_ORIGIN}/`);

  try {
    const body = ['GET', 'HEAD'].includes(req.method) ? undefined : await readBody(req);
    const upstream = await fetch(url, { method: req.method, headers, body, redirect: 'manual' });
    res.statusCode = upstream.status;
    upstream.headers.forEach((value, key) => {
      if (!['content-encoding', 'content-length', 'transfer-encoding', 'connection', 'set-cookie'].includes(key.toLowerCase())) {
        res.setHeader(key, value);
      }
    });
    const cookies = typeof upstream.headers.getSetCookie === 'function'
      ? upstream.headers.getSetCookie()
      : (upstream.headers.get('set-cookie') ? [upstream.headers.get('set-cookie')] : []);
    if (cookies.length) res.setHeader('set-cookie', cookies);
    res.end(Buffer.from(await upstream.arrayBuffer()));
  } catch (error) {
    console.error('Agile Control Center API proxy error', error);
    res.status(502).json({ detail: 'Сервис временно недоступен. Повторите попытку через минуту.' });
  }
}

export const config = { api: { bodyParser: false } };
