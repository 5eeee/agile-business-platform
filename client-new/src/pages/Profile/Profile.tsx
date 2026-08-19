import { useState, useEffect } from 'react';
import {
  Award,
  BadgeCheck,
  BellRing,
  Bot,
  CalendarCheck2,
  Camera,
  CheckCircle2,
  Clock4,
  Copy,
  Eye,
  Gauge,
  Headphones,
  KeyRound,
  Lightbulb,
  LoaderCircle,
  MapPin,
  MessageSquareHeart,
  Shield,
  ShieldCheck,
  ShieldOff,
  Sparkles,
  Timer,
  UserRound,
  X,
} from 'lucide-react';
import { useAppSelector, useAppDispatch } from '../../store/hooks';
import { fetchMe, setUserAvatar } from '../../store/slices/authSlice';
import { t } from '../../i18n';
import api from '../../api/client';
import { gamificationApi, type UserKPI } from '../../api/gamification';
import AttendanceCard from './AttendanceCard';
import styles from './Profile.module.css';

type Tab = 'personal' | 'kpi' | 'security';

async function makeLocalAvatar(file: File): Promise<string> {
  const objectUrl = URL.createObjectURL(file);
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error('Не удалось прочитать изображение'));
      img.src = objectUrl;
    });
    const maxSide = 512;
    const scale = Math.min(1, maxSide / Math.max(image.naturalWidth, image.naturalHeight));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
    const context = canvas.getContext('2d');
    if (!context) throw new Error('Не удалось обработать изображение');
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.86);
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

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
  const [avatarUploading, setAvatarUploading] = useState(false);
  const [avatarMessage, setAvatarMessage] = useState('');
  const [avatarVersion, setAvatarVersion] = useState(0);

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



  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.put('/users/profile', { ...form, skills: skills.join(', ') });
      await dispatch(fetchMe()).unwrap();
      setMsg(lang.profile.saved);
    } catch {
      setMsg('Не удалось сохранить профиль');
    }
    setTimeout(() => setMsg(''), 2500);
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
    if (!user) return;
    const userId = user.id;
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { window.dispatchEvent(new CustomEvent('api-error', { detail: lang.notifications.maxFileSize })); e.target.value = ''; return; }
    if (!file.type.startsWith('image/')) { window.dispatchEvent(new CustomEvent('api-error', { detail: lang.notifications.onlyImages })); e.target.value = ''; return; }
    const fd = new FormData();
    fd.append('file', file);
    setAvatarUploading(true);
    setAvatarMessage('');
    try {
      await api.post('/users/me/avatar', fd);
      await dispatch(fetchMe()).unwrap();
      setAvatarVersion(Date.now());
      setAvatarMessage('Фотография сохранена');
    } catch (error: unknown) {
      const response = (error as { response?: { status?: number; data?: { detail?: string } } })?.response;
      if (response?.status === 404 || response?.status === 405) {
        try {
          const localAvatar = await makeLocalAvatar(file);
          window.localStorage.setItem(`agile.avatar.${userId}`, localAvatar);
          dispatch(setUserAvatar(localAvatar));
          setAvatarVersion(Date.now());
          setAvatarMessage('Фотография сохранена');
        } catch {
          setAvatarMessage('Не удалось сохранить фотографию');
        }
      } else {
        const detail = response?.data?.detail;
        setAvatarMessage(typeof detail === 'string' ? detail : 'Не удалось загрузить фотографию');
      }
    } finally {
      setAvatarUploading(false);
      e.target.value = '';
    }
  };

  if (!user) return null;

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: 'personal', label: lang.profile.tabPersonal, icon: <UserRound size={16} aria-hidden /> },
    { key: 'kpi', label: 'Мои показатели', icon: <Gauge size={16} aria-hidden /> },
    { key: 'security', label: lang.profile.tabSecurity, icon: <ShieldCheck size={16} aria-hidden /> },
  ];

  const avatarSrc = user.avatar_url
    ? `${user.avatar_url}${user.avatar_url.includes('?') ? '&' : '?'}v=${avatarVersion}`
    : '';

  return (
    <div className={styles.page}>
      <h1>{lang.profile.title}</h1>

      <AttendanceCard />

      {/* Avatar + info header */}
      <div className={styles.header}>
        <div className={styles.avatarSection}>
          <div className={styles.avatarWrap}>
            {avatarSrc ? (
              <img src={avatarSrc} alt={`Фото: ${user.name}`} className={styles.avatar} />
            ) : (
              <div className={styles.avatarPlaceholder}>{(user.name || '?')[0]}</div>
            )}
            {user.is_online && <span className={styles.onlineDot} title="Online" />}
          </div>
          <label className={`${styles.avatarButton} ${avatarUploading ? styles.avatarButtonLoading : ''}`} aria-busy={avatarUploading}>
            {avatarUploading ? <LoaderCircle size={16} className={styles.spinner} aria-hidden /> : <Camera size={16} aria-hidden />}
            {avatarUploading ? 'Загрузка…' : lang.profile.changeAvatar}
            <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" onChange={uploadAvatar} disabled={avatarUploading} style={{ display: 'none' }} />
          </label>
          {avatarMessage && <span className={styles.avatarMessage} role="status">{avatarMessage}</span>}
        </div>
        <div className={styles.headerInfo}>
          <span className={styles.profileEyebrow}>Профиль сотрудника</span>
          <h2>{form.last_name ? `${form.last_name} ${form.name}${form.no_patronymic ? '' : (form.patronymic ? ` ${form.patronymic}` : '')}` : form.name}</h2>
          <div className={styles.headerMeta}>
            <span className={styles.roleBadge}><BadgeCheck size={14} aria-hidden />{user.role === 'owner' ? 'Владелец · супер-администратор' : user.role === 'admin' ? 'Администратор' : user.role === 'deputy_owner' ? 'Заместитель владельца' : user.role === 'intern' ? 'Стажёр' : 'Сотрудник'}</span>
            {form.city && <span><MapPin size={14} aria-hidden />{form.city}</span>}
          </div>
          {user.listening_to && <p className={styles.headerListening}><Headphones size={15} aria-hidden /> {user.listening_to}</p>}
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
      <div className={styles.tabs} role="tablist" aria-label="Разделы профиля">
        {tabs.map(t => (
          <button type="button" role="tab" aria-selected={tab === t.key} key={t.key} className={`${styles.tab} ${tab === t.key ? styles.tabActive : ''}`} onClick={() => setTab(t.key)}>{t.icon}{t.label}</button>
        ))}
      </div>

      {/* Tab: Personal */}
      {tab === 'personal' && (
        <form onSubmit={save} className={`${styles.form} ${styles.profileForm}`}>
          <div className={styles.formIntro}>
            <span><UserRound size={20} aria-hidden /></span>
            <div>
              <h3>Личные данные</h3>
              <p>Эти сведения используются в задачах, отчётах и кабинете руководителя.</p>
            </div>
          </div>
          <div className={styles.formRow}>
            <div className={styles.fieldGroup}>
              <label>{lang.profile.lastName}</label>
              <input value={form.last_name} onChange={e => setForm({ ...form, last_name: e.target.value })} placeholder="Фамилия" />
            </div>
            <div className={styles.fieldGroup}>
              <label>{lang.profile.name}</label>
              <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Имя" required />
            </div>
            <div className={styles.fieldGroup}>
              <label>{lang.profile.patronymic}</label>
              <input value={form.patronymic} onChange={e => setForm({ ...form, patronymic: e.target.value })} disabled={form.no_patronymic} placeholder="Отчество" />
              <label className={styles.checkLabel}>
                <input type="checkbox" checked={form.no_patronymic} onChange={e => setForm({ ...form, no_patronymic: e.target.checked, patronymic: e.target.checked ? '' : form.patronymic })} style={{ width: 'auto' }} />
                {lang.profile.noPatronymic}
              </label>
            </div>
          </div>
          <div className={styles.profileFormGrid}>
            <div className={styles.fieldGroup}>
              <label>Email</label>
              <input value={user.email} disabled />
              <small>Адрес входа меняется только администратором.</small>
            </div>
            <div className={styles.fieldGroup}>
              <label>{lang.profile.city}</label>
              <input value={form.city} onChange={e => setForm({ ...form, city: e.target.value })} placeholder="Город" />
            </div>
            <div className={styles.fieldGroup}>
              <label>{lang.profile.listeningTo}</label>
              <input value={form.listening_to} onChange={e => setForm({ ...form, listening_to: e.target.value })} placeholder="Трек, подкаст или плейлист" />
            </div>
            <div className={`${styles.fieldGroup} ${styles.aboutField}`}>
              <label>{lang.profile.about}</label>
              <textarea value={form.about} onChange={e => setForm({ ...form, about: e.target.value })} rows={4} placeholder="Коротко о роли, опыте и рабочих интересах" />
            </div>
          </div>
          <div className={`${styles.fieldGroup} ${styles.skillsField}`}>
            <label>{lang.profile.skills}</label>
            <div className={styles.skillsWrap}>
              {skills.map(s => (
                <button type="button" key={s} className="skill-tag" onClick={() => removeSkill(s)} aria-label={`Удалить навык ${s}`}>
                  {s}
                  <X size={12} style={{ marginLeft: 6 }} />
                </button>
              ))}
            </div>
            <div className={styles.skillInput}>
              <input value={skillInput} onChange={e => setSkillInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addSkill(); } }} placeholder={lang.profile.addSkill} />
              <button type="button" className="btn btn-secondary btn-sm" onClick={addSkill}>Добавить</button>
            </div>
          </div>

          <div className={styles.formFooter}>
            {msg ? <p className={styles.success} role="status">{msg}</p> : <p>Изменения сохраняются в защищённом профиле.</p>}
            <button type="submit" className="btn btn-primary">{lang.common.save}</button>
          </div>
        </form>
      )}

      {/* Tab: KPI */}
      {tab === 'kpi' && (
        <div className={styles.tabContent}>
          {kpi ? (
            <div className={styles.kpiGrid}>
              {[
                { key: 'deadlines', title: 'Соблюдение сроков', description: 'Доля задач, завершённых до дедлайна', value: kpi.kpi1_deadlines, icon: <CalendarCheck2 size={19} /> },
                { key: 'punctuality', title: 'Рабочая пунктуальность', description: 'Своевременное начало и завершение рабочего дня', value: kpi.kpi2_punctuality, icon: <Clock4 size={19} /> },
                { key: 'initiative', title: 'Полезные инициативы', description: 'Предложения, принятые командой в работу', value: kpi.kpi3_initiative, icon: <Lightbulb size={19} /> },
                { key: 'overtime', title: 'Дополнительная нагрузка', description: 'Вклад сверх плановой рабочей нагрузки', value: kpi.kpi4_overtime, icon: <Timer size={19} /> },
                { key: 'quality', title: 'Качество выполнения', description: 'Результат проверки завершённых задач', value: kpi.kpi5_quality, icon: <BadgeCheck size={19} /> },
                { key: 'attention', title: 'Внимательность', description: 'Точность работы и отсутствие повторных ошибок', value: kpi.kpi8_attentiveness, icon: <Eye size={19} /> },
                { key: 'bonus', title: 'Бонус за эффективность', description: 'Дополнительный балл за устойчивый результат', value: kpi.kpi9_bonus, icon: <Sparkles size={19} /> },
                { key: 'responsibility', title: 'Ответственность', description: 'Надёжность выполнения принятых обязательств', value: kpi.kpi10_responsibility, icon: <Award size={19} /> },
                { key: 'customer', title: 'Оценка заказчика', description: 'Удовлетворённость результатом командной работы', value: kpi.kpi_customer_satisfaction, icon: <MessageSquareHeart size={19} /> },
              ].map(item => (
                <div className={styles.kpiCard} key={item.key}>
                  <span className={styles.kpiIcon} aria-hidden>{item.icon}</span>
                  <div className={styles.kpiBody}>
                    <strong>{item.value === null ? '—' : `${Math.round(Number(item.value))}%`}</strong>
                    <span className={styles.kpiTitle}>{item.title}</span>
                    <small>{item.description}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ color: 'var(--color-text-muted)' }}>{lang.common.noData}</p>
          )}
        </div>
      )}

      {/* Tab: Security */}
      {tab === 'security' && (
        <div className={`${styles.tabContent} ${styles.securityGrid}`}>
          <div className={styles.section}>
            <div className={styles.sectionTitle}><KeyRound size={18} aria-hidden /><div><h3>{lang.profile.changePassword}</h3><p>Используйте отдельный пароль длиной не менее 8 символов.</p></div></div>
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
            <div className={styles.sectionTitle}><ShieldCheck size={18} aria-hidden /><div><h3>Двухфакторная защита</h3><p>Подтверждайте вход одноразовым шестизначным кодом.</p></div></div>
            <TwoFactorSetup />
          </div>

          <div className={styles.section}>
            <div className={styles.sectionTitle}><Bot size={18} aria-hidden /><div><h3>Telegram-бот</h3><p>Срочные уведомления и напоминания прямо в Telegram.</p></div></div>
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
            <div className={styles.sectionTitle}><BellRing size={18} aria-hidden /><div><h3>{lang.notifications.title}</h3><p>Выберите события, о которых нужно сообщать.</p></div></div>
            <NotificationSettings />
          </div>
        </div>
      )}


    </div>
  );
}

function TwoFactorSetup() {
  const { user } = useAppSelector(s => s.auth);
  const dispatch = useAppDispatch();
  const [step, setStep] = useState<'idle' | 'setup' | 'disable'>('idle');
  const [qrCode, setQrCode] = useState('');
  const [secret, setSecret] = useState('');
  const [code, setCode] = useState('');
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(false);
  const isEnabled = (user as any)?.totp_enabled;

  const resetFlow = () => {
    setStep('idle');
    setCode('');
    setMsg('');
  };

  const startSetup = async () => {
    setLoading(true);
    setMsg('');
    try {
      const { data } = await api.post('/auth/2fa/setup');
      setQrCode(data.qr_code);
      setSecret(data.secret);
      setStep('setup');
    } catch {
      setMsg('Не удалось начать настройку. Обновите страницу и попробуйте снова.');
    } finally {
      setLoading(false);
    }
  };

  const enableTotp = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMsg('');
    try {
      await api.post(`/auth/2fa/enable?code=${encodeURIComponent(code)}`);
      setMsg('Двухфакторная защита включена');
      setStep('idle');
      setCode('');
      await dispatch(fetchMe()).unwrap();
    } catch {
      setMsg('Код не подошёл. Дождитесь нового кода в приложении и повторите.');
    } finally {
      setLoading(false);
    }
  };

  const disableTotp = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMsg('');
    try {
      await api.post(`/auth/2fa/disable?code=${encodeURIComponent(code)}`);
      setMsg('Двухфакторная защита отключена');
      setCode('');
      setStep('idle');
      await dispatch(fetchMe()).unwrap();
    } catch {
      setMsg('Неверный код из приложения-аутентификатора');
    } finally {
      setLoading(false);
    }
  };

  const copySecret = async () => {
    try {
      await navigator.clipboard.writeText(secret);
      setMsg('Секретный ключ скопирован');
    } catch {
      setMsg('Не удалось скопировать ключ автоматически');
    }
  };

  if (isEnabled) {
    return (
      <div className={styles.twoFactor}>
        <div className={styles.securityStatusSuccess}>
          <span><ShieldCheck size={19} aria-hidden /></span>
          <div><strong>Защита включена</strong><p>При следующем входе потребуется код из приложения-аутентификатора.</p></div>
        </div>
        {step === 'disable' ? (
          <form className={styles.codeForm} onSubmit={disableTotp}>
            <label htmlFor="disable-2fa-code">Код для подтверждения отключения</label>
            <div>
              <input id="disable-2fa-code" inputMode="numeric" autoComplete="one-time-code" value={code} onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} placeholder="000 000" required maxLength={6} />
              <button type="submit" className="btn btn-danger" disabled={loading || code.length !== 6}>Отключить</button>
            </div>
            <button type="button" className={styles.textButton} onClick={resetFlow}>Отмена</button>
          </form>
        ) : (
          <button type="button" className={styles.dangerLink} onClick={() => { setStep('disable'); setCode(''); setMsg(''); }} disabled={loading}>
            <ShieldOff size={15} aria-hidden /> Отключить двухфакторную защиту
          </button>
        )}
        {msg && <p className={styles.feedback} role="status">{msg}</p>}
      </div>
    );
  }

  if (step === 'setup') {
    return (
      <div className={styles.twoFactor}>
        <ol className={styles.setupSteps}>
          <li><strong>Установите приложение</strong><span>Google Authenticator, Microsoft Authenticator, 1Password или аналог.</span></li>
          <li><strong>Отсканируйте QR-код</strong><span>Секрет остаётся внутри вашего аккаунта и приложения.</span></li>
          <li><strong>Введите код</strong><span>Так мы проверим, что приложение подключено правильно.</span></li>
        </ol>
        <div className={styles.qrPanel}>
          {qrCode && <img src={qrCode} alt="QR-код для подключения двухфакторной аутентификации" />}
          <div>
            <strong>Не получается отсканировать?</strong>
            <p>Добавьте секретный ключ вручную.</p>
            <div className={styles.secretRow}><code>{secret}</code><button type="button" onClick={copySecret} aria-label="Скопировать секретный ключ"><Copy size={16} /></button></div>
          </div>
        </div>
        <form onSubmit={enableTotp} className={styles.codeForm}>
          <label htmlFor="enable-2fa-code">Шестизначный код из приложения</label>
          <div>
            <input id="enable-2fa-code" inputMode="numeric" autoComplete="one-time-code" value={code} onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} placeholder="000 000" required maxLength={6} />
            <button className="btn btn-primary" type="submit" disabled={loading || code.length !== 6}>Включить защиту</button>
          </div>
        </form>
        {msg && <p className={styles.feedback} role="status">{msg}</p>}
        <button type="button" className={styles.textButton} onClick={resetFlow}>Отменить настройку</button>
      </div>
    );
  }

  return (
    <div className={styles.twoFactor}>
      <div className={styles.securityStatus}>
        <span><Shield size={19} aria-hidden /></span>
        <div><strong>Защита пока выключена</strong><p>Пароля недостаточно, если он попадёт к постороннему.</p></div>
      </div>
      <button type="button" className="btn btn-secondary" onClick={startSetup} disabled={loading}>
        <Shield size={16} aria-hidden /> {loading ? 'Подготавливаем…' : 'Подключить приложение-аутентификатор'}
      </button>
      {msg && <p className={styles.feedback} role="status">{msg}</p>}
    </div>
  );
}

function TelegramLink() {
  const [code, setCode] = useState('');
  const [botUrl, setBotUrl] = useState('');
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [linked, setLinked] = useState(false);
  const dispatch = useAppDispatch();
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);

  const getCode = async () => {
    setLoading(true);
    setMessage('');
    try {
      const { data } = await api.post('/users/telegram-link');
      setConfigured(data.configured !== false);
      if (data.configured === false) {
        setMessage(data.detail || 'Telegram-бот ещё не подключён администратором');
        return;
      }
      setCode(data.code || '');
      if (data.bot_url) setBotUrl(data.bot_url);
    } catch {
      setMessage('Не удалось подготовить привязку Telegram');
    } finally { setLoading(false); }
  };

  const confirmLink = async () => {
    setLoading(true);
    setMessage('');
    try {
      const { data } = await api.post('/users/telegram-confirm');
      if (data.linked) {
        setLinked(true);
        dispatch(fetchMe());
      } else {
        setMessage('Бот ещё не получил команду. Откройте Telegram, нажмите Start и повторите проверку.');
      }
    } catch {
      setMessage('Не удалось проверить привязку');
    } finally { setLoading(false); }
  };

  const copyLinkCode = async () => {
    try {
      await navigator.clipboard.writeText(`/start ${code}`);
      setMessage('Команда скопирована');
    } catch {
      setMessage('Не удалось скопировать команду');
    }
  };

  if (linked) return <p className={styles.integrationSuccess}><CheckCircle2 size={17} /> {lang.notifications.telegramSuccess}</p>;
  if (configured === false) return (
    <div className={styles.integrationUnavailable} role="status">
      <Bot size={20} aria-hidden />
      <div><strong>Требуется подключение бота</strong><p>{message}</p><small>Администратору нужно задать TELEGRAM_BOT_TOKEN и webhook на сервере.</small></div>
      <button type="button" className="btn btn-secondary btn-sm" onClick={getCode} disabled={loading}>Проверить снова</button>
    </div>
  );
  if (code) return (
    <div className={styles.telegramFlow}>
      {botUrl ? (
        <a href={botUrl} target="_blank" rel="noopener noreferrer" className="btn btn-secondary">
          <Bot size={16} aria-hidden />
          {lang.notifications.openBot}
        </a>
      ) : (
        <div className={styles.commandRow}><code>/start {code}</code><button type="button" onClick={copyLinkCode} aria-label="Скопировать команду"><Copy size={16} /></button></div>
      )}
      <p>{lang.notifications.afterBotStep}</p>
      <button type="button" className="btn btn-primary" onClick={confirmLink} disabled={loading}>{loading ? 'Проверяем…' : lang.notifications.confirmCode}</button>
      {message && <p className={styles.feedback} role="status">{message}</p>}
    </div>
  );
  return <button type="button" className="btn btn-secondary" onClick={getCode} disabled={loading}><Bot size={16} aria-hidden />{loading ? 'Подготавливаем…' : lang.notifications.getLinkCode}</button>;
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
    <button type="button" className={styles.dangerLink} onClick={unlink} disabled={loading}>
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
    <div className={styles.notificationSettings}>
      {([['notify_tasks', lang.notifications.tasks], ['notify_messages', lang.notifications.messages], ['notify_events', lang.notifications.events]] as const).map(([key, label]) => (
        <label key={key} className={styles.toggleRow}>
          <span>{label}</span>
          <input type="checkbox" role="switch" checked={(settings as any)[key]} onChange={e => toggle(key, e.target.checked)} />
        </label>
      ))}
    </div>
  );
}
