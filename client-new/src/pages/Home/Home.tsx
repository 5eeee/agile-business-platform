import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapPin, CalendarDays } from 'lucide-react';
import { useAppSelector } from '../../store/hooks';
import { t } from '../../i18n';
import api from '../../api/client';
import { CardSkeleton } from '../../components/Skeleton/Skeleton';
import type { Event, Notification as NotifType } from '../../types';
import styles from './Home.module.css';

interface DashboardData {
  completed_week: number;
  active_tasks: number;
  total_tasks: number;
  my_tasks: number;
  my_completed_week: number;
  progress_percent: number;
}

export default function HomePage() {
  const navigate = useNavigate();
  const { user } = useAppSelector(s => s.auth);
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);

  const [events, setEvents] = useState<Event[]>([]);
  const [recentNotifs, setRecentNotifs] = useState<NotifType[]>([]);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [tips, setTips] = useState<string[]>([]);
  const [budget, setBudget] = useState<{ total: number; spent: number; items: { label: string; amount: number }[] } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      api.get('/events').then(r => setEvents(r.data.slice(0, 3))),
      api.get('/notifications?limit=10').then(r => setRecentNotifs(r.data)),
      api.get('/analytics/dashboard').then(r => setDashboard(r.data)),
      api.get('/analytics/tips').then(r => setTips(r.data.tips || [])),
      api.get('/analytics/budget').then(r => setBudget(r.data)),
    ]).finally(() => setLoading(false));
  }, []);

  const activeEvent = events.find(e => e.is_active);

  return (
    <div className={`${styles.page} page-enter`}>
      <h1 className={styles.greeting}>
        {lang.dashboard.greeting}, {user?.name}!
      </h1>

      {loading && <CardSkeleton count={4} />}

      {!loading && (<>

      {/* Баннер текущего события */}
      {activeEvent && (
        <div className={styles.eventBanner}>
          <div className={styles.eventInfo}>
            <h2>{activeEvent.title}</h2>
            <p>{activeEvent.description}</p>
            <p style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><MapPin size={16} />{activeEvent.location}</span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><CalendarDays size={16} />{activeEvent.start_date ? new Date(activeEvent.start_date).toLocaleDateString() : activeEvent.event_date ? new Date(activeEvent.event_date).toLocaleDateString() : ''}</span>
            </p>
            <div className={styles.eventActions}>
              <button className={`btn btn-sm ${activeEvent.user_status === 'attending' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => {
                api.post(`/events/${activeEvent.id}/participate`, { status: 'attending' }).then(() => {
                  api.get('/events').then(r => setEvents(r.data.slice(0, 3)));
                });
              }}>
                {lang.events.attend}
              </button>
              <button className={`btn btn-sm ${activeEvent.user_status === 'not_attending' ? 'btn-danger' : 'btn-secondary'}`} onClick={() => {
                api.post(`/events/${activeEvent.id}/participate`, { status: 'not_attending' }).then(() => {
                  api.get('/events').then(r => setEvents(r.data.slice(0, 3)));
                });
              }}>
                {lang.events.notAttend}
              </button>
              <span className={styles.eventParticipants}>
                {activeEvent.participant_count} {lang.events.participants}
              </span>
            </div>
          </div>
        </div>
      )}

      <div className={styles.grid}>
        {/* Прогресс команды */}
        {dashboard && (
          <div className="card">
            <h3>{lang.dashboard.teamProgress}</h3>
            <div className={styles.progressBar}>
              <div className={styles.progressFill} style={{ width: `${Math.min(dashboard.progress_percent, 100)}%` }} />
            </div>
            <div className={styles.statsRow}>
              <div className={styles.stat}>
                <strong>{dashboard.completed_week}</strong>
                <span>{lang.dashboard.tasksCompleted}</span>
              </div>
              <div className={styles.stat}>
                <strong>{dashboard.active_tasks}</strong>
                <span>{lang.dashboard.activeTasks}</span>
              </div>
              <div className={styles.stat}>
                <strong>{dashboard.my_tasks}</strong>
                <span>{lang.dashboard.myTasks}</span>
              </div>
            </div>
          </div>
        )}

        {/* Быстрые действия */}
        <div className="card">
          <h3>{lang.dashboard.quickActions}</h3>
          <div className={styles.quickActions}>
            <button className="btn btn-primary" onClick={() => navigate('/projects')}>
              {lang.nav.myTasks}
            </button>
            <button className="btn btn-secondary" onClick={() => navigate('/analytics')}>
              {lang.nav.analytics}
            </button>
            <button className="btn btn-secondary" onClick={() => navigate('/events')}>
              {lang.dashboard.viewEvents}
            </button>
            <button className="btn btn-secondary" onClick={() => navigate('/music')}>
              {lang.nav.music}
            </button>
          </div>
        </div>

        {/* Советы */}
        {tips.length > 0 && (
          <div className="card">
            <h3>{lang.dashboard.tips}</h3>
            <div className={styles.tipsList}>
              {tips.map((tip, i) => (
                <div key={i} className={styles.tipItem}>{tip}</div>
              ))}
            </div>
          </div>
        )}

        {/* Бюджет */}
        {budget && (
          <div className="card">
            <h3>{lang.dashboard.companyBudget}</h3>
            <div className={styles.progressBar}>
              <div className={styles.progressFill} style={{ width: `${Math.min((budget.spent / (budget.total || 1)) * 100, 100)}%` }} />
            </div>
            <div className={styles.statsRow}>
              <div className={styles.stat}><strong>{budget.total.toLocaleString()}</strong><span>{lang.dashboard.total}</span></div>
              <div className={styles.stat}><strong>{budget.spent.toLocaleString()}</strong><span>{lang.dashboard.spent}</span></div>
              <div className={styles.stat}><strong>{(budget.total - budget.spent).toLocaleString()}</strong><span>{lang.dashboard.remaining}</span></div>
            </div>
            {budget.items?.length > 0 && <div style={{ marginTop: 12 }}>{budget.items.map((it, i) => <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--color-text-secondary)', padding: '3px 0' }}><span>{it.label}</span><span>{it.amount.toLocaleString()}</span></div>)}</div>}
          </div>
        )}

        {/* Последние обновления */}
        <div className="card">
          <h3>{lang.dashboard.recentUpdates}</h3>
          <div className={styles.updates}>
            {recentNotifs.length === 0 ? (
              <p className={styles.empty}>{lang.common.noData}</p>
            ) : (
              recentNotifs.map(n => (
                <div key={n.id} className={styles.updateItem}>
                  <strong>{n.title}</strong>
                  <p>{n.message}</p>
                  <small>{new Date(n.created_at).toLocaleString()}</small>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
      </>)}
    </div>
  );
}
