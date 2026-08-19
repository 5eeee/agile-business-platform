import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Inbox, Link2, Plus, RefreshCcw, ShieldCheck } from 'lucide-react';
import { useAppSelector } from '../../store/hooks';
import { t } from '../../i18n';
import api from '../../api/client';
import type { Application } from '../../types';
import { FULL_ACCESS_ROLES } from '../../types';
import type { UserRole } from '../../types';
import styles from './Applications.module.css';

const STATUS_BADGE: Record<string, string> = {
  new: styles.badgeNew,
  contacting: styles.badgeContacting,
  tz_received: styles.badgeTzReceived,
  review: styles.badgeReview,
  revision: styles.badgeRevision,
  approved: styles.badgeApproved,
  distributing: styles.badgeDistributing,
  completed: styles.badgeCompleted,
};

const STATUS_LABELS: Record<string, keyof ReturnType<typeof t>['applications']> = {
  new: 'statusNew',
  contacting: 'statusContacting',
  tz_received: 'statusTzReceived',
  review: 'statusReview',
  revision: 'statusRevision',
  approved: 'statusApproved',
  distributing: 'statusDistributing',
  completed: 'statusCompleted',
};

type Tab = 'all' | 'review' | 'distribute' | 'my';

export default function ApplicationsPage() {
  const navigate = useNavigate();
  const { user } = useAppSelector(s => s.auth);
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);
  const a = lang.applications;

  const userRole = (user?.role || 'user') as UserRole;
  const isReviewer = FULL_ACCESS_ROLES.includes(userRole);

  const [apps, setApps] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [form, setForm] = useState({
    client_name: '',
    client_email: '',
    client_phone: '',
    client_company: '',
    description: '',
    project_name: '',
  });
  const [tab, setTab] = useState<Tab>('all');

  useEffect(() => { loadApps(); }, []);

  useEffect(() => {
    const onRt = (e: Event) => {
      const d = (e as CustomEvent<unknown>).detail as { type?: string; resource?: string } | null;
      if (!d || d.type !== 'resource_changed' || d.resource !== 'application') return;
      loadApps();
    };
    window.addEventListener('agile-realtime', onRt);
    return () => window.removeEventListener('agile-realtime', onRt);
  }, []);

  const loadApps = async () => {
    setLoadError('');
    try {
      const { data } = await api.get<Application[]>('/applications');
      setApps(data);
    } catch {
      setApps([]);
      setLoadError('Не удалось получить заявки. Проверьте соединение с production API.');
    }
    setLoading(false);
  };

  const filtered = useMemo(() => {
    switch (tab) {
      case 'review':
        return apps.filter(a => a.status === 'review');
      case 'distribute':
        return apps.filter(a => a.status === 'approved' || a.status === 'distributing');
      case 'my':
        return apps.filter(a => {
          if (a.consultant_id === user?.id) return true;
          if (userRole === 'consultant' && a.source === 'website' && !a.consultant_id) return true;
          return false;
        });
      default:
        return apps;
    }
  }, [apps, tab, user?.id, userRole]);

  const reviewCount = useMemo(() => apps.filter(a => a.status === 'review').length, [apps]);
  const distCount = useMemo(() => apps.filter(a => a.status === 'approved' || a.status === 'distributing').length, [apps]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const { data } = await api.post<Application>('/applications', form);
      setForm({
        client_name: '',
        client_email: '',
        client_phone: '',
        client_company: '',
        description: '',
        project_name: '',
      });
      setShowCreate(false);
      navigate(`/applications/${data.id}`);
    } catch { /* handled by global interceptor */ }
  };

  if (loading) return <div className={styles.page}><p>Loading...</p></div>;

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <span className={styles.eyebrow}>Клиенты и новые проекты</span>
          <h1 className={styles.title}>{a.title}</h1>
          <p className={styles.subtitle}>Обращения с визитки и созданные вручную заявки находятся в одном рабочем потоке.</p>
        </div>
        <div className={styles.headerActions}>
          <span className={styles.integrationBadge}><ShieldCheck size={15} /> Визитка подключена</span>
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}><Plus size={17} /> {a.create}</button>
        </div>
      </div>

      <div className={styles.sourceNotice}>
        <span className={styles.sourceIcon}><Link2 size={19} /></span>
        <div><strong>Автоматический приём заявок</strong><p>Формы с agile-business-pro.com передают имя, контакты, услугу и описание проекта через защищённый webhook.</p></div>
        <button type="button" onClick={loadApps} aria-label="Обновить заявки"><RefreshCcw size={16} /> Обновить</button>
      </div>

      <div className={styles.tabs}>
        <button className={`${styles.tab} ${tab === 'all' ? styles.tabActive : ''}`} onClick={() => setTab('all')}>
          {a.tabAll}<span className={styles.tabCount}>{apps.length}</span>
        </button>
        {isReviewer && (
          <button className={`${styles.tab} ${tab === 'review' ? styles.tabActive : ''}`} onClick={() => setTab('review')}>
            {a.tabReview}
            {reviewCount > 0 && <span className={styles.tabCount}>{reviewCount}</span>}
          </button>
        )}
        {isReviewer && (
          <button className={`${styles.tab} ${tab === 'distribute' ? styles.tabActive : ''}`} onClick={() => setTab('distribute')}>
            {a.tabDistribute}
            {distCount > 0 && <span className={styles.tabCount}>{distCount}</span>}
          </button>
        )}
        <button className={`${styles.tab} ${tab === 'my' ? styles.tabActive : ''}`} onClick={() => setTab('my')}>
          {a.tabMy}
        </button>
      </div>

      {loadError ? (
        <div className={styles.errorState}><Inbox size={28} /><strong>Заявки временно недоступны</strong><p>{loadError}</p><button type="button" className="btn btn-secondary" onClick={loadApps}>Повторить</button></div>
      ) : filtered.length === 0 ? (
        <div className={styles.empty}><span><Inbox size={30} /></span><strong>{a.noApplications}</strong><p>Новые обращения с визитки появятся здесь автоматически. При необходимости создайте заявку вручную.</p><button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}><Plus size={17} /> {a.create}</button></div>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>{a.clientName}</th>
              <th>{a.tableProject}</th>
              <th>{a.source}</th>
              <th>{a.status}</th>
              <th>{a.consultant}</th>
              <th>{'Дата'}</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(app => (
              <tr key={app.id} onClick={() => navigate(`/applications/${app.id}`)}>
                <td>{app.client_name}</td>
                <td>{app.project_name || '—'}</td>
                <td>
                  <span className={`${styles.badge} ${app.source === 'website' ? styles.badgeWebsite : styles.badgeManual}`}>
                    {app.source === 'website' ? a.sourceWebsite : a.sourceManual}
                  </span>
                </td>
                <td>
                  <span className={`${styles.badge} ${STATUS_BADGE[app.status] || ''}`}>
                    {(a as any)[STATUS_LABELS[app.status]] || app.status}
                  </span>
                </td>
                <td>{app.consultant_name || '—'}</td>
                <td>{new Date(app.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {showCreate && (
        <div className={styles.modal}>
          <div className={styles.overlay} onClick={() => setShowCreate(false)} />
          <div className={styles.dialog}>
            <h3 style={{ marginBottom: 16 }}>{a.create}</h3>
            <form className={styles.form} onSubmit={handleCreate}>
              <input className="input" placeholder={a.clientName} value={form.client_name} onChange={e => setForm(f => ({ ...f, client_name: e.target.value }))} required />
              <input className="input" placeholder={a.projectName} value={form.project_name} onChange={e => setForm(f => ({ ...f, project_name: e.target.value }))} required />
              <input className="input" placeholder={a.clientEmail} type="email" value={form.client_email} onChange={e => setForm(f => ({ ...f, client_email: e.target.value }))} />
              <input className="input" placeholder={a.clientPhone} value={form.client_phone} onChange={e => setForm(f => ({ ...f, client_phone: e.target.value }))} />
              <input className="input" placeholder={a.clientCompany} value={form.client_company} onChange={e => setForm(f => ({ ...f, client_company: e.target.value }))} />
              <textarea className="input" placeholder={a.description} rows={3} value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
              {a.createBoardFlowHint && (
                <p style={{ fontSize: 12, color: 'var(--color-text-muted)', margin: '0 0 8px', lineHeight: 1.4 }}>
                  {a.createBoardFlowHint}
                </p>
              )}
              <div className={styles.formActions}>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowCreate(false)}>{lang.common?.cancel || 'Отмена'}</button>
                <button type="submit" className="btn btn-primary btn-sm">{a.create}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
