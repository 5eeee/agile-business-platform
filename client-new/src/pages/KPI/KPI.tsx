import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { 
  Activity, Timer, Gauge, Brain, RefreshCcw, Coins,
  Search, BookOpen, ChevronDown, ChevronUp, AlertCircle, Info, Award, HelpCircle, Briefcase, Sparkles, Filter,
  ArrowLeft, Building2, Clock3, UserRound, ClipboardCheck, ChevronRight, X, CalendarRange
} from 'lucide-react';
import { 
  gamificationApi, 
  type UserKPI, 
  type KPIDrop, 
  type PerformanceReview, 
  type ManagerKPIDetails,
  type DepartmentKPIHealth,
  type ManagerReactivity,
  type KPIDetail,
} from '../../api/gamification';
import { useAppSelector } from '../../store/hooks';
import api from '../../api/client';
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

const ROLE_LABELS: Record<string, string> = {
  owner: 'Владелец',
  deputy_owner: 'Заместитель владельца',
  admin: 'Руководитель отдела',
  user: 'Штатный сотрудник',
  intern: 'Стажёр',
  consultant: 'Консультант',
};

const valueTone = (value: number | null) => {
  if (value === null) return 'neutral';
  if (value >= 90) return 'success';
  if (value >= 70) return 'warning';
  return 'danger';
};

export default function KPIPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAppSelector(s => s.auth);
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);
  const [kpi, setKpi] = useState<UserKPI | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<KPIDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');

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
  const targetUserId = searchParams.get('user');
  const canInspectTeam = Boolean(user && ['admin', 'owner', 'deputy_owner'].includes(user.role));
  const isViewingOther = Boolean(targetUserId && targetUserId !== user?.id && canInspectTeam);

  // Regulations state
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [expandedCards, setExpandedCards] = useState<Record<string, boolean>>({});

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const { data: rawKpi } = isViewingOther && targetUserId
        ? await gamificationApi.getUserKPI(targetUserId)
        : await gamificationApi.getMyKPI();
      // Совместимость на время rolling deploy backend: старая схема KPI не
      // возвращала роль и должностную группу. Берём организационные данные из
      // профиля и никогда не показываем руководителя как рядового сотрудника.
      let profileRole = user?.role;
      let profileDepartment = user?.department_id ?? null;
      if (isViewingOther && targetUserId) {
        const profile = await api.get(`/users/${encodeURIComponent(targetUserId)}`);
        profileRole = profile.data?.role;
        profileDepartment = profile.data?.department_id ?? null;
      }
      const effectiveRole = rawKpi.role || profileRole || 'user';
      const isLeadershipRole = ['admin', 'owner', 'deputy_owner'].includes(effectiveRole);
      const data: UserKPI = {
        ...rawKpi,
        role: effectiveRole as UserKPI['role'],
        department_id: rawKpi.department_id ?? profileDepartment,
        has_occupational_kpi: rawKpi.has_occupational_kpi ?? isLeadershipRole,
      };
      setKpi(data);

      if (canInspectTeam && !isViewingOther) {
        const [managerResult, departmentResult, reactivityResult] = await Promise.allSettled([
          gamificationApi.getManagerKPIDetails(),
          gamificationApi.getDepartmentKPIHealth(),
          gamificationApi.getManagerReactivity(),
        ]);

        setManagerDetails(managerResult.status === 'fulfilled' ? managerResult.value.data : null);
        setDepartmentHealth(departmentResult.status === 'fulfilled' ? departmentResult.value.data : null);
        setManagerReactivity(reactivityResult.status === 'fulfilled' ? reactivityResult.value.data : null);
      } else {
        setManagerDetails(null);
        setDepartmentHealth(null);
        setManagerReactivity(null);
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
  }, [user, targetUserId]);

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

  const openKpiDetail = async (key: string) => {
    setDetailLoading(true);
    setDetailError('');
    setDetail(null);
    try {
      const { data } = await gamificationApi.getKPIDetails(key, isViewingOther ? targetUserId : null);
      setDetail(data);
    } catch (requestError: any) {
      setDetailError(requestError?.response?.data?.detail || 'Не удалось загрузить историю показателя');
    } finally {
      setDetailLoading(false);
    }
  };

  const closeKpiDetail = () => {
    setDetail(null);
    setDetailError('');
    setDetailLoading(false);
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

  const occupationalKpis = useMemo(() => {
    if (!kpi?.has_occupational_kpi) return [];
    return [
      { key: 'M1', title: 'Реакция на падения сотрудников', value: finiteKpiValue(kpi.manager_kpi1_reaction_index) },
      { key: 'M3', title: 'Ответственность руководителя', value: finiteKpiValue(kpi.manager_kpi3_responsibility) },
      { key: 'M4', title: 'Внимательность руководителя', value: finiteKpiValue(kpi.manager_kpi4_attentiveness) },
      { key: 'M5', title: 'Работа с инициативами', value: finiteKpiValue(kpi.manager_kpi5_idea_reaction) },
      { key: 'M6', title: 'Сверхурочная активность', value: finiteKpiValue(kpi.manager_kpi6_overtime) },
      { key: 'M7', title: 'Контроль показателей отдела', value: finiteKpiValue(kpi.manager_kpi7_department_control) },
    ];
  }, [kpi]);

  const calculatedGeneral = useMemo(() => {
    const values = liveEmployeeKpis
      .filter(item => item.key !== 'KPI9')
      .map(item => item.value)
      .filter((value): value is number => value !== null);
    return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
  }, [liveEmployeeKpis]);

  const generalScore = finiteKpiValue(kpi?.general_score) ?? calculatedGeneral;
  const occupationalScore = finiteKpiValue(kpi?.occupational_score);
  const overallScore = finiteKpiValue(kpi?.overall_score) ?? generalScore;

  const performanceFactor = useMemo(() => {
    if (generalScore === null) return null;
    const critical = [kpi?.kpi1_deadlines, kpi?.kpi2_punctuality, kpi?.kpi5_quality]
      .map(finiteKpiValue)
      .filter((value): value is number => value !== null);
    if (generalScore >= 90 && critical.length === 3 && critical.every(value => value >= 90)) return 1.1;
    if (generalScore < 70 || critical.some(value => value < 70)) return 0.9;
    return 1.0;
  }, [kpi, generalScore]);

  return (
    <div className={styles.page}>
      <div className={styles.head}>
        <div>
          {isViewingOther && (
            <button className={styles.backButton} type="button" onClick={() => navigate(-1)}>
              <ArrowLeft size={16} /> Назад к команде
            </button>
          )}
          <h1>{isViewingOther ? `KPI · ${kpi?.user_name || 'Сотрудник'}` : 'Показатели эффективности'}</h1>
          <p className={styles.muted}>Два уровня оценки: общие рабочие показатели и должностные показатели руководителя.</p>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={load} disabled={loading}><RefreshCcw size={14} /> Обновить</button>
      </div>

      {loading ? <div className={styles.empty}>{lang.common.loading}</div> : null}
      {error ? <div className={styles.error}>{error}</div> : null}

      {kpi && (
        <section className={styles.kpiOverview}>
          <div className={styles.scoreHero}>
            <div className={styles.personSummary}>
              <span className={styles.personAvatar}>
                {kpi.avatar_url ? <img src={kpi.avatar_url} alt="" /> : <UserRound size={27} />}
              </span>
              <div>
                <span className={styles.eyebrow}>Карточка эффективности</span>
                <h2>{kpi.user_name}</h2>
                <div className={styles.personMeta}>
                  <span><Briefcase size={13} />{ROLE_LABELS[kpi.role] || kpi.role}</span>
                  <span><Building2 size={13} />{kpi.department_id || 'Отдел не назначен'}</span>
                </div>
              </div>
            </div>

            <div className={styles.scoreBlock}>
              <div
                className={styles.scoreRing}
                data-tone={valueTone(overallScore)}
                style={{ background: `conic-gradient(var(--score-color) ${Math.max(0, Math.min(overallScore ?? 0, 100))}%, var(--color-bg-tertiary) 0)` }}
              >
                <div><strong>{overallScore === null ? '—' : Math.round(overallScore)}</strong><span>{overallScore === null ? '' : '%'}</span></div>
              </div>
              <div className={styles.scoreCopy}>
                <strong>Общая эффективность</strong>
                <span>{kpi.has_occupational_kpi ? 'Среднее по общим и должностным KPI' : 'Среднее по общим KPI сотрудника'}</span>
              </div>
            </div>

            <div className={styles.scoreFacts}>
              <div><span>Общие KPI</span><strong>{generalScore === null ? '—' : `${Math.round(generalScore)}%`}</strong></div>
              {kpi.has_occupational_kpi && <div><span>Должностные KPI</span><strong>{occupationalScore === null ? '—' : `${Math.round(occupationalScore)}%`}</strong></div>}
              <div><span>Коэффициент</span><strong>{performanceFactor === null ? '—' : `×${performanceFactor.toFixed(1)}`}</strong></div>
            </div>
          </div>

          <div className={styles.metricGroup}>
            <div className={styles.metricGroupHeader}>
              <div><span className={styles.groupNumber}>01</span><div><h3>Общие KPI</h3><p>Рабочая результативность, дисциплина и качество</p></div></div>
              <strong>{generalScore === null ? 'Нет данных' : `${Math.round(generalScore)}%`}</strong>
            </div>
            <div className={styles.metricStrip}>
            {liveEmployeeKpis.map(item => {
              const value = item.value;
              const carryover = finiteKpiValue(kpi.kpi9_carryover) ?? 0;
              return (
                <button
                  type="button"
                  className={styles.metricCard}
                  data-tone={valueTone(value)}
                  key={item.key}
                  onClick={() => openKpiDetail(item.key)}
                  aria-label={`Открыть расчёт: ${item.title}`}
                >
                  <div className={styles.metricTop}><span>{item.key}</span><Activity size={15} /></div>
                  <div className={styles.metricValue}>
                    <strong>
                      {value === null ? '—' : `${Math.round(value)}${item.key === 'KPI9' && carryover > 0 ? '% +' : '%'}`}
                    </strong>
                  </div>
                  <span className={styles.metricName}>{item.title}</span>
                  <span className={styles.metricBar}><i style={{ width: `${Math.max(0, Math.min(value ?? 0, 100))}%` }} /></span>
                  {item.key === 'KPI9' && carryover > 0 && <small>+{carryover}% перенос</small>}
                  <span className={styles.metricOpen}>Расшифровка <ChevronRight size={14} /></span>
                </button>
              );
            })}
            </div>
          </div>

          {kpi.has_occupational_kpi && (
            <div className={`${styles.metricGroup} ${styles.managerMetricGroup}`}>
              <div className={styles.metricGroupHeader}>
                <div><span className={styles.groupNumber}>02</span><div><h3>Должностные KPI руководителя</h3><p>Управление сотрудниками, инициативами и показателями отдела</p></div></div>
                <strong>{occupationalScore === null ? 'Нет данных' : `${Math.round(occupationalScore)}%`}</strong>
              </div>
              <button type="button" className={styles.managerSla} onClick={() => openKpiDetail('M2')}>
                <Clock3 size={17} /><span>Среднее время реакции</span>
                <strong>{finiteKpiValue(kpi.manager_kpi2_reaction_days) === null ? '—' : `${finiteKpiValue(kpi.manager_kpi2_reaction_days)?.toFixed(1)} раб. дн.`}</strong>
                <small>Норма: до 1 рабочего дня · открыть историю</small>
              </button>
              <div className={styles.metricStrip}>
                {occupationalKpis.map(item => (
                  <button
                    type="button"
                    className={styles.metricCard}
                    data-tone={valueTone(item.value)}
                    key={item.key}
                    onClick={() => openKpiDetail(item.key)}
                    aria-label={`Открыть расчёт: ${item.title}`}
                  >
                    <div className={styles.metricTop}><span>{item.key}</span><Briefcase size={15} /></div>
                    <div className={styles.metricValue}><strong>{item.value === null ? '—' : `${Math.round(item.value)}%`}</strong></div>
                    <span className={styles.metricName}>{item.title}</span>
                    <span className={styles.metricBar}><i style={{ width: `${Math.max(0, Math.min(item.value ?? 0, 100))}%` }} /></span>
                    <span className={styles.metricOpen}>Расшифровка <ChevronRight size={14} /></span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {(detailLoading || detailError || detail) && (
        <div className={styles.detailOverlay} onMouseDown={event => { if (event.target === event.currentTarget) closeKpiDetail(); }}>
          <aside className={styles.detailDrawer} role="dialog" aria-modal="true" aria-labelledby="kpi-detail-title">
            <header className={styles.detailHeader}>
              <div>
                <span className={styles.eyebrow}>Доказательная история KPI</span>
                <h2 id="kpi-detail-title">{detail?.title || 'Загрузка расчёта'}</h2>
                {detail && <p>{detail.user_name} · {detail.kpi_key}</p>}
              </div>
              <button type="button" className={styles.detailClose} onClick={closeKpiDetail} aria-label="Закрыть"><X size={20} /></button>
            </header>

            {detailLoading && <div className={styles.detailLoading}><span /><strong>Собираем события показателя…</strong></div>}
            {detailError && <div className={styles.detailError}><AlertCircle size={20} /><div><strong>История недоступна</strong><span>{detailError}</span></div></div>}

            {detail && (
              <>
                <section className={styles.detailSummary}>
                  <div className={styles.detailScore} data-tone={valueTone(detail.value)}>
                    <strong>{detail.value === null ? '—' : Number(detail.value.toFixed(1))}</strong>
                    <span>{detail.value === null ? 'нет данных' : detail.unit}</span>
                  </div>
                  <div className={styles.detailFormula}>
                    <span>Как считается</span>
                    <strong>{detail.formula}</strong>
                    <small><CalendarRange size={14} /> {new Date(detail.period_start).toLocaleDateString('ru-RU')} — {new Date(detail.period_end).toLocaleDateString('ru-RU')}</small>
                  </div>
                </section>

                <div className={styles.detailTimelineHeader}>
                  <div><h3>Что повлияло на показатель</h3><p>Каждое начисление и штраф привязаны к фактическому событию.</p></div>
                  <span>{detail.events.length}</span>
                </div>
                <div className={styles.detailTimeline}>
                  {detail.events.map(event => (
                    <article className={styles.detailEvent} data-status={event.status || 'neutral'} key={event.id}>
                      <span className={styles.detailEventDot} aria-hidden="true" />
                      <div className={styles.detailEventBody}>
                        <div className={styles.detailEventTop}>
                          <div><strong>{event.title}</strong><time>{new Date(event.occurred_at).toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</time></div>
                          {event.value_label && <span>{event.value_label}</span>}
                        </div>
                        {event.description && <p>{event.description}</p>}
                        <div className={styles.detailEventMeta}>
                          <span>{event.event_type.replace(/_/g, ' ')}</span>
                          {event.source_type && <span>Источник: {event.source_type}</span>}
                          {event.status && <span>Статус: {event.status}</span>}
                        </div>
                      </div>
                    </article>
                  ))}
                  {detail.events.length === 0 && (
                    <div className={styles.detailEmpty}><Info size={23} /><strong>Событий за период пока нет</strong><span>Значение появится после подтверждённого рабочего действия.</span></div>
                  )}
                </div>
              </>
            )}
          </aside>
        </div>
      )}

      {!isViewingOther && (
        <details className={styles.workflowDisclosure}>
          <summary><ClipboardCheck size={18} /><span><strong>Еженедельный отчёт и рабочие действия</strong><small>Откройте, чтобы заполнить отчёт или проверить отчёты сотрудников</small></span><ChevronDown size={18} /></summary>
          <WeeklyReportsPanel canReview={canInspectTeam} onKpiChanged={load} />
          <IdeasPanel onKpiChanged={load} />
        </details>
      )}

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

