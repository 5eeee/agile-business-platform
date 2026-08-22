import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { ArrowDownRight, ArrowUpRight, CircleDollarSign, Coins, RefreshCw, Trash2 } from 'lucide-react';

import api from '../../api/client';
import styles from './Finance.module.css';

type Period = 'week' | 'month' | 'quarter';

interface FinancialOperation {
  id: string;
  operation_type: 'income' | 'expense';
  category: string;
  description: string;
  amount: number;
  occurred_at: string;
  created_at: string;
}

interface FinanceSummary {
  income: number;
  expense: number;
  profit: number;
  operations_count: number;
}

const EMPTY_SUMMARY: FinanceSummary = { income: 0, expense: 0, profit: 0, operations_count: 0 };
const MONEY = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 });

function periodParams(period: Period) {
  const now = new Date();
  const from = new Date(now);
  if (period === 'week') from.setDate(now.getDate() - 7);
  if (period === 'month') from.setMonth(now.getMonth() - 1);
  if (period === 'quarter') from.setMonth(now.getMonth() - 3);
  return { date_from: from.toISOString(), date_to: now.toISOString() };
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium' }).format(new Date(value));
}

export default function FinancePage() {
  const [period, setPeriod] = useState<Period>('month');
  const [operations, setOperations] = useState<FinancialOperation[]>([]);
  const [summary, setSummary] = useState<FinanceSummary>(EMPTY_SUMMARY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [newOperation, setNewOperation] = useState({
    category: 'Маркетинг',
    description: '',
    amount: '',
    occurred_at: new Date().toISOString().slice(0, 10),
    operation_type: 'expense' as 'income' | 'expense',
  });

  const loadFinance = useCallback(async () => {
    setLoading(true);
    setError('');
    const params = periodParams(period);
    try {
      const [operationsResponse, summaryResponse] = await Promise.all([
        api.get<FinancialOperation[]>('/finance/operations', { params, _silentGlobalError: true } as never),
        api.get<FinanceSummary>('/finance/summary', { params, _silentGlobalError: true } as never),
      ]);
      setOperations(operationsResponse.data);
      setSummary(summaryResponse.data);
    } catch {
      setOperations([]);
      setSummary(EMPTY_SUMMARY);
      setError('Не удалось загрузить финансовые данные. Попробуйте обновить страницу.');
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => {
    void loadFinance();
  }, [loadFinance]);

  const signedOperations = useMemo(
    () => operations.map(operation => ({
      ...operation,
      signedAmount: operation.operation_type === 'expense' ? -Number(operation.amount) : Number(operation.amount),
    })),
    [operations],
  );

  const submitOperation = async (event: FormEvent) => {
    event.preventDefault();
    const amount = Number(newOperation.amount);
    if (!Number.isFinite(amount) || amount <= 0 || !newOperation.description.trim()) return;
    setSaving(true);
    setError('');
    try {
      await api.post('/finance/operations', {
        operation_type: newOperation.operation_type,
        category: newOperation.category,
        description: newOperation.description.trim(),
        amount,
        occurred_at: new Date(`${newOperation.occurred_at}T12:00:00`).toISOString(),
      });
      setNewOperation(current => ({ ...current, description: '', amount: '' }));
      await loadFinance();
    } catch {
      setError('Операция не сохранена. Проверьте данные и повторите попытку.');
    } finally {
      setSaving(false);
    }
  };

  const deleteOperation = async (operation: FinancialOperation) => {
    if (!window.confirm(`Удалить операцию «${operation.description}»?`)) return;
    try {
      await api.delete(`/finance/operations/${operation.id}`);
      await loadFinance();
    } catch {
      setError('Не удалось удалить финансовую операцию.');
    }
  };

  return (
    <div className={`${styles.page} page-enter`}>
      <div className={styles.header}>
        <div>
          <h1>Финансы владельца</h1>
          <p className={styles.subtitle}>Только фактически внесённые доходы и расходы. Доступ закрыт для сотрудников и руководителей.</p>
        </div>
        <div className={styles.headerActions}>
          <div className={styles.periodSelector} aria-label="Период финансовой аналитики">
            <button type="button" className={period === 'week' ? styles.periodActive : ''} onClick={() => setPeriod('week')}>Неделя</button>
            <button type="button" className={period === 'month' ? styles.periodActive : ''} onClick={() => setPeriod('month')}>Месяц</button>
            <button type="button" className={period === 'quarter' ? styles.periodActive : ''} onClick={() => setPeriod('quarter')}>Квартал</button>
          </div>
          <button type="button" className="btn btn-secondary" onClick={() => void loadFinance()} disabled={loading}>
            <RefreshCw size={16} aria-hidden /> Обновить
          </button>
        </div>
      </div>

      {error ? <div className={styles.error} role="alert">{error}</div> : null}

      <div className={styles.metricsGrid} aria-busy={loading}>
        <div className={styles.metricCard}>
          <div className={styles.cardHeader}><span className={styles.cardTitle}>Доходы за период</span><span className={`${styles.iconWrapper} ${styles.incomeIcon}`}><ArrowUpRight size={20} /></span></div>
          <div className={styles.cardBody}><h2>{MONEY.format(summary.income)} ₽</h2><p className={styles.factHint}>Сумма операций типа «Доход»</p></div>
        </div>
        <div className={styles.metricCard}>
          <div className={styles.cardHeader}><span className={styles.cardTitle}>Расходы за период</span><span className={`${styles.iconWrapper} ${styles.expenseIcon}`}><ArrowDownRight size={20} /></span></div>
          <div className={styles.cardBody}><h2>{MONEY.format(summary.expense)} ₽</h2><p className={styles.factHint}>Сумма операций типа «Расход»</p></div>
        </div>
        <div className={styles.metricCard}>
          <div className={styles.cardHeader}><span className={styles.cardTitle}>Фактический результат</span><span className={`${styles.iconWrapper} ${styles.profitIcon}`}><CircleDollarSign size={20} /></span></div>
          <div className={styles.cardBody}><h2 className={summary.profit < 0 ? styles.negative : styles.positive}>{MONEY.format(summary.profit)} ₽</h2><p className={styles.factHint}>Доходы минус расходы · {summary.operations_count} операций</p></div>
        </div>
      </div>

      <div className={styles.layoutGrid}>
        <section className="card">
          <h2 className={styles.sectionTitle}><Coins size={19} aria-hidden /> Добавить операцию</h2>
          <form onSubmit={submitOperation} className={styles.txForm}>
            <div className={styles.formRow}>
              <label className={styles.formGroup}><span>Тип операции</span><select className={styles.formInput} value={newOperation.operation_type} onChange={event => setNewOperation(current => ({ ...current, operation_type: event.target.value as 'income' | 'expense' }))}><option value="expense">Расход</option><option value="income">Доход</option></select></label>
              <label className={styles.formGroup}><span>Категория</span><select className={styles.formInput} value={newOperation.category} onChange={event => setNewOperation(current => ({ ...current, category: event.target.value }))}><option>Маркетинг</option><option>ФОТ</option><option>Хостинг и ПО</option><option>Продажи</option><option>Офис</option><option>Налоги</option><option>Другое</option></select></label>
              <label className={styles.formGroup}><span>Дата</span><input className={styles.formInput} type="date" value={newOperation.occurred_at} onChange={event => setNewOperation(current => ({ ...current, occurred_at: event.target.value }))} required /></label>
            </div>
            <div className={styles.formRow}>
              <label className={`${styles.formGroup} ${styles.descriptionField}`}><span>Описание и основание</span><input className={styles.formInput} value={newOperation.description} onChange={event => setNewOperation(current => ({ ...current, description: event.target.value }))} placeholder="Например: счёт №123 за хостинг" required /></label>
              <label className={styles.formGroup}><span>Сумма, ₽</span><input className={styles.formInput} type="number" min="0.01" step="0.01" value={newOperation.amount} onChange={event => setNewOperation(current => ({ ...current, amount: event.target.value }))} required /></label>
            </div>
            <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? 'Сохраняем…' : 'Сохранить фактическую операцию'}</button>
          </form>
        </section>

        <section className="card">
          <div className={styles.historyHeader}><div><h2 className={styles.sectionTitle}>История операций</h2><p>Показан выбранный период</p></div><strong>{operations.length}</strong></div>
          {signedOperations.length === 0 && !loading ? (
            <div className={styles.emptyState}><CircleDollarSign size={28} aria-hidden /><strong>Операций пока нет</strong><span>Добавьте первую фактическую операцию — показатели рассчитаются автоматически.</span></div>
          ) : (
            <div className={styles.tableWrapper}>
              <table className={styles.customTable}>
                <thead><tr><th>Дата</th><th>Категория</th><th>Основание</th><th>Сумма</th><th><span className="sr-only">Действия</span></th></tr></thead>
                <tbody>{signedOperations.map(operation => <tr key={operation.id}><td>{formatDate(operation.occurred_at)}</td><td><span className={styles.categoryBadge}>{operation.category}</span></td><td>{operation.description}</td><td className={operation.signedAmount < 0 ? styles.amountExpense : styles.amountIncome}>{operation.signedAmount > 0 ? '+' : ''}{MONEY.format(operation.signedAmount)} ₽</td><td><button type="button" className={styles.deleteButton} onClick={() => void deleteOperation(operation)} aria-label={`Удалить операцию ${operation.description}`}><Trash2 size={16} /></button></td></tr>)}</tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
