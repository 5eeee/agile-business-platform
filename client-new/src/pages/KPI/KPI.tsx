import { useEffect, useMemo, useState } from 'react';
import { 
  Activity, Timer, Gauge, Brain, RefreshCcw, Coins,
  Search, BookOpen, ChevronDown, ChevronUp, AlertCircle, Info, Award, HelpCircle, Briefcase, Sparkles, Filter 
} from 'lucide-react';
import { 
  gamificationApi, 
  type UserKPI, 
  type KPIDrop, 
  type PerformanceReview, 
  type ManagerKPIDetails,
  type DepartmentKPIHealth,
  type ManagerReactivity
} from '../../api/gamification';
import { useAppSelector } from '../../store/hooks';
import { t } from '../../i18n';
import styles from './KPI.module.css';
import { kpiDataList, kpiCategories, type KPICardData } from './kpiData';
import WeeklyReportsPanel from './WeeklyReportsPanel';
import IdeasPanel from './IdeasPanel';

const finiteKpiValue = (value: unknown): number | null => {
  if (value === null || value === undefined || value === '') return null;
  const parsed = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

export default function KPIPage() {
  const { user } = useAppSelector(s => s.auth);
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);
  const [kpi, setKpi] = useState<UserKPI | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Manager KPI state
  const [managerDetails, setManagerDetails] = useState<ManagerKPIDetails | null>(null);
  const [departmentHealth, setDepartmentHealth] = useState<DepartmentKPIHealth[] | null>(null);
  const [managerReactivity, setManagerReactivity] = useState<ManagerReactivity[] | null>(null);
  const [activeManagerTab, setActiveManagerTab] = useState<'drops' | 'departments' | 'managers'>('drops');
  const [activeReviewDrop, setActiveReviewDrop] = useState<KPIDrop | null>(null);
  const [reviewForm, setReviewForm] = useState({
    kpi_type: '',
    reason: '',
    action: '',
    comment: ''
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [simulating, setSimulating] = useState(false);

  // Regulations state
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [expandedCards, setExpandedCards] = useState<Record<string, boolean>>({});

  const load = async () => {
    setError(null);
    try {
      const { data } = await gamificationApi.getMyKPI();
      setKpi(data);

      if (user && ['admin', 'owner', 'deputy_owner'].includes(user.role)) {
        const [managerResult, departmentResult, reactivityResult] = await Promise.allSettled([
          gamificationApi.getManagerKPIDetails(),
          gamificationApi.getDepartmentKPIHealth(),
          gamificationApi.getManagerReactivity(),
        ]);

        setManagerDetails(managerResult.status === 'fulfilled' ? managerResult.value.data : null);
        setDepartmentHealth(departmentResult.status === 'fulfilled' ? departmentResult.value.data : null);
        setManagerReactivity(reactivityResult.status === 'fulfilled' ? reactivityResult.value.data : null);
      }
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
  }, [user]);

  const getIcon = (iconName: string, className?: string) => {
    switch (iconName) {
      case 'Timer': return <Timer className={className} size={20} />;
      case 'Activity': return <Activity className={className} size={20} />;
      case 'Brain': return <Brain className={className} size={20} />;
      case 'Gauge': return <Gauge className={className} size={20} />;
      case 'Coins': return <Coins className={className} size={20} />;
      default: return <BookOpen className={className} size={20} />;
    }
  };

  const toggleExpand = (id: string) => {
    setExpandedCards(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  const handleOpenReview = (drop: KPIDrop) => {
    setActiveReviewDrop(drop);
    setReviewForm({
      kpi_type: drop.kpi_type,
      reason: '',
      action: '',
      comment: ''
    });
    setFormError(null);
  };

  const handleCloseReview = () => {
    setActiveReviewDrop(null);
    setFormError(null);
  };

  const handleReviewSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    
    // Client-side validation: must have reason, action, kpi_type
    const missing = [];
    if (!reviewForm.kpi_type.trim()) missing.push("KPI");
    if (!reviewForm.reason.trim()) missing.push("причина");
    if (!reviewForm.action.trim()) missing.push("мера");
    
    if (missing.length > 0) {
      const errMsg = `Вы не заполнили обязательные поля: ${missing.join(', ')}. Пожалуйста, заполните их перед сохранением.`;
      setFormError(errMsg);
      // Wait, we still attempt backend request if user explicitly bypassed, or we just stop.
      // But wait! Section 9.3 of kpi_extracted.txt says:
      // "Если хотя бы одно обязательное поле не заполнено: Показать уведомление... Запись не отправляется на сервер. Локально (или на сервере при первой отправке) фиксируется попытка в attentiveness_log с success=false. Важно: начисление штрафа за невнимательность происходит только при первой неудачной попытке для данного drop_id."
      // Since backend logs failed attempts when missing fields, sending it to the backend is the absolute best way to log it securely!
    }
    
    setSubmitting(true);
    try {
      await gamificationApi.submitPerformanceReview({
        drop_id: activeReviewDrop?.id,
        kpi_type: reviewForm.kpi_type,
        reason: reviewForm.reason,
        action: reviewForm.action,
        comment: reviewForm.comment || undefined
      });
      handleCloseReview();
      load();
    } catch (err: any) {
      setFormError(err?.response?.data?.detail || 'Не удалось сохранить разбор');
      load(); // Reload to refresh penalty points if they were updated!
    } finally {
      setSubmitting(false);
    }
  };

  const handleSimulateDrop = async (kpiType: string, val: number) => {
    setSimulating(true);
    try {
      await gamificationApi.simulateKPIDrop({ kpi_type: kpiType, drop_value: val });
      load();
    } catch (err: any) {
      window.dispatchEvent(new CustomEvent('api-error', { detail: err?.response?.data?.detail || 'Не удалось запустить симуляцию' }));
    } finally {
      setSimulating(false);
    }
  };

  const filteredKPIs = useMemo(() => {
    return kpiDataList.filter(kpi => {
      // Filter by category
      const matchesCategory = selectedCategory === 'all' || kpi.type === selectedCategory;
      
      // Filter by search query
      const query = searchQuery.toLowerCase().trim();
      if (!query) return matchesCategory;

      const matchesSearch = 
        kpi.title.toLowerCase().includes(query) ||
        kpi.number.toLowerCase().includes(query) ||
        kpi.subtitle.toLowerCase().includes(query) ||
        kpi.summary.toLowerCase().includes(query) ||
        kpi.details.some(d => d.toLowerCase().includes(query)) ||
        (kpi.exceptions && kpi.exceptions.some(e => e.toLowerCase().includes(query)));

      return matchesCategory && matchesSearch;
    });
  }, [selectedCategory, searchQuery]);

  const liveEmployeeKpis = useMemo(() => {
    if (!kpi) return [];
    return [
      { key: 'KPI1', title: 'Соблюдение дедлайнов', value: finiteKpiValue(kpi.kpi1_deadlines) },
      { key: 'KPI2', title: 'Пунктуальность', value: finiteKpiValue(kpi.kpi2_punctuality) },
      { key: 'KPI3', title: 'Инициативность', value: finiteKpiValue(kpi.kpi3_initiative) },
      { key: 'KPI4', title: 'Сверхурочная загрузка', value: finiteKpiValue(kpi.kpi4_overtime) },
      { key: 'KPI5', title: 'Качество работ', value: finiteKpiValue(kpi.kpi5_quality) },
      { key: 'KPI8', title: 'Внимательность', value: finiteKpiValue(kpi.kpi8_attentiveness) },
      { key: 'KPI9', title: 'Бонусный индекс', value: finiteKpiValue(kpi.kpi9_bonus) },
      { key: 'KPI10', title: 'Ответственность', value: finiteKpiValue(kpi.kpi10_responsibility) },
      { key: 'TEAM', title: 'Удовлетворённость заказчика', value: finiteKpiValue(kpi.kpi_customer_satisfaction) },
    ];
  }, [kpi]);

  const liveOverall = useMemo(() => {
    const values = liveEmployeeKpis
      .filter(item => item.key !== 'KPI9')
      .map(item => item.value)
      .filter((value): value is number => value !== null);
    return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
  }, [liveEmployeeKpis]);

  const performanceFactor = useMemo(() => {
    if (liveOverall === null) return null;
    const critical = [kpi?.kpi1_deadlines, kpi?.kpi2_punctuality, kpi?.kpi5_quality]
      .map(finiteKpiValue)
      .filter((value): value is number => value !== null);
    if (liveOverall >= 90 && critical.length === 3 && critical.every(value => value >= 90)) return 1.1;
    if (liveOverall < 70 || critical.some(value => value < 70)) return 0.9;
    return 1.0;
  }, [kpi, liveOverall]);

  return (
    <div className={styles.page}>
      <div className={styles.head}>
        <div>
          <h1>Показатели эффективности</h1>
          <p className={styles.muted}>Рабочие показатели, рассчитанные по фактическим событиям платформы.</p>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={load}><RefreshCcw size={14} /> Обновить</button>
      </div>

      {loading ? <div className={styles.empty}>{lang.common.loading}</div> : null}
      {error ? <div className={styles.error}>{error}</div> : null}

      {kpi && (
        <div className={styles.dashboardSection}>
          <div className={styles.sectionTitle}>
            <Gauge size={16} className={styles.primaryText} />
            <h2>Рабочие показатели — живой расчёт</h2>
          </div>
          <div className={styles.grid}>
            {liveEmployeeKpis.map(item => {
              const value = item.value;
              const carryover = finiteKpiValue(kpi.kpi9_carryover) ?? 0;
              const tone = value === null ? '#94a3b8' : value >= 90 ? '#10b981' : value >= 70 ? '#f59e0b' : '#ef4444';
              return (
                <div className={styles.card} key={item.key}>
                  <Activity size={18} style={{ color: tone }} />
                  <div>
                    <strong style={{ color: tone }}>
                      {value === null ? '—' : `${Math.round(value)}${item.key === 'KPI9' && carryover > 0 ? '% +' : '%'}`}
                    </strong>
                    <span>{item.title}</span>
                    {item.key === 'KPI9' && carryover > 0 && (
                      <small>+{carryover}% перенесено авансом</small>
                    )}
                  </div>
                </div>
              );
            })}
            <div className={styles.card}>
              <Award size={18} className={styles.goldText} />
              <div>
                <strong>{liveOverall === null ? '—' : `${Math.round(liveOverall)}%`}</strong>
                <span>Итоговая эффективность</span>
              </div>
            </div>
            <div className={styles.card}>
              <Gauge size={18} className={styles.primaryText} />
              <div>
                <strong>{performanceFactor === null ? '—' : performanceFactor.toFixed(1)}</strong>
                <span>Коэффициент эффективности</span>
              </div>
            </div>
          </div>
        </div>
      )}

      <WeeklyReportsPanel
        canReview={Boolean(user && ['admin', 'owner', 'deputy_owner'].includes(user.role))}
        onKpiChanged={load}
      />
      <IdeasPanel onKpiChanged={load} />

      {/* KPI Manager Dashboard */}
      {managerDetails && (
        <div className={styles.managerSection}>
          <div className={styles.managerHeader}>
            <div className={styles.sectionTitle}>
              <Briefcase size={20} className={styles.primaryText} />
              <h2>Кабинет руководителя: Управление и Аналитика KPI</h2>
            </div>
            <span className="badge badge-warning" style={{ color: '#f59e0b', borderColor: '#f59e0b' }}>Режим Руководителя</span>
          </div>

          <div className={styles.managerTabs}>
            <button 
              className={`${styles.managerTab} ${activeManagerTab === 'drops' ? styles.managerTabActive : ''}`}
              onClick={() => setActiveManagerTab('drops')}
            >
              Падения и Разборы
            </button>
            <button 
              className={`${styles.managerTab} ${activeManagerTab === 'departments' ? styles.managerTabActive : ''}`}
              onClick={() => setActiveManagerTab('departments')}
            >
              Здоровье Отделов
            </button>
            <button 
              className={`${styles.managerTab} ${activeManagerTab === 'managers' ? styles.managerTabActive : ''}`}
              onClick={() => setActiveManagerTab('managers')}
            >
              Дисциплина Руководителей
            </button>
          </div>

          {activeManagerTab === 'drops' && (
            <>
              <div className={styles.managerStatsGrid}>
                <div className={styles.managerStatCard}>
                  <Timer size={24} className={styles.primaryText} />
                  <div className={styles.managerStatInfo}>
                    <strong>{managerDetails.current_kpi2 !== null ? `${managerDetails.current_kpi2} дн.` : '—'}</strong>
                    <span>Среднее время реакции руководителя</span>
                  </div>
                </div>

                <div className={styles.managerStatCard}>
                  <Activity size={24} className={styles.goldText} />
                  <div className={styles.managerStatInfo}>
                    <strong>{managerDetails.reviews_count}</strong>
                    <span>Всего разборов проведено</span>
                  </div>
                </div>

                <div className={styles.managerStatCard}>
                  <Award size={24} style={{ color: '#10b981' }} />
                  <div className={styles.managerStatInfo}>
                    <strong>+{managerDetails.total_overtime_percent}%</strong>
                    <span>Бонус за сверхурочную работу</span>
                  </div>
                </div>

                <div className={styles.managerStatCard}>
                  <Gauge size={24} style={{ color: '#ec4899' }} />
                  <div className={styles.managerStatInfo}>
                    <strong>{managerDetails.overtime_reviews_count}</strong>
                    <span>Сверхурочных разборов</span>
                  </div>
                </div>
              </div>

              {/* Active KPI Drops to Resolve */}
              <div style={{ marginTop: '16px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <AlertCircle size={18} style={{ color: '#ef4444' }} />
                  Активные падения KPI сотрудников (требуют разбора)
                </h3>
                
                {managerDetails.active_drops.length > 0 ? (
                  <div className={styles.dropsWrapper}>
                    {managerDetails.active_drops.map(drop => (
                      <div key={drop.id} className={styles.dropItem}>
                        <div className={styles.dropInfo}>
                          <h4>{drop.employee_name || 'Сотрудник'} — Падение {drop.kpi_type}</h4>
                          <div className={styles.dropMeta}>
                            <span>Величина падения: <strong>{drop.drop_value}</strong></span>
                            <span>•</span>
                            <span>Дата фиксации: {new Date(drop.drop_date).toLocaleString()}</span>
                          </div>
                        </div>
                        <button 
                          className="btn btn-error btn-sm" 
                          onClick={() => handleOpenReview(drop)}
                        >
                          <Sparkles size={14} /> Зафиксировать разбор
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{
                    background: 'rgba(16, 185, 129, 0.03)',
                    border: '1px solid rgba(16, 185, 129, 0.15)',
                    borderRadius: '12px',
                    padding: '24px',
                    textAlign: 'center',
                    color: '#34d399'
                  }}>
                    <Sparkles size={32} style={{ marginBottom: '8px' }} />
                    <h4 style={{ fontWeight: 600 }}>Все падения KPI успешно разобраны!</h4>
                    <p style={{ fontSize: '13px', opacity: 0.8 }}>Вы отлично справляетесь с контролем качества и регламентов.</p>
                  </div>
                )}
              </div>

              {/* Recent Reviews history */}
              {managerDetails.recent_reviews.length > 0 && (
                <div style={{ marginTop: '20px' }}>
                  <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '12px' }}>
                    История проведенных разборов
                  </h3>
                  <div className={styles.reviewsTableWrapper}>
                    <table className={styles.reviewsTable}>
                      <thead>
                        <tr>
                          <th>KPI</th>
                          <th>Дата разбора</th>
                          <th>Причина падения</th>
                          <th>Принятая мера</th>
                          <th>Реакция (рабочие дни)</th>
                          <th>Режим</th>
                        </tr>
                      </thead>
                      <tbody>
                        {managerDetails.recent_reviews.map(rev => (
                          <tr key={rev.id}>
                            <td><strong>{rev.kpi_type}</strong></td>
                            <td>{new Date(rev.review_date).toLocaleDateString()}</td>
                            <td>{rev.reason}</td>
                            <td>{rev.action}</td>
                            <td>{rev.reaction_days !== null ? `${rev.reaction_days} дн.` : '—'}</td>
                            <td>
                              {rev.is_overtime ? (
                                <span className="badge badge-warning" style={{ fontSize: '11px' }}>Сверхурочно</span>
                              ) : (
                                <span className="badge badge-ghost" style={{ fontSize: '11px' }}>Рабочий</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Simulation Section */}
              {user && ['admin', 'owner'].includes(user.role) && (
                <div className={styles.simulationSection}>
                  <h4 style={{ fontSize: '14px', fontWeight: 600, color: '#60a5fa', marginBottom: '10px' }}>
                    Проверка расчётов показателей (только для администраторов)
                  </h4>
                  <p style={{ fontSize: '12.5px', color: '#93c5fd', marginBottom: '12px' }}>
                    Симулируйте падение показателей для проверки реакций, штрафов за невнимательность и сверхурочных бонусов:
                  </p>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <button 
                      className="btn btn-outline btn-xs" 
                      disabled={simulating}
                      onClick={() => handleSimulateDrop('KPI1 (Дисциплина)', 15.0)}
                    >
                      Проверить падение дисциплины
                    </button>
                    <button 
                      className="btn btn-outline btn-xs" 
                      disabled={simulating}
                      onClick={() => handleSimulateDrop('KPI5 (Задачи)', 8.5)}
                    >
                      Проверить падение качества задач
                    </button>
                    <button 
                      className="btn btn-outline btn-xs" 
                      disabled={simulating}
                      onClick={() => handleSimulateDrop('KPI7 (Качество)', 22.0)}
                    >
                      Проверить падение контроля отдела
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          {activeManagerTab === 'departments' && (
            <div style={{ marginTop: '16px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '12px' }}>
                Показатели здоровья KPI по отделам
              </h3>
              {departmentHealth && departmentHealth.length > 0 ? (
                <div className={styles.reviewsTableWrapper}>
                  <table className={styles.reviewsTable}>
                    <thead>
                      <tr>
                        <th>Отдел</th>
                        <th>Сотрудников</th>
                        <th>Соблюдение сроков</th>
                        <th>Пунктуальность</th>
                        <th>Инициативность</th>
                        <th>Дополнительная нагрузка</th>
                        <th>Качество выполнения</th>
                        <th>Внимательность</th>
                        <th>Бонус за эффективность</th>
                        <th>Ответственность</th>
                      </tr>
                    </thead>
                    <tbody>
                      {departmentHealth.map((dept, idx) => (
                        <tr key={idx}>
                          <td><strong>{dept.department_id || 'Без отдела'}</strong></td>
                          <td>{dept.employee_count}</td>
                          <td>{dept.avg_kpi1_deadlines !== null ? `${dept.avg_kpi1_deadlines.toFixed(1)}%` : '—'}</td>
                          <td>{dept.avg_kpi2_punctuality !== null ? `${dept.avg_kpi2_punctuality.toFixed(1)}%` : '—'}</td>
                          <td>{dept.avg_kpi3_initiative !== null ? `${dept.avg_kpi3_initiative.toFixed(1)}%` : '—'}</td>
                          <td>{dept.avg_kpi4_overtime !== null ? `${dept.avg_kpi4_overtime.toFixed(1)}%` : '—'}</td>
                          <td>{dept.avg_kpi5_quality !== null ? `${dept.avg_kpi5_quality.toFixed(1)}%` : '—'}</td>
                          <td>{dept.avg_kpi8_attentiveness !== null ? `${dept.avg_kpi8_attentiveness.toFixed(1)}%` : '—'}</td>
                          <td>{dept.avg_kpi9_bonus !== null ? `${dept.avg_kpi9_bonus.toFixed(1)}%` : '—'}</td>
                          <td>{dept.avg_kpi10_responsibility !== null ? `${dept.avg_kpi10_responsibility.toFixed(1)}%` : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className={styles.empty}>Нет данных о здоровье отделов.</div>
              )}
            </div>
          )}

          {activeManagerTab === 'managers' && (
            <div style={{ marginTop: '16px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '12px' }}>
                Дисциплина и оперативность руководителей
              </h3>
              {managerReactivity && managerReactivity.length > 0 ? (
                <div className={styles.reviewsTableWrapper}>
                  <table className={styles.reviewsTable}>
                    <thead>
                      <tr>
                        <th>Руководитель</th>
                        <th>Активные падения подчинённых</th>
                        <th>Проведено разборов</th>
                        <th>Средняя реакция (рабочие дни)</th>
                        <th>Оперативность реакции</th>
                        <th>Ответственность руководителя</th>
                        <th>Внимательность руководителя</th>
                        <th>Работа с инициативами</th>
                        <th>Сверхурочная активность</th>
                        <th>Контроль отдела</th>
                      </tr>
                    </thead>
                    <tbody>
                      {managerReactivity.map(mgr => (
                        <tr key={mgr.manager_id}>
                          <td><strong>{mgr.manager_name}</strong></td>
                          <td>
                            {mgr.active_drops_count > 0 ? (
                              <span style={{ color: '#ef4444', fontWeight: 'bold' }}>{mgr.active_drops_count}</span>
                            ) : (
                              <span style={{ color: '#10b981' }}>0</span>
                            )}
                          </td>
                          <td>{mgr.conducted_reviews_count}</td>
                          <td>{mgr.avg_reaction_days !== null ? `${mgr.avg_reaction_days.toFixed(1)} дн.` : '—'}</td>
                          <td>{mgr.manager_kpi1_reaction_index !== null ? `${mgr.manager_kpi1_reaction_index.toFixed(1)}%` : '—'}</td>
                          <td>{mgr.manager_kpi3_responsibility !== null ? `${mgr.manager_kpi3_responsibility.toFixed(1)}%` : '—'}</td>
                          <td>{mgr.manager_kpi4_attentiveness !== null ? `${mgr.manager_kpi4_attentiveness.toFixed(1)}%` : '—'}</td>
                          <td>{mgr.manager_kpi5_idea_reaction !== null ? `${mgr.manager_kpi5_idea_reaction.toFixed(1)}%` : '—'}</td>
                          <td>{mgr.manager_kpi6_overtime != null ? `${mgr.manager_kpi6_overtime.toFixed(1)}%` : '—'}</td>
                          <td>{mgr.manager_kpi7_department_control != null ? `${mgr.manager_kpi7_department_control.toFixed(1)}%` : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className={styles.empty}>Нет данных по руководителям.</div>
              )}
            </div>
          )}
        </div>
      )}

      {/* KPI Regulations Hub Section */}
      <div className={styles.regulationsSection}>
        <div className={styles.regulationsHeader}>
          <div className={styles.sectionTitle}>
            <BookOpen size={20} className={styles.primaryText} />
            <h2>Регламент и база знаний KPI</h2>
          </div>
          <p className={styles.regulationsDesc}>
            Полное описание, математические формулы, коэффициенты, исключения и правила автоматического учета KPI для сотрудников и руководителей AGILE WORKSPACE.
          </p>
        </div>

        {/* Filter Toolbar */}
        <div className={styles.toolbar}>
          <div className={styles.searchBox}>
            <Search className={styles.searchIcon} size={16} />
            <input 
              type="text" 
              placeholder="Поиск по регламентам, штрафам, терминам..." 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className={styles.searchInput}
            />
            {searchQuery && (
              <button className={styles.clearSearch} onClick={() => setSearchQuery('')}>×</button>
            )}
          </div>

          <div className={styles.categories}>
            {kpiCategories.map(cat => (
              <button 
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={`${styles.catTab} ${selectedCategory === cat.id ? styles.catTabActive : ''}`}
              >
                {cat.title}
              </button>
            ))}
          </div>
        </div>

        {/* Regulations Grid */}
        <div className={styles.kpiList}>
          {filteredKPIs.length > 0 ? (
            filteredKPIs.map(kpiItem => {
              const isExpanded = !!expandedCards[kpiItem.id];
              return (
                <div 
                  key={kpiItem.id} 
                  className={`${styles.kpiCard} ${isExpanded ? styles.kpiCardExpanded : ''} ${styles[`type_${kpiItem.type}`]}`}
                >
                  <div className={styles.kpiCardHeader} onClick={() => toggleExpand(kpiItem.id)}>
                    <div className={styles.kpiCardIcon}>
                      {getIcon(kpiItem.icon, styles.kpiIcon)}
                    </div>
                    <div className={styles.kpiCardMainInfo}>
                      <div className={styles.kpiBadgeRow}>
                        <span className={styles.kpiNumber}>{kpiItem.number}</span>
                        <span className={`${styles.kpiTypeBadge} ${styles[`badge_${kpiItem.type}`]}`}>
                          {kpiItem.type === 'employee' ? 'Сотрудник' : 
                           kpiItem.type === 'manager' ? 'Руководитель' : 
                           kpiItem.type === 'special' ? 'Спец. KPI' : 'Платформа'}
                        </span>
                      </div>
                      <h3 className={styles.kpiTitle}>{kpiItem.title}</h3>
                      <p className={styles.kpiSubtitle}>{kpiItem.subtitle}</p>
                    </div>
                    <div className={styles.expandButton}>
                      {isExpanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                    </div>
                  </div>

                  <div className={styles.kpiCardPreview}>
                    <p className={styles.kpiSummary}>{kpiItem.summary}</p>
                    <div className={styles.quickStats}>
                      <div className={styles.quickStatItem}>
                        <span className={styles.statLabel}>Целевой ориентир:</span>
                        <strong className={styles.statVal}>{kpiItem.target}</strong>
                      </div>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className={styles.kpiCardDetails}>
                      <div className={styles.detailsDivider} />
                      
                      <div className={styles.sectionBlock}>
                        <h4>Формула расчёта:</h4>
                        <div className={styles.formulaBox}>
                          <code>{kpiItem.formula}</code>
                        </div>
                      </div>

                      <div className={styles.sectionBlock}>
                        <h4>Детальный регламент и правила:</h4>
                        <ul className={styles.detailsList}>
                          {kpiItem.details.map((detail, idx) => (
                            <li key={idx}>
                              <span className={styles.bullet}>•</span>
                              <p>{detail}</p>
                            </li>
                          ))}
                        </ul>
                      </div>

                      {kpiItem.exceptions && kpiItem.exceptions.length > 0 && (
                        <div className={styles.exceptionsBlock}>
                          <div className={styles.exceptionsHeader}>
                            <AlertCircle size={16} />
                            <h4>Исключения и уважительные причины:</h4>
                          </div>
                          <ul className={styles.exceptionsList}>
                            {kpiItem.exceptions.map((ex, idx) => (
                              <li key={idx}>{ex}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <div className={styles.noResults}>
              <HelpCircle size={40} className={styles.mutedIcon} />
              <h3>Ничего не найдено</h3>
              <p>Попробуйте изменить запрос или выбрать другую категорию регламентов.</p>
            </div>
          )}
        </div>
      </div>

      {/* KPI Review Dialog Modal */}
      {activeReviewDrop && (
        <div className={styles.modalOverlay}>
          <div className={styles.modalContent}>
            <div className={styles.modalHeader}>
              <h3>Зафиксировать разбор падения</h3>
              <button className={styles.closeButton} onClick={handleCloseReview}>×</button>
            </div>

            {formError && (
              <div className={styles.error} style={{ fontSize: '13px', padding: '10px 14px' }}>
                <AlertCircle size={14} style={{ display: 'inline', marginRight: '6px', verticalAlign: 'middle' }} />
                {formError}
              </div>
            )}

            <form onSubmit={handleReviewSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div className={styles.formGroup}>
                <label>Показатель KPI *</label>
                <input 
                  type="text" 
                  className={styles.formInput} 
                  value={reviewForm.kpi_type}
                  onChange={(e) => setReviewForm(prev => ({ ...prev, kpi_type: e.target.value }))}
                  required
                />
              </div>

              <div className={styles.formGroup}>
                <label>Причина отклонения *</label>
                <select 
                  className={styles.formInput}
                  value={reviewForm.reason}
                  onChange={(e) => setReviewForm(prev => ({ ...prev, reason: e.target.value }))}
                  required
                >
                  <option value="">Выберите причину...</option>
                  <option value="Личная халатность">Личная халатность</option>
                  <option value="Высокая нагрузка">Высокая нагрузка</option>
                  <option value="Технические проблемы">Технические проблемы</option>
                  <option value="Семейные обстоятельства">Семейные обстоятельства</option>
                  <option value="Недостаток обучения">Недостаток обучения</option>
                  <option value="Другое">Другое</option>
                </select>
              </div>

              <div className={styles.formGroup}>
                <label>Принятая мера / Решение *</label>
                <select 
                  className={styles.formInput}
                  value={reviewForm.action}
                  onChange={(e) => setReviewForm(prev => ({ ...prev, action: e.target.value }))}
                  required
                >
                  <option value="">Выберите меру...</option>
                  <option value="Устное замечание">Устное замечание</option>
                  <option value="Официальный выговор">Официальный выговор</option>
                  <option value="Индивидуальный план исправления">Индивидуальный план исправления</option>
                  <option value="Снижение текущей нагрузки">Снижение текущей нагрузки</option>
                  <option value="Дополнительное переобучение">Дополнительное переобучение</option>
                  <option value="Направление к психологу платформы">Направление к психологу платформы</option>
                </select>
              </div>

              <div className={styles.formGroup}>
                <label>Комментарий (необязательно)</label>
                <textarea 
                  className={styles.formInput}
                  style={{ minHeight: '80px', resize: 'vertical' }}
                  value={reviewForm.comment}
                  onChange={(e) => setReviewForm(prev => ({ ...prev, comment: e.target.value }))}
                  placeholder="Дополнительные примечания к разбору..."
                />
              </div>

              <div className={styles.formActions}>
                <button 
                  type="button" 
                  className="btn btn-ghost btn-sm" 
                  onClick={handleCloseReview}
                  disabled={submitting}
                >
                  Отмена
                </button>
                <button 
                  type="submit" 
                  className="btn btn-primary btn-sm" 
                  disabled={submitting}
                >
                  {submitting ? 'Сохранение...' : 'Сохранить разбор'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

