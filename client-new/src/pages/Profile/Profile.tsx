import { useState, useEffect } from 'react';
import { CheckCircle2, Bot, X, Timer, Activity, Brain, Coins, ShoppingBag, Award, Shield, ShieldOff } from 'lucide-react';
import { useAppSelector, useAppDispatch } from '../../store/hooks';
import { fetchMe } from '../../store/slices/authSlice';
import { t } from '../../i18n';
import api from '../../api/client';
import { gamificationApi, type UserKPI, type ShopPurchase, type Achievement, type EquippedItem } from '../../api/gamification';
import styles from './Profile.module.css';

type Tab = 'personal' | 'kpi' | 'security' | 'purchases';

export default function ProfilePage() {
  const dispatch = useAppDispatch();
  const { user } = useAppSelector(s => s.auth);
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);

  const [tab, setTab] = useState<Tab>('personal');
  const [form, setForm] = useState({ name: '', last_name: '', patronymic: '', no_patronymic: false, city: '', about: '', listening_to: '' });
  const [skills, setSkills] = useState<string[]>([]);
  const [skillInput, setSkillInput] = useState('');
  const [pwForm, setPwForm] = useState({ old_password: '', new_password: '' });
  const [msg, setMsg] = useState('');
  const [pwMsg, setPwMsg] = useState('');
  const [kpi, setKpi] = useState<UserKPI | null>(null);
  const [purchases, setPurchases] = useState<ShopPurchase[]>([]);
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [equipped, setEquipped] = useState<EquippedItem[]>([]);

  useEffect(() => {
    if (user) {
      setForm({
        name: user.name,
        last_name: (user as any).last_name || '',
        patronymic: (user as any).patronymic || '',
        no_patronymic: (user as any).no_patronymic || false,
        city: user.city || '',
        about: user.about || '',
        listening_to: user.listening_to || '',
      });
      setSkills(user.skills || []);
    }
  }, [user]);

  useEffect(() => {
    if (!user) return;
    const loadKpi = async () => {
      try {
        const { data } = await gamificationApi.getMyKPI();
        setKpi(data);
      } catch {
        setKpi(null);
      }
    };
    loadKpi();
    const id = window.setInterval(loadKpi, 60000);
    return () => window.clearInterval(id);
  }, [user]);

  useEffect(() => {
    if (tab === 'purchases') {
      Promise.all([
        gamificationApi.getMyPurchases(),
        gamificationApi.getAchievements(),
        gamificationApi.getEquipped(),
      ])
        .then(([p, a, e]) => {
          setPurchases(p.data);
          setAchievements(a.data);
          setEquipped(e.data);
        })
        .catch(() => {});
    }
  }, [tab]);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.put('/users/profile', { ...form, skills: skills.join(', ') });
    setMsg(lang.profile.saved);
    dispatch(fetchMe());
    setTimeout(() => setMsg(''), 2000);
  };

  const changePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.put('/auth/password', { current_password: pwForm.old_password, new_password: pwForm.new_password });
      setPwMsg(lang.profile.passwordChanged);
      setPwForm({ old_password: '', new_password: '' });
      setTimeout(() => setPwMsg(''), 2000);
    } catch {
      setPwMsg(lang.profile.passwordError);
    }
  };

  const addSkill = () => {
    const s = skillInput.trim();
    if (s && !skills.includes(s)) {
      setSkills([...skills, s]);
      setSkillInput('');
    }
  };

  const removeSkill = (s: string) => {
    setSkills(skills.filter(sk => sk !== s));
  };

  const uploadAvatar = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { alert(lang.notifications.maxFileSize); return; }
    if (!file.type.startsWith('image/')) { alert(lang.notifications.onlyImages); return; }
    const fd = new FormData();
    fd.append('file', file);
    await api.post('/users/me/avatar', fd);
    dispatch(fetchMe());
  };

  if (!user) return null;

  const tabs: { key: Tab; label: string }[] = [
    { key: 'personal', label: lang.profile.tabPersonal },
    { key: 'kpi', label: lang.nav.kpi || 'KPI' },
    { key: 'security', label: lang.profile.tabSecurity },
    { key: 'purchases', label: lang.profile.tabPurchases },
  ];

  return (
    <div className={styles.page}>
      <h1>{lang.profile.title}</h1>

      {/* Avatar + info header */}
      <div className={styles.header}>
        <div className={styles.avatarSection}>
          <div className={styles.avatarWrap}>
            {user.avatar_url ? (
              <img src={user.avatar_url} alt="" className={styles.avatar} />
            ) : (
              <div className={styles.avatarPlaceholder}>{(user.name || '?')[0]}</div>
            )}
            {user.is_online && <span className={styles.onlineDot} title="Online" />}
          </div>
          <label className="btn btn-secondary btn-sm" style={{ cursor: 'pointer' }}>
            {lang.profile.changeAvatar}
            <input type="file" accept="image/*" onChange={uploadAvatar} style={{ display: 'none' }} />
          </label>
        </div>
        <div className={styles.headerInfo}>
          <h2>{form.last_name ? `${form.last_name} ${form.name}${form.no_patronymic ? '' : (form.patronymic ? ` ${form.patronymic}` : '')}` : form.name}</h2>
          <p className={styles.headerMeta}>{user.role === 'admin' ? 'Администратор' : user.role === 'intern' ? 'Стажёр' : 'Сотрудник'}{form.city ? ` · ${form.city}` : ''}</p>
          {user.listening_to && <p className={styles.headerListening}>🎵 {user.listening_to}</p>}
          {user.sphere_roles && user.sphere_roles.length > 0 && (
            <div className={styles.sphereRoles}>
              {user.sphere_roles.map(sr => (
                <span key={`${sr.sphere}-${sr.role_title}`} className="badge badge-primary">{sr.sphere}: {sr.role_title}</span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className={styles.tabs}>
        {tabs.map(t => (
          <button key={t.key} className={`${styles.tab} ${tab === t.key ? styles.tabActive : ''}`} onClick={() => setTab(t.key)}>{t.label}</button>
        ))}
      </div>

      {/* Tab: Personal */}
      {tab === 'personal' && (
        <form onSubmit={save} className={styles.form}>
          <div className={styles.formRow}>
            <div>
              <label>{lang.profile.lastName}</label>
              <input value={form.last_name} onChange={e => setForm({ ...form, last_name: e.target.value })} placeholder="Фамилия" />
            </div>
            <div>
              <label>{lang.profile.name}</label>
              <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
            </div>
            <div>
              <label>{lang.profile.patronymic}</label>
              <input value={form.patronymic} onChange={e => setForm({ ...form, patronymic: e.target.value })} disabled={form.no_patronymic} placeholder="Отчество" />
              <label className={styles.checkLabel}>
                <input type="checkbox" checked={form.no_patronymic} onChange={e => setForm({ ...form, no_patronymic: e.target.checked, patronymic: e.target.checked ? '' : form.patronymic })} style={{ width: 'auto' }} />
                {lang.profile.noPatronymic}
              </label>
            </div>
          </div>
          <div>
            <label>Email</label>
            <input value={user.email} disabled />
          </div>
          <div>
            <label>{lang.profile.city}</label>
            <input value={form.city} onChange={e => setForm({ ...form, city: e.target.value })} />
          </div>
          <div>
            <label>{lang.profile.about}</label>
            <textarea value={form.about} onChange={e => setForm({ ...form, about: e.target.value })} rows={3} />
          </div>
          <div>
            <label>{lang.profile.listeningTo}</label>
            <input value={form.listening_to} onChange={e => setForm({ ...form, listening_to: e.target.value })} />
          </div>
          <div>
            <label>{lang.profile.skills}</label>
            <div className={styles.skillsWrap}>
              {skills.map(s => (
                <span key={s} className="skill-tag" onClick={() => removeSkill(s)}>
                  {s}
                  <X size={12} style={{ marginLeft: 6 }} />
                </span>
              ))}
            </div>
            <div className={styles.skillInput}>
              <input value={skillInput} onChange={e => setSkillInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addSkill(); } }} placeholder={lang.profile.addSkill} />
              <button type="button" className="btn btn-ghost btn-sm" onClick={addSkill}>+</button>
            </div>
          </div>

          {msg && <p className={styles.success}>{msg}</p>}
          <button type="submit" className="btn btn-primary">{lang.common.save}</button>
        </form>
      )}

      {/* Tab: KPI */}
      {tab === 'kpi' && (
        <div className={styles.tabContent}>
          {kpi ? (
            <div className={styles.kpiGrid}>
              <div className={styles.kpiCard}><Timer size={16} /><div><strong>{Math.floor(kpi.total_time_minutes / 60)}ч {kpi.total_time_minutes % 60}м</strong><span>Время на платформе</span></div></div>
              <div className={styles.kpiCard}><Activity size={16} /><div><strong>{kpi.speed_topics_per_day}/день</strong><span>Скорость</span></div></div>
              <div className={styles.kpiCard}><Brain size={16} /><div><strong>{kpi.retention_pct}%</strong><span>Усвоение</span></div></div>
              <div className={styles.kpiCard}><Coins size={16} /><div><strong>{kpi.coins_balance}</strong><span>Agile.Coins</span></div></div>
              <div className={styles.kpiCard}><CheckCircle2 size={16} /><div><strong>{kpi.topics_completed}/{kpi.topics_total}</strong><span>Темы пройдены</span></div></div>
              <div className={styles.kpiCard}><Award size={16} /><div><strong>{kpi.tests_passed}/{kpi.tests_total}</strong><span>Тесты сданы</span></div></div>
            </div>
          ) : (
            <p style={{ color: 'var(--color-text-muted)' }}>{lang.common.noData}</p>
          )}
        </div>
      )}

      {/* Tab: Security */}
      {tab === 'security' && (
        <div className={styles.tabContent}>
          <div className={styles.section}>
            <h3>{lang.profile.changePassword}</h3>
            <form onSubmit={changePassword} className={styles.form} style={{ maxWidth: 400 }}>
              <div>
                <label>{lang.profile.oldPassword}</label>
                <input type="password" value={pwForm.old_password} onChange={e => setPwForm({ ...pwForm, old_password: e.target.value })} required />
              </div>
              <div>
                <label>{lang.profile.newPassword}</label>
                <input type="password" value={pwForm.new_password} onChange={e => setPwForm({ ...pwForm, new_password: e.target.value })} required />
              </div>
              {pwMsg && <p className={styles.success}>{pwMsg}</p>}
              <button type="submit" className="btn btn-primary">{lang.common.save}</button>
            </form>
          </div>

          <div className={styles.section}>
            <h3>Двухфакторная аутентификация (2FA)</h3>
            <TwoFactorSetup />
          </div>

          <div className={styles.section}>
            <h3>Telegram</h3>
            {user.telegram_username ? (
              <div>
                <p style={{ display: 'flex', alignItems: 'center', gap: 8 }}><CheckCircle2 size={18} color="var(--color-success)" /> {lang.notifications.telegramLinked}: <strong>@{user.telegram_username}</strong></p>
                <TelegramUnlink />
              </div>
            ) : (
              <div style={{ maxWidth: 400 }}>
                <p style={{ marginBottom: 8, color: 'var(--color-text-secondary)', fontSize: 13 }}>{lang.notifications.telegramLinkPrompt}</p>
                <TelegramLink />
              </div>
            )}
          </div>

          <div className={styles.section}>
            <h3>{lang.notifications.title}</h3>
            <NotificationSettings />
          </div>

          <div className={styles.section}>
            <h3>Настройки проектов</h3>
            <ProjectSettings />
          </div>
        </div>
      )}

      {/* Tab: Purchases */}
      {tab === 'purchases' && (
        <div className={styles.tabContent}>
          {equipped.length > 0 && (
            <div className={styles.section}>
              <h3>Экипированные предметы</h3>
              <div className={styles.purchaseList}>
                {equipped.map((e) => (
                  <div key={e.purchase_id} className={styles.purchaseCard}>
                    <Award size={18} />
                    <div>
                      <strong>{e.item_title}</strong>
                      <span>{e.category} · {e.rarity}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {purchases.length === 0 ? (
            <p style={{ color: 'var(--color-text-muted)' }}>{lang.profile.noPurchases}</p>
          ) : (
            <div className={styles.purchaseList}>
              {purchases.map(p => (
                <div key={p.id} className={styles.purchaseCard}>
                  <ShoppingBag size={18} />
                  <div>
                    <strong>{p.item_title}</strong>
                    <span>{p.price_paid} Agile.Coins · {new Date(p.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {achievements.length > 0 && (
            <div className={styles.section}>
              <h3>{lang.profile.achievements}</h3>
              <div className={styles.kpiGrid}>
                {achievements.map((a) => (
                  <div key={a.id} className={styles.kpiCard}>
                    <Award size={16} />
                    <div>
                      <strong>{a.title}</strong>
                      <span>{a.rarity} · Lv.{a.level} · {a.progress}/{a.target}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TwoFactorSetup() {
  const { user } = useAppSelector(s => s.auth);
  const dispatch = useAppDispatch();
  const [step, setStep] = useState<'idle' | 'setup' | 'verify'>('idle');
  const [qrCode, setQrCode] = useState('');
  const [secret, setSecret] = useState('');
  const [code, setCode] = useState('');
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const isEnabled = (user as any)?.totp_enabled;

  const startSetup = async () => {
    setLoading(true);
    setMsg('');
    try {
      const { data } = await api.post('/auth/2fa/setup');
      setQrCode(data.qr_code);
      setSecret(data.secret);
      setStep('setup');
    } catch { setMsg('Ошибка при настройке 2FA'); }
    finally { setLoading(false); }
  };

  const enableTotp = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMsg('');
    try {
      await api.post(`/auth/2fa/enable?code=${encodeURIComponent(code)}`);
      setMsg('2FA успешно включена!');
      setStep('idle');
      setCode('');
      dispatch(fetchMe());
    } catch { setMsg('Неверный код. Попробуйте ещё раз.'); }
    finally { setLoading(false); }
  };

  const disableTotp = async () => {
    const disableCode = prompt('Введите код из приложения-аутентификатора для отключения 2FA:');
    if (!disableCode) return;
    setLoading(true);
    setMsg('');
    try {
      await api.post(`/auth/2fa/disable?code=${encodeURIComponent(disableCode)}`);
      setMsg('2FA отключена');
      dispatch(fetchMe());
    } catch { setMsg('Неверный код'); }
    finally { setLoading(false); }
  };

  if (isEnabled) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <p style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--color-success)' }}>
          <Shield size={18} /> 2FA включена
        </p>
        <button className="btn btn-ghost btn-sm" onClick={disableTotp} disabled={loading} style={{ color: 'var(--color-error)', maxWidth: 200 }}>
          <ShieldOff size={14} style={{ marginRight: 6 }} />
          Отключить 2FA
        </button>
        {msg && <p style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>{msg}</p>}
      </div>
    );
  }

  if (step === 'setup') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 360 }}>
        <p style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
          Отсканируйте QR-код в приложении (Google Authenticator, Authy и т.д.) и введите код подтверждения.
        </p>
        {qrCode && <img src={qrCode} alt="QR" style={{ width: 200, height: 200, borderRadius: 8, border: '1px solid var(--color-border)' }} />}
        <details style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
          <summary>Показать секретный ключ</summary>
          <code style={{ padding: '4px 8px', background: 'var(--color-surface-alt)', borderRadius: 4, wordBreak: 'break-all' }}>{secret}</code>
        </details>
        <form onSubmit={enableTotp} style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <label style={{ fontSize: 13 }}>Код из приложения</label>
            <input value={code} onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} placeholder="000000" required maxLength={6} style={{ width: '100%' }} />
          </div>
          <button className="btn btn-primary btn-sm" type="submit" disabled={loading || code.length !== 6}>Подтвердить</button>
        </form>
        {msg && <p style={{ fontSize: 13, color: 'var(--color-error)' }}>{msg}</p>}
        <button className="btn btn-ghost btn-sm" onClick={() => { setStep('idle'); setMsg(''); }} style={{ maxWidth: 100 }}>Отмена</button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <p style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
        Защитите аккаунт с помощью одноразовых кодов из приложения-аутентификатора.
      </p>
      <button className="btn btn-secondary btn-sm" onClick={startSetup} disabled={loading} style={{ maxWidth: 200 }}>
        <Shield size={14} style={{ marginRight: 6 }} />
        Настроить 2FA
      </button>
      {msg && <p style={{ fontSize: 13, color: 'var(--color-error)' }}>{msg}</p>}
    </div>
  );
}

function TelegramLink() {
  const [code, setCode] = useState('');
  const [botUrl, setBotUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [linked, setLinked] = useState(false);
  const dispatch = useAppDispatch();
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);

  const getCode = async () => {
    setLoading(true);
    try {
      const { data } = await api.post('/users/telegram-link');
      setCode(data.code);
      if (data.bot_url) setBotUrl(data.bot_url);
    } catch {} finally { setLoading(false); }
  };

  const confirmLink = async () => {
    setLoading(true);
    try {
      const { data } = await api.post('/users/telegram-confirm');
      if (data.linked) {
        setLinked(true);
        dispatch(fetchMe());
      }
    } catch {} finally { setLoading(false); }
  };

  if (linked) return <p style={{ color: 'var(--color-success)', display: 'flex', alignItems: 'center', gap: 6 }}><CheckCircle2 size={16} /> {lang.notifications.telegramSuccess}</p>;
  if (code) return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {botUrl ? (
        <a href={botUrl} target="_blank" rel="noopener noreferrer" className="btn btn-secondary btn-sm" style={{ textAlign: 'center' }}>
          <Bot size={16} style={{ marginRight: 6 }} />
          {lang.notifications.openBot}
        </a>
      ) : (
        <span>{lang.notifications.code}: <code style={{ padding: '2px 6px', background: 'var(--color-surface-alt)', borderRadius: 4 }}>{code}</code></span>
      )}
      <p style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>{lang.notifications.afterBotStep}</p>
      <button className="btn btn-primary btn-sm" onClick={confirmLink} disabled={loading}>{lang.notifications.confirmCode}</button>
    </div>
  );
  return <button className="btn btn-secondary btn-sm" onClick={getCode} disabled={loading}>{lang.notifications.getLinkCode}</button>;
}

function TelegramUnlink() {
  const [loading, setLoading] = useState(false);
  const dispatch = useAppDispatch();
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);

  const unlink = async () => {
    if (!confirm(lang.notifications.unlinkConfirm)) return;
    setLoading(true);
    try {
      await api.delete('/users/telegram-link');
      dispatch(fetchMe());
    } catch {} finally { setLoading(false); }
  };

  return (
    <button className="btn btn-ghost btn-sm" onClick={unlink} disabled={loading} style={{ marginTop: 8, color: 'var(--color-error)' }}>
      {lang.notifications.unlinkTelegram}
    </button>
  );
}

function NotificationSettings() {
  const { user } = useAppSelector(s => s.auth);
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);
  const dispatch = useAppDispatch();
  const [settings, setSettings] = useState({ notify_tasks: user?.notify_tasks ?? true, notify_messages: user?.notify_messages ?? true, notify_events: user?.notify_events ?? true });

  const toggle = async (field: string, value: boolean) => {
    const updated = { ...settings, [field]: value };
    setSettings(updated);
    await api.put('/users/profile', updated);
    dispatch(fetchMe());
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 300 }}>
      {([['notify_tasks', lang.notifications.tasks], ['notify_messages', lang.notifications.messages], ['notify_events', lang.notifications.events]] as const).map(([key, label]) => (
        <label key={key} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
          <input type="checkbox" checked={(settings as any)[key]} onChange={e => toggle(key, e.target.checked)} style={{ width: 'auto' }} />
          {label}
        </label>
      ))}
    </div>
  );
}

function ProjectSettings() {
  const { user } = useAppSelector(s => s.auth);
  const dispatch = useAppDispatch();
  const [showIterations, setShowIterations] = useState(user?.show_iterations ?? false);

  const toggle = async (value: boolean) => {
    setShowIterations(value);
    await api.put('/users/profile', { show_iterations: value });
    dispatch(fetchMe());
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 400 }}>
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
        <input type="checkbox" checked={showIterations} onChange={e => toggle(e.target.checked)} style={{ width: 'auto' }} />
        Показывать итерации (спринты) в проектах
      </label>
      <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', margin: 0 }}>
        Включите, чтобы видеть панель итераций и переключаться между спринтами внутри проекта.
      </p>
    </div>
  );
}
