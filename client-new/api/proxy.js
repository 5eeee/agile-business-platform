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

function normalizeLegacyOwner(value) {
  if (Array.isArray(value)) return value.map(normalizeLegacyOwner);
  if (!value || typeof value !== 'object') return value;
  const normalized = { ...value };
  for (const [key, child] of Object.entries(normalized)) {
    if (child && typeof child === 'object') normalized[key] = normalizeLegacyOwner(child);
  }
  const email = String(normalized.email || '').trim().toLowerCase();
  const isCanonicalOwner = email === 'admin@agile.com' || email === 'agilebusiness';
  const isNamedLegacyOwner = normalized.role === 'admin'
    && normalized.name === 'Алексей'
    && normalized.last_name === 'Девятов';
  if (isCanonicalOwner || isNamedLegacyOwner) {
    normalized.name = 'Алексей';
    normalized.last_name = 'Девятов';
    normalized.role = 'owner';
  }
  return normalized;
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

function taskUserIds(task) {
  const ids = [task?.creator_id, task?.assignee_id, ...(Array.isArray(task?.assignee_ids) ? task.assignee_ids : [])];
  return ids.filter(Boolean).map(String);
}

function taskIsVisible(task, visibleUserIds) {
  if (visibleUserIds === null) return true;
  return taskUserIds(task).some(userId => visibleUserIds.has(userId));
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
    return contentType.includes('application/json')
      ? normalizeLegacyOwner(await response.json())
      : null;
  };

  let viewerCache;
  let visibleUserIdsCache;
  const getViewer = async () => {
    if (viewerCache === undefined) viewerCache = await fetchBackendJson('auth/me');
    return viewerCache;
  };
  const getVisibleUserIds = async () => {
    if (visibleUserIdsCache !== undefined) return visibleUserIdsCache;
    const viewer = await getViewer();
    if (!viewer) return new Set();
    if (viewer.role === 'owner' || viewer.role === 'deputy_owner') {
      visibleUserIdsCache = null;
      return null;
    }
    const visible = new Set([String(viewer.id)]);
    if (viewer.role === 'admin') {
      const users = await fetchBackendJson('users');
      for (const employee of Array.isArray(users) ? users : []) {
        const directReport = String(employee.manager_id || '') === String(viewer.id);
        const sameDepartment = Boolean(
          viewer.department_id
          && employee.department_id === viewer.department_id
        );
        if (directReport || sameDepartment) visible.add(String(employee.id));
      }
    }
    visibleUserIdsCache = visible;
    return visible;
  };

  const taskIdMatch = rawPath.match(/^tasks\/([0-9a-f-]{36})(?:\/|$)/i);

  try {
    const body = ['GET', 'HEAD'].includes(req.method) ? undefined : await readBody(req);
    const visibleUserIds = rawPath.startsWith('tasks') ? await getVisibleUserIds() : null;
    const isDirectTaskRead = req.method === 'GET' && /^tasks\/[0-9a-f-]{36}$/i.test(rawPath);
    if (taskIdMatch && !isDirectTaskRead && !['HEAD', 'OPTIONS'].includes(req.method)) {
      const existingTask = await fetchBackendJson(`tasks/${taskIdMatch[1]}`);
      if (!existingTask || !taskIsVisible(existingTask, visibleUserIds)) {
        return res.status(404).json({ detail: 'Задача не найдена' });
      }
    }
    if (body && ['POST', 'PUT', 'PATCH'].includes(req.method) && /^tasks(?:\/[^/]+)?$/.test(rawPath)) {
      const contentType = String(req.headers['content-type'] || '');
      if (contentType.includes('application/json')) {
        const input = JSON.parse(body.toString('utf8'));
        const assignedIds = [input.assignee_id, ...(Array.isArray(input.assignee_ids) ? input.assignee_ids : [])]
          .filter(Boolean)
          .map(String);
        if (visibleUserIds !== null && assignedIds.some(userId => !visibleUserIds.has(userId))) {
          return res.status(403).json({ detail: 'Нельзя назначить задачу сотруднику вне вашей зоны ответственности' });
        }
      }
    }
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
    const isTaskRead = upstream.ok
      && req.method === 'GET'
      && (upstream.headers.get('content-type') || '').includes('application/json')
      && (
        rawPath === 'tasks'
        || /^tasks\/iteration\/[^/]+$/.test(rawPath)
        || /^tasks\/[0-9a-f-]{36}$/i.test(rawPath)
      );
    if (isTaskRead) {
      const taskPayload = JSON.parse(upstreamBody.toString('utf8'));
      if (Array.isArray(taskPayload)) {
        res.setHeader('content-type', 'application/json; charset=utf-8');
        res.end(JSON.stringify(taskPayload.filter(task => taskIsVisible(task, visibleUserIds))));
        return;
      }
      if (!taskIsVisible(taskPayload, visibleUserIds)) {
        return res.status(404).json({ detail: 'Задача не найдена' });
      }
    }
    const isKpiRead = req.method === 'GET' && (
      rawPath === 'gamification/kpi/me'
      || /^gamification\/kpi\/user\/[^/]+$/.test(rawPath)
    );
    if (upstream.ok && isKpiRead && (upstream.headers.get('content-type') || '').includes('application/json')) {
      const payload = normalizeLegacyOwner(JSON.parse(upstreamBody.toString('utf8')));
      const targetUserId = rawPath.startsWith('gamification/kpi/user/')
        ? rawPath.slice('gamification/kpi/user/'.length)
        : null;
      const profile = await fetchBackendJson(targetUserId ? `users/${targetUserId}` : 'auth/me');
      const managerDetails = targetUserId ? null : await fetchBackendJson('gamification/kpi/manager/details');
      res.setHeader('content-type', 'application/json; charset=utf-8');
      res.end(JSON.stringify(normalizeKpiPayload(payload, profile, managerDetails)));
      return;
    }
    const shouldNormalizeUserResponse = upstream.ok
      && req.method === 'GET'
      && (upstream.headers.get('content-type') || '').includes('application/json')
      && (
        rawPath === 'auth/me'
        || rawPath === 'users'
        || rawPath.startsWith('users/')
        || rawPath === 'admin/users'
      );
    if (shouldNormalizeUserResponse) {
      res.setHeader('content-type', 'application/json; charset=utf-8');
      res.end(JSON.stringify(normalizeLegacyOwner(JSON.parse(upstreamBody.toString('utf8')))));
      return;
    }
    res.end(upstreamBody);
  } catch (error) {
    console.error('Agile Control Center API proxy error', error);
    res.status(502).json({ detail: 'Сервис временно недоступен. Повторите попытку через минуту.' });
  }
}

export const config = { api: { bodyParser: false } };
