const BACKEND_ORIGIN = 'https://app-agile-business-pro.onrender.com';
// The current Render instance still has the legacy CORS list. Requests from the
// browser never reach Render directly: this same-origin Vercel function is the
// only public hop. Use the backend's existing local trusted origin until the
// rolling Render release with the production domain is active.
const TRUSTED_BACKEND_ORIGIN = 'http://localhost:5173';

const LEADERSHIP_ROLES = new Set(['admin', 'owner', 'deputy_owner']);
const KPI_PERCENT_FIELDS = [
  'kpi1_deadlines',
  'kpi2_punctuality',
  'kpi3_initiative',
  'kpi4_overtime',
  'kpi5_quality',
  'kpi8_attentiveness',
  'kpi10_responsibility',
  'kpi_customer_satisfaction',
];
const MANAGER_PERCENT_FIELDS = [
  'manager_kpi1_reaction_index',
  'manager_kpi3_responsibility',
  'manager_kpi4_attentiveness',
  'manager_kpi5_idea_reaction',
  'manager_kpi6_overtime',
  'manager_kpi7_department_control',
];

function finiteNumber(value) {
  if (value === null || value === undefined || value === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function averageFields(payload, fields) {
  const values = fields.map(field => finiteNumber(payload[field])).filter(value => value !== null);
  if (!values.length) return null;
  return Math.round((values.reduce((sum, value) => sum + value, 0) / values.length) * 10) / 10;
}

function normalizeKpiPayload(payload, profile, managerDetails) {
  const role = payload.role || profile?.role || 'user';
  const hasOccupationalKpi = payload.has_occupational_kpi ?? LEADERSHIP_ROLES.has(role);
  const normalized = {
    ...payload,
    role,
    department_id: payload.department_id ?? profile?.department_id ?? null,
    has_occupational_kpi: hasOccupationalKpi,
    kpi1_deadlines: finiteNumber(payload.kpi1_deadlines),
    kpi2_punctuality: finiteNumber(payload.kpi2_punctuality),
    kpi3_initiative: finiteNumber(payload.kpi3_initiative),
    kpi4_overtime: finiteNumber(payload.kpi4_overtime),
    kpi5_quality: finiteNumber(payload.kpi5_quality),
    kpi8_attentiveness: finiteNumber(payload.kpi8_attentiveness),
    kpi9_bonus: finiteNumber(payload.kpi9_bonus),
    kpi9_carryover: finiteNumber(payload.kpi9_carryover) ?? 0,
    kpi10_responsibility: finiteNumber(payload.kpi10_responsibility),
    kpi_customer_satisfaction: finiteNumber(payload.kpi_customer_satisfaction),
    manager_kpi1_reaction_index: finiteNumber(payload.manager_kpi1_reaction_index),
    manager_kpi2_reaction_days: finiteNumber(payload.manager_kpi2_reaction_days)
      ?? finiteNumber(managerDetails?.current_kpi2),
    manager_kpi3_responsibility: finiteNumber(payload.manager_kpi3_responsibility),
    manager_kpi4_attentiveness: finiteNumber(payload.manager_kpi4_attentiveness),
    manager_kpi5_idea_reaction: finiteNumber(payload.manager_kpi5_idea_reaction),
    manager_kpi6_overtime: finiteNumber(payload.manager_kpi6_overtime)
      ?? finiteNumber(managerDetails?.total_overtime_percent),
    manager_kpi7_department_control: finiteNumber(payload.manager_kpi7_department_control),
  };
  normalized.general_score = finiteNumber(payload.general_score) ?? averageFields(normalized, KPI_PERCENT_FIELDS);
  normalized.occupational_score = finiteNumber(payload.occupational_score)
    ?? (hasOccupationalKpi ? averageFields(normalized, MANAGER_PERCENT_FIELDS) : null);
  normalized.overall_score = finiteNumber(payload.overall_score)
    ?? (
      normalized.general_score !== null && normalized.occupational_score !== null
        ? Math.round(((normalized.general_score + normalized.occupational_score) / 2) * 10) / 10
        : normalized.general_score
    );
  return normalized;
}

async function readBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(Buffer.from(chunk));
  return chunks.length ? Buffer.concat(chunks) : undefined;
}

export default async function handler(req, res) {
  const unsafeMethod = !['GET', 'HEAD', 'OPTIONS'].includes(req.method);
  const requestOrigin = req.headers.origin;
  const expectedOrigin = `https://${req.headers.host}`;
  if (unsafeMethod && (
    req.headers['sec-fetch-site'] === 'cross-site'
    || (requestOrigin && requestOrigin !== expectedOrigin)
  )) {
    return res.status(403).json({ detail: 'Запрос с этого источника запрещён' });
  }

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

  const fetchBackendJson = async (backendPath) => {
    const response = await fetch(new URL(`/api/${backendPath}`, BACKEND_ORIGIN), {
      method: 'GET',
      headers,
      redirect: 'manual',
    });
    if (!response.ok) return null;
    const contentType = response.headers.get('content-type') || '';
    return contentType.includes('application/json') ? response.json() : null;
  };

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
    const upstreamBody = Buffer.from(await upstream.arrayBuffer());
    const isKpiRead = req.method === 'GET' && (
      rawPath === 'gamification/kpi/me'
      || /^gamification\/kpi\/user\/[^/]+$/.test(rawPath)
    );
    if (upstream.ok && isKpiRead && (upstream.headers.get('content-type') || '').includes('application/json')) {
      const payload = JSON.parse(upstreamBody.toString('utf8'));
      const targetUserId = rawPath.startsWith('gamification/kpi/user/')
        ? rawPath.slice('gamification/kpi/user/'.length)
        : null;
      const profile = await fetchBackendJson(targetUserId ? `users/${targetUserId}` : 'auth/me');
      const managerDetails = targetUserId ? null : await fetchBackendJson('gamification/kpi/manager/details');
      res.setHeader('content-type', 'application/json; charset=utf-8');
      res.end(JSON.stringify(normalizeKpiPayload(payload, profile, managerDetails)));
      return;
    }
    res.end(upstreamBody);
  } catch (error) {
    console.error('Agile Control Center API proxy error', error);
    res.status(502).json({ detail: 'Сервис временно недоступен. Повторите попытку через минуту.' });
  }
}

export const config = { api: { bodyParser: false } };
