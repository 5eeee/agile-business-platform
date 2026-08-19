import { useState } from 'react';
import { DollarSign, ArrowUpRight, ArrowDownRight, TrendingUp, Calendar, Wallet, Percent, PieChart, Coins } from 'lucide-react';
import styles from './Finance.module.css';

interface Transaction {
  id: string;
  date: string;
  category: string;
  description: string;
  amount: number;
  type: 'income' | 'expense';
  status: 'completed' | 'pending';
}

export default function FinancePage() {
  const [period, setPeriod] = useState<'week' | 'month' | 'quarter'>('month');
  const [transactions, setTransactions] = useState<Transaction[]>([
    { id: 't-1', date: '2026-06-14', category: 'Продажи', description: 'Оплата тарифа Agile Workspace (ООО Вектор)', amount: 120000, type: 'income', status: 'completed' },
    { id: 't-2', date: '2026-06-13', category: 'Хостинг', description: 'Оплата серверов AWS & Vercel', amount: -45000, type: 'expense', status: 'completed' },
    { id: 't-3', date: '2026-06-12', category: 'ФОТ', description: 'Выплата бонусов по KPI (Иван Иванов)', amount: -25000, type: 'expense', status: 'completed' },
    { id: 't-4', date: '2026-06-10', category: 'Маркетинг', description: 'Рекламная компания Яндекс.Директ', amount: -60000, type: 'expense', status: 'completed' },
    { id: 't-5', date: '2026-06-08', category: 'Консалтинг', description: 'Индивидуальная настройка интеграций для клиента', amount: 85000, type: 'income', status: 'completed' },
    { id: 't-6', date: '2026-06-05', category: 'ФОТ', description: 'Выплата заработной платы (Разработка)', amount: -320000, type: 'expense', status: 'completed' }
  ]);

  const [newTx, setNewTx] = useState({ category: 'Маркетинг', description: '', amount: '', type: 'expense' as 'income' | 'expense' });

  const handleAddTx = (e: React.FormEvent) => {
    e.preventDefault();
    const amt = parseFloat(newTx.amount);
    if (isNaN(amt) || !newTx.description) return;
    const finalAmount = newTx.type === 'expense' ? -Math.abs(amt) : Math.abs(amt);

    const tx: Transaction = {
      id: `t-${Date.now()}`,
      date: new Date().toISOString().split('T')[0],
      category: newTx.category,
      description: newTx.description,
      amount: finalAmount,
      type: newTx.type,
      status: 'completed'
    };

    setTransactions(prev => [tx, ...prev]);
    setNewTx({ category: 'Маркетинг', description: '', amount: '', type: 'expense' });
  };

  const totals = transactions.reduce(
    (acc, curr) => {
      if (curr.amount > 0) acc.income += curr.amount;
      else acc.expense += Math.abs(curr.amount);
      return acc;
    },
    { income: 0, expense: 0 }
  );

  const profit = totals.income - totals.expense;

  return (
    <div className={`${styles.page} page-enter`}>
      <div className={styles.header}>
        <div>
          <h1>Финансовая аналитика</h1>
          <p className={styles.subtitle}>Контроль доходов, расходов, бюджетов и эффективности инвестиций компании</p>
        </div>
        <div className={styles.periodSelector}>
          <button className={period === 'week' ? styles.periodActive : ''} onClick={() => setPeriod('week')}>Неделя</button>
          <button className={period === 'month' ? styles.periodActive : ''} onClick={() => setPeriod('month')}>Месяц</button>
          <button className={period === 'quarter' ? styles.periodActive : ''} onClick={() => setPeriod('quarter')}>Квартал</button>
        </div>
      </div>

      {/* Financial Metrics Cards */}
      <div className={styles.metricsGrid}>
        <div className={styles.metricCard}>
          <div className={styles.cardHeader}>
            <span className={styles.cardTitle}>Общий оборот (Доходы)</span>
            <div className={`${styles.iconWrapper} ${styles.incomeIcon}`}>
              <ArrowUpRight size={20} />
            </div>
          </div>
          <div className={styles.cardBody}>
            <h2>{totals.income.toLocaleString()} ₽</h2>
            <p className={styles.trendUp}>
              <TrendingUp size={14} /> +12.4% с прошлого периода
            </p>
          </div>
        </div>

        <div className={styles.metricCard}>
          <div className={styles.cardHeader}>
            <span className={styles.cardTitle}>Всего расходов</span>
            <div className={`${styles.iconWrapper} ${styles.expenseIcon}`}>
              <ArrowDownRight size={20} />
            </div>
          </div>
          <div className={styles.cardBody}>
            <h2>{totals.expense.toLocaleString()} ₽</h2>
            <p className={styles.trendDown}>
              Расходная часть оптимизирована на 3.2%
            </p>
          </div>
        </div>

        <div className={styles.metricCard}>
          <div className={styles.cardHeader}>
            <span className={styles.cardTitle}>Чистая прибыль</span>
            <div className={`${styles.iconWrapper} ${styles.profitIcon}`}>
              <DollarSign size={20} />
            </div>
          </div>
          <div className={styles.cardBody}>
            <h2 style={{ color: profit >= 0 ? 'var(--color-primary)' : '#ef4444' }}>
              {profit.toLocaleString()} ₽
            </h2>
            <p className={styles.trendUp}>
              Рентабельность бизнеса (ROI): 45.8%
            </p>
          </div>
        </div>
      </div>

      <div className={styles.layoutGrid}>
        {/* Left column: transaction list & form */}
        <div className={styles.leftCol}>
          <div className="card" style={{ marginBottom: '24px' }}>
            <h3 style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Coins size={18} /> Регистрация финансовой операции
            </h3>
            <form onSubmit={handleAddTx} className={styles.txForm}>
              <div className={styles.formRow}>
                <div className="formGroup" style={{ flex: 1 }}>
                  <label>Тип операции:</label>
                  <select
                    className={styles.formInput}
                    value={newTx.type}
                    onChange={e => setNewTx(prev => ({ ...prev, type: e.target.value as 'income' | 'expense' }))}
                  >
                    <option value="expense">Расход (-)</option>
                    <option value="income">Доход (+)</option>
                  </select>
                </div>
                <div className="formGroup" style={{ flex: 1 }}>
                  <label>Категория:</label>
                  <select
                    className={styles.formInput}
                    value={newTx.category}
                    onChange={e => setNewTx(prev => ({ ...prev, category: e.target.value }))}
                  >
                    <option value="Маркетинг">Маркетинг</option>
                    <option value="ФОТ">ФОТ (Зарплаты / Бонусы)</option>
                    <option value="Хостинг">Хостинг & ПО</option>
                    <option value="Продажи">Продажи / Лицензии</option>
                    <option value="Офис">Офисные расходы</option>
                  </select>
                </div>
              </div>
              <div className={styles.formRow}>
                <div className="formGroup" style={{ flex: 2 }}>
                  <label>Описание:</label>
                  <input
                    type="text"
                    className={styles.formInput}
                    placeholder="Например: Покупка лицензий Figma"
                    value={newTx.description}
                    onChange={e => setNewTx(prev => ({ ...prev, description: e.target.value }))}
                    required
                  />
                </div>
                <div className="formGroup" style={{ flex: 1 }}>
                  <label>Сумма (₽):</label>
                  <input
                    type="number"
                    min="1"
                    className={styles.formInput}
                    placeholder="5000"
                    value={newTx.amount}
                    onChange={e => setNewTx(prev => ({ ...prev, amount: e.target.value }))}
                    required
                  />
                </div>
              </div>
              <button type="submit" className="btn btn-primary btn-sm" style={{ width: '100%', marginTop: '8px' }}>
                Провести операцию
              </button>
            </form>
          </div>

          <div className="card">
            <h3 style={{ marginBottom: '16px' }}>История транзакций</h3>
            <div className={styles.tableWrapper}>
              <table className={styles.customTable}>
                <thead>
                  <tr>
                    <th>Дата</th>
                    <th>Категория</th>
                    <th>Описание</th>
                    <th>Сумма</th>
                    <th>Статус</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map(tx => (
                    <tr key={tx.id}>
                      <td>{tx.date}</td>
                      <td><span className={styles.categoryBadge}>{tx.category}</span></td>
                      <td>{tx.description}</td>
                      <td style={{ fontWeight: 700, color: tx.amount > 0 ? '#10b981' : '#ef4444' }}>
                        {tx.amount > 0 ? `+${tx.amount.toLocaleString()}` : tx.amount.toLocaleString()} ₽
                      </td>
                      <td>
                        <span className={tx.status === 'completed' ? styles.statusSuccess : styles.statusPending}>
                          {tx.status === 'completed' ? 'Выполнено' : 'В обработке'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right column: Budgets & target indices */}
        <div className={styles.rightCol}>
          <div className="card" style={{ marginBottom: '24px' }}>
            <h3 style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <PieChart size={18} /> Распределение бюджетов
            </h3>
            <div className={styles.budgetProgressSection}>
              <div className={styles.budgetProgressItem}>
                <div className={styles.budgetProgressLabel}>
                  <span>Бюджет отдела Разработки</span>
                  <strong>380 000 ₽ / 500 000 ₽</strong>
                </div>
                <div className={styles.progressBar}>
                  <div className={styles.progressFill} style={{ width: '76%', backgroundColor: '#6366f1' }} />
                </div>
              </div>

              <div className={styles.budgetProgressItem}>
                <div className={styles.budgetProgressLabel}>
                  <span>Рекламный бюджет (Маркетинг)</span>
                  <strong>210 000 ₽ / 300 000 ₽</strong>
                </div>
                <div className={styles.progressBar}>
                  <div className={styles.progressFill} style={{ width: '70%', backgroundColor: '#ec4899' }} />
                </div>
              </div>

              <div className={styles.budgetProgressItem}>
                <div className={styles.budgetProgressLabel}>
                  <span>Операционные & Офисные расходы</span>
                  <strong>95 000 ₽ / 150 000 ₽</strong>
                </div>
                <div className={styles.progressBar}>
                  <div className={styles.progressFill} style={{ width: '63.3%', backgroundColor: '#f59e0b' }} />
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <h3 style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Percent size={18} /> Эффективность инвестиций (ROI)
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div className={styles.roiItem}>
                <div>
                  <strong>SEO & Контент-маркетинг</strong>
                  <p className={styles.roiSub}>Расходы: 80 000 ₽ • Выручка: 350 000 ₽</p>
                </div>
                <span className={styles.roiBadge}>ROI +337%</span>
              </div>
              <div className={styles.roiItem}>
                <div>
                  <strong>Яндекс.Директ (Контекст)</strong>
                  <p className={styles.roiSub}>Расходы: 120 000 ₽ • Выручка: 280 000 ₽</p>
                </div>
                <span className={styles.roiBadge}>ROI +133%</span>
              </div>
              <div className={styles.roiItem}>
                <div>
                  <strong>Партнерская сеть</strong>
                  <p className={styles.roiSub}>Расходы: 40 000 ₽ • Выручка: 160 000 ₽</p>
                </div>
                <span className={styles.roiBadge}>ROI +300%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
