import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowRight,
  Bell,
  BriefcaseBusiness,
  CheckCircle2,
  ClipboardList,
  FolderKanban,
  Gauge,
  RefreshCcw,
  ShieldCheck,
  TrendingDown,
  Users,
  WalletCards,
} from 'lucide-react';
import api from '../../api/client';
import { gamificationApi, type ManagerReactivity, type UserKPI } from '../../api/gamification';
import { useAppSelector } from '../../store/hooks';
import styles from './OwnerDashboardLive.module.css';

interface AdminUser {
  id: string;
  name: string;
  last_name?: string | null;
  role: string;
  status: string;
  department_id?: string | null;
  avatar_url?: string | null;
}

interface ApplicationRow {
  id: string;
  client_name: string;
  project_name?: string | null;
  source: string;
  status: string;
  created_at: string;
}

interface Notice {
  id: string;
  title: string;
  message?: string | null;
  link?: string | null;
  created_at: string;
  is_read: boolean;
}

const KPI_FIELDS: Array<keyof UserKPI> = [
  'kpi1_deadlines',
  'kpi2_punctuality',
  'kpi3_initiative',
  'kpi4_overtime',
  'kpi5_quality',
  'kpi8_attentiveness',
  'kpi10_responsibility',
  'kpi_customer_satisfaction',
];

const ROLE_LABELS: Record<string, string> = {
  owner: 'Владелец',
  deputy_owner: 'Заместитель',
  admin: 'Руководитель отдела',
  manager: 'Руководитель',
  employee: 'Сотрудник',
  user: 'Сотрудник',
  consultant: 'Консультант',
  intern: 'Стажёр',
};

const displayName = (user: AdminUser) => `${user.last_name || ''} ${user.name}`.trim();
const valueText = (value: number | null | undefined) =>
  Number.isFinite(value) ? `${Math.round(value as number)}%` : '—';
const valueColor = (value: number | null | undefined) => {
  if (value == null) return 'var(--color-text-muted)';
  if (value >= 90) return 'var(--color-success)';
  if (value >= 70) return 'var(--color-warning)';
  return 'var(--color-error)';
};

const overallFor = (item?: UserKPI) => {
  if (!item) return null;
  if (typeof item.overall_score === 'number' && Number.isFinite(item.overall_score)) return item.overall_score;
  const values = KPI_FIELDS.map(field => item[field]).filter((value): value is number => typeof value === 'number');
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
};

const noticeTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('ru-RU', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
};

function MetricValue({ value, featured = false }: { value: number | null | undefined; featured?: boolean }) {
  const width = value == null ? 0 : Math.max(0, Math.min(value, 100));
  const color = valueColor(value);
  return (
    <div className={`${styles.metricValue} ${featured ? styles.metricFeatured : ''}`}>
      <span style={{ color }}>{valueText(value)}</span>
      <span className={styles.metricTrack} aria-hidden="true">
        <span style={{ width: `${width}%`, backgroundColor: color }} />
      </span>
    </div>
  );
}

export default function OwnerDashboard() {
  const navigate = useNavigate();
  const owner = useAppSelector(state => state.auth.user);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [applications, setApplications] = useState<ApplicationRow[]>([]);
  const [kpis, setKpis] = useState<Record<string, UserKPI>>({});
  const [managers, setManagers] = useState<ManagerReactivity[]>([]);
  const [notices, setNotices] = useState<Notice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [usersResponse, applicationsResponse, managersResponse, noticesResponse] = await Promise.allSettled([
        api.get<AdminUser[]>('/admin/users'),
        api.get<ApplicationRow[]>('/applications'),
        gamificationApi.getManagerReactivity(),
        api.get<Notice[]>('/notifications?limit=12'),
      ]);
      const loadedUsers = usersResponse.status === 'fulfilled' ? usersResponse.value.data : [];
      const activeUsers = loadedUsers.filter(item => item.status === 'active');
      setUsers(loadedUsers);
      setApplications(applicationsResponse.status === 'fulfilled' ? applicationsResponse.value.data : []);
      setManagers(managersResponse.status === 'fulfilled' ? managersResponse.value.data : []);
      setNotices(noticesResponse.status === 'fulfilled' ? noticesResponse.value.data : []);
      if (usersResponse.status === 'rejected') {
        throw usersResponse.reason;
      }

      const results = await Promise.allSettled(activeUsers.map(item => gamificationApi.getUserKPI(item.id)));
      const next: Record<string, UserKPI> = {};
      results.forEach((result, index) => {
        if (result.status === 'fulfilled') next[activeUsers[index].id] = result.value.data;
      });
      setKpis(next);
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Не удалось загрузить данные кабинета руководителя');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const activeUsers = useMemo(() => users.filter(item => item.status === 'active'), [users]);
  const employeeRows = useMemo(() => {
    const monitored = activeUsers.filter(item => item.role !== 'owner');
    return monitored.sort((left, right) => {
      const leftValue = overallFor(kpis[left.id]);
      const rightValue = overallFor(kpis[right.id]);
      if (leftValue == null && rightValue == null) return displayName(left).localeCompare(displayName(right), 'ru');
      if (leftValue == null) return 1;
      if (rightValue == null) return -1;
      return leftValue - rightValue;
    });
  }, [activeUsers, kpis]);

  const averages = useMemo(() => {
    const values = employeeRows.flatMap(item => {
      const kpi = kpis[item.id];
      if (!kpi) return [];
      return KPI_FIELDS.map(field => kpi[field]).filter((value): value is number => typeof value === 'number');
    });
    return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
  }, [employeeRows, kpis]);

  const orderCounts = useMemo(() => ({
    total: applications.length,
    queue: applications.filter(item => ['new', 'contacting', 'tz_received', 'review', 'revision', 'approved'].includes(item.status)).length,
    inDevelopment: applications.filter(item => item.status === 'distributing').length,
    completed: applications.filter(item => item.status === 'completed').length,
  }), [applications]);
  const recentOrders = useMemo(() => [...applications]
    .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime())
    .slice(0, 5), [applications]);
  const unreadNotices = useMemo(() => notices.filter(item => !item.is_read).length, [notices]);
  const atRiskEmployees = useMemo(() => employeeRows.filter(item => {
    const overall = overallFor(kpis[item.id]);
    return overall != null && overall < 70;
  }), [employeeRows, kpis]);
  const managerDrops = useMemo(() => managers.reduce((sum, item) => sum + item.active_drops_count, 0), [managers]);
  const ownerName = `${owner?.last_name || 'Девятов'} ${owner?.name || 'Алексей'}`.trim();

  const openNotice = (notice: Notice) => {
    if (!notice.link) return;
    const link = notice.link.startsWith('#') ? notice.link.slice(1) : notice.link;
    if (link.startsWith('/')) navigate(link);
  };

  return (
    <div className={styles.page} aria-busy={loading}>
      <header className={styles.hero}>
        <div className={styles.ownerBlock}>
          <div className={styles.ownerAvatar}>
            {owner?.avatar_url ? <img src={owner.avatar_url} alt="" /> : <ShieldCheck size={23} aria-hidden="true" />}
          </div>
          <div>
            <div className={styles.eyebrow}><span className={styles.liveDot} />Единый центр управления</div>
            <h1>Панель руководителя</h1>
            <p>{ownerName} <span aria-hidden="true">·</span> Супер‑администратор</p>
          </div>
        </div>
        <nav className={styles.actions} aria-label="Быстрые действия">
          <button className="btn btn-ghost" onClick={load} disabled={loading}>
            <RefreshCcw className={loading ? styles.spinning : ''} size={16} />{loading ? 'Обновляем' : 'Обновить'}
          </button>
          <button className="btn btn-outline" onClick={() => navigate('/admin')}><Users size={16} /> Команда</button>
          <button className="btn btn-outline" onClick={() => navigate('/applications')}><ClipboardList size={16} /> Заказы</button>
          <button className="btn btn-outline" onClick={() => navigate('/finance')}><WalletCards size={16} /> Финансы</button>
          <button className="btn btn-primary" onClick={() => navigate('/kpi')}><Gauge size={16} /> KPI</button>
        </nav>
      </header>

      {error && <div className={styles.error} role="alert"><AlertTriangle size={18} /><span>{error}</span><button type="button" onClick={load}>Повторить</button></div>}

      <section className={styles.stats} aria-label="Ключевые показатели">
        <button className={styles.stat} data-tone="blue" onClick={() => navigate('/applications')}>
          <span className={styles.statIcon}><ClipboardList size={20} /></span><span className={styles.statCopy}><strong>{orderCounts.total}</strong><span>всего заказов</span></span><ArrowRight className={styles.statArrow} size={17} />
        </button>
        <button className={styles.stat} data-tone="violet" onClick={() => navigate('/applications')}>
          <span className={styles.statIcon}><FolderKanban size={20} /></span><span className={styles.statCopy}><strong>{orderCounts.inDevelopment}</strong><span>заказов в разработке</span></span><ArrowRight className={styles.statArrow} size={17} />
        </button>
        <button className={styles.stat} data-tone="amber" onClick={() => navigate('/applications')}>
          <span className={styles.statIcon}><BriefcaseBusiness size={20} /></span><span className={styles.statCopy}><strong>{orderCounts.queue}</strong><span>заказов в очереди</span></span><ArrowRight className={styles.statArrow} size={17} />
        </button>
        <button className={styles.stat} data-tone="green" onClick={() => navigate('/kpi')}>
          <span className={styles.statIcon}><Gauge size={20} /></span><span className={styles.statCopy}><strong style={{ color: valueColor(averages) }}>{valueText(averages)}</strong><span>средний KPI команды</span></span><ArrowRight className={styles.statArrow} size={17} />
        </button>
      </section>

      <section className={`${styles.attention} ${(atRiskEmployees.length || managerDrops) ? styles.attentionWarning : styles.attentionGood}`}>
        <div className={styles.attentionLead}>
          <span className={styles.attentionIcon}>{(atRiskEmployees.length || managerDrops) ? <TrendingDown size={20} /> : <CheckCircle2 size={20} />}</span>
          <div><strong>{(atRiskEmployees.length || managerDrops) ? 'Требует внимания' : 'Ситуация стабильна'}</strong><span>{(atRiskEmployees.length || managerDrops) ? 'Проверьте показатели и назначьте разбор' : 'Критичных падений KPI нет'}</span></div>
        </div>
        <div className={styles.attentionFacts}>
          <div><strong>{atRiskEmployees.length}</strong><span>сотрудников ниже 70%</span></div>
          <div><strong>{managerDrops}</strong><span>активных падений</span></div>
          <div><strong>{unreadNotices}</strong><span>непрочитанных уведомлений</span></div>
        </div>
        <button className={styles.attentionAction} onClick={() => navigate('/kpi')}>
          {(atRiskEmployees.length || managerDrops) ? 'Перейти к разбору' : 'Открыть KPI'} <ArrowRight size={16} />
        </button>
      </section>

      <section className={`${styles.card} ${styles.ordersCard}`}>
        <div className={styles.cardHeader}>
          <div><div className={styles.cardTitle}><ClipboardList size={19} /><h2>Заказы компании</h2></div><p>Будущие, текущие и завершённые заказы из заявок сайта.</p></div>
          <button className={styles.textButton} onClick={() => navigate('/applications')}>Открыть все заказы <ArrowRight size={15} /></button>
        </div>
        <div className={styles.orderPipeline}>
          <div><span>Будущие и очередь</span><strong>{orderCounts.queue}</strong></div>
          <div><span>В разработке</span><strong>{orderCounts.inDevelopment}</strong></div>
          <div><span>Завершено</span><strong>{orderCounts.completed}</strong></div>
        </div>
        <div className={styles.orderList}>
          {recentOrders.map(order => <button type="button" key={order.id} onClick={() => navigate(`/applications/${encodeURIComponent(order.id)}`)}>
            <span className={styles.orderSource}>{order.source === 'website' ? 'Сайт' : 'Вручную'}</span>
            <span className={styles.orderName}><strong>{order.project_name || order.client_name}</strong><small>{order.client_name}</small></span>
            <span className={styles.orderStatus}>{order.status}</span>
            <ArrowRight size={15} />
          </button>)}
          {!loading && recentOrders.length === 0 && <div className={styles.empty}>Заказов пока нет. Новая заявка с сайта появится здесь автоматически.</div>}
        </div>
      </section>

      <section className={styles.contentGrid}>
        <div className={`${styles.card} ${styles.teamCard}`}>
          <div className={styles.cardHeader}>
            <div><div className={styles.cardTitle}><Gauge size={19} /><h2>Команда и KPI</h2></div><p>Сотрудники с низким итогом показаны первыми</p></div>
            <button className={styles.textButton} onClick={() => navigate('/kpi')}>Все расчёты <ArrowRight size={15} /></button>
          </div>
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead><tr><th>Сотрудник</th><th>Сроки</th><th>Дисциплина</th><th>Качество</th><th>Ответственность</th><th>Итог</th></tr></thead>
              <tbody>
                {employeeRows.map(item => {
                  const kpi = kpis[item.id];
                  const overall = overallFor(kpi);
                  const name = displayName(item);
                  const openProfile = () => navigate(`/kpi?user=${encodeURIComponent(item.id)}`);
                  return <tr
                    className={styles.personRow}
                    key={item.id}
                    role="button"
                    tabIndex={0}
                    aria-label={`Открыть KPI сотрудника ${name}`}
                    onClick={openProfile}
                    onKeyDown={event => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        openProfile();
                      }
                    }}
                  >
                    <td className={styles.personCell}><div className={styles.person}><span className={styles.avatar}>{item.avatar_url ? <img src={item.avatar_url} alt="" /> : name.slice(0, 1).toUpperCase()}</span><span className={styles.personCopy}><strong>{name}</strong><span>{ROLE_LABELS[item.role] || item.role}</span></span></div></td>
                    <td data-label="Сроки"><MetricValue value={kpi?.kpi1_deadlines} /></td>
                    <td data-label="Дисциплина"><MetricValue value={kpi?.kpi2_punctuality} /></td>
                    <td data-label="Качество"><MetricValue value={kpi?.kpi5_quality} /></td>
                    <td data-label="Ответственность"><MetricValue value={kpi?.kpi10_responsibility} /></td>
                    <td data-label="Итог"><MetricValue value={overall} featured /></td>
                  </tr>;
                })}
              </tbody>
            </table>
            {loading && employeeRows.length === 0 && <div className={styles.loadingState}><span /><span /><span /></div>}
            {!loading && employeeRows.length === 0 && <div className={styles.empty}>Активных сотрудников для расчёта KPI пока нет.</div>}
          </div>
        </div>

        <aside className={`${styles.card} ${styles.noticeCard}`}>
          <div className={styles.cardHeader}>
            <div><div className={styles.cardTitle}><Bell size={19} /><h2>Уведомления</h2></div><p>{unreadNotices ? `${unreadNotices} требуют просмотра` : 'Всё просмотрено'}</p></div>
            {unreadNotices > 0 && <span className={styles.counter}>{unreadNotices}</span>}
          </div>
          <div className={styles.noticeList}>
            {notices.map(item => <button className={`${styles.notice} ${!item.is_read ? styles.noticeUnread : ''}`} key={item.id} onClick={() => openNotice(item)} disabled={!item.link}>
              <span className={styles.noticeDot} aria-hidden="true" /><span className={styles.noticeBody}><strong>{item.title}</strong><span>{item.message || 'Системное уведомление'}</span><time>{noticeTime(item.created_at)}</time></span>{item.link && <ArrowRight className={styles.noticeArrow} size={15} />}
            </button>)}
            {loading && notices.length === 0 && <div className={styles.noticeSkeleton}><span /><span /><span /></div>}
            {!loading && notices.length === 0 && <div className={styles.empty}><CheckCircle2 size={24} /><span>Новых уведомлений нет.</span></div>}
          </div>
        </aside>
      </section>

      <section className={`${styles.card} ${styles.managersCard}`}>
        <div className={styles.cardHeader}>
          <div><div className={styles.cardTitle}><BriefcaseBusiness size={19} /><h2>Дисциплина руководителей</h2></div><p>Скорость реакции и контроль показателей команды</p></div>
          <button className={styles.textButton} onClick={() => navigate('/kpi')}>Разборы и отчёты <ArrowRight size={15} /></button>
        </div>
        <div className={styles.managerList}>
          {managers.map(item => {
            const hasDrops = item.active_drops_count > 0;
            return <article className={styles.manager} key={item.manager_id}>
              <div className={styles.managerIdentity}><span className={styles.managerAvatar}>{item.manager_name.slice(0, 1).toUpperCase()}</span><div><strong>{item.manager_name}</strong><span>Руководитель</span></div></div>
              <div className={styles.managerMetric}><span>Активные падения</span><strong className={hasDrops ? styles.dangerText : styles.successText}>{item.active_drops_count}</strong></div>
              <div className={styles.managerMetric}><span>Средняя реакция</span><strong>{item.avg_reaction_days == null ? '—' : `${item.avg_reaction_days.toFixed(1)} дн.`}</strong></div>
              <div className={styles.managerMetric}><span>Проведено разборов</span><strong>{item.conducted_reviews_count}</strong></div>
              <div className={styles.managerKpi}><span>Контроль показателей отдела</span><MetricValue value={item.manager_kpi7_department_control} featured /></div>
              <span className={`${styles.managerState} ${hasDrops ? styles.managerStateWarning : styles.managerStateGood}`}>{hasDrops ? 'Нужен разбор' : 'Без падений'}</span>
            </article>;
          })}
          {loading && managers.length === 0 && <div className={styles.managerSkeleton}><span /><span /></div>}
          {!loading && managers.length === 0 && <div className={styles.empty}>Нет руководителей с назначенными KPI.</div>}
        </div>
      </section>
    </div>
  );
}
