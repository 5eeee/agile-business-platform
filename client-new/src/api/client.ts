import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  withCredentials: true,
});

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
    
    if (error.response?.status === 401) {
      // Не пытаться обновлять токен для самой операции refresh.
      if ((originalRequest as any)?._skipAuthRefresh) {
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }

      if (!originalRequest._retry) {
        originalRequest._retry = true;
        try {
          await ensureRefreshed();
          return api(originalRequest);
        } catch (refreshError) {
          if (window.location.pathname !== '/login') {
            window.location.href = '/login';
          }
          return Promise.reject(refreshError);
        }
      }
    }
    
    // Проверка увольнения
    if (error.response?.status === 403 && error.response?.headers?.['x-fired']) {
      const fireMessage = error.response?.data?.detail || 'ВЫ УВОЛЕНЫ';
      window.dispatchEvent(new CustomEvent('user-fired', { detail: fireMessage }));
    }
    
    // Global error toast (skip 401 which is handled above)
    if (error.response && error.response.status !== 401) {
      const msg = error.response?.data?.detail || error.message || 'Ошибка';
      window.dispatchEvent(new CustomEvent('api-error', { detail: msg }));
    }
    
    return Promise.reject(error);
  }
);

export default api;
