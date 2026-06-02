import { useEffect, useState } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAppSelector, useAppDispatch } from '../../store/hooks';
import { login, register, clearError, verify2FA, clear2FA } from '../../store/slices/authSlice';
import { t } from '../../i18n';
import api from '../../api/client';
import styles from './Login.module.css';

export default function LoginPage() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const location = useLocation();
  const { loading, error, needs2FA, tempToken2FA } = useAppSelector(s => s.auth);
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);

  const mode = new URLSearchParams(location.search).get('mode');
  const storedMode = typeof window !== 'undefined' ? sessionStorage.getItem('login_mode') : null;
  const effectiveMode = mode || storedMode;

  useEffect(() => {
    // Храним только на короткое время: если query пропал (redirect), всё равно покажем нужную форму один раз.
    if (mode === 'register' || mode === 'forgot') {
      sessionStorage.setItem('login_mode', mode);
    } else {
      sessionStorage.removeItem('login_mode');
    }
  }, [mode]);

  const [isRegister, setIsRegister] = useState(() => effectiveMode === 'register');
  const [showForgot, setShowForgot] = useState(() => effectiveMode === 'forgot');
  /** email — запрос ссылки; token — ввод токена вручную */
  const [forgotPhase, setForgotPhase] = useState<'email' | 'token'>('email');
  const [form, setForm] = useState({ name: '', email: '', password: '' });
  const [registerSuccess, setRegisterSuccess] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotMsg, setForgotMsg] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [resetMsg, setResetMsg] = useState('');
  const [resetPasswordOk, setResetPasswordOk] = useState(false);
  const [totpCode, setTotpCode] = useState('');

  // При SPA-навигации между `/login?...` React Router переиспользует компонент, поэтому
  // локальное состояние нужно синхронизировать с `mode` / sessionStorage.
  useEffect(() => {
    setIsRegister(effectiveMode === 'register');
    setShowForgot(effectiveMode === 'forgot');
    if (effectiveMode !== 'forgot') {
      setForgotPhase('email');
      setForgotEmail('');
      setForgotMsg('');
      setResetToken('');
      setNewPassword('');
      setResetMsg('');
      setResetPasswordOk(false);
    }
  }, [effectiveMode]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    dispatch(clearError());

    if (isRegister) {
      const result = await dispatch(register(form));
      if (register.fulfilled.match(result)) {
        const payload = result.payload as { immediate_login?: boolean };
        if (payload?.immediate_login) {
          const loginResult = await dispatch(login({ email: form.email, password: form.password }));
          if (login.fulfilled.match(loginResult)) {
            navigate('/');
            return;
          }
          return;
        }
        setRegisterSuccess(true);
      }
    } else {
      const result = await dispatch(login({ email: form.email, password: form.password }));
      if (login.fulfilled.match(result)) {
        navigate('/');
      }
    }
  };

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/auth/forgot-password', { email: forgotEmail });
      setForgotMsg(lang.auth.resetLinkSent || 'Ссылка для сброса пароля отправлена на email');
    } catch {
      setForgotMsg(lang.auth.resetLinkSent || 'Ссылка для сброса пароля отправлена на email');
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/auth/reset-password', { token: resetToken, new_password: newPassword });
      setResetPasswordOk(true);
      setResetMsg(lang.auth.passwordResetSuccess || 'Пароль успешно сброшен');
      setTimeout(() => {
        setShowForgot(false);
        setForgotPhase('email');
        setResetMsg('');
        setResetToken('');
        setNewPassword('');
        setResetPasswordOk(false);
      }, 2000);
    } catch {
      setResetPasswordOk(false);
      setResetMsg(lang.auth.resetError || 'Неверный или истёкший токен');
    }
  };

  const handle2FASubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const result = await dispatch(verify2FA({ tempToken: tempToken2FA, code: totpCode }));
    if (verify2FA.fulfilled.match(result)) {
      navigate('/');
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.logo}>
          <span className={styles.logoIcon}>A</span>
          <h1>Agile.Workspace</h1>
        </div>

        {needs2FA ? (
          <form onSubmit={handle2FASubmit} className={styles.form}>
            <h2>Двухфакторная аутентификация</h2>
            <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', marginBottom: 8 }}>
              Введите код из приложения-аутентификатора
            </p>
            {error && <div className={styles.error}>{error}</div>}
            <input
              type="text"
              inputMode="numeric"
              placeholder="000000"
              value={totpCode}
              onChange={e => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              required
              maxLength={6}
              autoFocus
            />
            <button className="btn btn-primary" type="submit" disabled={loading || totpCode.length !== 6}>
              {loading ? lang.common.loading : 'Подтвердить'}
            </button>
            <p className={styles.toggle}>
              <a href="#" onClick={e => { e.preventDefault(); dispatch(clear2FA()); dispatch(clearError()); setTotpCode(''); }}>
                {lang.auth.login}
              </a>
            </p>
          </form>
        ) : registerSuccess ? (
          <div className={styles.successMsg}>
            <p style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <CheckCircle2 size={18} /> {lang.auth.pendingMessage}
            </p>
            <button className="btn btn-primary" onClick={() => { setIsRegister(false); setRegisterSuccess(false); }}>
              {lang.auth.login}
            </button>
          </div>
        ) : showForgot ? (
          <div className={styles.form}>
            <h2>{lang.auth.forgotPassword}</h2>
            {forgotPhase === 'email' ? (
              <>
                <form onSubmit={handleForgotPassword}>
                  <input type="email" placeholder={lang.auth.email} value={forgotEmail} onChange={e => setForgotEmail(e.target.value)} required style={{ width: '100%', marginBottom: 12 }} />
                  <button className="btn btn-primary" type="submit" style={{ width: '100%' }}>{lang.auth.resetPassword || 'Сбросить пароль'}</button>
                </form>
                {forgotMsg && <p style={{ color: 'var(--color-success)', marginTop: 10, fontSize: 13 }}>{forgotMsg}</p>}
                <p style={{ marginTop: 12, fontSize: 13 }}>
                  {lang.loginExtra.hasToken}{' '}
                  <a href="#" onClick={e => { e.preventDefault(); setForgotPhase('token'); setResetToken(''); }}>{lang.loginExtra.enterToken}</a>
                </p>
              </>
            ) : (
              <form onSubmit={handleResetPassword}>
                <input placeholder={lang.loginExtra.tokenPlaceholder} value={resetToken} onChange={e => setResetToken(e.target.value)} required style={{ width: '100%', marginBottom: 10 }} />
                <input type="password" placeholder={lang.auth.password} value={newPassword} onChange={e => setNewPassword(e.target.value)} required minLength={6} style={{ width: '100%', marginBottom: 12 }} />
                <button className="btn btn-primary" type="submit" style={{ width: '100%' }}>{lang.auth.resetPassword || 'Установить пароль'}</button>
                {resetMsg && (
                  <p style={{ color: resetPasswordOk ? 'var(--color-success)' : 'var(--color-error)', marginTop: 10, fontSize: 13 }}>{resetMsg}</p>
                )}
              </form>
            )}
            <p className={styles.toggle}>
              <a href="#" onClick={e => { e.preventDefault(); setShowForgot(false); setForgotPhase('email'); setResetToken(''); setNewPassword(''); setForgotMsg(''); setResetMsg(''); setResetPasswordOk(false); }}>{lang.auth.login}</a>
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className={styles.form}>
            <h2>{isRegister ? lang.auth.register : lang.auth.login}</h2>

            {error && <div className={styles.error}>{error}</div>}

            {isRegister && (
              <input
                type="text"
                placeholder={lang.auth.name}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
                minLength={2}
              />
            )}

            <input
              type="email"
              placeholder={lang.auth.email}
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
            />

            <input
              type="password"
              placeholder={lang.auth.password}
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required
              minLength={6}
            />

            <button className="btn btn-primary" type="submit" disabled={loading}>
              {loading ? lang.common.loading : (isRegister ? lang.auth.registerBtn : lang.auth.loginBtn)}
            </button>

            {!isRegister && (
              <p style={{ textAlign: 'center', fontSize: 13, marginTop: 8 }}>
                <a href="#" onClick={e => { e.preventDefault(); setShowForgot(true); setForgotPhase('email'); setResetToken(''); setForgotMsg(''); setResetMsg(''); setResetPasswordOk(false); }}>{lang.auth.forgotPassword}</a>
              </p>
            )}

            <p className={styles.toggle}>
              {isRegister ? lang.auth.hasAccount : lang.auth.noAccount}{' '}
              <a href="#" onClick={(e) => { e.preventDefault(); setIsRegister(!isRegister); dispatch(clearError()); }}>
                {isRegister ? lang.auth.login : lang.auth.register}
              </a>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
