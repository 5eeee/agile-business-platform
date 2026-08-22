import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { CalendarClock, ExternalLink, Maximize2, PhoneCall, Plus, RefreshCcw, ShieldCheck, Users } from 'lucide-react';

import api from '../../api/client';
import { useAppSelector } from '../../store/hooks';
import type { User } from '../../types';
import styles from './Call.module.css';

interface Conference {
  id: string;
  title: string;
  room_code: string;
  starts_at: string;
  ends_at?: string | null;
  status: 'scheduled' | 'live' | 'ended';
  invited_user_ids: string[];
  created_by_name?: string;
  can_manage: boolean;
}

const STATUS_LABELS = { scheduled: 'Запланирована', live: 'Идёт сейчас', ended: 'Завершена' } as const;

function localInputDate(offsetMinutes = 30) {
  const date = new Date(Date.now() + offsetMinutes * 60_000);
  date.setMinutes(Math.ceil(date.getMinutes() / 5) * 5, 0, 0);
  const timezoneOffset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - timezoneOffset).toISOString().slice(0, 16);
}

function buildCallUrl(token: string) {
  const base = import.meta.env.VITE_AGILE_CALL_URL || 'https://agile-business-platform.vercel.app/call/';
  const url = new URL(base, window.location.origin);
  url.searchParams.set('embed', '1');
  url.hash = new URLSearchParams({ platform_sso: token }).toString();
  return url.toString();
}

export default function CallPage() {
  const { user } = useAppSelector(state => state.auth);
  const isManager = !!user && ['owner', 'deputy_owner', 'admin'].includes(user.role);
  const [frameKey, setFrameKey] = useState(0);
  const [ssoToken, setSsoToken] = useState('');
  const [selectedConferenceId, setSelectedConferenceId] = useState('');
  const [conferences, setConferences] = useState<Conference[]>([]);
  const [employees, setEmployees] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ title: '', starts_at: localInputDate(), ends_at: '', invited_user_ids: [] as string[] });

  const loadPage = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const conferenceResult = await api.get<Conference[]>('/conferences', { _silentGlobalError: true } as never);
      setConferences(conferenceResult.data as Conference[]);
      if (isManager) {
        const employeeResult = await api.get<User[]>('/admin/users', { _silentGlobalError: true } as never);
        setEmployees(employeeResult.data.filter(employee => employee.status === 'active'));
      }
    } catch {
      setError('Не удалось подготовить Agile Call. Обновите страницу через несколько секунд.');
    } finally {
      setLoading(false);
    }
  }, [isManager]);

  useEffect(() => {
    void loadPage();
  }, [loadPage]);

  const callUrl = useMemo(() => {
    if (!ssoToken) return '';
    return buildCallUrl(ssoToken);
  }, [ssoToken]);

  const createConference = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    try {
      await api.post('/conferences', {
        title: form.title.trim(),
        starts_at: new Date(form.starts_at).toISOString(),
        ends_at: form.ends_at ? new Date(form.ends_at).toISOString() : null,
        invited_user_ids: form.invited_user_ids,
      });
      setForm({ title: '', starts_at: localInputDate(), ends_at: '', invited_user_ids: [] });
      setShowCreate(false);
      await loadPage();
    } catch {
      setError('Конференция не создана. Проверьте название, дату и приглашённых.');
    }
  };

  const setConferenceStatus = async (conference: Conference, status: 'live' | 'ended') => {
    try {
      await api.patch(`/conferences/${conference.id}/status`, { status });
      if (status === 'live') await api.post('/conference');
      if (status === 'ended') await api.delete('/conference');
      await loadPage();
      return true;
    } catch {
      setError('Не удалось изменить статус конференции.');
      return false;
    }
  };

  const mayJoin = (conference: Conference) => conference.status === 'live' || Date.now() >= new Date(conference.starts_at).getTime() - 5 * 60_000;

  const getConferenceToken = async (conferenceId: string) => {
    const result = await api.get<{ token: string }>('/conference/sso', {
      params: { conference_id: conferenceId },
      _silentGlobalError: true,
    } as never);
    return result.data.token;
  };

  const prepareConferenceSession = async (conferenceId: string) => {
    const token = await getConferenceToken(conferenceId);
    setSelectedConferenceId(conferenceId);
    setSsoToken(token);
    setFrameKey(value => value + 1);
    return token;
  };

  const joinConference = async (conference: Conference) => {
    if (!mayJoin(conference)) return;
    if (isManager && conference.status === 'scheduled' && !(await setConferenceStatus(conference, 'live'))) return;
    try {
      await prepareConferenceSession(conference.id);
      window.setTimeout(() => document.getElementById('agile-call-frame')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 0);
    } catch {
      setError('Не удалось войти в конференцию. Проверьте приглашение и время начала.');
    }
  };

  const restartCall = async () => {
    if (!selectedConferenceId) return;
    try {
      await prepareConferenceSession(selectedConferenceId);
    } catch {
      setError('Не удалось перезапустить Agile Call.');
    }
  };

  const openCallWindow = async () => {
    if (!selectedConferenceId) return;
    const popup = window.open('about:blank', '_blank');
    if (popup) popup.opener = null;
    try {
      const token = await getConferenceToken(selectedConferenceId);
      if (popup) popup.location.href = buildCallUrl(token);
    } catch {
      popup?.close();
      setError('Не удалось открыть Agile Call в отдельном окне.');
    }
  };

  const toggleInvite = (userId: string) => {
    setForm(current => ({
      ...current,
      invited_user_ids: current.invited_user_ids.includes(userId)
        ? current.invited_user_ids.filter(id => id !== userId)
        : [...current.invited_user_ids, userId],
    }));
  };

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.titleBlock}>
          <span className={styles.icon}><PhoneCall size={22} /></span>
          <div><h1>Agile Call</h1><p>Единый аккаунт AGILE WORKSPACE, расписание и защищённые рабочие комнаты.</p></div>
        </div>
        <div className={styles.actions}>
          <span className={styles.secure}><ShieldCheck size={14} /> Повторная регистрация не нужна</span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => void loadPage()} disabled={loading}><RefreshCcw size={14} /> Обновить</button>
          {isManager ? <button type="button" className="btn btn-primary btn-sm" onClick={() => setShowCreate(value => !value)}><Plus size={15} /> Запланировать</button> : null}
        </div>
      </header>

      {error ? <div className={styles.error} role="alert">{error}</div> : null}

      {showCreate && isManager ? (
        <form className={styles.createPanel} onSubmit={createConference}>
          <div className={styles.createHeading}><CalendarClock size={20} /><div><strong>Новая конференция</strong><span>Сотрудники увидят её в своём разделе и смогут войти к началу.</span></div></div>
          <div className={styles.createGrid}>
            <label><span>Название</span><input value={form.title} onChange={event => setForm(current => ({ ...current, title: event.target.value }))} placeholder="Например: планёрка отдела" required minLength={2} /></label>
            <label><span>Начало</span><input type="datetime-local" value={form.starts_at} onChange={event => setForm(current => ({ ...current, starts_at: event.target.value }))} required /></label>
            <label><span>Завершение</span><input type="datetime-local" value={form.ends_at} onChange={event => setForm(current => ({ ...current, ends_at: event.target.value }))} /></label>
          </div>
          <fieldset className={styles.invites}><legend><Users size={15} /> Пригласить сотрудников</legend><p>Никого не выбирайте, если конференция доступна всей компании.</p><div>{employees.filter(employee => employee.id !== user?.id).map(employee => <label key={employee.id}><input type="checkbox" checked={form.invited_user_ids.includes(employee.id)} onChange={() => toggleInvite(employee.id)} /><span>{employee.last_name ? `${employee.last_name} ` : ''}{employee.name}<small>{employee.department_id || 'Без отдела'}</small></span></label>)}</div></fieldset>
          <div className={styles.createActions}><button type="button" className="btn btn-secondary" onClick={() => setShowCreate(false)}>Отмена</button><button type="submit" className="btn btn-primary">Создать конференцию</button></div>
        </form>
      ) : null}

      <section className={styles.schedule}>
        <div className={styles.scheduleTitle}><div><h2>Расписание конференций</h2><p>{isManager ? 'Вы можете запускать и завершать встречи.' : 'Подключение станет доступно за 5 минут до начала.'}</p></div><span>{conferences.length}</span></div>
        {conferences.length === 0 && !loading ? <div className={styles.empty}><CalendarClock size={26} /><strong>Запланированных конференций нет</strong></div> : <div className={styles.conferenceList}>{conferences.map(conference => {
          const joinEnabled = mayJoin(conference);
          return <article key={conference.id} className={`${styles.conferenceCard} ${conference.status === 'live' ? styles.conferenceLive : ''}`}><div className={styles.conferenceTime}><strong>{new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: 'short' }).format(new Date(conference.starts_at))}</strong><span>{new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' }).format(new Date(conference.starts_at))}</span></div><div className={styles.conferenceInfo}><span className={styles[conference.status]}>{STATUS_LABELS[conference.status]}</span><h3>{conference.title}</h3><p>{conference.created_by_name || 'AGILE WORKSPACE'} · {conference.invited_user_ids.length ? `${conference.invited_user_ids.length} приглашённых` : 'Вся компания'}</p></div><div className={styles.conferenceActions}><button type="button" className={joinEnabled ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm'} disabled={!joinEnabled} onClick={() => void joinConference(conference)}>{conference.status === 'live' ? 'Войти' : joinEnabled ? 'Запустить и войти' : 'Ещё рано'}</button>{isManager && conference.status === 'live' ? <button type="button" className="btn btn-secondary btn-sm" onClick={() => void setConferenceStatus(conference, 'ended')}>Завершить</button> : null}</div></article>;
        })}</div>}
      </section>

      <div id="agile-call-frame" className={styles.frameShell}>
        <div className={styles.frameTopline}><span><Maximize2 size={13} /> Agile Call подключён под аккаунтом {user?.last_name ? `${user.last_name} ` : ''}{user?.name}</span>{callUrl ? <button type="button" onClick={() => void openCallWindow()}><ExternalLink size={13} /> Отдельное окно</button> : null}</div>
        {callUrl ? <iframe key={frameKey} className={styles.frame} src={callUrl} title="Agile Call" allow="camera; microphone; display-capture; fullscreen; clipboard-read; clipboard-write" referrerPolicy="no-referrer" /> : <div className={styles.frameLoading}>{loading ? 'Загружаем расписание…' : 'Выберите доступную конференцию выше'}<button type="button" className="btn btn-secondary btn-sm" disabled={!selectedConferenceId} onClick={() => void restartCall()}>Перезапустить модуль</button></div>}
      </div>
    </div>
  );
}
