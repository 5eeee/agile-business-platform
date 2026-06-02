import { useEffect, useMemo, useState } from 'react';
import { Activity, Timer, Gauge, Brain, RefreshCcw, Coins } from 'lucide-react';
import { gamificationApi, type UserKPI } from '../../api/gamification';
import { useAppSelector } from '../../store/hooks';
import { t } from '../../i18n';
import styles from './KPI.module.css';

export default function KPIPage() {
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);
  const [kpi, setKpi] = useState<UserKPI | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setError(null);
    try {
      const { data } = await gamificationApi.getMyKPI();
      setKpi(data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Не удалось загрузить KPI');
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

  const timeLabel = useMemo(() => {
    if (!kpi) return '0ч 0м';
    const h = Math.floor(kpi.total_time_minutes / 60);
    const m = kpi.total_time_minutes % 60;
    return `${h}ч ${m}м`;
  }, [kpi]);

  return (
    <div className={styles.page}>
      <div className={styles.head}>
        <div>
          <h1>{lang.nav.kpi || 'KPI'}</h1>
          <p className={styles.muted}>Ваша персональная статистика обучения в реальном времени.</p>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={load}><RefreshCcw size={14} /> Обновить</button>
      </div>

      {loading ? <div className={styles.empty}>{lang.common.loading}</div> : null}
      {error ? <div className={styles.error}>{error}</div> : null}

      {kpi && (
        <>
          <div className={styles.grid}>
            <div className={styles.card}><Timer size={18} /><div><strong>{timeLabel}</strong><span>Время на платформе</span></div></div>
            <div className={styles.card}><Activity size={18} /><div><strong>{kpi.speed_topics_per_day}/день</strong><span>Скорость прохождения</span></div></div>
            <div className={styles.card}><Brain size={18} /><div><strong>{kpi.retention_pct}%</strong><span>Усвоение материала</span></div></div>
            <div className={styles.card}><Gauge size={18} /><div><strong>{kpi.completion_pct}%</strong><span>Прогресс курса</span></div></div>
            <div className={styles.card}><Coins size={18} /><div><strong>{kpi.coins_balance}</strong><span>Agile.Coins</span></div></div>
          </div>

          <div className={styles.progressWrap}>
            <div className={styles.progressRow}><span>Подтемы</span><strong>{kpi.topics_completed}/{kpi.topics_total}</strong></div>
            <div className={styles.progressBar}><div style={{ width: `${Math.max(0, Math.min(100, kpi.completion_pct))}%` }} /></div>
          </div>

          <div className={styles.progressWrap}>
            <div className={styles.progressRow}><span>Тесты</span><strong>{kpi.tests_passed}/{kpi.tests_total}</strong></div>
            <div className={styles.progressBar}><div style={{ width: `${kpi.tests_total ? Math.round((kpi.tests_passed / kpi.tests_total) * 100) : 0}%` }} /></div>
          </div>
        </>
      )}
    </div>
  );
}
