import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, FlaskConical, Lightbulb, Send, XCircle } from 'lucide-react';
import { gamificationApi, type EmployeeIdea } from '../../api/gamification';
import styles from './IdeasPanel.module.css';

const TYPES = [
  ['technical', 'Техническая'], ['process', 'Процессная'], ['product', 'Продуктовая'],
  ['marketing_pr', 'Маркетинг и PR'], ['resource_saving', 'Экономия ресурсов'], ['other', 'Другая'],
];
const SPHERES = ['ИТ', 'Бизнес-анализ', 'Маркетинг', 'Продажи', 'Финансы', 'Кадры', 'Продукт', 'Другое'];
const STATUS: Record<string, string> = { submitted: 'На рассмотрении', testing: 'Тестируется', success: 'Внедрена', fail: 'Отклонена' };

export default function IdeasPanel({ onKpiChanged }: { onKpiChanged: () => void }) {
  const [mine, setMine] = useState<EmployeeIdea[]>([]);
  const [pending, setPending] = useState<EmployeeIdea[]>([]);
  const [form, setForm] = useState({ idea_type: 'process', sphere: 'ИТ', description: '' });
  const [comments, setComments] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const load = useCallback(async () => {
    const [myResponse, pendingResponse] = await Promise.all([
      gamificationApi.getMyIdeas(),
      gamificationApi.getPendingIdeas(),
    ]);
    setMine(myResponse.data);
    setPending(pendingResponse.data);
  }, []);

  useEffect(() => { load().catch(() => undefined); }, [load]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!form.description.trim()) return setMessage('Опишите идею');
    setBusy(true); setMessage('');
    try {
      await gamificationApi.createIdea({ ...form, description: form.description.trim() });
      setForm(current => ({ ...current, description: '' }));
      setMessage('Идея отправлена руководителю');
      await load(); onKpiChanged();
    } finally { setBusy(false); }
  };

  const decide = async (idea: EmployeeIdea, decision: 'testing' | 'success' | 'fail') => {
    const comment = (comments[idea.id] || '').trim();
    if (decision === 'fail' && comment.length < 10) return setMessage('Для отклонения напишите комментарий не менее 10 символов');
    setBusy(true); setMessage('');
    try {
      await gamificationApi.reviewIdea(idea.id, { decision, comment: comment || undefined });
      await load(); onKpiChanged();
    } finally { setBusy(false); }
  };

  return (
    <section className={styles.panel}>
      <header><span><Lightbulb size={19} /></span><div><h2>Идеи и инициативы</h2><p>Влияют на инициативность сотрудника и качество реакции руководителя</p></div></header>
      <form className={styles.form} onSubmit={submit}>
        <select value={form.idea_type} onChange={event => setForm(current => ({ ...current, idea_type: event.target.value }))}>{TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
        <select value={form.sphere} onChange={event => setForm(current => ({ ...current, sphere: event.target.value }))}>{SPHERES.map(value => <option key={value}>{value}</option>)}</select>
        <textarea rows={3} maxLength={5000} placeholder="Кратко опишите идею и ожидаемый эффект" value={form.description} onChange={event => setForm(current => ({ ...current, description: event.target.value }))} />
        <button className="btn btn-primary btn-sm" disabled={busy}><Send size={14} /> Отправить идею</button>
      </form>
      {message && <p className={styles.message}>{message}</p>}

      {pending.length > 0 && <div className={styles.pending}><h3>Требуют решения</h3>{pending.map(idea => (
        <article key={idea.id}>
          <div className={styles.ideaHead}><strong>{idea.employee_name || 'Сотрудник'} · {idea.sphere}</strong><time>{new Date(idea.created_at).toLocaleDateString('ru-RU')}</time></div>
          <p>{idea.description}</p>
          <textarea rows={2} placeholder="Комментарий руководителя (обязателен при отклонении)" value={comments[idea.id] || ''} onChange={event => setComments(current => ({ ...current, [idea.id]: event.target.value }))} />
          <div className={styles.actions}>
            <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => decide(idea, 'testing')}><FlaskConical size={14} /> На тестирование</button>
            <button className="btn btn-primary btn-sm" disabled={busy} onClick={() => decide(idea, 'success')}><CheckCircle2 size={14} /> Внедрить</button>
            <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => decide(idea, 'fail')}><XCircle size={14} /> Отклонить</button>
          </div>
        </article>
      ))}</div>}

      <div className={styles.history}><h3>Мои идеи</h3>{mine.length === 0 ? <p className={styles.empty}>Пока нет отправленных идей.</p> : mine.map(idea => (
        <article key={idea.id}><span className={`${styles.status} ${styles[idea.status] || ''}`}>{STATUS[idea.status] || idea.status}</span><div><strong>{idea.sphere} · {TYPES.find(item => item[0] === idea.idea_type)?.[1] || idea.idea_type}</strong><p>{idea.description}</p>{idea.comment && <small>Комментарий: {idea.comment}</small>}</div></article>
      ))}</div>
    </section>
  );
}
