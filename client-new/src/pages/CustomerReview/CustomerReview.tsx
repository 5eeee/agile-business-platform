import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { CheckCircle2, ShieldCheck, Star } from 'lucide-react';
import api from '../../api/client';
import styles from './CustomerReview.module.css';

type Survey = {
  project_name: string;
  customer_name: string;
  expires_at: string;
};

type Result = {
  message: string;
  promo_code: string;
  discount_percent: number;
  valid_until: string;
};

export default function CustomerReviewPage() {
  const { token = '' } = useParams();
  const [survey, setSurvey] = useState<Survey | null>(null);
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<Result | null>(null);

  useEffect(() => {
    api.get<Survey>(`/public/customer-surveys/${encodeURIComponent(token)}`)
      .then(response => setSurvey(response.data))
      .catch(err => setError(err?.response?.data?.detail || 'Ссылка на опрос недействительна'))
      .finally(() => setLoading(false));
  }, [token]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (rating < 1) return setError('Поставьте оценку от 1 до 5');
    if (comment.trim().length < 10) return setError('Комментарий должен содержать не менее 10 символов');
    setError('');
    setSending(true);
    try {
      const response = await api.post<Result>(`/public/customer-surveys/${encodeURIComponent(token)}`, {
        rating,
        comment: comment.trim(),
      });
      setResult(response.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Не удалось отправить отзыв');
    } finally {
      setSending(false);
    }
  };

  return (
    <main className={styles.page}>
      <section className={styles.card}>
        <div className={styles.brand}><ShieldCheck size={22} /><span>AGILE WORKSPACE</span></div>
        {loading && <p className={styles.muted}>Загрузка опроса…</p>}
        {!loading && error && !survey && <div className={styles.error}>{error}</div>}
        {survey && !result && (
          <form onSubmit={submit}>
            <span className={styles.eyebrow}>Оценка завершённого проекта</span>
            <h1>{survey.project_name}</h1>
            <p className={styles.muted}>{survey.customer_name}, оцените качество работы команды. Отзыв влияет на командный KPI.</p>
            <div className={styles.stars} role="radiogroup" aria-label="Оценка проекта">
              {[1, 2, 3, 4, 5].map(value => (
                <button
                  key={value}
                  type="button"
                  className={value <= rating ? styles.starActive : styles.star}
                  onClick={() => setRating(value)}
                  aria-label={`${value} из 5`}
                  aria-pressed={rating === value}
                >
                  <Star size={32} fill={value <= rating ? 'currentColor' : 'none'} />
                </button>
              ))}
            </div>
            <label className={styles.label}>
              Комментарий
              <textarea
                value={comment}
                onChange={event => setComment(event.target.value)}
                rows={5}
                maxLength={5000}
                placeholder="Что понравилось и что можно улучшить?"
              />
              <small>{comment.trim().length}/10 минимум</small>
            </label>
            {error && <div className={styles.error}>{error}</div>}
            <button className={styles.submit} disabled={sending}>{sending ? 'Отправляем…' : 'Отправить отзыв'}</button>
            <p className={styles.privacy}><ShieldCheck size={14} /> Ссылка одноразовая. Оценка доступна только команде проекта.</p>
          </form>
        )}
        {result && (
          <div className={styles.success}>
            <CheckCircle2 size={44} />
            <h1>Спасибо за отзыв</h1>
            <p>Ваш промокод на скидку {result.discount_percent}%:</p>
            <strong className={styles.promo}>{result.promo_code}</strong>
            <small>Действителен до {new Date(result.valid_until).toLocaleDateString('ru-RU')}</small>
          </div>
        )}
      </section>
    </main>
  );
}
