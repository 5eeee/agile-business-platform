import { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, ClipboardCheck, Save, Send, Undo2 } from 'lucide-react';
import { gamificationApi, type WeeklyReport } from '../../api/gamification';
import styles from './WeeklyReportsPanel.module.css';

const fields = [
  ['1', 'Выполненные задачи за неделю'],
  ['2', 'Задачи в работе'],
  ['3', 'Просроченные задачи'],
  ['4', 'Планы на следующую неделю (минимум 3 пункта с новой строки)'],
  ['5', 'Проблемы и риски'],
] as const;

const spheres = [
  ['technical', 'Техническая'],
  ['process', 'Процессная'],
  ['product', 'Продуктовая'],
  ['marketing_pr', 'Маркетинг / PR'],
  ['resource_saving', 'Экономия ресурсов'],
  ['learning_development', 'Обучение / развитие'],
  ['customer_service', 'Клиентский сервис'],
  ['social_team', 'Социальная / командная'],
  ['other', 'Другое'],
] as const;

const statusLabels: Record<WeeklyReport['status'], string> = {
  draft: 'Черновик',
  on_review: 'На проверке',
  approved: 'Принят',
  rework: 'На доработке',
};

interface Props {
  canReview: boolean;
  onKpiChanged: () => void;
}

export default function WeeklyReportsPanel({ canReview, onKpiChanged }: Props) {
  const [report, setReport] = useState<WeeklyReport | null>(null);
  const [criteria, setCriteria] = useState<Record<string, string>>({});
  const [sphere, setSphere] = useState('');
  const [pending, setPending] = useState<WeeklyReport[]>([]);
  const [checks, setChecks] = useState<Record<string, number[]>>({});
  const [comments, setComments] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const editable = report?.status !== 'approved' && report?.status !== 'on_review';

  const load = async () => {
    const own = await gamificationApi.getMyWeeklyReport();
    setReport(own.data);
    setCriteria(own.data.criteria || {});
    setSphere(own.data.initiative_sphere || '');
    if (canReview) {
      const queue = await gamificationApi.getPendingWeeklyReports();
      setPending(queue.data);
      setChecks(Object.fromEntries(queue.data.map(item => [
        item.id,
        [1, 2, 3, 4, 5, ...(item.criteria['6'] ? [6] : [])],
      ])));
    }
  };

  useEffect(() => {
    load().catch(() => setError('Не удалось загрузить еженедельный отчёт'));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canReview]);

  const weekLabel = useMemo(() => {
    if (!report) return '';
    const start = new Date(report.week_start);
    const end = new Date(start);
    end.setDate(start.getDate() + 6);
    return `${start.toLocaleDateString('ru-RU')} — ${end.toLocaleDateString('ru-RU')}`;
  }, [report]);

  const save = async (showSuccess = true) => {
    const response = await gamificationApi.saveMyWeeklyReport({
      criteria,
      initiative_sphere: sphere || null,
    });
    setReport(response.data);
    if (showSuccess) setMessage('Черновик сохранён');
  };

  const handleSave = async () => {
    setBusy(true); setError(''); setMessage('');
    try { await save(); }
    catch (err: any) { setError(err?.response?.data?.detail || 'Не удалось сохранить отчёт'); }
    finally { setBusy(false); }
  };

  const handleSubmit = async () => {
    setBusy(true); setError(''); setMessage('');
    try {
      await save(false);
      const response = await gamificationApi.submitMyWeeklyReport();
      setReport(response.data);
      setMessage('Отчёт отправлен руководителю и учтён в KPI');
      onKpiChanged();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Не удалось отправить отчёт');
    } finally { setBusy(false); }
  };

  const toggleCheck = (reportId: string, criterion: number) => {
    setChecks(current => {
      const values = current[reportId] || [];
      return {
        ...current,
        [reportId]: values.includes(criterion)
          ? values.filter(item => item !== criterion)
          : [...values, criterion].sort(),
      };
    });
  };

  const review = async (item: WeeklyReport) => {
    setBusy(true); setError(''); setMessage('');
    try {
      const response = await gamificationApi.reviewWeeklyReport(item.id, {
        checked_criteria: checks[item.id] || [],
        comment: comments[item.id] || undefined,
      });
      setMessage(response.data.status === 'approved' ? 'Отчёт принят' : 'Отчёт возвращён на доработку');
      await load();
      onKpiChanged();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Не удалось проверить отчёт');
    } finally { setBusy(false); }
  };

  return (
    <section className={styles.panel}>
      <div className={styles.header}>
        <div>
          <div className={styles.title}><ClipboardCheck size={20} /><h2>Еженедельный отчёт</h2></div>
          <div className={styles.meta}>{weekLabel} · срок до пятницы 22:00</div>
        </div>
        {report && <span className={styles.status}>{statusLabels[report.status]}</span>}
      </div>

      <div className={styles.formGrid}>
        {fields.map(([key, label]) => (
          <div className={styles.field} key={key}>
            <label htmlFor={`weekly-${key}`}>{key}. {label}</label>
            <textarea
              id={`weekly-${key}`}
              value={criteria[key] || ''}
              disabled={!editable || busy}
              onChange={event => setCriteria(current => ({ ...current, [key]: event.target.value }))}
              placeholder={key === '3' || key === '5' ? 'Если отсутствуют — напишите «нет»' : 'Минимум 10 символов'}
            />
          </div>
        ))}
      </div>

      <div className={styles.initiative}>
        <label htmlFor="weekly-sphere">6. Инициативы и предложения (опционально)</label>
        <select id="weekly-sphere" value={sphere} disabled={!editable || busy} onChange={event => setSphere(event.target.value)}>
          <option value="">Выберите сферу</option>
          {spheres.map(([value, label]) => <option value={value} key={value}>{label}</option>)}
        </select>
        <textarea
          value={criteria['6'] || ''}
          disabled={!editable || busy}
          onChange={event => setCriteria(current => ({ ...current, '6': event.target.value }))}
          placeholder="Предложение минимум из 10 символов"
        />
        <div className={styles.hint}>Подтверждённая инициатива автоматически повышает показатель инициативности.</div>
      </div>

      {editable && (
        <div className={styles.actions}>
          <button className="btn btn-ghost" disabled={busy} onClick={handleSave}><Save size={15} /> Сохранить черновик</button>
          <button className="btn btn-primary" disabled={busy} onClick={handleSubmit}><Send size={15} /> Отправить на проверку</button>
        </div>
      )}
      {error && <div className={styles.error}>{error}</div>}
      {message && <div className={styles.success}>{message}</div>}

      {canReview && (
        <div className={styles.reviewSection}>
          <div className={styles.reviewHeader}>
            <h3>Отчёты сотрудников на проверке</h3>
            <span className={styles.meta}>{pending.length} шт.</span>
          </div>
          {pending.length === 0 ? <div className={styles.empty}>Новых отчётов нет.</div> : (
            <div className={styles.reviewList}>
              {pending.map(item => (
                <article className={styles.reviewCard} key={item.id}>
                  <strong>{item.employee_name || 'Сотрудник'}</strong>
                  <div className={styles.meta}>Отправлен: {item.submitted_at ? new Date(item.submitted_at).toLocaleString('ru-RU') : '—'}</div>
                  <div className={styles.criteriaList}>
                    {[1, 2, 3, 4, 5, ...(item.criteria['6'] ? [6] : [])].map(number => (
                      <label className={styles.criterion} key={number}>
                        <input
                          type="checkbox"
                          checked={(checks[item.id] || []).includes(number)}
                          onChange={() => toggleCheck(item.id, number)}
                        />
                        <span><strong>Критерий {number}</strong>{item.criteria[String(number)] || 'Не заполнен'}</span>
                      </label>
                    ))}
                  </div>
                  <textarea
                    className={styles.reviewComment}
                    value={comments[item.id] || ''}
                    onChange={event => setComments(current => ({ ...current, [item.id]: event.target.value }))}
                    placeholder="Пояснение обязательно, если возвращаете на доработку"
                  />
                  <div className={styles.actions}>
                    {(checks[item.id] || []).filter(value => value <= 5).length === 5
                      ? <CheckCircle2 size={16} color="#10b981" />
                      : <Undo2 size={16} color="#f59e0b" />}
                    <button className="btn btn-primary" disabled={busy} onClick={() => review(item)}>
                      {(checks[item.id] || []).filter(value => value <= 5).length === 5 ? 'Принять' : 'Вернуть на доработку'}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
