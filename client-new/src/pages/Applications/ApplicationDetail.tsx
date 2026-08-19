import { useState, useEffect, useMemo, useRef, type ReactNode } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, ClipboardCheck, CalendarDays, ChevronDown, LayoutList } from 'lucide-react';
import { useAppSelector } from '../../store/hooks';
import { t } from '../../i18n';
import api from '../../api/client';
import type { Application, ApplicationTask, User } from '../../types';
import { SPHERES } from '../../types';
import { FULL_ACCESS_ROLES } from '../../types';
import type { UserRole } from '../../types';
import styles from './Applications.module.css';
import CustomerSatisfactionPanel from './CustomerSatisfactionPanel';

const STATUS_BADGE: Record<string, string> = {
  new: styles.badgeNew,
  contacting: styles.badgeContacting,
  tz_received: styles.badgeTzReceived,
  review: styles.badgeReview,
  revision: styles.badgeRevision,
  approved: styles.badgeApproved,
  distributing: styles.badgeDistributing,
  completed: styles.badgeCompleted,
};

const STATUS_LABELS: Record<string, string> = {
  new: 'statusNew',
  contacting: 'statusContacting',
  tz_received: 'statusTzReceived',
  review: 'statusReview',
  revision: 'statusRevision',
  approved: 'statusApproved',
  distributing: 'statusDistributing',
  completed: 'statusCompleted',
};

const NEXT_ACTIONS: Record<string, { next: string; labelKey: string }[]> = {
  new: [{ next: 'contacting', labelKey: 'statusContacting' }],
  contacting: [{ next: 'review', labelKey: 'sendForReview' }],
  tz_received: [{ next: 'review', labelKey: 'sendForReview' }],
  review: [
    { next: 'approved', labelKey: 'approve' },
    { next: 'revision', labelKey: 'reject' },
  ],
  revision: [{ next: 'review', labelKey: 'sendForReview' }],
  approved: [{ next: 'distributing', labelKey: 'statusDistributing' }],
  distributing: [{ next: 'completed', labelKey: 'markCompleted' }],
};

function initSphereDraft(tz: string): { intro: string; rows: { localId: string; name: string; content: string }[] } {
  const blocks = parseDepartments(tz);
  let intro = '';
  const rows: { localId: string; name: string; content: string }[] = [];
  let seenNamed = false;
  for (const b of blocks) {
    if (b.name) {
      seenNamed = true;
      rows.push({ localId: crypto.randomUUID(), name: b.name, content: b.content.trim() });
    } else if (!seenNamed) {
      intro += (intro ? '\n' : '') + b.content;
    }
  }
  return { intro: intro.trim(), rows };
}

function buildTzContent(intro: string, rows: { name: string; content: string }[]): string {
  const parts: string[] = [];
  const i = intro.trim();
  if (i) parts.push(i);
  for (const row of rows) {
    const n = row.name.trim();
    const c = row.content.trim();
    if (!n && !c) continue;
    parts.push(`## ${n || 'Сфера'}\n${c}`);
  }
  return parts.join('\n\n');
}

/** Совпадение сферы в профиле с выбранной (в т.ч. старое написание HR). */
function userSphereMatchesProfile(userSphere: string, selectedSphere: string): boolean {
  const a = userSphere.trim().toLowerCase();
  const b = selectedSphere.trim().toLowerCase();
  if (a === b) return true;
  const hrOld = 'кадры и организации (hr)';
  const hrNew = 'кадры и организация (hr)';
  if ((a === hrOld && b === hrNew) || (a === hrNew && b === hrOld)) return true;
  return false;
}

function usersInSphere(users: User[], sphereName: string): User[] {
  const t = sphereName.trim();
  if (!t) return [];
  return users.filter(u =>
    (u.sphere_roles || []).some(sr => userSphereMatchesProfile(sr.sphere || '', sphereName)),
  );
}

function parseDepartments(raw: string | undefined): { name: string; content: string }[] {
  if (!raw) return [];
  const blocks: { name: string; content: string }[] = [];
  const lines = raw.split('\n');
  let current: { name: string; content: string } | null = null;

  for (const line of lines) {
    const headerMatch = line.match(/^##?\s+(.+)/);
    if (headerMatch) {
      if (current) blocks.push(current);
      current = { name: headerMatch[1].trim(), content: '' };
    } else if (current) {
      current.content += (current.content ? '\n' : '') + line;
    } else {
      blocks.push({ name: '', content: line });
    }
  }
  if (current) blocks.push(current);
  return blocks.filter(b => b.name || b.content.trim());
}

function groupTasksByParent(tasks: ApplicationTask[]) {
  const by = new Map<string | undefined, ApplicationTask[]>();
  for (const t of tasks) {
    const p = t.parent_id || undefined;
    if (!by.has(p)) by.set(p, []);
    by.get(p)!.push(t);
  }
  for (const arr of by.values()) {
    arr.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
  }
  return by;
}

function formatAppDeadline(iso: string | null | undefined) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}.${pad(d.getMinutes())}`;
}

/** Значение для input[type=datetime-local] из сохранённой строки или ISO. */
function toDateTimeLocalValue(stored: string | undefined | null): string {
  if (!stored?.trim()) return '';
  const s = stored.trim();
  const d0 = new Date(s);
  if (!Number.isNaN(d0.getTime())) {
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d0.getFullYear()}-${pad(d0.getMonth() + 1)}-${pad(d0.getDate())}T${pad(d0.getHours())}:${pad(d0.getMinutes())}`;
  }
  const m = s.match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})(?:\s+(\d{1,2})[.:](\d{1,2}))?$/);
  if (m) {
    const dd = Number(m[1]);
    const mm = Number(m[2]);
    const yyyy = Number(m[3]);
    const hh = m[4] != null ? Number(m[4]) : 0;
    const mi = m[5] != null ? Number(m[5]) : 0;
    const d = new Date(yyyy, mm - 1, dd, hh, mi);
    if (!Number.isNaN(d.getTime())) {
      const pad = (n: number) => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    }
  }
  return '';
}

/** Формат, который принимает API заявок (_parse_app_deadline). */
function fromDateTimeLocalToAppDeadline(dtLocal: string): string {
  if (!dtLocal.trim()) return '';
  const d = new Date(dtLocal);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}.${pad(d.getMinutes())}`;
}

function AppDeadlinePicker({
  value,
  onCommit,
  placeholder,
}: {
  value: string;
  onCommit: (next: string) => void;
  placeholder: string;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState('');
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const display = value.trim() ? formatAppDeadline(value) || value : '';

  const togglePicker = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDraft(toDateTimeLocalValue(value));
    setOpen(o => !o);
  };

  const apply = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!draft.trim()) return;
    onCommit(fromDateTimeLocalToAppDeadline(draft));
    setOpen(false);
  };

  const clear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onCommit('');
    setOpen(false);
  };

  return (
    <div className={styles.appDeadlinePicker} ref={wrapRef}>
      <button
        type="button"
        className={`${styles.appDeadlinePickerTrigger} ${!display ? styles.appDeadlinePickerTriggerMuted : ''}`}
        onClick={togglePicker}
      >
        <span>{display || placeholder}</span>
        <CalendarDays size={18} aria-hidden style={{ flexShrink: 0, opacity: 0.7 }} />
      </button>
      {open ? (
        <div className={styles.appDeadlinePickerPopover} onMouseDown={e => e.stopPropagation()} role="presentation">
          <label>
            Дата и время
            <input
              type="datetime-local"
              value={draft}
              onChange={e => setDraft(e.target.value)}
              autoFocus
            />
          </label>
          <div className={styles.appDeadlinePickerActions}>
            <button type="button" className={styles.appDeadlinePickerApply} disabled={!draft.trim()} onClick={apply}>
              Применить
            </button>
            {value.trim() ? (
              <button type="button" className={styles.appDeadlinePickerClear} onClick={clear}>
                Убрать
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function assigneeDisplayName(u: User): string {
  const parts = [u.name?.trim(), u.last_name?.trim()].filter(Boolean);
  if (parts.length) return parts.join(' ');
  if (u.email?.trim()) return u.email.trim();
  return u.id || '—';
}

function CollapsibleAssigneePicker({
  staff,
  selectedIds,
  onToggle,
  nonePlaceholder,
  disabled,
}: {
  staff: User[];
  selectedIds: string[];
  onToggle: (userId: string, checked: boolean) => void;
  nonePlaceholder: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const idSelected = (uid: string) => selectedIds.some(s => String(s) === String(uid));

  const summary = useMemo(() => {
    if (!selectedIds.length) return nonePlaceholder;
    const sel = new Set(selectedIds.map(String));
    const names = staff.filter(u => sel.has(String(u.id))).map(assigneeDisplayName);
    if (names.length === 0) return nonePlaceholder;
    if (names.length <= 2) return names.join(', ');
    return `${names.slice(0, 2).join(', ')} +${names.length - 2}`;
  }, [staff, selectedIds, nonePlaceholder]);

  const canOpen = !disabled && staff.length > 0;

  return (
    <div className={styles.collapsibleAssignee} ref={wrapRef}>
      <button
        type="button"
        className={styles.collapsibleAssigneeTrigger}
        onClick={() => canOpen && setOpen(o => !o)}
        disabled={!canOpen}
        aria-expanded={open}
      >
        <span className={selectedIds.length ? undefined : styles.collapsibleAssigneePlaceholder}>{summary}</span>
        {staff.length > 0 ? (
          <ChevronDown
            size={18}
            className={`${styles.collapsibleAssigneeChevron} ${open ? styles.collapsibleAssigneeChevronOpen : ''}`}
            aria-hidden
          />
        ) : null}
      </button>
      {open && staff.length > 0 ? (
        <div className={styles.collapsibleAssigneePanel} role="listbox" aria-label={nonePlaceholder}>
          {staff.map(u => (
            <label key={u.id} className={styles.collapsibleAssigneeRow}>
              <input
                type="checkbox"
                checked={idSelected(u.id)}
                onChange={e => onToggle(u.id, e.target.checked)}
              />
              <span className={styles.collapsibleAssigneeName}>{assigneeDisplayName(u)}</span>
            </label>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default function ApplicationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAppSelector(s => s.auth);
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);
  const a = lang.applications;

  const userRole = (user?.role || 'user') as UserRole;
  const isReviewer = FULL_ACCESS_ROLES.includes(userRole);
  const isConsultant = userRole === 'consultant';

  const [app, setApp] = useState<Application | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    client_name: '',
    client_email: '',
    client_phone: '',
    client_company: '',
    description: '',
    project_name: '',
    tz_content: '',
    departments: '',
  });
  const [sphereDraft, setSphereDraft] = useState({ intro: '', rows: [] as { localId: string; name: string; content: string }[] });
  const [rejectComment, setRejectComment] = useState('');
  const [showReject, setShowReject] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [selectedUserId, setSelectedUserId] = useState('');

  const [newTask, setNewTask] = useState({
    title: '',
    description: '',
    department: '',
    deadline: '',
    parent_id: '',
    assignee_ids: [] as string[],
  });
  const [sphereDeadlineByName, setSphereDeadlineByName] = useState<Record<string, string>>({});
  const [sphereAssignChecks, setSphereAssignChecks] = useState<Record<number, string[]>>({});
  /** Заголовок карточки на доске (колонка = название сферы). Ключ — нормализованное имя сферы из ТЗ. */
  const [sphereTaskTitles, setSphereTaskTitles] = useState<Record<string, string>>({});
  /** Описание задачи на доске (ТЗ); если ключа нет — при рендере подставляется текст сферы из ТЗ. */
  const [sphereTaskDescriptions, setSphereTaskDescriptions] = useState<Record<string, string>>({});
  const [projectNameQuick, setProjectNameQuick] = useState('');

  const consultantOwns = !!(
    user?.id &&
    app &&
    (app.consultant_id === user.id || (app.source === 'website' && !app.consultant_id))
  );

  const tasksByParent = useMemo(() => groupTasksByParent(app?.tasks || []), [app?.tasks]);
  const parentTitleById = useMemo(() => {
    const m = new Map<string, string>();
    (app?.tasks || []).forEach(t => m.set(t.id, t.title));
    return m;
  }, [app?.tasks]);

  useEffect(() => { load(); loadUsers(); }, [id]);

  useEffect(() => {
    const onRt = (e: Event) => {
      const d = (e as CustomEvent<unknown>).detail as {
        type?: string;
        resource?: string;
        application_id?: string;
      } | null;
      if (!d || d.type !== 'resource_changed' || d.resource !== 'application') return;
      if (d.application_id !== id) return;
      load();
    };
    window.addEventListener('agile-realtime', onRt);
    return () => window.removeEventListener('agile-realtime', onRt);
  }, [id]);

  const load = async () => {
    try {
      const { data } = await api.get<Application>(`/applications/${id}`);
      setApp(data);
      setForm({
        client_name: data.client_name || '',
        client_email: data.client_email || '',
        client_phone: data.client_phone || '',
        client_company: data.client_company || '',
        description: data.description || '',
        project_name: data.project_name || '',
        tz_content: data.tz_content || '',
        departments: data.departments || '',
      });
      setSphereDraft(initSphereDraft(data.tz_content || ''));
      let sd: Record<string, string> = {};
      if (data.sphere_deadlines_json) {
        try {
          const p = JSON.parse(data.sphere_deadlines_json);
          if (p && typeof p === 'object' && !Array.isArray(p)) sd = p as Record<string, string>;
        } catch {
          /* ignore */
        }
      }
      setSphereDeadlineByName(sd);
      setProjectNameQuick(data.project_name || '');
    } catch { /* handled globally */ }
    setLoading(false);
  };

  const loadUsers = async () => {
    try {
      const { data } = await api.get<User[]>('/users');
      setUsers(data);
    } catch { setUsers([]); }
  };

  const handleSave = async () => {
    try {
      await api.put(`/applications/${id}`, form);
      setEditing(false);
      await load();
    } catch { /* handled globally */ }
  };

  const changeStatus = async (status: string, comment?: string) => {
    try {
      await api.post(`/applications/${id}/status`, { status, comment });
      setShowReject(false);
      setRejectComment('');
      await load();
    } catch { /* handled globally */ }
  };

  const saveSphereTz = async () => {
    const tz_content = buildTzContent(sphereDraft.intro, sphereDraft.rows);
    const departments =
      sphereDraft.rows.map(r => r.name.trim()).filter(Boolean).join(', ') || undefined;
    await api.put(`/applications/${id}`, { tz_content, departments });
  };

  const handleSendForReview = async () => {
    try {
      if (['contacting', 'tz_received', 'revision'].includes(app?.status || '')) {
        await saveSphereTz();
      }
      await api.post(`/applications/${id}/status`, { status: 'review' });
      setShowReject(false);
      setRejectComment('');
      await load();
    } catch { /* handled globally */ }
  };

  const handleSaveSphereOnly = async () => {
    try {
      await saveSphereTz();
      await load();
    } catch { /* handled globally */ }
  };

  const addMember = async () => {
    if (!selectedUserId) return;
    try {
      await api.post(`/applications/${id}/members`, { user_id: selectedUserId });
      setSelectedUserId('');
      await load();
    } catch { /* handled globally */ }
  };

  const removeMember = async (memberId: string) => {
    try {
      await api.delete(`/applications/${id}/members/${memberId}`);
      await load();
    } catch { /* handled globally */ }
  };

  const handleAddTask = async () => {
    if (!newTask.title.trim()) return;
    try {
      await api.post(`/applications/${id}/tasks`, {
        title: newTask.title,
        description: newTask.description || undefined,
        department: newTask.department || undefined,
        deadline: newTask.deadline.trim() || undefined,
        parent_id: newTask.parent_id || undefined,
        assignee_ids: newTask.assignee_ids.length ? newTask.assignee_ids : undefined,
      });
      setNewTask({
        title: '',
        description: '',
        department: '',
        deadline: '',
        parent_id: '',
        assignee_ids: [],
      });
      await load();
    } catch { /* handled globally */ }
  };

  const handleDeleteTask = async (taskId: string) => {
    try {
      await api.delete(`/applications/${id}/tasks/${taskId}`);
      await load();
    } catch { /* handled globally */ }
  };

  const handleAssignSphereTask = async (dept: { name: string; content: string }, idx: number) => {
    const ids = sphereAssignChecks[idx] || [];
    const deptKey = dept.name.trim();
    const title = (sphereTaskTitles[deptKey] || '').trim();
    if (!ids.length || !deptKey || !title) return;
    try {
      const dl = (sphereDeadlineByName[deptKey] || '').trim() || undefined;
      const descRaw =
        sphereTaskDescriptions[deptKey] !== undefined
          ? sphereTaskDescriptions[deptKey]
          : dept.content;
      const description = String(descRaw || '').trim() || undefined;
      await api.post(`/applications/${id}/tasks`, {
        title,
        description,
        department: deptKey,
        assignee_ids: ids,
        deadline: dl,
      });
      setSphereTaskTitles(prev => {
        const next = { ...prev };
        delete next[deptKey];
        return next;
      });
      setSphereTaskDescriptions(prev => {
        const next = { ...prev };
        delete next[deptKey];
        return next;
      });
      await load();
    } catch { /* handled globally */ }
  };

  const handleSaveSphereDeadlines = async () => {
    try {
      const cleaned: Record<string, string> = {};
      for (const [k, v] of Object.entries(sphereDeadlineByName)) {
        if (v && String(v).trim()) cleaned[k] = String(v).trim();
      }
      await api.put(`/applications/${id}`, { sphere_deadlines_json: JSON.stringify(cleaned) });
      await load();
    } catch { /* handled globally */ }
  };

  const toggleSphereAssignee = (idx: number, uid: string, checked: boolean) => {
    setSphereAssignChecks(prev => {
      const cur = prev[idx] || [];
      if (checked) return { ...prev, [idx]: [...cur.filter(x => x !== uid), uid] };
      return { ...prev, [idx]: cur.filter(x => x !== uid) };
    });
  };

  const toggleNewTaskAssignee = (uid: string, checked: boolean) => {
    setNewTask(f => ({
      ...f,
      assignee_ids: checked ? [...f.assignee_ids.filter(x => x !== uid), uid] : f.assignee_ids.filter(x => x !== uid),
    }));
  };

  const renderTaskNodes = (parentId: string | undefined, depth: number): ReactNode => {
    const list = tasksByParent.get(parentId) || [];
    return list.map(task => (
      <div key={task.id}>
        <div
          className={styles.taskCard}
          style={{ marginLeft: depth * 14, marginBottom: 8 }}
        >
          <div className={styles.taskCardHeader}>
            <span className={styles.taskCardTitle}>{task.title}</span>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                style={{ fontSize: 12 }}
                onClick={() => setNewTask(f => ({ ...f, parent_id: task.id }))}
              >
                {(a as any).addSubtask || 'Подзадача'}
              </button>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                style={{ color: 'var(--color-danger)', fontSize: 12 }}
                onClick={() => handleDeleteTask(task.id)}
              >
                {a.deleteTask}
              </button>
            </div>
          </div>
          <div className={styles.taskCardMeta}>
            {task.department && <span>{a.taskDepartment}: {task.department}</span>}
            {(task.department && (task.assignee_name || task.assignee_names?.length)) ? <span> · </span> : null}
            {(task.assignee_names && task.assignee_names.length > 0) ? (
              <span>{(a as any).assignees || 'Ответственные'}: {task.assignee_names.join(', ')}</span>
            ) : task.assignee_name ? (
              <span>{a.taskAssignee}: {task.assignee_name}</span>
            ) : null}
            {task.deadline ? (
              <>
                <span> · </span>
                <span>{(a as any).taskDeadline || 'Дедлайн'}: {formatAppDeadline(task.deadline)}</span>
              </>
            ) : null}
          </div>
          {task.description && <div className={styles.taskCardDesc}>{task.description}</div>}
        </div>
        {renderTaskNodes(task.id, depth + 1)}
      </div>
    ));
  };

  if (loading) return <div className={styles.page}><p>Loading...</p></div>;
  if (!app) return <div className={styles.page}><p>Not found</p></div>;

  const statusLabel = (s: string) => (a as any)[STATUS_LABELS[s]] || s;
  const actions = NEXT_ACTIONS[app.status] || [];
  const existingMemberIds = new Set(app.members.map(m => m.user_id));
  const availableUsers = users.filter(u => !existingMemberIds.has(u.id));
  const tzDepartments = parseDepartments(app.tz_content);
  const isReviewStatus = app.status === 'review';
  const isDistributeStatus = app.status === 'approved' || app.status === 'distributing';
  const tzSphereEditable =
    (isReviewer || (isConsultant && consultantOwns)) &&
    ['contacting', 'tz_received', 'revision'].includes(app.status);
  const canConsultantEditMain =
    isConsultant && consultantOwns && ['new', 'contacting', 'tz_received', 'revision'].includes(app.status);
  const canShowMainEdit =
    app.status !== 'completed' &&
    !isReviewStatus &&
    !isDistributeStatus &&
    (isReviewer || canConsultantEditMain);

  return (
    <div className={`${styles.page} ${styles.detail}`}>
      <button className={styles.backBtn} onClick={() => navigate('/applications')}>
        <ArrowLeft size={16} /> {a.back}
      </button>

      {/* Main info card */}
      <div className={styles.card}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
          <h2 className={styles.cardTitle} style={{ marginBottom: 0 }}>{app.client_name}</h2>
          <span className={`${styles.badge} ${STATUS_BADGE[app.status] || ''}`}>{statusLabel(app.status)}</span>
        </div>

        {(app.project_name || app.project_id) && (
          <div style={{ marginBottom: 12, display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
            {app.project_name && (
              <span style={{ fontSize: 14 }}>
                <span className={styles.fieldLabel} style={{ marginRight: 8 }}>{(a as any).projectName || 'Проект'}</span>
                <span className={styles.fieldValue}>{app.project_name}</span>
              </span>
            )}
            {app.project_id && (
              <button type="button" className="btn btn-primary btn-sm" onClick={() => navigate(`/project/${app.project_id}`)}>
                {(a as any).projectOpen || 'Открыть проект'}
              </button>
            )}
          </div>
        )}

        {editing ? (
          <div className={styles.form}>
            <div className={styles.fieldGrid}>
              <div className={styles.field}>
                <label className={styles.fieldLabel}>{a.clientName}</label>
                <input className="input" value={form.client_name} onChange={e => setForm(f => ({ ...f, client_name: e.target.value }))} />
              </div>
              <div className={styles.field}>
                <label className={styles.fieldLabel}>{a.clientEmail}</label>
                <input className="input" value={form.client_email} onChange={e => setForm(f => ({ ...f, client_email: e.target.value }))} />
              </div>
              <div className={styles.field}>
                <label className={styles.fieldLabel}>{a.clientPhone}</label>
                <input className="input" value={form.client_phone} onChange={e => setForm(f => ({ ...f, client_phone: e.target.value }))} />
              </div>
              <div className={styles.field}>
                <label className={styles.fieldLabel}>{a.clientCompany}</label>
                <input className="input" value={form.client_company} onChange={e => setForm(f => ({ ...f, client_company: e.target.value }))} />
              </div>
              <div className={`${styles.field} ${styles.fieldFull}`}>
                <label className={styles.fieldLabel}>{(a as any).projectName || 'Проект'}</label>
                <input
                  className="input"
                  value={form.project_name}
                  onChange={e => setForm(f => ({ ...f, project_name: e.target.value }))}
                  required
                />
              </div>
              <div className={`${styles.field} ${styles.fieldFull}`}>
                <label className={styles.fieldLabel}>{a.description}</label>
                <textarea className={`input ${styles.tzTextarea}`} rows={3} value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
              </div>
            </div>
            <div className={styles.formActions}>
              <button className="btn btn-ghost btn-sm" onClick={() => setEditing(false)}>{lang.common?.cancel || 'Отмена'}</button>
              <button className="btn btn-primary btn-sm" onClick={handleSave}>{a.save}</button>
            </div>
          </div>
        ) : (
          <>
            <div className={styles.fieldGrid}>
              <div className={styles.field}>
                <span className={styles.fieldLabel}>{a.clientEmail}</span>
                <span className={styles.fieldValue}>{app.client_email || '—'}</span>
              </div>
              <div className={styles.field}>
                <span className={styles.fieldLabel}>{a.clientPhone}</span>
                <span className={styles.fieldValue}>{app.client_phone || '—'}</span>
              </div>
              <div className={styles.field}>
                <span className={styles.fieldLabel}>{a.clientCompany}</span>
                <span className={styles.fieldValue}>{app.client_company || '—'}</span>
              </div>
              <div className={styles.field}>
                <span className={styles.fieldLabel}>{a.source}</span>
                <span className={`${styles.badge} ${app.source === 'website' ? styles.badgeWebsite : styles.badgeManual}`}>
                  {app.source === 'website' ? a.sourceWebsite : a.sourceManual}
                </span>
              </div>
              <div className={styles.field}>
                <span className={styles.fieldLabel}>{a.consultant}</span>
                <span className={styles.fieldValue}>{app.consultant_name || '—'}</span>
              </div>
              {app.approved_by_id && (
                <div className={styles.field}>
                  <span className={styles.fieldLabel}>{a.approvedBy}</span>
                  <span className={styles.fieldValue}>{app.approved_by_name || app.approved_by_id}</span>
                </div>
              )}
              {app.description && (
                <div className={`${styles.field} ${styles.fieldFull}`}>
                  <span className={styles.fieldLabel}>{a.description}</span>
                  <span className={styles.fieldValue}>{app.description}</span>
                </div>
              )}
              {app.review_comment && (
                <div className={`${styles.field} ${styles.fieldFull}`}>
                  <span className={styles.fieldLabel}>{a.reviewComment}</span>
                  <span className={styles.fieldValue} style={{ color: 'var(--color-danger)' }}>{app.review_comment}</span>
                </div>
              )}
            </div>

            {!isReviewStatus && !isDistributeStatus && (
              <div className={styles.actions}>
                {canShowMainEdit && (
                  <button className="btn btn-ghost btn-sm" onClick={() => setEditing(true)}>{lang.common?.edit || 'Редактировать'}</button>
                )}
                {actions.map(act => {
                  if (act.next === 'revision') {
                    return (
                      <button key={act.next} className="btn btn-danger btn-sm" onClick={() => setShowReject(true)}>
                        {(a as any)[act.labelKey] || act.labelKey}
                      </button>
                    );
                  }
                  if (act.next === 'review') {
                    return (
                      <button key={act.next} className="btn btn-primary btn-sm" onClick={() => handleSendForReview()}>
                        {(a as any)[act.labelKey] || act.labelKey}
                      </button>
                    );
                  }
                  return (
                    <button key={act.next} className="btn btn-primary btn-sm" onClick={() => changeStatus(act.next)}>
                      {(a as any)[act.labelKey] || act.labelKey}
                    </button>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>

      {tzSphereEditable && (
        <div className={styles.card}>
          <h3 className={styles.cardTitle}>{(a as any).tzBySpheres || 'ТЗ по сферам'}</h3>
          <p style={{ color: 'var(--color-text-muted)', fontSize: 13, marginBottom: 12 }}>
            {(a as any).tzBySpheresHint ||
              'Добавьте сферы и опишите часть ТЗ для каждой. Кнопка «Отправить на проверку» сохранит ТЗ и отправит заявку руководству.'}
          </p>
          <div className={`${styles.field} ${styles.fieldFull}`}>
            <label className={styles.fieldLabel}>{(a as any).tzIntro || 'Общее ТЗ / вводная'}</label>
            <textarea
              className={`input ${styles.tzTextarea}`}
              rows={3}
              value={sphereDraft.intro}
              onChange={e => setSphereDraft(d => ({ ...d, intro: e.target.value }))}
            />
          </div>
          {sphereDraft.rows.map((row, idx) => (
            <div key={row.localId} className={styles.taskCard} style={{ marginTop: 12 }}>
              <div className={styles.newTaskRow} style={{ marginBottom: 8, alignItems: 'center' }}>
                <select
                  className="input"
                  value={row.name}
                  onChange={e =>
                    setSphereDraft(d => ({
                      ...d,
                      rows: d.rows.map((r, i) => (i === idx ? { ...r, name: e.target.value } : r)),
                    }))
                  }
                >
                  <option value="">{(a as { selectSphere?: string }).selectSphere || 'Выберите сферу'}</option>
                  {SPHERES.map(s => {
                    const takenElsewhere = sphereDraft.rows.some((r, i) => i !== idx && r.name === s);
                    if (takenElsewhere && row.name !== s) return null;
                    return (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    );
                  })}
                </select>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  style={{ color: 'var(--color-danger)' }}
                  onClick={() => setSphereDraft(d => ({ ...d, rows: d.rows.filter((_, i) => i !== idx) }))}
                >
                  {(a as any).removeSphere || 'Удалить сферу'}
                </button>
              </div>
              <textarea
                className={`input ${styles.tzTextarea}`}
                rows={4}
                placeholder={(a as any).spherePart || 'Часть ТЗ для этой сферы'}
                value={row.content}
                onChange={e =>
                  setSphereDraft(d => ({
                    ...d,
                    rows: d.rows.map((r, i) => (i === idx ? { ...r, content: e.target.value } : r)),
                  }))
                }
              />
            </div>
          ))}
          <div className={styles.actions} style={{ marginTop: 12 }}>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() =>
                setSphereDraft(d => ({
                  ...d,
                  rows: [...d.rows, { localId: crypto.randomUUID(), name: '', content: '' }],
                }))
              }
            >
              {(a as any).addSphere || 'Добавить сферу'}
            </button>
            <button type="button" className="btn btn-primary btn-sm" onClick={() => handleSaveSphereOnly()}>
              {(a as any).saveTzDraft || 'Сохранить ТЗ'}
            </button>
          </div>
        </div>
      )}

      {isConsultant && consultantOwns && isReviewStatus && (
        <div className={styles.card} style={{ borderLeft: '3px solid var(--color-warning, #d97706)' }}>
          <p style={{ margin: '0 0 12px', fontSize: 14 }}>{(a as any).lockedForReview || 'Заявка на проверке. Редактирование недоступно до решения руководства.'}</p>
          <div className={styles.fieldLabel} style={{ marginBottom: 8 }}>{(a as any).pendingReviewReadonly || 'Отправленное ТЗ'}</div>
          {tzDepartments.length > 0 ? (
            tzDepartments.map((dept, idx) => (
              <div key={idx} className={styles.taskCard} style={{ marginBottom: 8 }}>
                {dept.name && <div className={styles.taskCardTitle}>{dept.name}</div>}
                <div className={`${styles.taskCardDesc} ${styles.tzBody}`}>{dept.content.trim()}</div>
              </div>
            ))
          ) : app.tz_content ? (
            <div className={`${styles.taskCardDesc} ${styles.tzBody}`}>{app.tz_content}</div>
          ) : (
            <span style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>—</span>
          )}
        </div>
      )}

      {/* Review panel — prominent for owner/deputy/admin when status=review */}
      {isReviewStatus && isReviewer && (
        <div className={styles.reviewPanel}>
          <div className={styles.reviewPanelTitle}>
            <ClipboardCheck size={20} />
            {a.reviewPanel}
          </div>
          <p className={styles.reviewPanelHint}>{a.reviewApproveHint}</p>

          {/* TZ by departments */}
          {app.tz_content && (
            <div style={{ marginBottom: 16 }}>
              <div className={styles.fieldLabel} style={{ marginBottom: 8, fontSize: 13 }}>{a.reviewTzByDept}</div>
              {tzDepartments.length > 0 ? (
                tzDepartments.map((dept, idx) => (
                  <div key={idx} className={styles.taskCard}>
                    {dept.name && <div className={styles.taskCardTitle}>{dept.name}</div>}
                    <div className={`${styles.taskCardDesc} ${styles.tzBody}`}>{dept.content.trim()}</div>
                  </div>
                ))
              ) : (
                <div className={styles.taskCard}>
                  <div className={`${styles.taskCardDesc} ${styles.tzBody}`}>{app.tz_content}</div>
                </div>
              )}
            </div>
          )}

          {/* Show departments list */}
          {app.departments && (
            <div style={{ marginBottom: 16 }}>
              <div className={styles.fieldLabel} style={{ marginBottom: 4 }}>{a.departments}</div>
              <div className={styles.fieldValue}>{app.departments}</div>
            </div>
          )}

          <div className={styles.actions}>
            <button className="btn btn-ghost btn-sm" onClick={() => setEditing(true)}>{lang.common?.edit || 'Редактировать'}</button>
            <button className="btn btn-primary btn-sm" onClick={() => changeStatus('approved')}>{a.approve}</button>
            <button className="btn btn-danger btn-sm" onClick={() => setShowReject(true)}>{a.reject}</button>
          </div>
        </div>
      )}

      {/* Distribute panel — for owner/deputy/admin when status=approved or distributing */}
      {isDistributeStatus && isReviewer && (
        <div className={styles.distributePanel}>
          <div className={styles.distributePanelTitle}>
            <LayoutList size={20} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 8 }} />
            {a.distributeTitle}
          </div>
          <p className={styles.distributePanelHint}>
            {a.distributeHint}
            {a.distributeBoardColumnsHint ? ` ${a.distributeBoardColumnsHint}` : ''}
          </p>

          <div className={styles.taskCard} style={{ marginBottom: 16 }}>
            <label className={styles.fieldLabel} style={{ fontSize: 13 }}>
              {(a as any).projectName || 'Проект'}
            </label>
            <div className={styles.newTaskRow} style={{ marginTop: 6 }}>
              <input
                className="input"
                value={projectNameQuick}
                onChange={e => setProjectNameQuick(e.target.value)}
                placeholder={(a as any).projectName || 'Проект'}
              />
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={async () => {
                  try {
                    await api.put(`/applications/${id}`, { project_name: projectNameQuick.trim() || undefined });
                    await load();
                  } catch { /* global */ }
                }}
              >
                {a.save}
              </button>
            </div>
          </div>

          {tzDepartments.some(d => d.name.trim()) && (
            <div style={{ marginBottom: 20 }}>
              <div className={styles.fieldLabel} style={{ marginBottom: 8, fontSize: 13 }}>
                {a.distributeBySphere}
              </div>
              <p style={{ color: 'var(--color-text-muted)', fontSize: 12, marginBottom: 12 }}>
                {a.distributeBySphereHint}
              </p>
              <div className={styles.actions} style={{ marginBottom: 12 }}>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => handleSaveSphereDeadlines()}>
                  {a.saveSphereDeadlines}
                </button>
              </div>
              {tzDepartments.map((dept, idx) => {
                if (!dept.name.trim()) return null;
                const staff = usersInSphere(users, dept.name);
                const checked = sphereAssignChecks[idx] || [];
                const deptKey = dept.name.trim();
                return (
                  <div key={`sph-${idx}-${dept.name}`} className={styles.taskCard} style={{ marginBottom: 12 }}>
                    <div className={styles.taskCardTitle}>{dept.name}</div>
                    <div className={`${styles.taskCardDesc} ${styles.tzBody}`} style={{ marginBottom: 10 }}>
                      {dept.content.trim()}
                    </div>
                    <div className={styles.field} style={{ marginBottom: 8 }}>
                      <label className={styles.fieldLabel} style={{ fontSize: 12 }}>
                        {(a as any).sphereDeadline || 'Дедлайн по сфере'}
                      </label>
                      <AppDeadlinePicker
                        value={sphereDeadlineByName[deptKey] || ''}
                        placeholder={(a as any).sphereDeadlinePlaceholder || 'дд.мм.гггг чч.мм'}
                        onCommit={next =>
                          setSphereDeadlineByName(d => {
                            const copy = { ...d };
                            if (next.trim()) copy[deptKey] = next.trim();
                            else delete copy[deptKey];
                            return copy;
                          })
                        }
                      />
                    </div>
                    <div className={styles.fieldLabel} style={{ fontSize: 12, marginBottom: 4 }}>
                      {a.boardCardTitleLabel}
                    </div>
                    <input
                      className="input"
                      style={{ marginBottom: 10 }}
                      value={sphereTaskTitles[deptKey] || ''}
                      onChange={e => setSphereTaskTitles(d => ({ ...d, [deptKey]: e.target.value }))}
                      placeholder={a.boardCardTitlePlaceholder}
                    />
                    <div className={styles.fieldLabel} style={{ fontSize: 12, marginBottom: 4 }}>
                      {a.boardCardDescriptionLabel}
                    </div>
                    <p style={{ fontSize: 11, color: 'var(--color-text-muted)', margin: '0 0 6px', lineHeight: 1.35 }}>
                      {a.boardCardDescriptionHint}
                    </p>
                    <textarea
                      className={`input ${styles.tzTextarea}`}
                      rows={5}
                      value={
                        sphereTaskDescriptions[deptKey] !== undefined
                          ? sphereTaskDescriptions[deptKey]
                          : dept.content
                      }
                      onChange={e =>
                        setSphereTaskDescriptions(d => ({ ...d, [deptKey]: e.target.value }))
                      }
                      placeholder={a.taskDescription}
                      style={{ marginBottom: 10 }}
                    />
                    <div className={styles.fieldLabel} style={{ fontSize: 12, marginBottom: 6 }}>
                      {a.assignees}
                    </div>
                    <CollapsibleAssigneePicker
                      staff={staff}
                      selectedIds={checked}
                      onToggle={(userId, isOn) => toggleSphereAssignee(idx, userId, isOn)}
                      nonePlaceholder={a.selectAssignees}
                      disabled={staff.length === 0}
                    />
                    <div className={styles.newTaskRow}>
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        disabled={
                          !checked.length ||
                          !staff.length ||
                          !(sphereTaskTitles[deptKey] || '').trim()
                        }
                        onClick={() => handleAssignSphereTask(dept, idx)}
                      >
                        {a.assignSphereTask}
                      </button>
                    </div>
                    {staff.length === 0 && (
                      <p style={{ color: 'var(--color-danger)', fontSize: 12, marginTop: 6 }}>
                        {a.noStaffInSphere}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Existing tasks (дерево корень → подзадачи) */}
          {(app.tasks || []).length === 0 ? (
            <p style={{ color: 'var(--color-text-muted)', fontSize: 13, marginBottom: 12 }}>{a.noTasks}</p>
          ) : (
            <div style={{ marginBottom: 16 }}>{renderTaskNodes(undefined, 0)}</div>
          )}

          {/* New task form */}
          <div className={styles.newTaskForm}>
            {newTask.parent_id && (
              <div style={{ fontSize: 13, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ color: 'var(--color-text-muted)' }}>
                  {(a as any).creatingSubtaskFor || 'Подзадача для'}:{' '}
                  <strong>{parentTitleById.get(newTask.parent_id) || '…'}</strong>
                </span>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => setNewTask(f => ({ ...f, parent_id: '' }))}
                >
                  {(a as any).clearParent || 'Сбросить'}
                </button>
              </div>
            )}
            <div className={styles.fieldLabel} style={{ marginBottom: 8, fontSize: 12, color: 'var(--color-text-muted)' }}>
              {a.extraTaskHint}
            </div>
            <div className={styles.newTaskRow}>
              <input className="input" placeholder={a.taskTitle} value={newTask.title} onChange={e => setNewTask(f => ({ ...f, title: e.target.value }))} />
              <select
                className="input"
                style={{ minWidth: 0 }}
                value={newTask.department}
                onChange={e => setNewTask(f => ({ ...f, department: e.target.value }))}
                aria-label={a.taskSphereColumn}
              >
                <option value="">{a.taskSphereNone}</option>
                {SPHERES.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <textarea className={`input ${styles.tzTextarea}`} placeholder={a.taskDescription} rows={2} value={newTask.description} onChange={e => setNewTask(f => ({ ...f, description: e.target.value }))} />
            <div style={{ marginTop: 8 }}>
              <AppDeadlinePicker
                value={newTask.deadline}
                onCommit={next => setNewTask(f => ({ ...f, deadline: next }))}
                placeholder={`${(a as any).taskDeadline || 'Дедлайн'} (${(a as any).sphereDeadlinePlaceholder || 'дд.мм.гггг чч.мм'})`}
              />
            </div>
            <div className={styles.fieldLabel} style={{ fontSize: 12, marginTop: 10, marginBottom: 6 }}>
              {(a as any).assignees || 'Ответственные'}
            </div>
            <CollapsibleAssigneePicker
              staff={users}
              selectedIds={newTask.assignee_ids}
              onToggle={(userId, isOn) => toggleNewTaskAssignee(userId, isOn)}
              nonePlaceholder={a.selectAssignees || 'Выберите ответственных'}
              disabled={users.length === 0}
            />
            <div className={styles.newTaskRow}>
              <button className="btn btn-primary btn-sm" onClick={handleAddTask} disabled={!newTask.title.trim()}>
                {a.addTask}
              </button>
            </div>
          </div>

          {/* Status actions */}
          <div className={styles.reviewActions}>
            {app.status === 'approved' && (
              <button className="btn btn-primary btn-sm" onClick={() => changeStatus('distributing')}>
                {statusLabel('distributing')}
              </button>
            )}
            {app.status === 'distributing' && (
              <button className="btn btn-primary btn-sm" onClick={() => changeStatus('completed')}>
                {a.markCompleted}
              </button>
            )}
          </div>
        </div>
      )}

      {showReject && (
        <div className={styles.modal}>
          <div className={styles.overlay} onClick={() => setShowReject(false)} />
          <div className={styles.dialog}>
            <h3 style={{ marginBottom: 12 }}>{a.reject}</h3>
            <textarea className={`input ${styles.tzTextarea}`} rows={3} placeholder={a.rejectComment} value={rejectComment} onChange={e => setRejectComment(e.target.value)} />
            <div className={styles.formActions} style={{ marginTop: 12 }}>
              <button className="btn btn-ghost btn-sm" onClick={() => setShowReject(false)}>{lang.common?.cancel || 'Отмена'}</button>
              <button className="btn btn-danger btn-sm" onClick={() => changeStatus('revision', rejectComment)}>{a.reject}</button>
            </div>
          </div>
        </div>
      )}

      {!isConsultant && <CustomerSatisfactionPanel applicationId={app.id} />}

      {/* Members — только руководство (API не даст консультанту) */}
      {!isConsultant && (
      <div className={styles.card}>
        <h3 className={styles.cardTitle}>{a.members}</h3>
        {app.members.length === 0 ? (
          <p style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>—</p>
        ) : (
          <div className={styles.memberList}>
            {app.members.map(m => (
              <div key={m.id} className={styles.memberRow}>
                <span className={styles.memberName}>{m.user_name || m.user_id}</span>
                <button className="btn btn-ghost btn-sm" style={{ color: 'var(--color-danger)' }} onClick={() => removeMember(m.id)}>{a.removeMember}</button>
              </div>
            ))}
          </div>
        )}
        <div className={styles.addMemberRow}>
          <select className="input" value={selectedUserId} onChange={e => setSelectedUserId(e.target.value)}>
            <option value="">{a.addMember}...</option>
            {availableUsers.map(u => (
              <option key={u.id} value={u.id}>{u.name}</option>
            ))}
          </select>
          <button className="btn btn-primary btn-sm" onClick={addMember} disabled={!selectedUserId}>{a.addMember}</button>
        </div>
      </div>
      )}

      {/* History */}
      <div className={styles.card}>
        <h3 className={styles.cardTitle}>{a.history}</h3>
        {app.history.length === 0 ? (
          <p style={{ color: 'var(--color-text-muted)', fontSize: 13 }}>—</p>
        ) : (
          <div className={styles.historyList}>
            {app.history.map(h => (
              <div key={h.id} className={styles.historyItem}>
                <span className={styles.historyDot} />
                <div className={styles.historyContent}>
                  <span>
                    {h.old_status ? `${statusLabel(h.old_status)} → ` : ''}
                    {statusLabel(h.new_status)}
                  </span>
                  {h.comment && <span style={{ marginLeft: 8, fontStyle: 'italic' }}>«{h.comment}»</span>}
                  <div className={styles.historyMeta}>
                    {h.user_name || ''} · {new Date(h.created_at).toLocaleString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
