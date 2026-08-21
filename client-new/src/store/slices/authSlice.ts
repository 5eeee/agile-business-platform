import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import api, { resetAuthRedirectGate } from '../../api/client';
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

function normalizeUser(raw: User): User {
  const user = { ...raw };
  const email = String(user.email || '').trim().toLowerCase();

  // Compatibility for the first production owner created by the legacy seed.
  // The backend performs the same normalization after its rolling update.
  if (email === 'admin@agile.com') {
    user.name = 'Алексей';
    user.last_name = 'Девятов';
    user.role = 'owner';
  }

  if (typeof window !== 'undefined') {
    const localAvatar = window.localStorage.getItem(`agile.avatar.${user.id}`);
    if (localAvatar) user.avatar_url = localAvatar;
  }
  return user;
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
  resetAuthRedirectGate();
  return normalizeUser(data);
});

export const login = createAsyncThunk(
  'auth/login',
  async (credentials: { email: string; password: string }, { rejectWithValue }) => {
    try {
      let loginResponse;
      try {
        loginResponse = await api.post('/auth/login', credentials, { _skipAuthRefresh: true } as any);
      } catch (initialError: unknown) {
        const status = (initialError as { response?: { status?: number } })?.response?.status;
        // The production owner used the legacy login "agilebusiness" before
        // accounts were standardized on email. Try the canonical owner email
        // only after the original identifier is rejected.
        if (status === 401 && credentials.email.trim().toLowerCase() === 'agilebusiness') {
          loginResponse = await api.post(
            '/auth/login',
            { ...credentials, email: 'admin@agile.com' },
            { _skipAuthRefresh: true } as any
          );
        } else {
          throw initialError;
        }
      }
      const { data } = loginResponse;
      
      // Проверка увольнения
      if (data.token_type === 'fired') {
        return rejectWithValue({ fired: true, message: data.fire_message });
      }

      // 2FA required
      if (data.token_type === '2fa_required') {
        return rejectWithValue({ needs2FA: true, tempToken: data.temp_token });
      }

      const me = await api.get('/auth/me');
      resetAuthRedirectGate();
      return normalizeUser(me.data);
    } catch (err: unknown) {
      return rejectWithValue(formatAuthRequestError(err, 'Ошибка входа'));
    }
  }
);

export const register = createAsyncThunk(
  'auth/register',
  async (data: { name: string; email: string; password: string }, { rejectWithValue }) => {
    try {
      const res = await api.post('/auth/register', data, { _skipAuthRefresh: true } as any);
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
      await api.post(
        '/auth/2fa/verify',
        { temp_token: payload.tempToken, code: payload.code },
        { _skipAuthRefresh: true } as any
      );
      const me = await api.get('/auth/me');
      resetAuthRedirectGate();
      return normalizeUser(me.data);
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
    setUserAvatar(state, action: PayloadAction<string>) {
      if (state.user) state.user.avatar_url = action.payload;
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

export const { logout, setFired, clearError, clear2FA, setUserAvatar } = authSlice.actions;
export default authSlice.reducer;
