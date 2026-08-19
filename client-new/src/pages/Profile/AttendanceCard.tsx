import { useEffect, useState } from 'react';
import { CheckCircle2, Clock3, LogIn, LogOut, ShieldCheck } from 'lucide-react';
import api from '../../api/client';
import styles from './AttendanceCard.module.css';

interface Attendance {
  date: string;
  check_in: string | null;
  check_out: string | null;
  late_minutes: number;
  early_leave_minutes: number;
  penalty_points: number;
  is_weekend: boolean;
}

const time = (value: string | null) => {
  if (!value) return '—';
  const match = value.match(/T(\d{2}):(\d{2})/);
  return match ? `${match[1]}:${match[2]}` : '—';
};

export default function AttendanceCard() {
  const [attendance, setAttendance] = useState<Attendance | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const load = async () => {
    try {
      setAttendance((await api.get<Attendance>('/gamification/kpi/attendance/today')).data);
    } catch {
      setMessage('Не удалось загрузить рабочий день');
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { void load(); }, []);

  const mark = async (kind: 'check-in' | 'check-out') => {
    setBusy(true); setMessage('');
    try {
      const response = await api.post<Attendance>(`/gamification/kpi/attendance/${kind}`);
      setAttendance(response.data);
      setMessage(kind === 'check-in' ? 'Приход зафиксирован сервером' : 'Завершение работы зафиксировано сервером');
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || 'Не удалось зафиксировать время');
    } finally { setBusy(false); }
  };

  const hasStarted = Boolean(attendance?.check_in);
  const hasFinished = Boolean(attendance?.check_out);
  const statusText = hasFinished ? 'Рабочий день завершён' : hasStarted ? 'Рабочий день идёт' : 'Ожидается начало дня';

  return (
    <section className={`${styles.card} ${hasStarted && !hasFinished ? styles.cardActive : ''}`} aria-labelledby="workday-title">
      <div className={styles.heading}>
        <span className={styles.icon}><Clock3 size={22} aria-hidden /></span>
        <div className={styles.headingText}>
          <span className={styles.eyebrow}>Учёт рабочего времени</span>
          <h2 id="workday-title">Мой рабочий день</h2>
        </div>
        <span className={`${styles.status} ${hasStarted && !hasFinished ? styles.statusActive : ''}`}>
          {hasFinished ? <CheckCircle2 size={15} aria-hidden /> : <span className={styles.statusDot} />}
          {loading ? 'Проверяем статус…' : statusText}
        </span>
      </div>

      <div className={styles.times} aria-label="Отметки рабочего дня">
        <div className={styles.timeItem}>
          <span>Начало</span>
          <strong>{time(attendance?.check_in || null)}</strong>
        </div>
        <div className={styles.timeDivider} aria-hidden />
        <div className={styles.timeItem}>
          <span>Завершение</span>
          <strong>{time(attendance?.check_out || null)}</strong>
        </div>
        {attendance?.is_weekend && <span className={styles.weekend}>Выходной день</span>}
      </div>

      <p className={styles.hint}>
        <ShieldCheck size={16} aria-hidden />
        Время фиксируется сервером только из вашей авторизованной сессии — изменить его вручную нельзя.
      </p>

      <div className={styles.actions}>
        <button type="button" className="btn btn-secondary" disabled={loading || busy || hasStarted} onClick={() => mark('check-in')}>
          <LogIn size={17} aria-hidden /> Начать рабочий день
        </button>
        <button type="button" className="btn btn-primary" disabled={loading || busy || !hasStarted || hasFinished} onClick={() => mark('check-out')}>
          <LogOut size={17} aria-hidden /> Завершить рабочий день
        </button>
      </div>
      {message && <p className={styles.message} role="status" aria-live="polite">{message}</p>}
    </section>
  );
}
