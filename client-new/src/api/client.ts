import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  withCredentials: true,
});

/** После успешного редиректа на /login флаг остаётся true до сброса — см. resetAuthRedirectGate */
let authRedirectScheduled = false;

/**
 * Сбросить «замок» редиректа (после успешного входа /auth/me без перезагрузки страницы).
 * Вызывать из authSlice при fulfilled login / fetchMe / verify2FA.
 */
export function resetAuthRedirectGate(): void {
  authRedirectScheduled = false;
}

function scheduleAuthRedirect(): void {
  if (typeof window === 'undefined') return;
  if (window.location.hash.startsWith('#/login')) return;
  if (authRedirectScheduled) return;
  authRedirectScheduled = true;
  window.location.replace('/#/login');
}

// Автоматически ставим Content-Type: application/json только для не-FormData
api.interceptors.request.use((config) => {
  if (!(config.data instanceof FormData)) {
    config.headers['Content-Type'] = 'application/json';
  }
  return config;
});

// Mutex для предотвращения параллельных refresh-запросов
let refreshPromise: Promise<void> | null = null;
async function ensureRefreshed(): Promise<void> {
  if (!refreshPromise) {
    refreshPromise = api
      .post('/auth/refresh', null, { _skipAuthRefresh: true } as any)
      .then(() => undefined)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

// Интерцептор для обновления токена (через HttpOnly cookies)
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (!originalRequest) {
      return Promise.reject(error);
    }

    const status = error.response?.status;
    const req = originalRequest as any;

    if (status === 401) {
      // Не трогаем refresh/редирект: разгрузка сессии, выход, ошибки на странице логина и т.п.
      if (req._silent401) {
        return Promise.reject(error);
      }

      // Сама операция refresh: при провале — один редирект на логин (не дублировать десятками запросов).
      if (req._skipAuthRefresh) {
        scheduleAuthRedirect();
        return Promise.reject(error);
      }

      // Уже был retry после refresh — снова 401, не крутим refresh по кругу.
      if (req._retry) {
        scheduleAuthRedirect();
        return Promise.reject(error);
      }

      req._retry = true;
      try {
        await ensureRefreshed();
        return api(originalRequest);
      } catch (refreshError) {
        scheduleAuthRedirect();
        return Promise.reject(refreshError);
      }
    }

    // Проверка увольнения
    if (error.response?.status === 403 && error.response?.headers?.['x-fired']) {
      const fireMessage = error.response?.data?.detail || 'ВЫ УВОЛЕНЫ';
      window.dispatchEvent(new CustomEvent('user-fired', { detail: fireMessage }));
    }

    // Global error toast (skip 401 and optional background widgets which render
    // their own empty/error state). This prevents a stale backend during a
    // rolling deploy from showing a misleading page-level "Not Found" toast.
    if (error.response && error.response.status !== 401 && !req._silentGlobalError) {
      const raw = error.response?.data?.detail;
      let msg: string;
      if (typeof raw === 'string') {
        msg = raw;
      } else if (Array.isArray(raw)) {
        msg = raw
          .map((item: { msg?: string; loc?: unknown[] }) =>
            typeof item?.msg === 'string' ? item.msg : JSON.stringify(item)
          )
          .join('; ');
      } else if (raw != null && typeof raw === 'object') {
        msg = JSON.stringify(raw);
      } else {
        msg = error.message || 'Ошибка';
      }
      window.dispatchEvent(new CustomEvent('api-error', { detail: msg }));
    }

    return Promise.reject(error);
  }
);

export default api;
