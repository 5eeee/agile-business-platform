import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import api from '../../api/client';
import type { User } from '../../types';

/** Единый разбор ошибок API для входа/регистрации (422, CSRF, сеть, 429). */
function formatAuthRequestError(err: unknown, fallback: string): string {
  const e = err as {
    code?: string;
    response?: { status?: number; data?: { detail?: string | Array<{ msg?: string }> } };
  };
  if (!e.response) {
    if (e.code === 'ECONNABORTED') return 'Превышено время ожидания сервера';
    return 'Сервер недоступен. Запустите API (порт 8000) и проверьте, что Vite проксирует /api.';
  }
  const st = e.response.status;
  if (st === 403) {
    const d = e.response.data?.detail;
    if (typeof d === 'string' && d.toLowerCase().includes('csrf')) {
      return 'Доступ с этого адреса запрещён настройками сервера. В CORS_ORIGINS должен быть точный URL из адресной строки (https, домен, без лишнего слэша в конце).';
    }
  }
  if (st === 429) return 'Слишком много попыток. Подождите минуту.';
  const detail = e.response.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((x: { msg?: string }) => x.msg || JSON.stringify(x)).join('; ');
  }
  return fallback;
}

interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;
  isFired: boolean;
  fireMessage: string;
  needs2FA: boolean;
  tempToken2FA: string;
}

const initialState: AuthState = {
  user: null,
  loading: true,
  error: null,
  isFired: false,
  fireMessage: '',
  needs2FA: false,
  tempToken2FA: '',
};

export const fetchMe = createAsyncThunk('auth/fetchMe', async () => {
  const { data } = await api.get('/auth/me');
  return data;
});

export const login = createAsyncThunk(
  'auth/login',
  async (credentials: { email: string; password: string }, { rejectWithValue }) => {
    try {
      const { data } = await api.post('/auth/login', credentials, { _skipAuthRefresh: true } as any);
      
      // Проверка увольнения
      if (data.token_type === 'fired') {
        return rejectWithValue({ fired: true, message: data.fire_message });
      }

      // 2FA required
      if (data.token_type === '2fa_required') {
        return rejectWithValue({ needs2FA: true, tempToken: data.temp_token });
      }

      const me = await api.get('/auth/me');
      return me.data;
    } catch (err: unknown) {
      return rejectWithValue(formatAuthRequestError(err, 'Ошибка входа'));
    }
  }
);

export const register = createAsyncThunk(
  'auth/register',
  async (data: { name: string; email: string; password: string }, { rejectWithValue }) => {
    try {
      const res = await api.post('/auth/register', data);
      return res.data;
    } catch (err: unknown) {
      return rejectWithValue(formatAuthRequestError(err, 'Ошибка регистрации'));
    }
  }
);

export const verify2FA = createAsyncThunk(
  'auth/verify2FA',
  async (payload: { tempToken: string; code: string }, { rejectWithValue }) => {
    try {
      await api.post('/auth/2fa/verify', { temp_token: payload.tempToken, code: payload.code });
      const me = await api.get('/auth/me');
      return me.data;
    } catch (err: unknown) {
      return rejectWithValue(formatAuthRequestError(err, 'Неверный код 2FA'));
    }
  }
);

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    logout(state) {
      state.user = null;
      state.isFired = false;
      // Токены хранятся в HttpOnly cookies — их очищает сервер через /auth/logout.
    },
    setFired(state, action: PayloadAction<string>) {
      state.isFired = true;
      state.fireMessage = action.payload;
    },
    clearError(state) {
      state.error = null;
    },
    clear2FA(state) {
      state.needs2FA = false;
      state.tempToken2FA = '';
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchMe.pending, (state) => { state.loading = true; })
      .addCase(fetchMe.fulfilled, (state, action) => {
        state.user = action.payload;
        state.loading = false;
      })
      .addCase(fetchMe.rejected, (state) => {
        state.user = null;
        state.loading = false;
      })
      .addCase(login.pending, (state) => { state.loading = true; state.error = null; })
      .addCase(login.fulfilled, (state, action) => {
        state.user = action.payload;
        state.loading = false;
      })
      .addCase(login.rejected, (state, action: any) => {
        state.loading = false;
        if (action.payload?.fired) {
          state.isFired = true;
          state.fireMessage = action.payload.message;
        } else if (action.payload?.needs2FA) {
          state.needs2FA = true;
          state.tempToken2FA = action.payload.tempToken;
        } else {
          state.error = typeof action.payload === 'string' ? action.payload : 'Ошибка входа';
        }
      })
      .addCase(register.pending, (state) => { state.loading = true; state.error = null; })
      .addCase(register.fulfilled, (state) => { state.loading = false; })
      .addCase(register.rejected, (state, action: any) => {
        state.loading = false;
        state.error = typeof action.payload === 'string' ? action.payload : 'Ошибка';
      })
      .addCase(verify2FA.pending, (state) => { state.loading = true; state.error = null; })
      .addCase(verify2FA.fulfilled, (state, action) => {
        state.user = action.payload;
        state.loading = false;
        state.needs2FA = false;
        state.tempToken2FA = '';
      })
      .addCase(verify2FA.rejected, (state, action: any) => {
        state.loading = false;
        state.error = typeof action.payload === 'string' ? action.payload : 'Неверный код';
      });
  },
});

export const { logout, setFired, clearError, clear2FA } = authSlice.actions;
export default authSlice.reducer;
