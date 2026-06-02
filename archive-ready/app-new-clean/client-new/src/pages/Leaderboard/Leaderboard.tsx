import { useEffect, useMemo, useState } from 'react';
import { Crown, Coins, Clock3, GraduationCap, RefreshCcw, CheckCircle2, AlertTriangle } from 'lucide-react';
import { gamificationApi, type LeaderboardEntry } from '../../api/gamification';
import { useAppSelector } from '../../store/hooks';
import { t } from '../../i18n';
import styles from './Leaderboard.module.css';

export default function LeaderboardPage() {
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);
  const [rows, setRows] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setError(null);
    try {
      const { data } = await gamificationApi.getLeaderboard();
      setRows(data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Не удалось загрузить лидерборд');
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

  const top3 = useMemo(() => rows.slice(0, 3), [rows]);

  return (
    <div className={styles.page}>
      <div className={styles.head}>
        <div>
          <h1>{lang.nav.leaderboard || 'Лидерборд'}</h1>
          <p className={styles.muted}>Топ стажёров по Agile.Coins, задачам и обучению.</p>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={load}><RefreshCcw size={14} /> Обновить</button>
      </div>

      {top3.length > 0 && (
        <div className={styles.top3}>
          {top3.map(u => (
            <div key={u.user_id} className={styles.topCard}>
              <div className={styles.rank}><Crown size={16} /> #{u.rank}</div>
              <div className={styles.name}>{u.user_name}</div>
              <div className={styles.meta}><Coins size={14} /> {u.coins_balance} · <CheckCircle2 size={14} /> {u.tasks_completed_week}/нед</div>
            </div>
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
                <th title="Agile.Coins"><Coins size={14} /></th>
                <th title="Задач за день">День</th>
                <th title="Задач за неделю">Нед</th>
                <th title="Задач за месяц">Мес</th>
                <th title="Задач за год">Год</th>
                <th title="Просрочено"><AlertTriangle size={14} /></th>
                <th title="Обучение"><GraduationCap size={14} /></th>
                <th title="Прогресс обучения">Обуч %</th>
                <th title="Монеты за задачи">Монет за задачи</th>
                <th title="Анти-чит скор">Anti-cheat</th>
                <th title="Тесты (ср. %)">Тесты %</th>
                <th title="Время на платформе"><Clock3 size={14} /></th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.user_id}>
                  <td>{r.rank}</td>
                  <td>{r.user_name}</td>
                  <td><strong>{r.coins_balance}</strong></td>
                  <td>{r.tasks_completed_day}</td>
                  <td>{r.tasks_completed_week}</td>
                  <td>{r.tasks_completed_month}</td>
                  <td>{r.tasks_completed_year}</td>
                  <td style={{ color: r.tasks_overdue > 0 ? '#dc2626' : undefined }}>{r.tasks_overdue}</td>
                  <td>{r.topics_completed}</td>
                  <td>{r.training_progress_pct}%</td>
                  <td>{r.coins_earned_tasks}</td>
                  <td title={r.anti_cheat_flags.join(', ')} style={{ color: r.anti_cheat_score < 70 ? '#dc2626' : undefined }}>
                    {r.anti_cheat_score}
                  </td>
                  <td>{r.avg_test_score}</td>
                  <td>{r.total_time_hours}ч</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
