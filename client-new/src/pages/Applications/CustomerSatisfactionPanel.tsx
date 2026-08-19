import { useCallback, useEffect, useMemo, useState } from 'react';
import { Check, Clipboard, ExternalLink, RefreshCcw, Star, Users } from 'lucide-react';
import api from '../../api/client';
import styles from './CustomerSatisfactionPanel.module.css';

type Contribution = { user_id: string; user_name: string; weight: number };
type Review = { id: string; rating: number; comment: string; submitted_at: string };
type Setup = { ready: boolean; project_id: string | null; contributions: Contribution[]; reviews: Review[] };

export default function CustomerSatisfactionPanel({ applicationId }: { applicationId: string }) {
  const [setup, setSetup] = useState<Setup | null>(null);
  const [weights, setWeights] = useState<Record<string, string>>({});
  const [surveyUrl, setSurveyUrl] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const response = await api.get<Setup>(`/customer-satisfaction/applications/${applicationId}`);
    setSetup(response.data);
    setWeights(Object.fromEntries(response.data.contributions.map(item => [item.user_id, String(Math.round(item.weight * 10000) / 100)])));
  }, [applicationId]);

  useEffect(() => { load().catch(() => undefined); }, [load]);

  const total = useMemo(
    () => Object.values(weights).reduce((sum, value) => sum + (Number(value) || 0), 0),
    [weights],
  );

  const saveWeights = async () => {
    if (!setup || Math.abs(total - 100) > 0.001) return setMessage('Сумма вкладов должна быть ровно 100%');
    setBusy(true);
    setMessage('');
    try {
      await api.put(`/customer-satisfaction/applications/${applicationId}/contributions`, setup.contributions.map(item => ({
        user_id: item.user_id,
        weight: Number(weights[item.user_id]) / 100,
      })));
      setMessage('Веса участников сохранены');
      await load();
    } finally {
      setBusy(false);
    }
  };

  const generate = async () => {
    setBusy(true);
    setMessage('');
    try {
      const response = await api.post<{ survey_path: string }>(`/customer-satisfaction/applications/${applicationId}/survey-link`);
      const url = `${window.location.origin}${response.data.survey_path}`;
      setSurveyUrl(url);
      await navigator.clipboard.writeText(url).catch(() => undefined);
      setMessage('Одноразовая ссылка создана и скопирована');
    } finally {
      setBusy(false);
    }
  };

  if (!setup) return null;

  return (
    <section className={styles.panel}>
      <header className={styles.head}>
        <div><span className={styles.icon}><Star size={18} /></span><div><h3>Удовлетворённость заказчика</h3><p>Командный KPI по оценке завершённого проекта</p></div></div>
        <button className="btn btn-ghost btn-sm" onClick={load} aria-label="Обновить отзывы"><RefreshCcw size={14} /></button>
      </header>
      {!setup.ready && <div className={styles.notice}>Опрос станет доступен после создания проекта и перевода заявки в статус «Завершена».</div>}
      {setup.ready && (
        <>
          <div className={styles.subhead}><Users size={15} /><strong>Вес вклада участников</strong><span className={Math.abs(total - 100) < .001 ? styles.totalOk : styles.totalBad}>{total.toFixed(1)}%</span></div>
          <div className={styles.weights}>
            {setup.contributions.map(item => (
              <label key={item.user_id}><span>{item.user_name}</span><div><input type="number" min="0.01" max="100" step="0.01" value={weights[item.user_id] ?? ''} onChange={event => setWeights(current => ({ ...current, [item.user_id]: event.target.value }))} /><span>%</span></div></label>
            ))}
          </div>
          <div className={styles.actions}>
            <button className="btn btn-ghost btn-sm" onClick={saveWeights} disabled={busy || Math.abs(total - 100) > .001}><Check size={14} /> Сохранить веса</button>
            <button className="btn btn-primary btn-sm" onClick={generate} disabled={busy}><Clipboard size={14} /> Создать ссылку на опрос</button>
          </div>
          {surveyUrl && <a className={styles.link} href={surveyUrl} target="_blank" rel="noreferrer"><ExternalLink size={14} />{surveyUrl}</a>}
          {message && <p className={styles.message}>{message}</p>}
          <div className={styles.reviews}>
            <strong>Полученные отзывы</strong>
            {setup.reviews.length === 0 ? <p>Пока нет отзывов.</p> : setup.reviews.map(review => (
              <article key={review.id}><span>{review.rating}/5</span><p>{review.comment}</p><time>{new Date(review.submitted_at).toLocaleDateString('ru-RU')}</time></article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
