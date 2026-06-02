import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Pencil,
  Users,
  FileText,
  UserRound,
  CalendarDays,
  Reply,
  Trash2,
  Check,
  X,
  Paperclip,
  BarChart3,
  Loader2,
  Send,
  LayoutGrid,
  PanelRightOpen,
  PanelRightClose,
  MoreVertical,
  Star,
  Bell,
  Search,
  ChevronLeft,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  Circle,
  Settings,
  Filter,
  Plus,
  Archive,
  GripVertical,
  Copy,
  ImagePlus,
  ArrowRight,
  CirclePlus,
} from 'lucide-react';
import { useAppSelector } from '../../store/hooks';
import { t } from '../../i18n';
import api from '../../api/client';
import { iterationBoardColumnsPath } from '../../api/iterationPaths';
import axios, { type AxiosError } from 'axios';
import type { Project, Iteration, Task, User, ChatMessage, BoardColumn } from '../../types';
import { TASK_STATUSES, TASK_PRIORITIES, SPHERES } from '../../types';
import styles from './ProjectDetail.module.css';
import { SubtasksPanel } from './ProjectViews';

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user: currentUser } = useAppSelector(s => s.auth);
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);
  const LOCALE_MAP: Record<string, string> = { ru: 'ru-RU', ka: 'ka-GE', en: 'en-US', ar: 'ar-SA' };

  const [project, setProject] = useState<Project | null>(null);
  const [iterations, setIterations] = useState<Iteration[]>([]);
  const [selectedIteration, setSelectedIteration] = useState<Iteration | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [members, setMembers] = useState<User[]>([]);
  const [workspaceTab, setWorkspaceTab] = useState<'board'>('board');
  const [rightPanelOpen, setRightPanelOpen] = useState(false);
  const [taskDetailTab, setTaskDetailTab] = useState<'chat' | 'info' | 'desc' | 'sub'>('chat');
  const [descDraft, setDescDraft] = useState('');
  const [workspaceSearch, setWorkspaceSearch] = useState('');
  const [filterDeadline, setFilterDeadline] = useState('');

  const [showIterForm, setShowIterForm] = useState(false);
  const [iterForm, setIterForm] = useState({ name: '', start_date: '', end_date: '', template: '' });
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [taskForm, setTaskForm] = useState({ title: '', description: '', assignee_id: '', start_date: '', deadline: '', priority: 'Средний' });
  const [inlineTaskColId, setInlineTaskColId] = useState<string | null>(null);
  const [inlineTaskTitle, setInlineTaskTitle] = useState('');
  const [selectedTask, setSelectedTask] = useState<Task | null>(null);
  const [comment, setComment] = useState('');

  const iterScrollRef = useRef<HTMLDivElement>(null);

  const [isEditingProjectTitle, setIsEditingProjectTitle] = useState(false);
  const [projectTitleDraft, setProjectTitleDraft] = useState('');
  const [showMembersModal, setShowMembersModal] = useState(false);
  const [projectMembers, setProjectMembers] = useState<any[]>([]);
  const [allUsers, setAllUsers] = useState<User[]>([]);
  const [addMemberId, setAddMemberId] = useState('');
  const [memberSearch, setMemberSearch] = useState('');
  const [showEditIter, setShowEditIter] = useState(false);
  const [editIterForm, setEditIterForm] = useState({ name: '', start_date: '', end_date: '' });
  const [iterContextMenuId, setIterContextMenuId] = useState<string | null>(null);
  const iterContextRef = useRef<HTMLDivElement>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [dragIterIdx, setDragIterIdx] = useState<number | null>(null);
  const [dragOverIterIdx, setDragOverIterIdx] = useState<number | null>(null);

  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [chatSearch, setChatSearch] = useState('');
  const [chatSearchResults, setChatSearchResults] = useState<any[] | null>(null);
  const [showMentions, setShowMentions] = useState(false);
  const [mentionFilter, setMentionFilter] = useState('');
  const [editingMsg, setEditingMsg] = useState<string | null>(null);
  const [editMsgText, setEditMsgText] = useState('');
  const [replyTo, setReplyTo] = useState<ChatMessage | null>(null);
  const [typingUsers, setTypingUsers] = useState<string[]>([]);
  const typingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const chatInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [showPollForm, setShowPollForm] = useState(false);
  const [pollForm, setPollForm] = useState({ question: '', is_multiple: false, options: ['', ''] });

  const [chatFileUploading, setChatFileUploading] = useState(false);

  const [boardColumns, setBoardColumns] = useState<BoardColumn[]>([]);
  const [expandedBoardTasks, setExpandedBoardTasks] = useState<Record<string, boolean>>({});
  const [taskFormColumnId, setTaskFormColumnId] = useState<string | null>(null);
  const [taskFormParentId, setTaskFormParentId] = useState<string | null>(null);
  const [showColumnForm, setShowColumnForm] = useState(false);
  const [columnFormTitle, setColumnFormTitle] = useState('');
  const [iterCtxMenuPos, setIterCtxMenuPos] = useState<{ top: number; left: number } | null>(null);

  // Drag-and-drop state
  const [dragTaskId, setDragTaskId] = useState<string | null>(null);
  const [dragOverColumnId, setDragOverColumnId] = useState<string | null>(null);
  const [dragColumnId, setDragColumnId] = useState<string | null>(null);
  const [dragOverColTargetId, setDragOverColTargetId] = useState<string | null>(null);

  // Column context menu state
  const [columnMenuId, setColumnMenuId] = useState<string | null>(null);
  const [columnMenuPos, setColumnMenuPos] = useState<{ top: number; left: number } | null>(null);
  const [columnMenuSub, setColumnMenuSub] = useState<'sort' | null>(null);
  const [columnSortSub, setColumnSortSub] = useState<string | null>(null);
  const [columnSorts, setColumnSorts] = useState<Record<string, { key: string; dir: string }>>({});
  const [editingColumnId, setEditingColumnId] = useState<string | null>(null);
  const [editingColumnTitle, setEditingColumnTitle] = useState('');

  // Task context menu state
  const [taskCtxMenuId, setTaskCtxMenuId] = useState<string | null>(null);
  const [taskCtxMenuSub, setTaskCtxMenuSub] = useState<'move' | null>(null);
  const [taskCtxMenuPos, setTaskCtxMenuPos] = useState<{ top: number; left: number } | null>(null);
  const [renamingTaskId, setRenamingTaskId] = useState<string | null>(null);
  const [renamingTaskTitle, setRenamingTaskTitle] = useState('');
  const taskCoverRef = useRef<HTMLInputElement>(null);
  const [taskCoverTargetId, setTaskCoverTargetId] = useState<string | null>(null);

  // Sticker popup state
  const [stickerMenuId, setStickerMenuId] = useState<string | null>(null);
  const [stickerSub, setStickerSub] = useState<'assignee' | 'deadline' | 'priority' | null>(null);
  const [stickerMenuPos, setStickerMenuPos] = useState<{ top: number; left: number } | null>(null);
  const [stickerStartDate, setStickerStartDate] = useState('');
  const [stickerDeadline, setStickerDeadline] = useState('');

  // Inline subtask creation
  const [inlineSubParentId, setInlineSubParentId] = useState<string | null>(null);
  const [inlineSubTitle, setInlineSubTitle] = useState('');

  const COLUMN_COLORS = [
    '#334155', '#ef4444', '#f97316', '#eab308', '#22c55e', '#14b8a6', '#3b82f6', '#a855f7',
    '#475569', '#dc2626', '#ea580c', '#f59e0b', '#16a34a', '#0d9488', '#2563eb', '#9333ea',
  ];

  const taskFileRef = useRef<HTMLInputElement>(null);

  // Task filters
  const [filterAssignee, setFilterAssignee] = useState('');
  const [filterPriority, setFilterPriority] = useState('');
  const [openFilterDropdown, setOpenFilterDropdown] = useState<'assignee' | 'deadline' | 'priority' | null>(null);
  const [filterMyTasks, setFilterMyTasks] = useState(false);
  const filterDropdownRef = useRef<HTMLDivElement>(null);
  const columnsScrollRef = useRef<HTMLDivElement>(null);

  const CHAT_PANEL_WIDTH_KEY = 'projectChatPanelWidthPx';
  const clampChatWidth = useCallback((w: number) => {
    if (typeof window === 'undefined') return Math.min(800, Math.max(280, w));
    const max = Math.floor(window.innerWidth * 0.5);
    return Math.min(max, Math.max(280, Math.round(w)));
  }, []);
  const [chatPanelWidth, setChatPanelWidth] = useState(() => {
    try {
      const raw = localStorage.getItem(CHAT_PANEL_WIDTH_KEY);
      const n = raw ? parseInt(raw, 10) : 320;
      if (!Number.isFinite(n)) return 320;
      const max = typeof window !== 'undefined' ? Math.floor(window.innerWidth * 0.5) : 600;
      return Math.min(max, Math.max(280, n));
    } catch {
      return 320;
    }
  });
  const dragChatRef = useRef(false);

  useEffect(() => {
    try {
      localStorage.setItem(CHAT_PANEL_WIDTH_KEY, String(chatPanelWidth));
    } catch {
      /* ignore */
    }
  }, [chatPanelWidth]);

  useEffect(() => {
    const onResize = () => setChatPanelWidth(w => clampChatWidth(w));
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [clampChatWidth]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragChatRef.current) return;
      const rtl = document.documentElement.getAttribute('dir') === 'rtl';
      const max = window.innerWidth * 0.5;
      const min = 280;
      const w = rtl ? e.clientX : window.innerWidth - e.clientX;
      setChatPanelWidth(Math.min(max, Math.max(min, w)));
    };
    const onUp = () => {
      if (!dragChatRef.current) return;
      dragChatRef.current = false;
      document.body.style.removeProperty('cursor');
      document.body.style.removeProperty('user-select');
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, []);

  const onChatResizeStart = (e: React.MouseEvent) => {
    e.preventDefault();
    dragChatRef.current = true;
    document.body.style.cursor = 'ew-resize';
    document.body.style.userSelect = 'none';
  };

  const isOverdue = (deadline?: string) => {
    if (!deadline) return false;
    return new Date(deadline) < new Date() && new Date(deadline).toDateString() !== new Date().toDateString();
  };

  const isDueToday = (deadline?: string) => {
    if (!deadline) return false;
    return new Date(deadline).toDateString() === new Date().toDateString();
  };

  // Close filter dropdown on outside click
  useEffect(() => {
    if (!openFilterDropdown) return;
    const handler = (e: MouseEvent) => {
      if (filterDropdownRef.current && !filterDropdownRef.current.contains(e.target as Node)) {
        setOpenFilterDropdown(null);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [openFilterDropdown]);

  // Close iteration context menu on outside click
  useEffect(() => {
    if (!iterContextMenuId) return;
    const handler = (e: MouseEvent) => {
      if (iterContextRef.current && !iterContextRef.current.contains(e.target as Node)) {
        setIterContextMenuId(null);
        setIterCtxMenuPos(null);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [iterContextMenuId]);

  const filteredTasks = tasks.filter(task => {
    if (filterMyTasks && currentUser && task.assignee_id !== currentUser.id) return false;
    if (filterAssignee && task.assignee_id !== filterAssignee) return false;
    if (filterPriority && task.priority !== filterPriority) return false;
    if (workspaceSearch && !task.title.toLowerCase().includes(workspaceSearch.toLowerCase())) return false;
    if (filterDeadline === 'overdue' && !isOverdue(getTaskEffectiveDeadline(task))) return false;
    if (filterDeadline === 'today' && !isDueToday(getTaskEffectiveDeadline(task))) return false;
    return true;
  });

  const filteredTaskIds = useMemo(() => new Set(filteredTasks.map(t => t.id)), [filteredTasks]);

  const rootVisibleInColumn = (root: Task, columnId: string): boolean => {
    if (root.parent_id || root.board_column_id !== columnId) return false;
    const dfs = (id: string): boolean => {
      if (filteredTaskIds.has(id)) return true;
      return tasks.filter(x => x.parent_id === id).some(c => dfs(c.id));
    };
    return dfs(root.id);
  };

  const COLUMN_ACCENTS = ['#3b82f6', '#f97316', '#14b8a6', '#a855f7', '#eab308'];

  const toDateTimeLocalValue = (value?: string | null) => {
    if (!value) return '';
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return '';
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

  const formatTaskDatePoint = (value?: string | null) => {
    if (!value) return null;
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return null;
    const datePart = d.toLocaleDateString(LOCALE_MAP[language] || 'en-US', { day: 'numeric', month: 'short' });
    const h = d.getHours(); const m = d.getMinutes();
    if (h === 0 && m === 0) return datePart;
    return `${datePart} к ${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  };

  const formatTaskDateRange = (task: Pick<Task, 'start_date' | 'deadline'>) => {
    const start = formatTaskDatePoint(task.start_date);
    const end = formatTaskDatePoint(task.deadline);
    if (start && end) return start === end ? start : `${start} - ${end}`;
    return end || start || null;
  };

  const getTaskEffectiveDeadline = (task: Pick<Task, 'start_date' | 'deadline'>) => task.deadline || task.start_date;

  const getFloatingMenuPosition = useCallback((target: HTMLElement, menuWidth: number, menuHeight: number) => {
    const rect = target.getBoundingClientRect();
    const left = Math.max(12, Math.min(rect.right - menuWidth, window.innerWidth - menuWidth - 12));
    const belowTop = rect.bottom + 6;
    const aboveTop = rect.top - menuHeight - 6;
    const top = belowTop + menuHeight <= window.innerHeight - 12 ? belowTop : Math.max(12, aboveTop);
    return { top, left };
  }, []);

  const closeTaskContextMenu = useCallback(() => {
    setTaskCtxMenuId(null);
    setTaskCtxMenuSub(null);
    setTaskCtxMenuPos(null);
  }, []);

  const closeStickerMenu = useCallback(() => {
    setStickerMenuId(null);
    setStickerSub(null);
    setStickerMenuPos(null);
    setStickerStartDate('');
    setStickerDeadline('');
  }, []);

  const openTaskContextMenu = (e: React.MouseEvent<HTMLButtonElement>, taskId: string) => {
    e.stopPropagation();
    if (taskCtxMenuId === taskId) {
      closeTaskContextMenu();
      return;
    }
    setTaskCtxMenuPos(getFloatingMenuPosition(e.currentTarget, 220, 320));
    setTaskCtxMenuSub(null);
    setTaskCtxMenuId(taskId);
  };

  const openStickerMenuForTask = (
    e: React.MouseEvent<HTMLElement>,
    task: Task,
    sub: 'assignee' | 'deadline' | 'priority' | null,
  ) => {
    e.stopPropagation();
    if (stickerMenuId === task.id && stickerSub === sub) {
      closeStickerMenu();
      return;
    }
    setStickerStartDate(toDateTimeLocalValue(task.start_date));
    setStickerDeadline(toDateTimeLocalValue(task.deadline));
    setStickerMenuPos(getFloatingMenuPosition(e.currentTarget, 260, sub === 'assignee' ? 360 : sub === 'deadline' ? 300 : 240));
    setStickerMenuId(task.id);
    setStickerSub(sub);
  };

  const AVATAR_COLORS = ['#3b82f6','#f59e0b','#ef4444','#22c55e','#8b5cf6','#ec4899','#14b8a6','#f97316'];
  const avatarColor = (name: string) => AVATAR_COLORS[Math.abs([...name].reduce((a, c) => a + c.charCodeAt(0), 0)) % AVATAR_COLORS.length];

  const renderTaskContextMenu = (parentTask: Task) => {
    if (taskCtxMenuId !== parentTask.id || !taskCtxMenuPos || typeof document === 'undefined') return null;
    return createPortal(
      <div className={styles.ygTaskCtxMenuPortal} style={{ top: taskCtxMenuPos.top, left: taskCtxMenuPos.left }} onClick={e => e.stopPropagation()}>
        <button type="button" onClick={() => { closeTaskContextMenu(); setExpandedBoardTasks(prev => ({ ...prev, [parentTask.id]: true })); setInlineSubParentId(parentTask.id); setInlineSubTitle(''); }}>
          <Plus size={14} /> Создать подзадачу
        </button>
        <button type="button" onClick={() => { toggleTaskCompleted(parentTask); closeTaskContextMenu(); }}>
          <Check size={14} /> {parentTask.is_completed ? 'Снять выполнение' : 'Выполнена'}
        </button>
        <button type="button" onClick={() => { setRenamingTaskId(parentTask.id); setRenamingTaskTitle(parentTask.title); closeTaskContextMenu(); }}>
          <Pencil size={14} /> Переименовать
        </button>
        <div className={styles.ygTaskCtxMoveWrap}>
          <button type="button" onClick={(e) => { e.stopPropagation(); setTaskCtxMenuSub(taskCtxMenuSub === 'move' ? null : 'move'); }}>
            <ArrowRight size={14} /> Переместить <ChevronRight size={12} />
          </button>
        </div>
        {taskCtxMenuSub === 'move' && taskCtxMenuPos && createPortal(
          <div className={styles.ygTaskCtxSubpanel} style={{ top: taskCtxMenuPos.top, left: taskCtxMenuPos.left + 224 }} onClick={e => e.stopPropagation()}>
            {boardColumns.filter(c => c.id !== parentTask.board_column_id).map(c => (
              <button key={c.id} type="button" onClick={() => moveTaskToColumn(parentTask.id, c.id)}>
                {c.title}
              </button>
            ))}
          </div>,
          document.body,
        )}
        <button type="button" onClick={() => deleteTaskById(parentTask.id)}>
          <Archive size={14} /> Поместить в архив
        </button>
        <button type="button" onClick={() => copyTaskLink(parentTask.id)}>
          <Copy size={14} /> Копировать ссылку
        </button>
        <button type="button" onClick={() => { setTaskCoverTargetId(parentTask.id); closeTaskContextMenu(); setTimeout(() => taskCoverRef.current?.click(), 50); }}>
          <ImagePlus size={14} /> Загрузить обложку...
        </button>
        <div className={styles.ygColMenuDivider} />
        <button type="button" className={styles.ygColMenuDanger} onClick={() => deleteTaskById(parentTask.id)}>
          <Trash2 size={14} /> Удалить
        </button>
      </div>,
      document.body,
    );
  };

  const renderStickerMenu = (parentTask: Task) => {
    if (stickerMenuId !== parentTask.id || !stickerMenuPos || typeof document === 'undefined') return null;
    return createPortal(
      <div className={styles.ygStickerMenuPortal} style={{ top: stickerMenuPos.top, left: stickerMenuPos.left }} onClick={e => e.stopPropagation()}>
        {!stickerSub && (
          <>
            <div className={styles.ygStickerMenuTitle}>Добавить стикер</div>
            <button type="button" onClick={() => setStickerSub('assignee')}>
              <UserRound size={14} /> Исполнитель
            </button>
            <button type="button" onClick={() => setStickerSub('deadline')}>
              <CalendarDays size={14} /> Дата или период
            </button>
            <button type="button" onClick={() => setStickerSub('priority')}>
              <BarChart3 size={14} /> Приоритет
            </button>
          </>
        )}
        {stickerSub === 'assignee' && (
          <>
            <div className={styles.ygStickerMenuTitle}>Исполнитель</div>
            {members.map(m => (
              <button key={m.id} type="button" onClick={() => applyStickerAssignee(parentTask.id, m.id)}>
                {m.name}
              </button>
            ))}
            {parentTask.assignee_id && (
              <button type="button" className={styles.ygColMenuDanger} onClick={() => applyStickerAssignee(parentTask.id, '')}>
                <X size={14} /> Убрать
              </button>
            )}
          </>
        )}
        {stickerSub === 'deadline' && (
          <>
            <div className={styles.ygStickerMenuTitle}>Дата или период</div>
            <div className={styles.ygStickerDateRange}>
              <label className={styles.ygStickerFieldLabel}>
                Начало
                <input
                  type="datetime-local"
                  className={styles.ygStickerDateInput}
                  value={stickerStartDate}
                  onChange={e => setStickerStartDate(e.target.value)}
                />
              </label>
              <label className={styles.ygStickerFieldLabel}>
                Конец
                <input
                  type="datetime-local"
                  className={styles.ygStickerDateInput}
                  value={stickerDeadline}
                  onChange={e => setStickerDeadline(e.target.value)}
                  autoFocus
                />
              </label>
            </div>
            <button type="button" className={styles.ygStickerApplyBtn} onClick={() => applyStickerDeadline(parentTask.id, stickerStartDate, stickerDeadline)} disabled={!stickerStartDate && !stickerDeadline}>
              Применить
            </button>
            {(parentTask.start_date || parentTask.deadline) && (
              <button type="button" className={styles.ygColMenuDanger} onClick={() => applyStickerDeadline(parentTask.id, '', '')}>
                <X size={14} /> Убрать
              </button>
            )}
          </>
        )}
        {stickerSub === 'priority' && (
          <>
            <div className={styles.ygStickerMenuTitle}>Приоритет</div>
            {TASK_PRIORITIES.map(p => (
              <button key={p} type="button" onClick={() => applyStickerPriority(parentTask.id, p)}>
                {priorityLabel(p)}
              </button>
            ))}
          </>
        )}
      </div>,
      document.body,
    );
  };

  const renderBoardTaskTree = (parentTask: Task, depth: number, indexInParent: number) => {
    const kids = tasks
      .filter(t => t.parent_id === parentTask.id)
      .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
    const expanded = expandedBoardTasks[parentTask.id];
    const doneSub = kids.filter(k => k.is_completed).length;
    const totalSub = kids.length;
    const completed = !!parentTask.is_completed;
    const kidAssignees = kids.reduce<{ id: string; name: string }[]>((acc, k) => {
      if (k.assignee_id && k.assignee_name && !acc.some(a => a.id === k.assignee_id)) acc.push({ id: k.assignee_id, name: k.assignee_name });
      return acc;
    }, []);

    const row = (
      <div
        key={parentTask.id}
        className={`${styles.ygTaskCard} ${depth > 0 ? styles.ygSubtaskCard : ''} ${completed ? styles.ygTaskCardDone : ''} ${dragTaskId === parentTask.id ? styles.ygTaskDragging : ''}`}
        draggable={depth === 0}
        onDragStart={depth === 0 ? (e) => handleTaskDragStart(e, parentTask.id) : undefined}
        onDragEnd={depth === 0 ? handleTaskDragEnd : undefined}
        onClick={() => loadTaskDetail(parentTask.id)}
        role="presentation"
      >
        <div className={styles.ygTaskTopRow}>
          <button
            type="button"
            className={`${styles.ygStatusBtn} ${completed ? styles.ygStatusDone : ''}`}
            onClick={e => toggleTaskCompleted(parentTask, e)}
            aria-label={lang.tasks.status}
          >
            {completed ? <Check size={10} strokeWidth={3} /> : <Circle size={14} strokeWidth={2} />}
          </button>
          {renamingTaskId === parentTask.id ? (
            <input
              className={styles.ygTaskRenameInput}
              value={renamingTaskTitle}
              onChange={e => setRenamingTaskTitle(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') renameTask(parentTask.id, renamingTaskTitle); if (e.key === 'Escape') { setRenamingTaskId(null); setRenamingTaskTitle(''); } }}
              onBlur={() => renameTask(parentTask.id, renamingTaskTitle)}
              onClick={e => e.stopPropagation()}
              autoFocus
            />
          ) : (
            <>
              <h5 className={styles.ygTaskTitle}>
                {depth > 0 ? `${indexInParent + 1}. ` : ''}
                {parentTask.title}
              </h5>
              <button
                type="button"
                className={styles.ygTitleEditBtn}
                onClick={e => { e.stopPropagation(); setRenamingTaskId(parentTask.id); setRenamingTaskTitle(parentTask.title); }}
              >
                <Pencil size={12} />
              </button>
            </>
          )}
          <div style={{ position: 'relative' }}>
            <button type="button" className={styles.ygIconGhost} aria-label={lang.workspace.moreTools} onClick={e => openTaskContextMenu(e, parentTask.id)}>
              <MoreVertical size={14} />
            </button>
          </div>
        </div>
        <div className={styles.ygTaskMetaRow}>
          <div className={styles.ygTaskMetaPrimary}>
            {formatTaskDateRange(parentTask) ? (
              <button
                type="button"
                className={`${styles.ygMetaPill} ${styles.ygMetaPillClickable}`}
                onClick={e => openStickerMenuForTask(e, parentTask, 'deadline')}
              >
                <CalendarDays size={10} aria-hidden />
                {formatTaskDateRange(parentTask)}
              </button>
            ) : (
              <button
                type="button"
                className={`${styles.ygMetaPill} ${styles.ygMetaPillGhost}`}
                title="Дедлайн"
                onClick={e => openStickerMenuForTask(e, parentTask, 'deadline')}
              >
                <CalendarDays size={10} />
              </button>
            )}
            <button
              type="button"
              className={`${styles.ygPriorityBadge} ${styles.ygMetaPillClickable} ${
                parentTask.priority === 'Высокий'
                  ? styles.ygPriorityHigh
                  : parentTask.priority === 'Средний'
                    ? styles.ygPriorityMed
                    : styles.ygPriorityLow
              }`}
              onClick={e => openStickerMenuForTask(e, parentTask, 'priority')}
            >
              {priorityLabel(parentTask.priority)}
            </button>
          </div>
          <div className={styles.ygTaskMetaSecondary}>
            {parentTask.assignee_name ? (
              <button
                type="button"
                className={`${styles.ygAssigneeChip} ${styles.ygMetaPillClickable}`}
                title={parentTask.assignee_name}
                onClick={e => openStickerMenuForTask(e, parentTask, 'assignee')}
              >
                {parentTask.assignee_name.slice(0, 2).toUpperCase()}
              </button>
            ) : (
              <button
                type="button"
                className={`${styles.ygAssigneeChip} ${styles.ygAssigneeGhost}`}
                title="Исполнитель"
                onClick={e => openStickerMenuForTask(e, parentTask, 'assignee')}
              >
                <UserRound size={10} />
              </button>
            )}
            <div className={styles.ygStickerWrap}>
              <button
                type="button"
                className={styles.ygStickerBtn}
                onClick={e => openStickerMenuForTask(e, parentTask, null)}
              >
                <CirclePlus size={16} />
              </button>
            </div>
          </div>
        </div>
        {renderTaskContextMenu(parentTask)}
        {renderStickerMenu(parentTask)}
        {totalSub > 0 && (
          <>
            <div className={styles.ygNestProgress} onClick={e => { e.stopPropagation(); setExpandedBoardTasks(prev => ({ ...prev, [parentTask.id]: !prev[parentTask.id] })); }}>
              <div className={styles.ygNestProgressTrack}>
                <div className={styles.ygNestProgressFill} style={{ width: `${Math.round((doneSub / totalSub) * 100)}%` }} />
              </div>
              <span className={styles.ygNestProgressCount}>{doneSub}/{totalSub}</span>
              <span className={styles.ygNestChevron}>
                {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </span>
            </div>
            {kidAssignees.length > 0 && (
              <div className={styles.ygCardAvatars}>
                {kidAssignees.map(a => (
                  <span key={a.id} className={styles.ygCardAvatar} style={{ background: avatarColor(a.name) }} title={a.name}>
                    {a.name.slice(0, 2).toUpperCase()}
                  </span>
                ))}
              </div>
            )}
          </>
        )}
        {expanded && (
          <div className={`${styles.ygSubtaskNest} ${depth === 0 ? styles.ygSubtaskNestScrollable : ''}`}>
            {kids.map((child, i) => renderBoardTaskTree(child, depth + 1, i))}
            {inlineSubParentId === parentTask.id ? (
              <div className={styles.ygInlineSubtaskCard} onClick={e => e.stopPropagation()}>
                <span className={styles.ygInlineTaskCircle}><Circle size={14} strokeWidth={2} /></span>
                <input
                  className={styles.ygInlineTaskInput}
                  placeholder="Введите название подзадачи"
                  value={inlineSubTitle}
                  onChange={e => setInlineSubTitle(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && inlineSubTitle.trim()) createInlineSubtask(parentTask.id); if (e.key === 'Escape') { setInlineSubParentId(null); setInlineSubTitle(''); } }}
                  onBlur={() => { if (inlineSubTitle.trim()) createInlineSubtask(parentTask.id); else { setInlineSubParentId(null); setInlineSubTitle(''); } }}
                  autoFocus
                />
              </div>
            ) : (
              <button
                type="button"
                className={styles.ygAddSubtaskLink}
                onClick={e => {
                  e.stopPropagation();
                  setInlineSubParentId(parentTask.id);
                  setInlineSubTitle('');
                }}
              >
                + {lang.workspace.addSubtask}
              </button>
            )}
          </div>
        )}
      </div>
    );

    return row;
  };

  useEffect(() => {
    setSelectedIteration(null);
    setTasks([]);
    setBoardColumns([]);
    setIterations([]);
    setSelectedTask(null);
    setChatMessages([]);
    setWorkspaceTab('board');
    loadProject(); loadIterations(); loadMembers();
  }, [id]);
  useEffect(() => { loadIterations(); }, [showArchived]);
  useEffect(() => {
    if (!selectedIteration) return;
    const ac = new AbortController();
    const { signal } = ac;
    loadTasks(selectedIteration.id, signal);
    loadBoardColumns(selectedIteration.id, signal);
    return () => ac.abort();
  }, [selectedIteration]);

  // Global keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const isInput = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT' || target.isContentEditable;
      if (e.key === 'Escape') {
        if (selectedTask) { setSelectedTask(null); return; }
        if (showTaskForm) {
          setShowTaskForm(false);
          setTaskFormParentId(null);
          setTaskFormColumnId(null);
          return;
        }
        if (showIterForm) { setShowIterForm(false); return; }
        if (isEditingProjectTitle) { setIsEditingProjectTitle(false); setProjectTitleDraft(project?.name || ''); return; }
        if (showMembersModal) { setShowMembersModal(false); return; }
        if (showColumnForm) { setShowColumnForm(false); return; }
        if (showPollForm) { setShowPollForm(false); return; }
      }
      if (isInput) return;
      if (e.key === 'n' && !e.ctrlKey && !e.metaKey && workspaceTab === 'board' && selectedIteration) {
        e.preventDefault();
        if (boardColumns.length === 0) setShowColumnForm(true);
        else {
          setTaskFormParentId(null);
          setTaskFormColumnId(boardColumns[0].id);
          setShowTaskForm(true);
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [selectedTask, showTaskForm, showIterForm, isEditingProjectTitle, showMembersModal, showPollForm, workspaceTab, selectedIteration, showColumnForm, boardColumns, project?.name]);

  // Close column menu on outside click or scroll
  useEffect(() => {
    if (!columnMenuId) return;
    const handler = () => { setColumnMenuId(null); setColumnMenuPos(null); };
    window.addEventListener('click', handler);
    window.addEventListener('scroll', handler, true);
    return () => { window.removeEventListener('click', handler); window.removeEventListener('scroll', handler, true); };
  }, [columnMenuId]);

  // Prevent browser back/forward gesture on horizontal scroll of columns
  useEffect(() => {
    const el = columnsScrollRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
        const atLeft = el.scrollLeft <= 0 && e.deltaX < 0;
        const atRight = el.scrollLeft + el.clientWidth >= el.scrollWidth - 1 && e.deltaX > 0;
        if (atLeft || atRight) e.preventDefault();
      }
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  });

  // Close task context menu on outside click or scroll
  useEffect(() => {
    if (!taskCtxMenuId) return;
    const handler = () => closeTaskContextMenu();
    window.addEventListener('click', handler);
    window.addEventListener('scroll', handler, true);
    return () => { window.removeEventListener('click', handler); window.removeEventListener('scroll', handler, true); };
  }, [taskCtxMenuId, closeTaskContextMenu]);

  // Close sticker menu on outside click or scroll
  useEffect(() => {
    if (!stickerMenuId) return;
    const handler = () => closeStickerMenu();
    window.addEventListener('click', handler);
    window.addEventListener('scroll', handler, true);
    return () => { window.removeEventListener('click', handler); window.removeEventListener('scroll', handler, true); };
  }, [stickerMenuId, closeStickerMenu]);

  const applyStickerAssignee = async (taskId: string, assigneeId: string) => {
    try { await api.put(`/tasks/${taskId}`, { assignee_id: assigneeId || null }); } catch {}
    closeStickerMenu();
    if (selectedIteration) loadTasks(selectedIteration.id);
  };
  const applyStickerDeadline = async (taskId: string, startDate: string, deadline: string) => {
    if (startDate && deadline && new Date(startDate) > new Date(deadline)) {
      window.alert('Начало периода не может быть позже конца');
      return;
    }
    try { await api.put(`/tasks/${taskId}`, { start_date: startDate || null, deadline: deadline || null }); } catch {}
    closeStickerMenu();
    if (selectedIteration) loadTasks(selectedIteration.id);
  };
  const applyStickerPriority = async (taskId: string, priority: string) => {
    try { await api.put(`/tasks/${taskId}`, { priority }); } catch {}
    closeStickerMenu();
    if (selectedIteration) loadTasks(selectedIteration.id);
  };

  const loadProject = async () => {
    const { data } = await api.get(`/projects/${id}`);
    setProject(data);
    setProjectTitleDraft(data.name || '');
  };
  const loadIterations = async () => {
    const { data } = await api.get(`/iterations/project/${id}`, { params: { include_archived: showArchived } });
    setIterations(data);
    setSelectedIteration(prev => {
      if (prev && data.some((d: Iteration) => d.id === prev.id)) return prev;
      return data.length > 0 ? data[0] : null;
    });
  };
  const loadTasks = async (iid: string, signal?: AbortSignal) => {
    try {
      const { data } = await api.get(`/tasks/iteration/${iid}`, { signal });
      setTasks(data);
    } catch (e) {
      if (axios.isCancel(e)) return;
    }
  };
  const loadBoardColumns = async (iid: string, signal?: AbortSignal) => {
    try {
      const path = iterationBoardColumnsPath(iid);
      const { data } = await api.get<BoardColumn[]>(path, { signal });
      setBoardColumns(data);
    } catch (e) {
      if (axios.isCancel(e)) return;
      setBoardColumns([]);
    }
  };
  const loadMembers = async () => { try { const { data } = await api.get('/users'); setMembers(data); setAllUsers(data); } catch {} };
  const loadProjectMembers = async () => { try { const { data } = await api.get(`/projects/${id}`); setProjectMembers(data.members || []); } catch {} };

  const saveProjectTitle = async () => {
    if (!project) return;
    const nextName = projectTitleDraft.trim();
    if (!nextName) {
      setProjectTitleDraft(project.name);
      setIsEditingProjectTitle(false);
      return;
    }
    if (nextName === project.name) {
      setIsEditingProjectTitle(false);
      return;
    }
    await api.put(`/projects/${id}`, { name: nextName, description: project.description || '' });
    setProject(prev => (prev ? { ...prev, name: nextName } : prev));
    setIsEditingProjectTitle(false);
  };
  const addMember = async () => { if (!addMemberId) return; await api.post(`/projects/${id}/members`, { user_id: addMemberId }); setAddMemberId(''); loadProjectMembers(); };
  const removeMember = async (uid: string) => { await api.delete(`/projects/${id}/members/${uid}`); loadProjectMembers(); };

  const createIteration = async (e: React.FormEvent) => {
    e.preventDefault();
    if (iterForm.template) {
      await api.post('/iterations', { project_id: id, name: iterForm.name, start_date: iterForm.start_date, end_date: iterForm.end_date, template_name: iterForm.template });
    } else {
      await api.post('/iterations', { ...iterForm, project_id: id });
    }
    setShowIterForm(false); setIterForm({ name: '', start_date: '', end_date: '', template: '' }); loadIterations();
  };
  const saveIteration = async (e: React.FormEvent) => { e.preventDefault(); if (!selectedIteration) return; await api.put(`/iterations/${selectedIteration.id}`, editIterForm); setShowEditIter(false); loadIterations(); };
  const changeIterationStatus = async (iterId: string, newStatus: string) => { await api.put(`/iterations/${iterId}`, { status: newStatus }); setIterContextMenuId(null); setIterCtxMenuPos(null); loadIterations(); };
  const deleteIteration = async (iterId: string) => { try { await api.delete(`/iterations/${iterId}`); setIterContextMenuId(null); setIterCtxMenuPos(null); loadIterations(); } catch { /* ignore */ } };

  // Iteration drag-and-drop reorder
  const handleIterDragStart = (idx: number) => { setDragIterIdx(idx); };
  const handleIterDragOver = (e: React.DragEvent, idx: number) => { e.preventDefault(); setDragOverIterIdx(idx); };
  const handleIterDragLeave = () => { setDragOverIterIdx(null); };
  const handleIterDrop = async (targetIdx: number) => {
    if (dragIterIdx === null || dragIterIdx === targetIdx) { setDragIterIdx(null); setDragOverIterIdx(null); return; }
    const reordered = [...iterations];
    const [moved] = reordered.splice(dragIterIdx, 1);
    reordered.splice(targetIdx, 0, moved);
    setIterations(reordered);
    setDragIterIdx(null);
    setDragOverIterIdx(null);
    const items = reordered.map((it, i) => ({ id: it.id, sort_order: i }));
    try { await api.patch(`/iterations/project/${id}/reorder`, items); } catch { /* ignore */ }
  };
  const handleIterDragEnd = () => { setDragIterIdx(null); setDragOverIterIdx(null); };

  const createTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedIteration) return;
    if (taskForm.start_date && taskForm.deadline && new Date(taskForm.start_date) > new Date(taskForm.deadline)) {
      window.alert('Начало периода не может быть позже конца');
      return;
    }
    if (taskFormParentId) {
      await api.post('/tasks', {
        ...taskForm,
        iteration_id: selectedIteration.id,
        assignee_id: taskForm.assignee_id || null,
        start_date: taskForm.start_date || null,
        deadline: taskForm.deadline || null,
        parent_id: taskFormParentId,
      });
    } else {
      if (!taskFormColumnId) {
        window.alert(lang.projectDetail.taskNeedColumn);
        return;
      }
      await api.post('/tasks', {
        ...taskForm,
        iteration_id: selectedIteration.id,
        assignee_id: taskForm.assignee_id || null,
        start_date: taskForm.start_date || null,
        deadline: taskForm.deadline || null,
        board_column_id: taskFormColumnId,
      });
    }
    setShowTaskForm(false);
    setTaskFormParentId(null);
    setTaskFormColumnId(null);
    setTaskForm({ title: '', description: '', assignee_id: '', start_date: '', deadline: '', priority: 'Средний' });
    loadTasks(selectedIteration.id);
  };
  const createInlineTask = async (colId: string) => {
    if (!selectedIteration || !inlineTaskTitle.trim()) { setInlineTaskColId(null); setInlineTaskTitle(''); return; }
    await api.post('/tasks', {
      title: inlineTaskTitle.trim(),
      iteration_id: selectedIteration.id,
      board_column_id: colId,
      priority: 'Средний',
      assignee_id: null,
      start_date: null,
      deadline: null,
    });
    setInlineTaskTitle('');
    loadTasks(selectedIteration.id);
  };
  const createInlineSubtask = async (parentId: string) => {
    if (!selectedIteration || !inlineSubTitle.trim()) { setInlineSubParentId(null); setInlineSubTitle(''); return; }
    await api.post('/tasks', {
      title: inlineSubTitle.trim(),
      iteration_id: selectedIteration.id,
      parent_id: parentId,
      priority: 'Средний',
      assignee_id: null,
      start_date: null,
      deadline: null,
    });
    setInlineSubTitle('');
    loadTasks(selectedIteration.id);
  };
  const createBoardColumn = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!selectedIteration || !columnFormTitle.trim()) return;
    let path: string;
    try {
      path = iterationBoardColumnsPath(selectedIteration.id);
    } catch {
      window.alert(lang.projectDetail.boardListInvalidIteration);
      return;
    }
    try {
      await api.post(path, {
        title: columnFormTitle.trim(),
        sort_order: boardColumns.length,
      });
      setShowColumnForm(false);
      setColumnFormTitle('');
      await loadBoardColumns(selectedIteration.id);
    } catch (err) {
      const ax = err as AxiosError<{ detail?: string | string[] }>;
      const d = ax.response?.data?.detail;
      const detail =
        typeof d === 'string' ? d : Array.isArray(d) ? d.map(x => String(x)).join('\n') : ax.message;
      const head =
        ax.response?.status === 404 ? lang.projectDetail.boardListNotFound : `${lang.common.error}: ${detail}`;
      window.alert(`${head}\n\n${lang.projectDetail.boardListServerHint}`);
    }
  };
  const toggleTaskCompleted = async (task: Task, e?: React.MouseEvent) => {
    e?.stopPropagation();
    await api.put(`/tasks/${task.id}`, { is_completed: !task.is_completed });
    if (selectedIteration) loadTasks(selectedIteration.id);
  };
  const deleteTaskById = async (taskId: string) => {
    try { await api.delete(`/tasks/${taskId}`); } catch {}
    setTaskCtxMenuId(null);
    if (selectedIteration) loadTasks(selectedIteration.id);
  };
  const moveTaskToColumn = async (taskId: string, colId: string) => {
    try { await api.put(`/tasks/${taskId}`, { board_column_id: colId }); } catch {}
    setTaskCtxMenuId(null);
    setTaskCtxMenuSub(null);
    if (selectedIteration) loadTasks(selectedIteration.id);
  };
  const renameTask = async (taskId: string, newTitle: string) => {
    if (!newTitle.trim()) return;
    try { await api.put(`/tasks/${taskId}`, { title: newTitle.trim() }); } catch {}
    setRenamingTaskId(null);
    setRenamingTaskTitle('');
    if (selectedIteration) loadTasks(selectedIteration.id);
  };
  const copyTaskLink = (taskId: string) => {
    const url = `${window.location.origin}${window.location.pathname}?task=${taskId}`;
    navigator.clipboard.writeText(url);
    setTaskCtxMenuId(null);
  };
  const uploadTaskCover = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.[0] || !taskCoverTargetId) return;
    const fd = new FormData(); fd.append('file', e.target.files[0]);
    try { await api.post(`/tasks/${taskCoverTargetId}/attachments`, fd); } catch {}
    setTaskCoverTargetId(null);
    setTaskCtxMenuId(null);
    if (selectedIteration) loadTasks(selectedIteration.id);
  };
  const loadTaskDetail = async (tid: string) => {
    const { data } = await api.get(`/tasks/${tid}`);
    setSelectedTask(data);
  };
  const saveTaskDescription = async () => {
    if (!selectedTask) return;
    await api.put(`/tasks/${selectedTask.id}`, { description: descDraft || null });
    await loadTaskDetail(selectedTask.id);
  };
  const addComment = async (e: React.FormEvent) => { e.preventDefault(); if (!selectedTask || !comment.trim()) return; await api.post(`/tasks/${selectedTask.id}/comments`, { content: comment }); setComment(''); loadTaskDetail(selectedTask.id); };
  const uploadTaskFile = async (e: React.ChangeEvent<HTMLInputElement>) => { if (!e.target.files?.[0] || !selectedTask) return; const fd = new FormData(); fd.append('file', e.target.files[0]); await api.post(`/tasks/${selectedTask.id}/attachments`, fd); loadTaskDetail(selectedTask.id); };

  const completeIteration = async (iid: string) => { await api.post(`/iterations/${iid}/complete`); loadIterations(); };

  // Chat
  const loadChatMessages = useCallback(async (iid: string) => { setChatLoading(true); try { const { data } = await api.get(`/chat/${iid}/messages?limit=100`); setChatMessages(data); } catch {} setChatLoading(false); }, []);
  const connectWs = useCallback((iid: string) => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${proto}://${location.host}/ws/chat/${iid}`);
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === 'message') {
        setChatMessages(prev => [...prev, { id: msg.id, iteration_id: iid, user_id: msg.user_id, user_name: msg.user_name, user_avatar: msg.user_avatar, content: msg.content, is_edited: false, is_deleted: false, reply_to_id: msg.reply_to_id, reply_to_content: msg.reply_to_content, reply_to_user_name: msg.reply_to_user_name, created_at: msg.created_at, updated_at: msg.created_at }]);
      } else if (msg.type === 'typing') {
        setTypingUsers(prev => prev.includes(msg.user_name) ? prev : [...prev, msg.user_name]);
        setTimeout(() => setTypingUsers(prev => prev.filter(n => n !== msg.user_name)), 3000);
      } else if (msg.type === 'task_update') {
        setTasks(prev =>
          prev.map(t =>
            t.id === msg.task_id
              ? {
                  ...t,
                  status: msg.status ?? t.status,
                  priority: msg.priority ?? t.priority,
                  title: msg.title ?? t.title,
                  is_completed: msg.is_completed !== undefined ? msg.is_completed : t.is_completed,
                }
              : t
          )
        );
      }
    };
    ws.onclose = () => { wsRef.current = null; };
    ws.onerror = () => { ws.close(); };
    wsRef.current = ws;
  }, []);
  const wsReconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Connect WebSocket whenever an iteration is selected (not just chat tab) for real-time task updates
  useEffect(() => {
    if (!selectedIteration) return;
    let stopped = false;
    const connect = () => {
      if (stopped) return;
      connectWs(selectedIteration.id);
      const ws = wsRef.current;
      if (!ws) return;
      const origOnClose = ws.onclose;
      ws.onclose = (ev) => {
        if (typeof origOnClose === 'function') origOnClose.call(ws, ev);
        if (!stopped) { wsReconnectTimer.current = setTimeout(connect, 2000); }
      };
    };
    connect();
    return () => {
      stopped = true;
      if (wsReconnectTimer.current) clearTimeout(wsReconnectTimer.current);
      wsRef.current?.close();
    };
  }, [selectedIteration, connectWs]);
  useEffect(() => {
    if (selectedIteration) loadChatMessages(selectedIteration.id);
  }, [selectedIteration, loadChatMessages]);
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [chatMessages]);

  const sendChatMessage = (e: React.FormEvent) => { e.preventDefault(); if (!chatInput.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return; const payload: any = { content: chatInput.trim() }; if (replyTo) { payload.reply_to_id = replyTo.id; } wsRef.current.send(JSON.stringify(payload)); setChatInput(''); setReplyTo(null); setShowMentions(false); };
  const sendTypingEvent = () => { if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) { wsRef.current.send(JSON.stringify({ type: 'typing' })); } };
  const editMessage = async (mid: string) => { if (!editMsgText.trim() || !selectedIteration) return; await api.put(`/chat/messages/${mid}`, { content: editMsgText }); setEditingMsg(null); setEditMsgText(''); loadChatMessages(selectedIteration.id); };
  const deleteMessage = async (mid: string) => { if (!selectedIteration) return; await api.delete(`/chat/messages/${mid}`); loadChatMessages(selectedIteration.id); };
  const uploadChatFile = async (e: React.ChangeEvent<HTMLInputElement>) => { if (!e.target.files?.[0] || !selectedIteration) return; setChatFileUploading(true); try { const fd = new FormData(); fd.append('file', e.target.files[0]); fd.append('content', e.target.files[0].name); await api.post(`/chat/${selectedIteration.id}/messages/upload`, fd); loadChatMessages(selectedIteration.id); } finally { setChatFileUploading(false); } };
  const searchChat = async () => { if (!chatSearch.trim()) { setChatSearchResults(null); return; } try { const { data } = await api.get(`/chat/search/messages`, { params: { q: chatSearch, iteration_id: selectedIteration?.id, limit: 20 } }); setChatSearchResults(data); } catch { setChatSearchResults([]); } };
  useEffect(() => { const t = setTimeout(searchChat, 400); return () => clearTimeout(t); }, [chatSearch, selectedIteration]);

  const createPoll = async (e: React.FormEvent) => { e.preventDefault(); if (!selectedIteration) return; const opts = pollForm.options.filter(o => o.trim()); if (opts.length < 2) return; await api.post(`/chat/${selectedIteration.id}/polls`, { question: pollForm.question, is_multiple: pollForm.is_multiple, options: opts }); setShowPollForm(false); setPollForm({ question: '', is_multiple: false, options: ['', ''] }); loadChatMessages(selectedIteration.id); };
  const votePoll = async (pid: string, oid: string) => { if (!selectedIteration) return; await api.post(`/chat/polls/${pid}/vote`, { option_id: oid }); loadChatMessages(selectedIteration.id); };
  const closePoll = async (pid: string) => { if (!selectedIteration) return; await api.post(`/chat/polls/${pid}/close`); loadChatMessages(selectedIteration.id); };

  // --- Drag-and-drop: tasks between columns ---
  const handleTaskDragStart = (e: React.DragEvent, taskId: string) => {
    e.stopPropagation();
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('application/task-id', taskId);
    setDragTaskId(taskId);
    setDragColumnId(null);
  };
  const handleTaskDragEnd = () => { setDragTaskId(null); setDragOverColumnId(null); };
  const handleColumnDragOver = (e: React.DragEvent, colId: string) => {
    if (!dragTaskId && !dragColumnId) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    if (dragTaskId) { setDragOverColumnId(colId); }
    if (dragColumnId && dragColumnId !== colId) { setDragOverColTargetId(colId); }
  };
  const handleColumnDragLeave = (e: React.DragEvent) => {
    const related = e.relatedTarget as Node | null;
    const current = e.currentTarget as Node;
    if (!related || !current.contains(related)) {
      if (dragTaskId) setDragOverColumnId(null);
      if (dragColumnId) setDragOverColTargetId(null);
    }
  };
  const handleColumnDrop = async (e: React.DragEvent, targetColumnId: string) => {
    e.preventDefault();
    if (dragTaskId) {
      const task = tasks.find(t => t.id === dragTaskId);
      if (task && task.board_column_id !== targetColumnId) {
        setTasks(prev => prev.map(t => t.id === dragTaskId ? { ...t, board_column_id: targetColumnId } : t));
        try { await api.put(`/tasks/${dragTaskId}`, { board_column_id: targetColumnId }); } catch { if (selectedIteration) loadTasks(selectedIteration.id); }
      }
    }
    if (dragColumnId && dragColumnId !== targetColumnId) {
      const oldIdx = boardColumns.findIndex(c => c.id === dragColumnId);
      const newIdx = boardColumns.findIndex(c => c.id === targetColumnId);
      if (oldIdx !== -1 && newIdx !== -1) {
        const reordered = [...boardColumns];
        const [removed] = reordered.splice(oldIdx, 1);
        reordered.splice(newIdx, 0, removed);
        setBoardColumns(reordered);
        const orderPayload = reordered.map((c, i) => ({ id: c.id, sort_order: i }));
        try { await api.patch(`tasks/iteration/${selectedIteration?.id}/board-columns/reorder`, orderPayload); } catch { if (selectedIteration) loadBoardColumns(selectedIteration.id); }
      }
    }
    setDragTaskId(null); setDragOverColumnId(null); setDragColumnId(null); setDragOverColTargetId(null);
  };

  // --- Column drag (reorder) ---
  const handleColDragStart = (e: React.DragEvent, colId: string) => {
    if (dragTaskId) { e.preventDefault(); return; }
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('application/col-id', colId);
    setDragColumnId(colId);
  };
  const handleColDragEnd = () => { setDragColumnId(null); setDragOverColTargetId(null); };

  // --- Column management ---
  const renameColumn = async (colId: string, title: string) => {
    if (!selectedIteration || !title.trim()) return;
    try { await api.put(`tasks/iteration/${selectedIteration.id}/board-columns/${colId}`, { title: title.trim(), sort_order: boardColumns.find(c => c.id === colId)?.sort_order || 0 }); } catch {}
    setEditingColumnId(null);
    setEditingColumnTitle('');
    loadBoardColumns(selectedIteration.id);
  };
  const deleteColumn = async (colId: string) => {
    if (!selectedIteration) return;
    try { await api.delete(`tasks/iteration/${selectedIteration.id}/board-columns/${colId}`); } catch {}
    setColumnMenuId(null);
    loadBoardColumns(selectedIteration.id);
    loadTasks(selectedIteration.id);
  };
  const updateColumnColor = async (colId: string, color: string) => {
    if (!selectedIteration) return;
    const col = boardColumns.find(c => c.id === colId);
    if (!col) return;
    try { await api.put(`tasks/iteration/${selectedIteration.id}/board-columns/${colId}`, { title: col.title, sort_order: col.sort_order, color }); } catch {}
    loadBoardColumns(selectedIteration.id);
  };
  const archiveColumnTasks = async (colId: string, onlyCompleted: boolean) => {
    if (!selectedIteration) return;
    const colTasks = tasks.filter(t => t.board_column_id === colId && !t.parent_id);
    const toArchive = onlyCompleted ? colTasks.filter(t => t.is_completed) : colTasks;
    for (const task of toArchive) {
      try { await api.delete(`/tasks/${task.id}`); } catch {}
    }
    setColumnMenuId(null);
    loadTasks(selectedIteration.id);
  };
  const duplicateColumn = async (colId: string) => {
    if (!selectedIteration) return;
    const col = boardColumns.find(c => c.id === colId);
    if (!col) return;
    try {
      await api.post(`tasks/iteration/${selectedIteration.id}/board-columns`, { title: `${col.title} (копия)`, sort_order: (boardColumns.length + 1) });
    } catch {}
    setColumnMenuId(null);
    loadBoardColumns(selectedIteration.id);
  };
  const applyColumnSort = (colId: string, key: string, dir: string) => {
    setColumnSorts(prev => ({ ...prev, [colId]: { key, dir } }));
    setColumnMenuId(null);
    setColumnMenuSub(null);
    setColumnSortSub(null);
  };

  const sortColumnTasks = (colTasks: Task[], colId: string) => {
    const sort = columnSorts[colId];
    if (!sort) return colTasks;
    const sorted = [...colTasks];
    const { key, dir } = sort;
    sorted.sort((a, b) => {
      let cmp = 0;
      if (key === 'deadline') {
        cmp = (a.deadline || '').localeCompare(b.deadline || '');
      } else if (key === 'assignee') {
        cmp = (a.assignee_name || '').localeCompare(b.assignee_name || '');
      } else if (key === 'created') {
        cmp = a.created_at.localeCompare(b.created_at);
      } else if (key === 'completed') {
        cmp = (a.is_completed ? 1 : 0) - (b.is_completed ? 1 : 0);
      } else if (key === 'title') {
        cmp = a.title.localeCompare(b.title);
      } else if (key === 'priority') {
        const pOrder: Record<string, number> = { '\u041d\u0438\u0437\u043a\u0438\u0439': 0, '\u0421\u0440\u0435\u0434\u043d\u0438\u0439': 1, '\u0412\u044b\u0441\u043e\u043a\u0438\u0439': 2 };
        cmp = (pOrder[a.priority] ?? 0) - (pOrder[b.priority] ?? 0);
      }
      return dir === 'desc' ? -cmp : cmp;
    });
    return sorted;
  };

  const handleChatInputChange = (val: string) => {
    setChatInput(val);
    if (typingTimeoutRef.current) clearTimeout(typingTimeoutRef.current);
    typingTimeoutRef.current = setTimeout(() => sendTypingEvent(), 300);
    const lastAt = val.lastIndexOf('@');
    if (lastAt !== -1 && (lastAt === 0 || val[lastAt - 1] === ' ')) { const f = val.slice(lastAt + 1); if (!f.includes(' ')) { setMentionFilter(f.toLowerCase()); setShowMentions(true); return; } }
    setShowMentions(false);
  };
  const insertMention = (name: string) => { const lastAt = chatInput.lastIndexOf('@'); if (lastAt !== -1) setChatInput(chatInput.slice(0, lastAt) + '@' + name + ' '); setShowMentions(false); chatInputRef.current?.focus(); };
  const priorityLabel = (p: string) => p === 'Высокий' ? lang.tasks.high : p === 'Средний' ? lang.tasks.medium : lang.tasks.low;
  const formatDateSeparator = (ds: string) => { const d = new Date(ds); const today = new Date(); if (d.toDateString() === today.toDateString()) return lang.common.today; const y = new Date(today); y.setDate(y.getDate() - 1); if (d.toDateString() === y.toDateString()) return lang.common.yesterday; return d.toLocaleDateString(LOCALE_MAP[language] || 'en-US', { day: 'numeric', month: 'long', year: 'numeric' }); };

  const renderFormattedText = (text: string) => {
    const parts: React.ReactNode[] = []; let rem = text; let k = 0;
    while (rem.length > 0) {
      const mm = rem.match(/^(@\S+)/); if (mm) { parts.push(<span key={k++} className={styles.mention}>{mm[1]}</span>); rem = rem.slice(mm[1].length); continue; }
      const bm = rem.match(/^\*\*(.+?)\*\*/); if (bm) { parts.push(<strong key={k++}>{bm[1]}</strong>); rem = rem.slice(bm[0].length); continue; }
      const im = rem.match(/^\*(.+?)\*/); if (im) { parts.push(<em key={k++}>{im[1]}</em>); rem = rem.slice(im[0].length); continue; }
      const lm = rem.match(/^\[([^\]]+)\]\((https?:\/\/[^)]+)\)/); if (lm) { parts.push(<a key={k++} href={lm[2]} target="_blank" rel="noopener noreferrer">{lm[1]}</a>); rem = rem.slice(lm[0].length); continue; }
      const nx = rem.slice(1).search(/[@*\[]/); if (nx === -1) { parts.push(rem); break; }
      parts.push(rem.slice(0, nx + 1)); rem = rem.slice(nx + 1);
    }
    return parts;
  };

  useEffect(() => {
    if (selectedTask) {
      setDescDraft(selectedTask.description || '');
      setTaskDetailTab('chat');
    }
  }, [selectedTask?.id]);
  const exportIterationPdf = async () => { if (!selectedIteration) return; const { data } = await api.get(`/export/iteration/${selectedIteration.id}`, { responseType: 'blob' }); const url = window.URL.createObjectURL(new Blob([data])); const a = document.createElement('a'); a.href = url; a.download = `iteration_${selectedIteration.name}.pdf`; a.click(); };

  if (!project) return <p>{lang.common.loading}</p>;
  const canEditMsg = (m: ChatMessage) => m.user_id === currentUser?.id && !m.is_deleted && (Date.now() - new Date(m.created_at).getTime()) < 86400000;
  const canDeleteMsg = (m: ChatMessage) => !m.is_deleted && (m.user_id === currentUser?.id || currentUser?.role === 'admin');
  const projectMemberRows = (project.members && project.members.length > 0 ? project.members : projectMembers) || [];
  const projectHeaderMembers = projectMemberRows
    .map((pm: any) => {
      const known = allUsers.find(u => u.id === pm.user_id);
      return {
        id: pm.user_id,
        name: known?.name || pm.user_name || 'U',
        avatarUrl: known?.avatar_url || '',
      };
    })
    .slice(0, 8);
  const visibleProjectMembers = projectMembers.filter((m: any) => {
    const person = allUsers.find(u => u.id === m.user_id);
    const text = `${m.user_name || ''} ${person?.name || ''} ${person?.email || ''}`.toLowerCase();
    return text.includes(memberSearch.trim().toLowerCase());
  });

  const headerSlot = typeof document !== 'undefined' ? document.getElementById('header-project-slot') : null;

  return (
    <div className={`${styles.workspaceRoot} page-enter`}>
      <div className={styles.workspaceBg} aria-hidden />
      {headerSlot && createPortal(
        <div className={styles.workspaceHeaderPortal}>
          <div className={styles.workspaceHeaderLead}>
            <button type="button" className={styles.workspaceBack} onClick={() => navigate('/projects')} aria-label={lang.common.back}>
              <ChevronLeft size={17} strokeWidth={2.6} />
            </button>
          </div>
          <div className={styles.workspaceHeaderTools}>
            <div className={styles.workspaceAvatars}>
              {projectHeaderMembers.map(m => (
                <span key={m.id} className={styles.workspaceAvatar} title={m.name}>
                  {m.avatarUrl ? (
                    <img src={m.avatarUrl} alt={m.name} className={styles.workspaceAvatarImg} />
                  ) : (
                    m.name.slice(0, 2).toUpperCase()
                  )}
                </span>
              ))}
            </div>
            <button
              type="button"
              className={styles.workspaceIconBtn}
              onClick={() => {
                loadProjectMembers();
                setShowMembersModal(true);
              }}
              aria-label={lang.projects.members}
            >
              <Users size={14} />
            </button>
          </div>
        </div>,
        headerSlot
      )}
      <div className={styles.workspaceInner}>

        <div className={styles.iterationsBarYougile} style={currentUser?.show_iterations ? {} : { display: 'none' }}>
          <button
            type="button"
            className={styles.iterScrollBtn}
            onClick={() => iterScrollRef.current?.scrollBy({ left: -200, behavior: 'smooth' })}
            aria-label="Scroll left"
          >
            <ChevronLeft size={18} strokeWidth={2.6} />
          </button>
          <div className={styles.iterTabs} ref={iterScrollRef}>
            {iterations.map((iter, idx) => (
              <div
                key={iter.id}
                className={`${styles.iterTabWrap} ${dragOverIterIdx === idx ? styles.iterTabDropTarget : ''} ${dragIterIdx === idx ? styles.iterTabDragging : ''}`}
                draggable
                onDragStart={() => handleIterDragStart(idx)}
                onDragOver={e => handleIterDragOver(e, idx)}
                onDragLeave={handleIterDragLeave}
                onDrop={() => handleIterDrop(idx)}
                onDragEnd={handleIterDragEnd}
              >
                <button
                  type="button"
                  className={`${styles.iterTab} ${selectedIteration?.id === iter.id ? styles.iterActive : ''}`}
                  onClick={() => setSelectedIteration(iter)}
                  onContextMenu={e => {
                    e.preventDefault();
                    const rect = e.currentTarget.getBoundingClientRect();
                    setIterCtxMenuPos({ top: rect.bottom + 4, left: rect.left });
                    setIterContextMenuId(iterContextMenuId === iter.id ? null : iter.id);
                  }}
                >
                  <GripVertical size={12} className={styles.iterGripIcon} />
                  {iter.name}
                  <span
                    className={`badge ${iter.status === 'active' ? 'badge-success' : iter.status === 'completed' ? 'badge-warning' : 'badge-primary'}`}
                  >
                    {iter.status === 'active'
                      ? lang.iterations.active
                      : iter.status === 'completed'
                        ? lang.iterations.completed
                        : lang.iterations.archived}
                  </span>
                  <Settings
                    size={14}
                    className={styles.iterMenuIcon}
                    onClick={e => {
                      e.stopPropagation();
                      const rect = (e.target as HTMLElement).getBoundingClientRect();
                      setIterCtxMenuPos({ top: rect.bottom + 4, left: rect.left });
                      setIterContextMenuId(iterContextMenuId === iter.id ? null : iter.id);
                    }}
                  />
                </button>
              </div>
            ))}
          </div>
          <button
            type="button"
            className={styles.iterScrollBtn}
            onClick={() => iterScrollRef.current?.scrollBy({ left: 200, behavior: 'smooth' })}
            aria-label="Scroll right"
          >
            <ChevronRight size={18} strokeWidth={2.6} />
          </button>
          <div className={styles.iterActions}>
            <button type="button" className="btn btn-primary btn-sm" onClick={() => setShowIterForm(true)}>
              + {lang.iterations.create}
            </button>
            <button
              type="button"
              className={`${styles.archiveToggleBtn} ${showArchived ? styles.archiveToggleBtnActive : ''}`}
              onClick={() => setShowArchived(v => !v)}
              title={showArchived ? 'Скрыть архив' : 'Показать архив'}
            >
              <Archive size={14} />
            </button>
          </div>
        </div>

        {selectedIteration && (
          <>
            <div className={styles.unifiedToolbar}>
              <div className={styles.viewPills}>
                <button
                  type="button"
                  className={`${styles.viewPill} ${workspaceTab === 'board' ? styles.viewPillActive : ''}`}
                  onClick={() => setWorkspaceTab('board')}
                >
                  <LayoutGrid size={15} />
                  <span>{lang.workspace.board}</span>
                </button>

              </div>

              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => setShowColumnForm(true)}
              >
                + {lang.projectDetail.createList}
              </button>

              <div className={styles.toolbarDivider} />
              <button
                type="button"
                className={`${styles.toolbarIconBtn} ${filterMyTasks ? styles.toolbarIconBtnActive : ''}`}
                aria-label={lang.tasks.assignee}
                onClick={() => setFilterMyTasks(f => !f)}
                title={filterMyTasks ? lang.tasks.assignee : lang.tasks.assignee}
              >
                <UserRound size={16} />
              </button>

              <div className={styles.filterPills} ref={filterDropdownRef}>
                <div className={`${styles.filterPill} ${filterAssignee ? styles.filterPillActive : ''}`} onClick={() => setOpenFilterDropdown(openFilterDropdown === 'assignee' ? null : 'assignee')}>
                  <UserRound size={13} />
                  <span>{filterAssignee ? members.find(m => m.id === filterAssignee)?.name || lang.tasks.assignee : lang.tasks.assignee}</span>
                  <Filter size={12} className={styles.filterPillIcon} />
                  {openFilterDropdown === 'assignee' && (
                    <div className={styles.filterDropdown} onClick={e => e.stopPropagation()}>
                      <div className={`${styles.filterDropdownItem} ${!filterAssignee ? styles.filterDropdownItemActive : ''}`} onClick={() => { setFilterAssignee(''); setOpenFilterDropdown(null); }}>
                        {lang.tasks.assignee} (Все)
                      </div>
                      {members.map(m => (
                        <div key={m.id} className={`${styles.filterDropdownItem} ${filterAssignee === m.id ? styles.filterDropdownItemActive : ''}`} onClick={() => { setFilterAssignee(m.id); setOpenFilterDropdown(null); }}>
                          {m.name}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <div className={`${styles.filterPill} ${filterDeadline ? styles.filterPillActive : ''}`} onClick={() => setOpenFilterDropdown(openFilterDropdown === 'deadline' ? null : 'deadline')}>
                  <CalendarDays size={13} />
                  <span>{filterDeadline === 'today' ? lang.common.today : filterDeadline === 'overdue' ? lang.workspace.filterOverdue : lang.workspace.filterDeadline}</span>
                  <Filter size={12} className={styles.filterPillIcon} />
                  {openFilterDropdown === 'deadline' && (
                    <div className={styles.filterDropdown} onClick={e => e.stopPropagation()}>
                      <div className={`${styles.filterDropdownItem} ${!filterDeadline ? styles.filterDropdownItemActive : ''}`} onClick={() => { setFilterDeadline(''); setOpenFilterDropdown(null); }}>
                        {lang.workspace.filterDeadline} (Все)
                      </div>
                      <div className={`${styles.filterDropdownItem} ${filterDeadline === 'today' ? styles.filterDropdownItemActive : ''}`} onClick={() => { setFilterDeadline('today'); setOpenFilterDropdown(null); }}>
                        {lang.common.today}
                      </div>
                      <div className={`${styles.filterDropdownItem} ${filterDeadline === 'overdue' ? styles.filterDropdownItemActive : ''}`} onClick={() => { setFilterDeadline('overdue'); setOpenFilterDropdown(null); }}>
                        {lang.workspace.filterOverdue}
                      </div>
                    </div>
                  )}
                </div>
                <div className={`${styles.filterPill} ${filterPriority ? styles.filterPillActive : ''}`} onClick={() => setOpenFilterDropdown(openFilterDropdown === 'priority' ? null : 'priority')}>
                  <BarChart3 size={13} />
                  <span>{filterPriority ? priorityLabel(filterPriority) : lang.tasks.priority}</span>
                  <Filter size={12} className={styles.filterPillIcon} />
                  {openFilterDropdown === 'priority' && (
                    <div className={styles.filterDropdown} onClick={e => e.stopPropagation()}>
                      <div className={`${styles.filterDropdownItem} ${!filterPriority ? styles.filterDropdownItemActive : ''}`} onClick={() => { setFilterPriority(''); setOpenFilterDropdown(null); }}>
                        {lang.tasks.priority} (Все)
                      </div>
                      {TASK_PRIORITIES.map(p => (
                        <div key={p} className={`${styles.filterDropdownItem} ${filterPriority === p ? styles.filterDropdownItemActive : ''}`} onClick={() => { setFilterPriority(p); setOpenFilterDropdown(null); }}>
                          {priorityLabel(p)}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>




            </div>

            <div className={styles.workspaceBody}>
              <div className={styles.workspaceMain}>

                {workspaceTab === 'board' && (() => {
                  const rootScope = filteredTasks.filter(t => !t.parent_id);
                  const doneBoard = rootScope.filter(t => t.is_completed).length;
                  const totalBoard = rootScope.length;
                  const pctBoard = totalBoard === 0 ? 0 : Math.round((doneBoard / totalBoard) * 100);
                  return (
                    <div className={`${styles.taskBoard} ${styles.boardShellYougile}`}>
                      {boardColumns.length > 0 && (
                        <div className={styles.boardProgressYougile}>
                          <div className={styles.boardProgressLabels}>
                            <span>{lang.projectDetail.progress}</span>
                            <span>
                              {doneBoard} / {totalBoard}
                            </span>
                          </div>
                          <div className={styles.boardProgressTrack}>
                            <div className={styles.boardProgressFill} style={{ width: `${pctBoard}%` }} />
                          </div>
                        </div>
                      )}
                      {boardColumns.length === 0 ? (
                        <div className={styles.ygBoardEmpty}>
                          {showColumnForm ? (
                            <div className={styles.ygAddColumnInline}>
                              <input
                                className={styles.ygAddColumnInput}
                                placeholder={lang.projectDetail.listTitle}
                                value={columnFormTitle}
                                onChange={e => setColumnFormTitle(e.target.value)}
                                onKeyDown={e => {
                                  if (e.key === 'Enter') { e.preventDefault(); createBoardColumn(); }
                                  if (e.key === 'Escape') { setShowColumnForm(false); setColumnFormTitle(''); }
                                }}
                                autoFocus
                              />
                              <div className={styles.ygAddColumnActions}>
                                <button type="button" className="btn btn-secondary btn-sm" onClick={() => { setShowColumnForm(false); setColumnFormTitle(''); }}>
                                  {lang.common.cancel}
                                </button>
                                <button type="button" className="btn btn-primary btn-sm" onClick={() => createBoardColumn()}>
                                  {lang.projectDetail.createList}
                                </button>
                              </div>
                            </div>
                          ) : (
                            <>
                              <p className={styles.ygBoardEmptyTitle}>{lang.projectDetail.boardEmptyTitle}</p>
                              <p className={styles.ygBoardEmptyHint}>{lang.projectDetail.boardEmptyHint}</p>
                            </>
                          )}
                        </div>
                      ) : (
                        <div className={styles.columnsYougile} ref={columnsScrollRef}>
                          {boardColumns.map((col, colIdx) => {
                            const roots = sortColumnTasks(
                              tasks
                                .filter(t => !t.parent_id && t.board_column_id === col.id && rootVisibleInColumn(t, col.id))
                                .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()),
                              col.id,
                            );
                            const accent = col.color || COLUMN_ACCENTS[colIdx % COLUMN_ACCENTS.length];
                            return (
                              <div key={col.id} className={styles.ygColumnShell}>
                                {dragColumnId && dragColumnId !== col.id && dragOverColTargetId === col.id && (
                                  <div className={styles.ygColumnInsertSlot} aria-hidden />
                                )}
                                <div
                                  className={`${styles.column} ${styles.ygColumn} ${dragColumnId === col.id ? styles.ygColumnDragging : ''}`}
                                  style={{ '--col-accent': accent } as React.CSSProperties}
                                  draggable
                                  onDragStart={(e) => { e.stopPropagation(); handleColDragStart(e, col.id); }}
                                  onDragEnd={handleColDragEnd}
                                  onDragOver={(e) => handleColumnDragOver(e, col.id)}
                                  onDragLeave={handleColumnDragLeave}
                                  onDrop={(e) => handleColumnDrop(e, col.id)}
                                >
                                <div className={styles.ygColumnAccent} style={{ background: accent }} />
                                <div className={styles.ygColumnHead}>
                                  {editingColumnId === col.id ? (
                                    <form onSubmit={(e) => { e.preventDefault(); renameColumn(col.id, editingColumnTitle); }} style={{ display: 'flex', gap: 4, flex: 1 }}>
                                      <input
                                        autoFocus
                                        value={editingColumnTitle}
                                        onChange={(e) => setEditingColumnTitle(e.target.value)}
                                        onBlur={() => renameColumn(col.id, editingColumnTitle)}
                                        className={styles.ygColumnTitleInput}
                                      />
                                    </form>
                                  ) : (
                                    <h3 className={styles.ygColumnTitle}>{col.title}</h3>
                                  )}
                                  <div className={styles.ygColumnHeadActions} style={{ position: 'relative' }}>
                                    <button
                                      type="button"
                                      className={styles.ygIconGhost}
                                      aria-label={lang.workspace.moreTools}
                                      onClick={(e) => { e.stopPropagation(); const r = e.currentTarget.getBoundingClientRect(); if (columnMenuId === col.id) { setColumnMenuId(null); setColumnMenuPos(null); } else { setColumnMenuPos({ top: r.bottom + 4, left: r.right - 230 }); setColumnMenuId(col.id); } setColumnMenuSub(null); setColumnSortSub(null); }}
                                    >
                                      <MoreVertical size={16} />
                                    </button>
                                    {columnMenuId === col.id && columnMenuPos && createPortal(
                                      <div className={styles.ygColumnMenuPortal} style={{ top: columnMenuPos.top, left: columnMenuPos.left }} onClick={e => e.stopPropagation()}>
                                        <button type="button" onClick={() => { setEditingColumnId(col.id); setEditingColumnTitle(col.title); setColumnMenuId(null); }}>
                                          <Pencil size={14} /> Переименовать
                                        </button>
                                        <button type="button" onClick={() => archiveColumnTasks(col.id, false)}>
                                          <Archive size={14} /> Архивировать все задачи
                                        </button>
                                        <button type="button" onClick={() => archiveColumnTasks(col.id, true)}>
                                          <Archive size={14} /> Архивировать выполненные
                                        </button>
                                        <button type="button" onClick={() => duplicateColumn(col.id)}>
                                          <Plus size={14} /> Дублировать
                                        </button>
                                        <div className={styles.ygColMenuSortWrap}>
                                          <button type="button" onClick={() => setColumnMenuSub(columnMenuSub === 'sort' ? null : 'sort')}>
                                            <BarChart3 size={14} /> Сортировать задачи по... <ChevronRight size={12} />
                                          </button>
                                          {columnMenuSub === 'sort' && (
                                            <div className={styles.ygColMenuSubpanel}>
                                              {[
                                                { key: 'deadline', label: 'Дедлайну', icon: <CalendarDays size={13} />, opts: [{ dir: 'asc', label: 'Сначала старые' }, { dir: 'desc', label: 'Сначала новые' }] },
                                                { key: 'assignee', label: 'Исполнителю', icon: <UserRound size={13} />, opts: [{ dir: 'asc', label: 'А→Я' }, { dir: 'desc', label: 'Я→А' }] },
                                                { key: 'created', label: 'Дате создания', icon: <CalendarDays size={13} />, opts: [{ dir: 'asc', label: 'Сначала старые' }, { dir: 'desc', label: 'Сначала новые' }] },
                                                { key: 'completed', label: 'Выполненности', icon: <Check size={13} />, opts: [{ dir: 'desc', label: 'Сначала выполненные' }, { dir: 'asc', label: 'Сначала невыполненные' }] },
                                                { key: 'title', label: 'Названию', icon: <FileText size={13} />, opts: [{ dir: 'asc', label: 'А→Я' }, { dir: 'desc', label: 'Я→А' }] },
                                                { key: 'priority', label: 'Приоритет', icon: <BarChart3 size={13} />, opts: [{ dir: 'asc', label: 'Возрастание' }, { dir: 'desc', label: 'Убывание' }] },
                                              ].map(s => (
                                                <div key={s.key} className={styles.ygColMenuSortGroup}>
                                                  <button
                                                    type="button"
                                                    className={`${styles.ygColMenuSortItem} ${columnSortSub === s.key ? styles.ygColMenuSortItemActive : ''}`}
                                                    onClick={() => setColumnSortSub(columnSortSub === s.key ? null : s.key)}
                                                  >
                                                    {s.icon} {s.label} <ChevronRight size={12} />
                                                  </button>
                                                  {columnSortSub === s.key && (
                                                    <div className={styles.ygColMenuSortOpts}>
                                                      {s.opts.map(o => (
                                                        <button key={o.dir} type="button" onClick={() => applyColumnSort(col.id, s.key, o.dir)}>
                                                          {o.label}
                                                        </button>
                                                      ))}
                                                    </div>
                                                  )}
                                                </div>
                                              ))}
                                            </div>
                                          )}
                                        </div>
                                        <div className={styles.ygColMenuDivider} />
                                        <div className={styles.ygColMenuColorLabel}>ЦВЕТ КОЛОНКИ</div>
                                        <div className={styles.ygColMenuColors}>
                                          {COLUMN_COLORS.map(c => (
                                            <button
                                              key={c}
                                              type="button"
                                              className={`${styles.ygColMenuColorDot} ${col.color === c ? styles.ygColMenuColorDotActive : ''}`}
                                              style={{ background: c }}
                                              onClick={() => updateColumnColor(col.id, c)}
                                            />
                                          ))}
                                        </div>
                                        <div className={styles.ygColMenuDivider} />
                                        <button type="button" className={styles.ygColMenuDanger} onClick={() => deleteColumn(col.id)}>
                                          <Trash2 size={14} /> Удалить
                                        </button>
                                      </div>,
                                      document.body
                                    )}
                                  </div>
                                </div>
                                <button
                                  type="button"
                                  className={styles.ygAddTaskBtn}
                                  onClick={() => setInlineTaskColId(inlineTaskColId === col.id ? null : col.id)}
                                >
                                  + Добавить задачу
                                </button>
                                <div className={styles.ygColumnBody}>
                                  {dragTaskId && dragOverColumnId === col.id && (
                                    <div className={styles.ygTaskDropSlot}>Переместить задачу сюда</div>
                                  )}
                                  {inlineTaskColId === col.id && (
                                    <div className={styles.ygInlineTaskCard}>
                                      <span className={styles.ygInlineTaskCircle}><Circle size={16} strokeWidth={2} /></span>
                                      <input
                                        className={styles.ygInlineTaskInput}
                                        placeholder="Введите название задачи..."
                                        value={inlineTaskTitle}
                                        onChange={e => setInlineTaskTitle(e.target.value)}
                                        onKeyDown={e => { if (e.key === 'Enter' && inlineTaskTitle.trim()) createInlineTask(col.id); if (e.key === 'Escape') { setInlineTaskColId(null); setInlineTaskTitle(''); } }}
                                        onBlur={() => { if (inlineTaskTitle.trim()) createInlineTask(col.id); else { setInlineTaskColId(null); setInlineTaskTitle(''); } }}
                                        autoFocus
                                      />
                                    </div>
                                  )}
                                  {roots.map((task, ri) => renderBoardTaskTree(task, 0, ri))}
                                </div>
                                </div>
                              </div>
                            );
                          })}
                          {showColumnForm ? (
                            <div className={styles.ygAddColumnInline}>
                              <input
                                className={styles.ygAddColumnInput}
                                placeholder={lang.projectDetail.listTitle}
                                value={columnFormTitle}
                                onChange={e => setColumnFormTitle(e.target.value)}
                                onKeyDown={e => {
                                  if (e.key === 'Enter') {
                                    e.preventDefault();
                                    createBoardColumn();
                                  }
                                  if (e.key === 'Escape') {
                                    setShowColumnForm(false);
                                    setColumnFormTitle('');
                                  }
                                }}
                                autoFocus
                              />
                              <div className={styles.ygAddColumnActions}>
                                <button type="button" className="btn btn-secondary btn-sm" onClick={() => { setShowColumnForm(false); setColumnFormTitle(''); }}>
                                  {lang.common.cancel}
                                </button>
                                <button type="button" className="btn btn-primary btn-sm" onClick={() => createBoardColumn()}>
                                  {lang.projectDetail.createList}
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className={styles.ygAddColumnPanel}>
                              <button
                                type="button"
                                className={styles.ygAddColumnPanelBtn}
                                onClick={() => setShowColumnForm(true)}
                              >
                                <Plus size={14} /> Создать колонку
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })()}


              </div>

              {rightPanelOpen && workspaceTab === 'board' && (
                <aside className={styles.rightChatPanel} style={{ width: chatPanelWidth, maxWidth: '50vw' }}>
                  <button
                    type="button"
                    className={styles.chatEdgeToggle}
                    onClick={() => setRightPanelOpen(false)}
                    aria-label={lang.workspace.hideChat}
                    title={`${lang.workspace.hideChat} (${lang.workspace.chatEdgeToggle})`}
                  >
                    <ChevronRight size={18} strokeWidth={2.25} aria-hidden />
                  </button>
                  <button
                    type="button"
                    className={styles.chatResizeHandle}
                    aria-label={lang.workspace.resizeChat}
                    title={lang.workspace.resizeChat}
                    onMouseDown={onChatResizeStart}
                  />
                  <div className={styles.rightChatInner}>
                  <div className={styles.rightChatHeader}>
                    <div className={styles.rightChatHeaderTop}>
                      <h3 className={styles.rightChatTitle}>{lang.workspace.chatsTitle}</h3>
                      <button
                        type="button"
                        className={styles.rightChatClose}
                        onClick={() => setRightPanelOpen(false)}
                        aria-label={lang.workspace.hideChat}
                        title={lang.workspace.hideChat}
                      >
                        <X size={20} strokeWidth={2} />
                      </button>
                    </div>
                    <div className={styles.rightChatTabs}>
                      <span className={styles.rightChatTabActive}>{lang.workspace.chatAll}</span>
                      <span className={styles.rightChatTab}>{lang.workspace.iterationChat}</span>
                    </div>
                  </div>
                  <input
                    className={styles.rightChatSearch}
                    value={chatSearch}
                    onChange={e => setChatSearch(e.target.value)}
                    placeholder={lang.workspace.chatSearch}
                  />
                  <div className={`${styles.chatContainer} ${styles.chatYougile}`}>
                    <div className={styles.chatMessagesYougile}>
                      {chatSearchResults !== null ? (
                        <>
                          <p className={styles.chatSearchMeta}>
                            {lang.projectDetail.searchResults}: {chatSearchResults.length}
                          </p>
                          {chatSearchResults.map(r => (
                            <div key={r.message_id} className={styles.chatMsg}>
                              <div className={styles.chatMsgHeader}>
                                <strong>{r.user_name || '?'}</strong>
                                <span className={styles.chatTime}>{new Date(r.created_at).toLocaleString()}</span>
                              </div>
                              <div className={styles.chatMsgContent}>{r.content}</div>
                            </div>
                          ))}
                          <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setChatSearch(''); setChatSearchResults(null); }}>
                            {lang.projectDetail.backToChat}
                          </button>
                        </>
                      ) : (
                        <>
                          {chatLoading && <p className={styles.chatLoading}>{lang.common.loading}</p>}
                          {!chatLoading && chatMessages.length === 0 && (
                            <div className={styles.chatEmptyState}>{lang.workspace.chatEmpty}</div>
                          )}
                          {chatMessages.map((msg, i) => {
                            const prevD = i > 0 ? new Date(chatMessages[i - 1].created_at).toDateString() : '';
                            const curD = new Date(msg.created_at).toDateString();
                            return (
                              <div key={msg.id}>
                                {curD !== prevD && (
                                  <div className={styles.dateSeparator}>
                                    <span>{formatDateSeparator(msg.created_at)}</span>
                                  </div>
                                )}
                                <div className={`${styles.chatMsg} ${msg.user_id === currentUser?.id ? styles.chatMsgOwn : ''}`}>
                                  {msg.reply_to_id && msg.reply_to_user_name && (
                                    <div className={styles.replyBubble}>
                                      <strong>{msg.reply_to_user_name}</strong>
                                      <span>
                                        {msg.reply_to_content?.slice(0, 80)}
                                        {(msg.reply_to_content?.length || 0) > 80 ? '...' : ''}
                                      </span>
                                    </div>
                                  )}
                                  <div className={styles.chatMsgHeader}>
                                    <strong>{msg.user_name || '?'}</strong>
                                    <span className={styles.chatTime}>
                                      {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                    </span>
                                    {msg.is_edited && <span className={styles.chatEdited}>({lang.chat.edited})</span>}
                                    <span className={styles.chatMsgActions}>
                                      {!msg.is_deleted && (
                                        <button type="button" className={styles.msgAction} onClick={() => setReplyTo(msg)} title={lang.chat.replyTo} aria-label={lang.chat.replyTo}>
                                          <Reply size={14} />
                                        </button>
                                      )}
                                      {canEditMsg(msg) && (
                                        <button type="button" className={styles.msgAction} onClick={() => { setEditingMsg(msg.id); setEditMsgText(msg.content); }} aria-label={lang.common.edit}>
                                          <Pencil size={14} />
                                        </button>
                                      )}
                                      {canDeleteMsg(msg) && (
                                        <button type="button" className={styles.msgAction} onClick={() => deleteMessage(msg.id)} aria-label={lang.common.delete}>
                                          <Trash2 size={14} />
                                        </button>
                                      )}
                                    </span>
                                  </div>
                                  {editingMsg === msg.id ? (
                                    <div className={styles.editMsgRow}>
                                      <input value={editMsgText} onChange={e => setEditMsgText(e.target.value)} autoFocus />
                                      <button type="button" className="btn btn-primary btn-sm" onClick={() => editMessage(msg.id)}>
                                        <Check size={14} />
                                      </button>
                                      <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditingMsg(null)}>
                                        <X size={14} />
                                      </button>
                                    </div>
                                  ) : (
                                    <div className={styles.chatMsgContent}>
                                      {msg.is_deleted ? <em className={styles.chatDeleted}>{lang.common.deleted}</em> : renderFormattedText(msg.content)}
                                    </div>
                                  )}
                                  {msg.file_url && (
                                    <a href={msg.file_url} target="_blank" rel="noopener noreferrer" className={styles.chatFile}>
                                      <Paperclip size={14} style={{ marginRight: 6 }} />
                                      {msg.file_name || lang.common.file}
                                    </a>
                                  )}
                                  {msg.poll && (
                                    <div className={styles.pollCard}>
                                      <h5 className={styles.pollQuestion} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                        <BarChart3 size={16} /> {msg.poll.question}
                                      </h5>
                                      {msg.poll.is_closed && <span className="badge badge-warning">{lang.projectDetail.pollClosed}</span>}
                                      <div className={styles.pollOptions}>
                                        {msg.poll.options.map(opt => {
                                          const total = msg.poll!.options.reduce((s, o) => s + o.votes_count, 0);
                                          const pct = total > 0 ? Math.round((opt.votes_count / total) * 100) : 0;
                                          const voted = opt.voters?.some(v => v.user_id === currentUser?.id);
                                          return (
                                            <div key={opt.id} className={`${styles.pollOption} ${voted ? styles.pollVoted : ''}`}>
                                              <button type="button" className={styles.pollVoteBtn} onClick={() => !msg.poll!.is_closed && votePoll(msg.poll!.id, opt.id)} disabled={msg.poll!.is_closed}>
                                                <span className={styles.pollBar} style={{ width: `${pct}%` }} />
                                                <span className={styles.pollText}>{opt.text}</span>
                                                <span className={styles.pollPct}>
                                                  {opt.votes_count} ({pct}%)
                                                </span>
                                              </button>
                                              {opt.voters && opt.voters.length > 0 && (
                                                <div className={styles.pollVoters}>
                                                  {opt.voters.map(v => (
                                                    <span key={v.user_id} className={styles.pollVoterName}>
                                                      {members.find(m => m.id === v.user_id)?.name || '?'}
                                                    </span>
                                                  ))}
                                                </div>
                                              )}
                                            </div>
                                          );
                                        })}
                                      </div>
                                      {msg.user_id === currentUser?.id && !msg.poll.is_closed && (
                                        <button type="button" className="btn btn-secondary btn-sm" onClick={() => closePoll(msg.poll!.id)} style={{ marginTop: 8 }}>
                                          {lang.chat.closePoll}
                                        </button>
                                      )}
                                    </div>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                          <div ref={chatEndRef} />
                        </>
                      )}
                    </div>
                    {typingUsers.length > 0 && (
                      <div className={styles.chatTyping}>{typingUsers.join(', ')} {lang.chat.typing}</div>
                    )}
                    {replyTo && (
                      <div className={styles.chatReplyBar}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <Reply size={14} /> {lang.chat.replying} <strong>{replyTo.user_name}</strong>: {replyTo.content?.slice(0, 60)}
                          {(replyTo.content?.length || 0) > 60 ? '...' : ''}
                        </span>
                        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setReplyTo(null)}>
                          <X size={14} />
                        </button>
                      </div>
                    )}
                    <form className={styles.chatInputBar} onSubmit={sendChatMessage}>
                      <div className={styles.chatInputWrap}>
                        <input
                          ref={chatInputRef}
                          value={chatInput}
                          onChange={e => handleChatInputChange(e.target.value)}
                          placeholder={lang.chat.sendMessage}
                          autoComplete="off"
                        />
                        {showMentions && (
                          <div className={styles.mentionDropdown}>
                            {members
                              .filter(m => m.name.toLowerCase().includes(mentionFilter))
                              .slice(0, 6)
                              .map(m => (
                                <div key={m.id} className={styles.mentionItem} onClick={() => insertMention(m.name)} role="presentation">
                                  {m.name}
                                </div>
                              ))}
                          </div>
                        )}
                      </div>
                      <input ref={fileInputRef} type="file" hidden onChange={uploadChatFile} />
                      <button type="button" className="btn btn-ghost btn-sm" onClick={() => fileInputRef.current?.click()} disabled={chatFileUploading} aria-label={lang.common.uploadFile}>
                        {chatFileUploading ? <Loader2 size={16} className={styles.spin} /> : <Paperclip size={16} />}
                      </button>
                      <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowPollForm(true)} aria-label={lang.chat.createPoll}>
                        <BarChart3 size={16} />
                      </button>
                      <button type="submit" className="btn btn-primary btn-sm" disabled={!chatInput.trim()}>
                        <Send size={16} />
                      </button>
                    </form>
                    <div className={styles.chatParticipants}>
                      <span>{lang.workspace.participants}</span>
                      {members.slice(0, 4).map(m => (
                        <span key={m.id} className={styles.workspaceAvatar} title={m.name}>
                          {m.name.slice(0, 2).toUpperCase()}
                        </span>
                      ))}
                    </div>
                  </div>
                  </div>
                </aside>
              )}
            </div>

            {workspaceTab === 'board' && !rightPanelOpen && (
              <button
                type="button"
                className={styles.chatExpandStrip}
                onClick={() => setRightPanelOpen(true)}
                aria-label={lang.workspace.showChat}
                title={lang.workspace.showChat}
              >
                <PanelRightOpen size={20} strokeWidth={2} aria-hidden />
              </button>
            )}
          </>
        )}
      </div>

      {/* MODALS */}
      {selectedTask && (
        <div className={styles.taskOverlay} onClick={() => setSelectedTask(null)}>
          <div className={styles.taskSlidePanel} onClick={e => e.stopPropagation()}>
            <button type="button" className={styles.taskSlideBack} onClick={() => setSelectedTask(null)}>
              ← {lang.workspace.backToChats}
            </button>
            <div className={styles.taskSlideHead}>
              <div className={styles.taskSlideTitleRow}>
                <span className={styles.taskSlideCheckbox} aria-hidden />
                <div>
                  <h2 className={styles.taskSlideTitle}>{selectedTask.title}</h2>
                  <span className={styles.taskSlideId}>#{String(selectedTask.id).slice(0, 8)}</span>
                </div>
              </div>
              <div className={styles.taskSlideActions}>
                <button type="button" className={styles.taskSlideIconBtn} aria-label={lang.workspace.searchPlaceholder}>
                  <Search size={18} />
                </button>
                <button type="button" className={styles.taskSlideIconBtn} aria-label={lang.common.files}>
                  <Paperclip size={18} />
                </button>
                <button type="button" className={styles.taskSlideIconBtn} aria-label="Star">
                  <Star size={18} />
                </button>
                <button type="button" className={styles.taskSlideIconBtn} aria-label="Notify">
                  <Bell size={18} />
                </button>
              </div>
            </div>
            <div className={styles.taskSlideTabs}>
              {(['chat', 'info', 'desc', 'sub'] as const).map(k => (
                <button
                  key={k}
                  type="button"
                  className={`${styles.taskSlideTab} ${taskDetailTab === k ? styles.taskSlideTabActive : ''}`}
                  onClick={() => setTaskDetailTab(k)}
                >
                  {k === 'chat' && lang.workspace.taskTabChat}
                  {k === 'info' && lang.workspace.taskTabInfo}
                  {k === 'desc' && lang.workspace.taskTabDesc}
                  {k === 'sub' && lang.workspace.taskTabSubtasks}
                </button>
              ))}
            </div>
            <div className={styles.taskSlideBody}>
              {taskDetailTab === 'chat' && (
                <>
                  <div className={styles.taskChatList}>
                    {selectedTask.comments?.map(c => (
                      <div key={c.id} className={styles.taskChatBubble}>
                        <strong>{c.user_name}</strong>
                        <p>{c.content}</p>
                        <small>{new Date(c.created_at).toLocaleString()}</small>
                      </div>
                    ))}
                  </div>
                  <form onSubmit={addComment} className={styles.commentForm}>
                    <input value={comment} onChange={e => setComment(e.target.value)} placeholder={lang.tasks.addComment} />
                    <button className="btn btn-primary btn-sm" type="submit">
                      {lang.common.save}
                    </button>
                  </form>
                </>
              )}
              {taskDetailTab === 'info' && (
                <div className={styles.taskInfoSection}>
                  <h4>{lang.workspace.taskInfoTitle}</h4>
                  <p>
                    <UserRound size={14} style={{ marginRight: 6 }} />
                    {lang.tasks.assignee}: {selectedTask.assignee_name || '—'}
                  </p>
                  <p>
                    <CalendarDays size={14} style={{ marginRight: 6 }} />
                    {lang.tasks.deadline}: {formatTaskDateRange(selectedTask) || '—'}
                  </p>
                  <p>
                    <span className={`badge ${selectedTask.status === TASK_STATUSES[2] ? 'badge-success' : 'badge-primary'}`}>{selectedTask.status}</span>
                    <span className={`badge ${selectedTask.priority === 'Высокий' ? 'badge-error' : 'badge-warning'}`}>{priorityLabel(selectedTask.priority)}</span>
                  </p>
                  <h4>{lang.common.files}</h4>
                  {selectedTask.attachments?.map(a => (
                    <a key={a.id} href={a.file_url} target="_blank" rel="noopener noreferrer" className={styles.chatFile} style={{ display: 'block', margin: '4px 0' }}>
                      <Paperclip size={14} style={{ marginRight: 6 }} />
                      {a.filename}
                    </a>
                  ))}
                  <input ref={taskFileRef} type="file" hidden onChange={uploadTaskFile} />
                  <input ref={taskCoverRef} type="file" hidden accept="image/*" onChange={uploadTaskCover} />
                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => taskFileRef.current?.click()}>
                    {lang.common.uploadFile}
                  </button>
                  <h4>{lang.workspace.logTitle}</h4>
                  {selectedTask.history?.map(h => (
                    <div key={h.id} className={styles.historyItem}>
                      <small>
                        {h.user_name}: {h.field} «{h.old_value}» → «{h.new_value}» | {new Date(h.created_at).toLocaleString()}
                      </small>
                    </div>
                  ))}
                </div>
              )}
              {taskDetailTab === 'desc' && (
                <div className={styles.taskDescEditor}>
                  <textarea value={descDraft} onChange={e => setDescDraft(e.target.value)} rows={12} className={styles.taskDescTextarea} />
                  <div className={styles.taskDescActions}>
                    <button type="button" className="btn btn-primary btn-sm" onClick={() => saveTaskDescription()}>
                      {lang.workspace.saveDesc}
                    </button>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setDescDraft(selectedTask.description || '')}>
                      {lang.workspace.cancelDesc}
                    </button>
                  </div>
                </div>
              )}
              {taskDetailTab === 'sub' && selectedTask && (
                <SubtasksPanel
                  lang={lang}
                  subtasks={tasks
                    .filter(t => t.parent_id === selectedTask.id)
                    .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())}
                  onAddSubtask={() => {
                    setTaskFormParentId(selectedTask.id);
                    setTaskFormColumnId(null);
                    setShowTaskForm(true);
                  }}
                />
              )}
            </div>
          </div>
        </div>
      )}

      {showIterForm && (
        <div className="modal-overlay" onClick={() => setShowIterForm(false)}><div className="modal" onClick={e => e.stopPropagation()}><h2>{lang.iterations.create}</h2><form onSubmit={createIteration} className={styles.form}>
          <input placeholder={lang.projects.name} value={iterForm.name} onChange={e => setIterForm({ ...iterForm, name: e.target.value })} required />
          <label>{lang.iterations.template}</label><select value={iterForm.template} onChange={e => setIterForm({ ...iterForm, template: e.target.value })}><option value="">{lang.common.noTemplate}</option>{SPHERES.map(s => <option key={s} value={s}>{s}</option>)}</select>
          <label>{lang.iterations.startDate}</label><input type="date" value={iterForm.start_date} onChange={e => setIterForm({ ...iterForm, start_date: e.target.value })} required />
          <label>{lang.iterations.endDate}</label><input type="date" value={iterForm.end_date} onChange={e => setIterForm({ ...iterForm, end_date: e.target.value })} required />
          <div className={styles.formActions}><button type="button" className="btn btn-secondary" onClick={() => setShowIterForm(false)}>{lang.common.cancel}</button><button type="submit" className="btn btn-primary">{lang.common.create}</button></div>
        </form></div></div>
      )}

      {showEditIter && (
        <div className="modal-overlay" onClick={() => setShowEditIter(false)}><div className="modal" onClick={e => e.stopPropagation()}><h2>{lang.common.edit}</h2><form onSubmit={saveIteration} className={styles.form}>
          <input placeholder={lang.projects.name} value={editIterForm.name} onChange={e => setEditIterForm({ ...editIterForm, name: e.target.value })} required />
          <label>{lang.iterations.startDate}</label><input type="date" value={editIterForm.start_date} onChange={e => setEditIterForm({ ...editIterForm, start_date: e.target.value })} required />
          <label>{lang.iterations.endDate}</label><input type="date" value={editIterForm.end_date} onChange={e => setEditIterForm({ ...editIterForm, end_date: e.target.value })} required />
          <div className={styles.formActions}><button type="button" className="btn btn-secondary" onClick={() => setShowEditIter(false)}>{lang.common.cancel}</button><button type="submit" className="btn btn-primary">{lang.common.save}</button></div>
        </form></div></div>
      )}

      {iterContextMenuId && iterCtxMenuPos && (() => {
        const iter = iterations.find(it => it.id === iterContextMenuId);
        if (!iter) return null;
        return createPortal(
          <div className={styles.iterContextMenuPortal} ref={iterContextRef} style={{ top: iterCtxMenuPos.top, left: iterCtxMenuPos.left }} onClick={e => e.stopPropagation()}>
            <div className={styles.iterCtxHeader}>{iter.name}</div>
            <div className={styles.iterCtxSection}>Статус</div>
            <div className={`${styles.iterCtxItem} ${iter.status === 'active' ? styles.iterCtxItemActive : ''}`} onClick={() => changeIterationStatus(iter.id, 'active')}>
              <Circle size={10} fill="#22c55e" color="#22c55e" /> {lang.iterations.active}
            </div>
            <div className={`${styles.iterCtxItem} ${iter.status === 'completed' ? styles.iterCtxItemActive : ''}`} onClick={() => changeIterationStatus(iter.id, 'completed')}>
              <Circle size={10} fill="#f59e0b" color="#f59e0b" /> {lang.iterations.completed}
            </div>
            <div className={`${styles.iterCtxItem} ${iter.status === 'archived' ? styles.iterCtxItemActive : ''}`} onClick={() => changeIterationStatus(iter.id, 'archived')}>
              <Circle size={10} fill="#6366f1" color="#6366f1" /> {lang.iterations.archived}
            </div>
            <div className={styles.iterCtxDivider} />
            <div className={styles.iterCtxItem} onClick={() => {
              setEditIterForm({ name: iter.name, start_date: iter.start_date, end_date: iter.end_date });
              setSelectedIteration(iter);
              setShowEditIter(true);
              setIterContextMenuId(null);
              setIterCtxMenuPos(null);
            }}>
              <Pencil size={12} /> {lang.common.edit}
            </div>
            <div className={`${styles.iterCtxItem} ${styles.iterCtxDanger}`} onClick={() => deleteIteration(iter.id)}>
              <Trash2 size={12} /> {lang.common.delete}
            </div>
          </div>,
          document.body
        );
      })()}

      {showTaskForm && taskFormParentId && (
        <div
          className="modal-overlay"
          onClick={() => {
            setShowTaskForm(false);
            setTaskFormParentId(null);
            setTaskFormColumnId(null);
          }}
        >
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>{lang.projectDetail.subtaskModalTitle}</h2>
            <form onSubmit={createTask} className={styles.form}>
              <input
                placeholder={lang.tasks.title}
                value={taskForm.title}
                onChange={e => setTaskForm({ ...taskForm, title: e.target.value })}
                required
                autoFocus
              />
              <label>Начало периода</label>
              <input
                type="datetime-local"
                value={taskForm.start_date}
                onChange={e => setTaskForm({ ...taskForm, start_date: e.target.value })}
              />
              <label>Конец периода</label>
              <input
                type="datetime-local"
                value={taskForm.deadline}
                onChange={e => setTaskForm({ ...taskForm, deadline: e.target.value })}
              />
              <div className={styles.formActions}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => {
                    setShowTaskForm(false);
                    setTaskFormParentId(null);
                    setTaskFormColumnId(null);
                  }}
                >
                  {lang.common.cancel}
                </button>
                <button type="submit" className="btn btn-primary">
                  {lang.common.create}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showMembersModal && (
        <div className={styles.membersFullscreenOverlay} onClick={() => setShowMembersModal(false)}>
          <div className={styles.membersFullscreenModal} onClick={e => e.stopPropagation()}>
            <div className={styles.membersFullscreenHead}>
              <h2 className={styles.membersFullscreenTitle}>Участники проекта "{project.name}"</h2>
              <button type="button" className={styles.membersCloseBtn} onClick={() => setShowMembersModal(false)} aria-label={lang.common.close}>
                <X size={18} />
              </button>
            </div>

            <div className={styles.membersInviteBlock}>
              <h3>Добавить участника вручную</h3>
              <div className={styles.membersInviteRow}>
                <select value={addMemberId} onChange={e => setAddMemberId(e.target.value)}>
                  <option value="">{lang.common.selectUser}</option>
                  {allUsers
                    .filter(u => !projectMembers.some((m: any) => m.user_id === u.id))
                    .map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
                </select>
                <button type="button" className="btn btn-primary" onClick={addMember}>
                  Добавить
                </button>
              </div>
            </div>

            <div className={styles.membersTableBlock}>
              <div className={styles.membersTableTop}>
                <h3>{lang.projects.members}</h3>
                <input
                  className={styles.membersSearchInput}
                  placeholder="Поиск участника"
                  value={memberSearch}
                  onChange={e => setMemberSearch(e.target.value)}
                />
              </div>
              <div className={styles.membersTableRows}>
                {visibleProjectMembers.map((m: any) => {
                  const memberUser = allUsers.find(u => u.id === m.user_id);
                  return (
                    <div key={m.id} className={styles.membersRow}>
                      <div className={styles.membersUserCell}>
                        <span className={styles.membersUserAvatar}>
                          {memberUser?.avatar_url ? (
                            <img src={memberUser.avatar_url} alt={memberUser.name} className={styles.membersUserAvatarImg} />
                          ) : (
                            (memberUser?.name || m.user_name || '?').slice(0, 2).toUpperCase()
                          )}
                        </span>
                        <span>{memberUser?.name || m.user_name || m.user_id}</span>
                        {memberUser?.is_online && <span className={styles.onlineDot} />}
                      </div>
                      <div className={styles.membersRoleCell}>{m.is_admin ? 'Управляющий' : 'Сотрудник'}</div>
                      <button className="btn btn-danger btn-sm" onClick={() => removeMember(m.user_id)} aria-label={lang.common.delete}>
                        <X size={14} />
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {showPollForm && (
        <div className="modal-overlay" onClick={() => setShowPollForm(false)}><div className="modal" onClick={e => e.stopPropagation()}><h2>{lang.chat.createPoll}</h2><form onSubmit={createPoll} className={styles.form}>
          <input placeholder={lang.chat.pollQuestion} value={pollForm.question} onChange={e => setPollForm({ ...pollForm, question: e.target.value })} required />
          <label><input type="checkbox" checked={pollForm.is_multiple} onChange={e => setPollForm({ ...pollForm, is_multiple: e.target.checked })} style={{ width: 'auto', marginRight: 8 }} />{lang.chat.multipleChoice}</label>
          <label>{lang.chat.pollOptions}</label>
          {pollForm.options.map((opt, i) => (
            <div key={i} style={{ display: 'flex', gap: 6 }}>
              <input
                placeholder={`${i + 1}`}
                value={opt}
                onChange={e => {
                  const o = [...pollForm.options];
                  o[i] = e.target.value;
                  setPollForm({ ...pollForm, options: o });
                }}
              />
              {pollForm.options.length > 2 && (
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => setPollForm({ ...pollForm, options: pollForm.options.filter((_, j) => j !== i) })}
                  aria-label={lang.common.delete}
                >
                  <X size={14} />
                </button>
              )}
            </div>
          ))}
          {pollForm.options.length < 20 && <button type="button" className="btn btn-ghost btn-sm" onClick={() => setPollForm({ ...pollForm, options: [...pollForm.options, ''] })}>+ {lang.chat.addOption}</button>}
          <div className={styles.formActions}><button type="button" className="btn btn-secondary" onClick={() => setShowPollForm(false)}>{lang.common.cancel}</button><button type="submit" className="btn btn-primary">{lang.common.create}</button></div>
        </form></div></div>
      )}

    </div>
  );
}
