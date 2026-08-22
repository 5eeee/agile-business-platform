import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart3, BriefcaseBusiness, Crown, Gauge, RefreshCcw, UserRound } from 'lucide-react';
import { gamificationApi, type LeaderboardEntry } from '../../api/gamification';
import { useAppSelector } from '../../store/hooks';
import { t } from '../../i18n';
import styles from './Leaderboard.module.css';

const ROLE_LABELS: Record<string, string> = {
  owner: 'Владелец',
  deputy_owner: 'Заместитель владельца',
  admin: 'Руководитель отдела',
  user: 'Штатный сотрудник',
  intern: 'Стажёр',
  consultant: 'Консультант',
};

const score = (value: number | null | undefined) => Number.isFinite(value) ? `${Math.round(value as number)}%` : '—';

export default function LeaderboardPage() {
  const navigate = useNavigate();
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);
  const [rows, setRows] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setError(null);
    setLoading(true);
    try {
      const { data } = await gamificationApi.getLeaderboard();
      setRows(data);
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Не удалось загрузить рейтинг KPI');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const id = window.setInterval(load, 60 * 1000);
    return () => window.clearInterval(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const top3 = useMemo(() => rows.filter(row => row.overall_score !== null).slice(0, 3), [rows]);

  return (
    <div className={styles.page}>
      <div className={styles.head}>
        <div className={styles.headContent}>
          <span className={styles.headIcon}><BarChart3 size={22} aria-hidden /></span>
          <div>
            <span className={styles.eyebrow}>Результаты команды</span>
            <h1>{lang.nav.leaderboard || 'Лидерборд KPI'}</h1>
            <p className={styles.muted}>Место определяется только итоговой эффективностью. Монеты и игровая активность на рейтинг не влияют.</p>
          </div>
        </div>
        <button className={styles.refreshButton} onClick={load} disabled={loading}><RefreshCcw size={16} className={loading ? styles.refreshing : ''} /> Обновить KPI</button>
      </div>

      {top3.length > 0 && (
        <div className={styles.top3}>
          {top3.map(person => (
            <button type="button" key={person.user_id} className={`${styles.topCard} ${styles[`rank${Math.min(person.rank, 3)}`] || ''}`} onClick={() => navigate(`/kpi?user=${encodeURIComponent(person.user_id)}`)}>
              <div className={styles.topCardHead}>
                <div className={styles.avatarWrap}>{person.avatar_url ? <img src={person.avatar_url} alt="" /> : <UserRound size={22} />}</div>
                <div className={styles.rank}><Crown size={16} /> Место #{person.rank}</div>
              </div>
              <div className={styles.name}>{person.user_name}</div>
              <div className={styles.meta}><span><Gauge size={14} /> Итог {score(person.overall_score)}</span><span><BriefcaseBusiness size={14} /> {ROLE_LABELS[person.role] || person.role}</span></div>
            </button>
          ))}
        </div>
      )}

      {loading ? <div className={styles.empty}>{lang.common.loading}</div> : null}
      {error ? <div className={styles.error}>{error}</div> : null}

      {!loading && rows.length > 0 && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>#</th>
                <th>Сотрудник</th>
                <th>Роль и отдел</th>
                <th>Общие KPI</th>
                <th>Должностные KPI</th>
                <th>Итог</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.user_id} role="button" tabIndex={0} onClick={() => navigate(`/kpi?user=${encodeURIComponent(row.user_id)}`)} onKeyDown={event => {
                  if (event.key === 'Enter' || event.key === ' ') navigate(`/kpi?user=${encodeURIComponent(row.user_id)}`);
                }}>
                  <td><strong>#{row.rank}</strong></td>
                  <td><div className={styles.userCell}>{row.avatar_url ? <img src={row.avatar_url} alt="" /> : <span>{row.user_name.slice(0, 1).toUpperCase()}</span>}<strong>{row.user_name}</strong></div></td>
                  <td><div className={styles.roleCell}><strong>{ROLE_LABELS[row.role] || row.role}</strong><span>{row.department_id || 'Отдел не назначен'}</span></div></td>
                  <td>{score(row.general_score)}</td>
                  <td>{row.occupational_score === null ? 'Не применяется' : score(row.occupational_score)}</td>
                  <td><span className={styles.kpiTotal}>{score(row.overall_score)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && !error && rows.length === 0 && <div className={styles.empty}>Нет сотрудников с доступными показателями KPI.</div>}
    </div>
  );
}
