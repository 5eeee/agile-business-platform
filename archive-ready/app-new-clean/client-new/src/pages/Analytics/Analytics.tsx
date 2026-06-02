import { useState, useEffect } from 'react';
import { useAppSelector } from '../../store/hooks';
import { t } from '../../i18n';
import api from '../../api/client';
import { MetricsSkeleton, CardSkeleton } from '../../components/Skeleton/Skeleton';
import styles from './Analytics.module.css';

interface DashboardData {
  completed_week: number;
  active_tasks: number;
  total_tasks: number;
  user_projects: number;
  my_tasks: number;
  my_completed_week: number;
  progress_percent: number;
}

interface Report {
  id: string;
  content: string;
  report_data?: Record<string, number>;
  created_at: string;
}

export default function AnalyticsPage() {
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);

  const [data, setData] = useState<DashboardData | null>(null);
  const [tips, setTips] = useState<string[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      api.get('/analytics/dashboard').then(r => setData(r.data)),
      api.get('/analytics/tips').then(r => setTips(r.data.tips || [])),
      api.get('/analytics/reports').then(r => setReports(r.data)),
    ]).finally(() => setLoading(false));
  }, []);

  const handleGenerate = async () => {
    const r = await api.post('/analytics/reports/generate');
    setReports(prev => [r.data, ...prev]);
  };

  return (
    <div className={`${styles.page} page-enter`}>
      <div className={styles.header}>
        <h1>{lang.analytics.title}</h1>
        <button className="btn btn-primary btn-sm" onClick={handleGenerate}>
          {lang.analytics.generateReport}
        </button>
      </div>

      {loading ? (
        <>
          <MetricsSkeleton count={6} />
          <CardSkeleton count={2} />
        </>
      ) : (<>

      {/* Метрики */}
      {data ? (
        <div className={styles.metrics}>
          <div className={styles.metric}>
            <span className={styles.metricValue}>{data.completed_week}</span>
            <span className={styles.metricLabel}>{lang.dashboard.tasksCompleted}</span>
          </div>
          <div className={styles.metric}>
            <span className={styles.metricValue}>{data.active_tasks}</span>
            <span className={styles.metricLabel}>{lang.dashboard.activeTasks}</span>
          </div>
          <div className={styles.metric}>
            <span className={styles.metricValue}>{data.total_tasks}</span>
            <span className={styles.metricLabel}>{lang.analytics.totalTasks}</span>
          </div>
          <div className={styles.metric}>
            <span className={styles.metricValue}>{data.user_projects}</span>
            <span className={styles.metricLabel}>{lang.analytics.myProjects}</span>
          </div>
          <div className={styles.metric}>
            <span className={styles.metricValue}>{data.my_tasks}</span>
            <span className={styles.metricLabel}>{lang.analytics.myTasks}</span>
          </div>
          <div className={styles.metric}>
            <span className={styles.metricValue}>{data.progress_percent}%</span>
            <span className={styles.metricLabel}>{lang.analytics.progress}</span>
          </div>
        </div>
      ) : (
        <div className="card" style={{ padding: 24, textAlign: 'center', color: 'var(--color-text-muted)' }}>
          {lang.common.noData}
        </div>
      )}

      {/* Прогресс-бар */}
      {data && (
        <div className={`card ${styles.progressCard}`}>
          <h3>{lang.dashboard.teamProgress}</h3>
          <div className={styles.progressBar}>
            <div className={styles.progressFill} style={{ width: `${Math.min(data.progress_percent, 100)}%` }} />
          </div>
          <p className={styles.progressText}>
            {data.completed_week} / {data.total_tasks} {lang.analytics.completed}
          </p>
        </div>
      )}

      <div className={styles.grid}>
        {/* Советы */}
        <div className="card">
          <h3>{lang.dashboard.tips}</h3>
          <div className={styles.tipsList}>
            {tips.length === 0 ? (
              <p className={styles.empty}>{lang.common.noData}</p>
            ) : tips.map((tip, i) => (
              <div key={i} className={styles.tipItem}>{tip}</div>
            ))}
          </div>
        </div>

        {/* Отчёты */}
        <div className="card">
          <h3>{lang.analytics.reports}</h3>
          <div className={styles.reportsList}>
            {reports.length === 0 ? (
              <p className={styles.empty}>{lang.common.noData}</p>
            ) : (
              reports.map(r => (
                <div key={r.id} className={styles.reportItem}>
                  <pre className={styles.reportContent}>{r.content}</pre>
                  <small>{new Date(r.created_at).toLocaleString()}</small>
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
