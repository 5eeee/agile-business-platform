import { useState, useEffect, useCallback, useMemo } from 'react';
import { useAppSelector } from '../../store/hooks';
import DOMPurify from 'dompurify';
import RichEditor from './RichEditor';
import QuizRenderer from './QuizRenderer';
import ConfirmModal from '../../components/ConfirmModal/ConfirmModal';
import FloatingCompiler from '../../components/FloatingCompiler/FloatingCompiler';
import {
  BookOpen, Code2, CheckCircle2, Paperclip, Lock, Pencil, Trash2,
  ClipboardList, FileText, Rocket, Users, Check, X,
  XCircle, ChevronLeft, ChevronDown, Sparkles, GraduationCap
} from 'lucide-react';
import {
  trainingApi,
  type Course, type Topic, type TopicDetail,
  type Submission, type Intern, type CourseAssignment,
  type HashtagType,
} from '../../api/training';
import styles from './Training.module.css';

/* ============ Helpers ============ */
function fmtDate(d: string) {
  try { return new Date(d).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' }); }
  catch { return d; }
}

const PROGRESS_LABELS: Record<string, { label: string; cls: string }> = {
  not_started: { label: 'Не начато', cls: 'progNotStarted' },
  in_progress: { label: 'В процессе', cls: 'progInProgress' },
  completed:   { label: 'Пройдено',  cls: 'progCompleted' },
};

const DIFFICULTY_LABELS: Record<string, { label: string; cls: string }> = {
  basic:    { label: 'База',    cls: 'lvl_basic' },
  medium:   { label: 'Средний', cls: 'lvl_medium' },
  advanced: { label: 'Сложный', cls: 'lvl_advanced' },
};

const CONTENT_TABS = [
  { key: 'theory' as const, label: 'Теория', Icon: BookOpen },
  { key: 'practice' as const, label: 'Практика', Icon: Code2 },
  { key: 'test' as const, label: 'Тест', Icon: CheckCircle2 },
  { key: 'resources' as const, label: 'Ресурсы', Icon: Paperclip },
];

/* ============ TopicsBySection sub-component ============ */
function TopicsBySection({ topics, canEdit, editingTopicId, editTopicText, setEditTopicText, setEditingTopicId, handleSaveTopic, handleDeleteTopic, openTopic, handleToggleProgress, pct, completed, total }: {
  topics: Topic[]; canEdit: boolean; editingTopicId: string | null; editTopicText: string;
  setEditTopicText: (v: string) => void; setEditingTopicId: (v: string | null) => void;
  handleSaveTopic: (id: string) => void; handleDeleteTopic: (id: string) => void;
  openTopic: (t: Topic) => void; handleToggleProgress: (id: string, cur: string) => void;
  pct: number; completed: number; total: number;
}) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());

  const toggleSection = (key: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  const sections = useMemo(() => {
    const map = new Map<string, Topic[]>();
    for (const t of topics) {
      const key = t.section_title || '';
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(t);
    }
    return Array.from(map.entries());
  }, [topics]);

  const renderTopicCard = (t: Topic) => {
    const isEditing = editingTopicId === t.id;
    const isLocked = !t.is_unlocked && !canEdit;
    const prog = PROGRESS_LABELS[t.progress] || PROGRESS_LABELS.not_started;
    const diff = t.difficulty ? DIFFICULTY_LABELS[t.difficulty] : null;
    return (
      <div key={t.id}
        className={`${styles.themeCard} ${t.progress === 'completed' ? styles.themeDone : t.progress === 'in_progress' ? styles.themeProgress : ''} ${isLocked ? styles.themeLocked : ''}`}
        onClick={() => !isEditing && !isLocked && openTopic(t)}>
        <div className={`${styles.themeNum} ${t.progress === 'completed' ? styles.numDone : t.progress === 'in_progress' ? styles.numProg : ''}`}>
          {isLocked ? <Lock size={14} /> : t.order + 1}
        </div>
        <div className={styles.themeInfo}>
          {isEditing && canEdit ? (
            <div className={styles.inlineEdit} onClick={e => e.stopPropagation()}>
              <input value={editTopicText} onChange={e => setEditTopicText(e.target.value)} className={styles.inlineInput}
                onKeyDown={e => { if (e.key === 'Enter') handleSaveTopic(t.id); if (e.key === 'Escape') setEditingTopicId(null); }} autoFocus />
              <button className={styles.btnSm} onClick={() => handleSaveTopic(t.id)} aria-label="Сохранить тему"><Check size={14} /></button>
              <button className={styles.btnSmGray} onClick={() => setEditingTopicId(null)} aria-label="Отменить редактирование"><X size={14} /></button>
            </div>
          ) : (
            <>
              <div className={styles.themeName}>{t.title}</div>
              <div className={styles.themeMeta}>
                {diff && <span className={`${styles.lvl} ${styles[diff.cls]}`}>{diff.label}</span>}
                {t.has_task && <span className={styles.badgeBlue}>Задание</span>}
                {t.hashtags?.map(h => (
                  <span key={h.id} className={styles.hashtagChip} style={{ borderColor: h.color, color: h.color }}>{h.name}</span>
                ))}
              </div>
            </>
          )}
        </div>
        {/* progress toggle */}
        <button
          className={`${styles.progressToggle} ${styles[prog.cls]}`}
          title="Сменить статус"
          onClick={e => { e.stopPropagation(); handleToggleProgress(t.id, t.progress); }}
        >
          {prog.label}
        </button>
        {canEdit && !isEditing && (
          <div className={styles.themeActions} onClick={e => e.stopPropagation()}>
            <button className={styles.btnIcon} title="Редактировать" onClick={() => { setEditingTopicId(t.id); setEditTopicText(t.title); }}><Pencil size={14} /></button>
            <button className={styles.btnIcon} title="Удалить" onClick={() => handleDeleteTopic(t.id)}><Trash2 size={14} /></button>
          </div>
        )}
      </div>
    );
  };

  if (sections.length === 1 && sections[0][0] === '') {
    const sectionKey = '__all__';
    const isExpanded = expandedSections.has(sectionKey);
    return (
      <div className={styles.block}>
        <div className={styles.blockHeader} onClick={() => toggleSection(sectionKey)}>
          <div className={styles.blockDot} style={{ background: pct === 100 ? '#16a34a' : 'var(--color-accent)' }} />
          <h3 className={styles.blockTitle}>Темы курса</h3>
          <div className={styles.blockProg}>{completed}/{total}</div>
          <ChevronDown size={18} className={`${styles.chevron} ${!isExpanded ? styles.chevronCollapsed : ''}`} />
        </div>
        {isExpanded && (
          <div className={styles.blockBody}>
            {topics.map(renderTopicCard)}
          </div>
        )}
      </div>
    );
  }

  return (
    <div>
      {sections.map(([section, sTopics]) => {
        const sDone = sTopics.filter(t => t.progress === 'completed').length;
        const sectionKey = section || '__no_section';
        const isExpanded = expandedSections.has(sectionKey);
        return (
          <div key={sectionKey} className={styles.block}>
            <div className={styles.blockHeader} onClick={() => toggleSection(sectionKey)}>
              <div className={styles.blockDot} style={{ background: sDone === sTopics.length ? '#16a34a' : 'var(--color-accent)' }} />
              <h3 className={styles.blockTitle}>{section || 'Без раздела'}</h3>
              <div className={styles.blockProg}>{sDone}/{sTopics.length}</div>
              <ChevronDown size={18} className={`${styles.chevron} ${!isExpanded ? styles.chevronCollapsed : ''}`} />
            </div>
            {isExpanded && (
              <div className={styles.blockBody}>
                {sTopics.map(renderTopicCard)}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ============ Component ============ */
export default function TrainingPage() {
  const { user } = useAppSelector(s => s.auth);
  const canEdit = user?.role === 'admin' || user?.training_role === 'training_editor';

  /* --- data --- */
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);

  /* --- course detail --- */
  const [currentCourseId, setCurrentCourseId] = useState<string | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [topicsLoading, setTopicsLoading] = useState(false);

  /* --- topic overlay --- */
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);
  const [topicDetail, setTopicDetail] = useState<TopicDetail | null>(null);
  const [topicLoading, setTopicLoading] = useState(false);

  /* --- edit mode --- */
  const [editMode, setEditMode] = useState(false);

  /* --- content block edit --- */
  const [editingBlockId, setEditingBlockId] = useState<string | null>(null);
  const [editBlockTitle, setEditBlockTitle] = useState('');
  const [editBlockBody, setEditBlockBody] = useState('');
  const [showAddContent, setShowAddContent] = useState(false);
  const [newContentTitle, setNewContentTitle] = useState('');
  const [newContentBody, setNewContentBody] = useState('');

  /* --- create course --- */
  const [showCreateCourse, setShowCreateCourse] = useState(false);
  const [newCourseName, setNewCourseName] = useState('');

  /* --- course name edit --- */
  const [editingCourseName, setEditingCourseName] = useState(false);
  const [editCourseNameText, setEditCourseNameText] = useState('');
  const [editCourseDescText, setEditCourseDescText] = useState('');

  /* --- create topic --- */
  const [showCreateTopic, setShowCreateTopic] = useState(false);
  const [newTopicName, setNewTopicName] = useState('');

  /* --- topic name edit --- */
  const [editingTopicId, setEditingTopicId] = useState<string | null>(null);
  const [editTopicText, setEditTopicText] = useState('');


  /* --- pending submissions --- */
  const [showPending, setShowPending] = useState(false);
  const [pendingSubmissions, setPendingSubmissions] = useState<Submission[]>([]);
  const [pendingLoading, setPendingLoading] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);
  const [reviewComments, setReviewComments] = useState<Record<string, string>>({});

  /* --- assignments --- */
  const [showAssignments, setShowAssignments] = useState(false);
  const [assignments, setAssignments] = useState<CourseAssignment[]>([]);
  const [interns, setInterns] = useState<Intern[]>([]);
  const [assignLoading, setAssignLoading] = useState(false);
  const [selectedInterns, setSelectedInterns] = useState<Set<string>>(new Set());

  /* --- confirm modal --- */
  const [confirmAction, setConfirmAction] = useState<{ msg: string; action: () => void } | null>(null);

  /* --- hashtags --- */
  const [allHashtags, setAllHashtags] = useState<HashtagType[]>([]);
  const [newHashtagName, setNewHashtagName] = useState('');
  const [newHashtagColor, setNewHashtagColor] = useState('#2563eb');

  /* --- content tab in topic overlay --- */
  const [activeContentTab, setActiveContentTab] = useState<'theory' | 'practice' | 'test' | 'resources'>('theory');

  /* ========== DATA LOADING ========== */
  const loadCourses = useCallback(async () => {
    try {
      const { data } = await trainingApi.getCourses();
      setCourses(data);
    } catch { /* interceptor handles */ }
    finally { setLoading(false); }
  }, []);

  const loadTopics = useCallback(async (courseId: string) => {
    setTopicsLoading(true);
    try {
      const { data } = await trainingApi.getTopics(courseId);
      setTopics(data);
    } catch { /* interceptor */ }
    finally { setTopicsLoading(false); }
  }, []);

  const loadTopicDetail = useCallback(async (topicId: string) => {
    setTopicLoading(true);
    try {
      const { data } = await trainingApi.getTopicDetail(topicId);
      setTopicDetail(data);
    } catch { /* interceptor */ }
    finally { setTopicLoading(false); }
  }, []);

  const loadPendingCount = useCallback(async () => {
    if (!canEdit) return;
    try {
      const { data } = await trainingApi.getPendingSubmissions();
      setPendingCount(data.length);
    } catch { /* ignore */ }
  }, [canEdit]);

  const loadHashtags = useCallback(async () => {
    try {
      const { data } = await trainingApi.getHashtags();
      setAllHashtags(data);
    } catch { /* ignore */ }
  }, []);

  /* ========== EFFECTS ========== */
  useEffect(() => { loadCourses(); loadPendingCount(); loadHashtags(); }, [loadCourses, loadPendingCount, loadHashtags]);

  useEffect(() => {
    if (currentCourseId) loadTopics(currentCourseId);
  }, [currentCourseId, loadTopics]);

  useEffect(() => {
    if (!currentCourseId) return;
    const id = window.setInterval(() => {
      loadTopics(currentCourseId);
    }, 30000);
    return () => window.clearInterval(id);
  }, [currentCourseId, loadTopics]);

  useEffect(() => {
    if (selectedTopicId) loadTopicDetail(selectedTopicId);
  }, [selectedTopicId, loadTopicDetail]);

  useEffect(() => {
    if (!canEdit) return;
    const id = window.setInterval(() => {
      loadPendingCount();
    }, 30000);
    return () => window.clearInterval(id);
  }, [canEdit, loadPendingCount]);

  /* body scroll lock */
  useEffect(() => {
    document.body.style.overflow = (selectedTopicId || showPending || showAssignments) ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [selectedTopicId, showPending, showAssignments]);

  /* ESC to close */
  useEffect(() => {
    if (!selectedTopicId && !showPending && !showAssignments) return;
    const h = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showAssignments) setShowAssignments(false);
        else if (showPending) setShowPending(false);
        else if (selectedTopicId) closeTopic();
      }
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTopicId, showPending, showAssignments]);

  const currentCourse = currentCourseId ? courses.find(c => c.id === currentCourseId) : null;

  /* ========== COURSE ACTIONS ========== */
  const handleCreateCourse = async () => {
    if (!newCourseName.trim()) return;
    try {
      const { data } = await trainingApi.createCourse({ title: newCourseName.trim() });
      setCourses(prev => [...prev, data]);
      setCurrentCourseId(data.id);
      setNewCourseName(''); setShowCreateCourse(false);
    } catch { /* interceptor */ }
  };

  const handleUpdateCourse = async (updates: { title?: string; description?: string; is_published?: boolean }) => {
    if (!currentCourseId) return;
    try {
      const { data } = await trainingApi.updateCourse(currentCourseId, updates);
      setCourses(prev => prev.map(c => c.id === currentCourseId ? data : c));
    } catch { /* interceptor */ }
  };

  const handleDeleteCourse = (id: string) => {
    setConfirmAction({ msg: 'Удалить курс и все его темы?', action: async () => {
      try {
        await trainingApi.deleteCourse(id);
        setCourses(prev => prev.filter(c => c.id !== id));
        if (currentCourseId === id) { setCurrentCourseId(null); setTopics([]); }
      } catch { /* interceptor */ }
    }});
  };

  /* ========== TOPIC ACTIONS ========== */
  const handleCreateTopic = async () => {
    if (!newTopicName.trim() || !currentCourseId) return;
    try {
      await trainingApi.createTopic(currentCourseId, { title: newTopicName.trim() });
      await loadTopics(currentCourseId);
      setCourses(prev => prev.map(c => c.id === currentCourseId ? { ...c, topic_count: c.topic_count + 1 } : c));
      setNewTopicName(''); setShowCreateTopic(false);
    } catch { /* interceptor */ }
  };

  const handleSaveTopic = async (topicId: string) => {
    if (!editTopicText.trim()) return;
    try {
      await trainingApi.updateTopic(topicId, { title: editTopicText.trim() });
      if (currentCourseId) await loadTopics(currentCourseId);
      setEditingTopicId(null);
    } catch { /* interceptor */ }
  };

  const handleDeleteTopic = (topicId: string) => {
    setConfirmAction({ msg: 'Удалить тему и все её содержимое?', action: async () => {
      try {
        await trainingApi.deleteTopic(topicId);
        if (currentCourseId) {
          await loadTopics(currentCourseId);
          setCourses(prev => prev.map(c => c.id === currentCourseId ? { ...c, topic_count: Math.max(0, c.topic_count - 1) } : c));
        }
      } catch { /* interceptor */ }
    }});
  };

  const openTopic = (topic: Topic) => {
    if (!topic.is_unlocked && !canEdit) return;
    setSelectedTopicId(topic.id);
    setEditMode(false);
    setEditingBlockId(null);
    setShowAddContent(false);
  };

  const closeTopic = () => {
    setSelectedTopicId(null);
    setTopicDetail(null);
    setEditMode(false);
    setActiveContentTab('theory');
    if (currentCourseId) loadTopics(currentCourseId);
  };

  /* ========== PROGRESS TOGGLE ========== */
  const handleToggleProgress = async (topicId: string, current: string) => {
    const next = current === 'not_started' ? 'in_progress' : current === 'in_progress' ? 'completed' : 'not_started';
    try {
      await trainingApi.updateProgress(topicId, next);
      setTopics(prev => prev.map(t => t.id === topicId ? { ...t, progress: next as Topic['progress'] } : t));
    } catch { /* interceptor */ }
  };

  /* ========== HASHTAG ACTIONS ========== */
  const handleCreateHashtag = async () => {
    if (!newHashtagName.trim()) return;
    try {
      const { data } = await trainingApi.createHashtag({ name: newHashtagName.trim(), color: newHashtagColor });
      setAllHashtags(prev => [...prev, data]);
      setNewHashtagName(''); setNewHashtagColor('#2563eb');
    } catch { /* interceptor */ }
  };

  const handleDeleteHashtag = async (id: string) => {
    try {
      await trainingApi.deleteHashtag(id);
      setAllHashtags(prev => prev.filter(h => h.id !== id));
    } catch { /* interceptor */ }
  };

  const handleAssignHashtag = async (topicId: string, hashtagId: string) => {
    try {
      await trainingApi.assignHashtag(topicId, hashtagId);
      if (currentCourseId) await loadTopics(currentCourseId);
      if (selectedTopicId) await loadTopicDetail(selectedTopicId);
    } catch { /* interceptor */ }
  };

  const handleRemoveHashtag = async (topicId: string, hashtagId: string) => {
    try {
      await trainingApi.removeHashtag(topicId, hashtagId);
      if (currentCourseId) await loadTopics(currentCourseId);
      if (selectedTopicId) await loadTopicDetail(selectedTopicId);
    } catch { /* interceptor */ }
  };

  /* ========== CONTENT BLOCK ACTIONS ========== */
  const handleSaveContentBlock = async (blockId: string) => {
    try {
      await trainingApi.updateContent(blockId, { title: editBlockTitle || undefined, body: editBlockBody || undefined });
      if (selectedTopicId) await loadTopicDetail(selectedTopicId);
      setEditingBlockId(null);
    } catch { /* interceptor */ }
  };

  const handleAddContentBlock = async () => {
    if (!selectedTopicId) return;
    try {
      await trainingApi.createContent(selectedTopicId, { title: newContentTitle || undefined, body: newContentBody || undefined });
      await loadTopicDetail(selectedTopicId);
      setNewContentTitle(''); setNewContentBody(''); setShowAddContent(false);
    } catch { /* interceptor */ }
  };

  const handleDeleteContentBlock = (blockId: string) => {
    setConfirmAction({ msg: 'Удалить блок контента?', action: async () => {
      try {
        await trainingApi.deleteContent(blockId);
        if (selectedTopicId) await loadTopicDetail(selectedTopicId);
      } catch { /* interceptor */ }
    }});
  };

  /* ========== PENDING SUBMISSIONS ========== */
  const openPending = async () => {
    setShowPending(true);
    setPendingLoading(true);
    try {
      const { data } = await trainingApi.getPendingSubmissions();
      setPendingSubmissions(data);
    } catch { /* interceptor */ }
    finally { setPendingLoading(false); }
  };

  const handleReview = async (subId: string, status: 'approved' | 'rejected') => {
    try {
      await trainingApi.reviewSubmission(subId, { status, review_comment: reviewComments[subId] || undefined });
      setPendingSubmissions(prev => prev.filter(s => s.id !== subId));
      setPendingCount(prev => Math.max(0, prev - 1));
      setReviewComments(prev => { const n = { ...prev }; delete n[subId]; return n; });
    } catch { /* interceptor */ }
  };

  /* ========== ASSIGNMENTS ========== */
  const openAssignments = async () => {
    if (!currentCourseId) return;
    setShowAssignments(true);
    setAssignLoading(true);
    try {
      const [assignRes, internsRes] = await Promise.all([
        trainingApi.getAssignments(currentCourseId),
        trainingApi.getInterns(),
      ]);
      setAssignments(assignRes.data);
      setInterns(internsRes.data);
      setSelectedInterns(new Set());
    } catch { /* interceptor */ }
    finally { setAssignLoading(false); }
  };

  const handleAssignInterns = async () => {
    if (!currentCourseId || selectedInterns.size === 0) return;
    try {
      const { data } = await trainingApi.assignCourse(currentCourseId, Array.from(selectedInterns));
      setAssignments(data);
      setSelectedInterns(new Set());
    } catch { /* interceptor */ }
  };

  const handleUnassign = async (userId: string) => {
    if (!currentCourseId) return;
    try {
      await trainingApi.unassignCourse(currentCourseId, userId);
      setAssignments(prev => prev.filter(a => a.user_id !== userId));
    } catch { /* interceptor */ }
  };

  /* ==================== RENDER: COURSES LIST ==================== */
  const renderCoursesList = () => {
    if (loading) {
      return <div className={styles.emptyState}><p>Загрузка курсов...</p></div>;
    }
    if (!courses.length) {
      return (
        <div className={styles.emptyState}>
          <GraduationCap size={64} strokeWidth={1.2} style={{ color: '#94a3b8', marginBottom: 20 }} />
          <h2>Нет курсов</h2>
          <p>{canEdit ? 'Создайте свой первый курс обучения' : 'Вам пока не назначены курсы'}</p>
          {canEdit && (showCreateCourse ? (
            <div className={styles.addForm} style={{ justifyContent: 'center' }}>
              <input className={styles.addInput} style={{ maxWidth: 300 }} placeholder="Название курса" value={newCourseName}
                onChange={e => setNewCourseName(e.target.value)} maxLength={200}
                onKeyDown={e => { if (e.key === 'Enter') handleCreateCourse(); }} autoFocus />
              <button className={styles.btnPrimary} onClick={handleCreateCourse}>Создать</button>
              <button className={styles.btnGray} onClick={() => { setShowCreateCourse(false); setNewCourseName(''); }}>Отмена</button>
            </div>
          ) : (
            <button className={styles.btnSuccess} onClick={() => setShowCreateCourse(true)}>+ Создать курс</button>
          ))}
        </div>
      );
    }

    return (
      <div>
        <div className={styles.pageHeader}>
          <h1>Обучение</h1>
          <p>Курсы и программы обучения</p>
          {canEdit && (
            <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
              {showCreateCourse ? (
                <div className={styles.addForm} style={{ marginTop: 0 }}>
                  <input className={styles.addInput} placeholder="Название курса" value={newCourseName}
                    onChange={e => setNewCourseName(e.target.value)} maxLength={200}
                    onKeyDown={e => { if (e.key === 'Enter') handleCreateCourse(); }} autoFocus />
                  <button className={styles.btnPrimary} onClick={handleCreateCourse}>Создать</button>
                  <button className={styles.btnGray} onClick={() => { setShowCreateCourse(false); setNewCourseName(''); }}>Отмена</button>
                </div>
              ) : (
                <button className={styles.btnSuccess} onClick={() => setShowCreateCourse(true)}>+ Создать курс</button>
              )}
              <button className={styles.btnGray} onClick={openPending}>
                <ClipboardList size={14} /> На проверке{pendingCount > 0 && <span className={styles.tabBadge}>{pendingCount}</span>}
              </button>
            </div>
          )}
        </div>
        <div className={styles.plansGrid}>
          {courses.map(c => (
            <div key={c.id} className={styles.planCard} onClick={() => setCurrentCourseId(c.id)}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <h3>{c.title}</h3>
                <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                  {!c.is_published && canEdit && <span className={styles.badgeGray}>Черновик</span>}
                  {c.is_published && <span className={styles.badgeGreen}>Опубликован</span>}
                  {canEdit && (
                    <button
                      className={styles.btnIconDanger}
                      onClick={e => { e.stopPropagation(); handleDeleteCourse(c.id); }}
                      title="Удалить"
                      aria-label="Удалить курс"
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>
              </div>
              {c.description && <div className={styles.planCardMeta}>{c.description}</div>}
              <div className={styles.planCardBottom}>
                <span>{c.topic_count} тем</span>
                <span className={styles.planCardPct}>{fmtDate(c.created_at)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  /* ==================== RENDER: COURSE DETAIL ==================== */
  const renderCourseDetail = () => {
    if (!currentCourse) return null;
    const completed = topics.filter(t => t.status === 'completed').length;
    const inProgress = topics.filter(t => t.status === 'in_progress').length;
    const locked = topics.filter(t => t.status === 'locked').length;
    const total = topics.length;
    const pct = total ? Math.round(completed / total * 100) : 0;

    return (
      <div>
        <button className={styles.backLink} onClick={() => { setCurrentCourseId(null); setTopics([]); }}><ChevronLeft size={16} /> Все курсы</button>

        <div className={styles.pageHeader}>
          {editingCourseName && canEdit ? (
            <div className={styles.addFormVert} style={{ marginBottom: 4 }}>
              <input className={styles.addInput} style={{ fontSize: 20, fontWeight: 700 }} value={editCourseNameText}
                onChange={e => setEditCourseNameText(e.target.value)} maxLength={200}
                onKeyDown={e => {
                  if (e.key === 'Enter') { handleUpdateCourse({ title: editCourseNameText.trim(), description: editCourseDescText.trim() || undefined }); setEditingCourseName(false); }
                  if (e.key === 'Escape') setEditingCourseName(false);
                }} autoFocus />
              <textarea className={styles.addTextarea} placeholder="Описание (необязательно)" value={editCourseDescText}
                onChange={e => setEditCourseDescText(e.target.value)} rows={2} />
              <div className={styles.addFormRow}>
                <button className={styles.btnSm} onClick={() => { handleUpdateCourse({ title: editCourseNameText.trim(), description: editCourseDescText.trim() || undefined }); setEditingCourseName(false); }}>
                  <Check size={14} style={{ marginRight: 6 }} /> Сохранить
                </button>
                <button className={styles.btnSmGray} onClick={() => setEditingCourseName(false)}>
                  <X size={14} style={{ marginRight: 6 }} /> Отмена
                </button>
              </div>
            </div>
          ) : (
            <h1 style={{ cursor: canEdit ? 'pointer' : undefined }}
              onClick={() => { if (canEdit) { setEditingCourseName(true); setEditCourseNameText(currentCourse.title); setEditCourseDescText(currentCourse.description || ''); } }}>
              {currentCourse.title}
              {canEdit && <Pencil size={14} style={{ marginLeft: 8, opacity: 0.4 }} />}
            </h1>
          )}
          {currentCourse.description && !editingCourseName && <p>{currentCourse.description}</p>}
          <div className={styles.badges}>
            {currentCourse.is_published ? <span className={styles.badgeGreen}>Опубликован</span> : <span className={styles.badgeGray}>Черновик</span>}
            <span className={styles.badgeGray}>{fmtDate(currentCourse.created_at)}</span>
          </div>
        </div>

        {/* progress */}
        <div className={styles.progressCard}>
          <div className={styles.progressCardTop}>
            <div>
              <div className={styles.progressTitle}>Прогресс курса</div>
              <div className={styles.progressSub}>{completed} из {total} тем пройдено{inProgress > 0 && ` | ${inProgress} в процессе`}</div>
            </div>
            <div className={styles.progressPct}>{pct}%</div>
          </div>
          <div className={styles.barBig}><div className={`${styles.barFill} ${pct === 100 ? styles.barGreen : ''}`} style={{ width: pct + '%' }} /></div>
        </div>

        {/* stats */}
        <div className={styles.statsRow}>
          <div className={styles.statCard}><div className={styles.statVal} style={{ color: 'var(--color-accent)' }}>{total}</div><div className={styles.statLbl}>Тем</div></div>
          <div className={styles.statCard}><div className={styles.statVal} style={{ color: '#16a34a' }}>{completed}</div><div className={styles.statLbl}>Пройдено</div></div>
          <div className={styles.statCard}><div className={styles.statVal} style={{ color: '#ca8a04' }}>{inProgress}</div><div className={styles.statLbl}>В процессе</div></div>
          <div className={styles.statCard}><div className={styles.statVal} style={{ color: '#dc2626' }}>{locked}</div><div className={styles.statLbl}>Заблокировано</div></div>
        </div>

        {pct === 100 && total > 0 && <div className={styles.congratsBanner}><Sparkles size={18} /> Все темы пройдены!</div>}

        {/* topics list */}
        {topicsLoading ? (
          <div className={styles.emptyContent}>Загрузка тем...</div>
        ) : (
          <TopicsBySection
            topics={topics}
            canEdit={canEdit}
            editingTopicId={editingTopicId}
            editTopicText={editTopicText}
            setEditTopicText={setEditTopicText}
            setEditingTopicId={setEditingTopicId}
            handleSaveTopic={handleSaveTopic}
            handleDeleteTopic={handleDeleteTopic}
            openTopic={openTopic}
            handleToggleProgress={handleToggleProgress}
            pct={pct}
            completed={completed}
            total={total}
          />
        )}

        {/* add topic */}
        {canEdit && !topicsLoading && (
          showCreateTopic ? (
            <div className={styles.addForm}>
              <input className={styles.addInput} placeholder="Название темы" value={newTopicName}
                onChange={e => setNewTopicName(e.target.value)} maxLength={200}
                onKeyDown={e => { if (e.key === 'Enter') handleCreateTopic(); }} autoFocus />
              <button className={styles.btnPrimary} onClick={handleCreateTopic}>Добавить</button>
              <button className={styles.btnGray} onClick={() => { setShowCreateTopic(false); setNewTopicName(''); }}>Отмена</button>
            </div>
          ) : (
            <button className={styles.addBtn} onClick={() => setShowCreateTopic(true)}>+ Добавить тему</button>
          )
        )}

        {/* course actions */}
        <div className={styles.planActions}>
          {canEdit && (
            <>
              <button className={styles.btnPrimary} onClick={() => handleUpdateCourse({ is_published: !currentCourse.is_published })}>
                {currentCourse.is_published ? <><FileText size={14} /> Снять с публикации</> : <><Rocket size={14} /> Опубликовать</>}
              </button>
              <button className={styles.btnGray} onClick={openAssignments}><Users size={14} /> Назначения</button>
              <button className={styles.btnDanger} onClick={() => handleDeleteCourse(currentCourse.id)}>Удалить курс</button>
            </>
          )}
        </div>
      </div>
    );
  };

  /* ==================== RENDER: TOPIC OVERLAY ==================== */
  const renderTopicOverlay = () => {
    if (!selectedTopicId) return null;

    if (topicLoading || !topicDetail) {
      return (
        <div className={styles.overlay}>
          <div className={styles.overlayBox}>
            <div className={styles.overlayTop}><button className={styles.backBtn} onClick={closeTopic}>← Назад</button></div>
            <div className={styles.emptyContent}>Загрузка...</div>
          </div>
        </div>
      );
    }

    const blocks = [...topicDetail.content_blocks].sort((a, b) => a.order - b.order);
    const blocksByType: Record<string, typeof blocks> = { theory: [], practice: [], test: [], resources: [] };
    for (const b of blocks) {
      const ct = b.content_type || 'theory';
      if (blocksByType[ct]) blocksByType[ct].push(b);
      else blocksByType.theory.push(b);
    }
    const diff = topicDetail.difficulty ? DIFFICULTY_LABELS[topicDetail.difficulty] : null;

    return (
      <div className={styles.overlay} onClick={closeTopic}>
        <div className={styles.overlayBox} onClick={e => e.stopPropagation()}>
          {/* top bar: back + progress + esc hint */}
          <div className={styles.overlayTop}>
            <div className={styles.overlayTopLeft}>
              <button className={styles.backBtn} onClick={closeTopic} aria-label="Закрыть">← Назад</button>
              {topics.length > 0 && (() => {
                const idx = topics.findIndex(t => t.id === selectedTopicId);
                if (idx < 0) return null;
                const prev = topics[idx - 1];
                const next = topics[idx + 1];
                return (
                  <span className={styles.topicNav}>
                    {prev && (
                      <button type="button" className={styles.navBtn} onClick={() => openTopic(prev)} title={`Предыдущая: ${prev.title}`}>
                        ← Пред.
                      </button>
                    )}
                    <span className={styles.topicProgress}>
                      {idx + 1} / {topics.length}
                    </span>
                    {next && (
                      <button type="button" className={styles.navBtn} onClick={() => openTopic(next)} title={`Следующая: ${next.title}`}>
                        След. →
                      </button>
                    )}
                  </span>
                );
              })()}
              <span className={styles.escHint}>Esc — закрыть</span>
            </div>
            {canEdit && (
              <label className={styles.editToggle}>
                <input type="checkbox" checked={editMode} onChange={e => setEditMode(e.target.checked)} />
                <span>Режим редактирования</span>
              </label>
            )}
          </div>

          {/* breadcrumbs */}
          <div className={styles.breadcrumbs}>
            <span className={styles.crumbLink} onClick={closeTopic}>{currentCourse?.title || 'Курс'}</span>
            <span className={styles.crumbSep}>›</span>
            <span className={styles.crumbCur}>{topicDetail.title}</span>
          </div>

          {/* meta badges: difficulty + hashtags */}
          <div className={styles.moduleBadges}>
            {diff && <span className={`${styles.lvl} ${styles[diff.cls]}`}>{diff.label}</span>}
            {topicDetail.hashtags?.map(h => (
              <span key={h.id} className={styles.hashtagChip} style={{ borderColor: h.color, color: h.color }}>
                {h.name}
                {editMode && canEdit && (
                  <button className={styles.hashtagRemove} onClick={() => handleRemoveHashtag(topicDetail.id, h.id)} aria-label="Удалить хэштег">
                    <X size={12} />
                  </button>
                )}
              </span>
            ))}
          </div>

          {/* editor: difficulty + hashtag management */}
          {editMode && canEdit && (
            <div className={styles.editMetaRow}>
              <div className={styles.editMetaGroup}>
                <label className={styles.editMetaLabel}>Сложность:</label>
                <select className={styles.addSelect} value={topicDetail.difficulty || ''}
                  onChange={async e => {
                    const val = e.target.value || undefined;
                    await trainingApi.updateTopic(topicDetail.id, { difficulty: val });
                    await loadTopicDetail(topicDetail.id);
                  }}>
                  <option value="">Не указано</option>
                  <option value="basic">База</option>
                  <option value="medium">Средний</option>
                  <option value="advanced">Сложный</option>
                </select>
              </div>
              <div className={styles.editMetaGroup}>
                <label className={styles.editMetaLabel}>Хэштеги:</label>
                <div className={styles.hashtagPicker}>
                  {allHashtags.filter(h => !topicDetail.hashtags?.some(th => th.id === h.id)).map(h => (
                    <button key={h.id} className={styles.hashtagAdd} style={{ borderColor: h.color, color: h.color }}
                      onClick={() => handleAssignHashtag(topicDetail.id, h.id)}>+ {h.name}</button>
                  ))}
                  <div className={styles.hashtagCreateInline}>
                    <input className={styles.hashtagInput} placeholder="Новый #" value={newHashtagName}
                      onChange={e => setNewHashtagName(e.target.value)} maxLength={50}
                      onKeyDown={e => { if (e.key === 'Enter') handleCreateHashtag(); }} />
                    <input type="color" value={newHashtagColor} onChange={e => setNewHashtagColor(e.target.value)}
                      className={styles.hashtagColorPick} />
                    {newHashtagName.trim() && <button className={styles.btnSm} onClick={handleCreateHashtag}>+</button>}
                  </div>
                </div>
              </div>
            </div>
          )}

          {topicDetail.description && <p style={{ color: 'var(--color-text-secondary)', fontSize: 14, margin: '0 0 16px' }}>{topicDetail.description}</p>}

          {/* ===== CONTENT TABS ===== */}
          <div className={styles.contentTabs}>
            {CONTENT_TABS.map(tab => (
              <button key={tab.key}
                className={`${styles.contentTab} ${activeContentTab === tab.key ? styles.contentTabActive : ''}`}
                onClick={() => setActiveContentTab(tab.key)}>
                <span className={styles.contentTabIcon}><tab.Icon size={16} /></span> {tab.label}
                {blocksByType[tab.key]?.length > 0 && <span className={styles.tabCount}>{blocksByType[tab.key].length}</span>}
              </button>
            ))}
          </div>

          {/* ===== CONTENT BLOCKS FOR ACTIVE TAB ===== */}
          <section className={styles.section}>
            {(blocksByType[activeContentTab] || []).length > 0 ? (
              (blocksByType[activeContentTab] || []).map(block => (
                <div key={block.id} style={{ marginBottom: 16 }}>
                  {editMode && editingBlockId === block.id ? (
                    <div className={styles.addFormVert}>
                      <input className={styles.addInput} placeholder="Заголовок блока" value={editBlockTitle}
                        onChange={e => setEditBlockTitle(e.target.value)} maxLength={200} />
                      <RichEditor key={block.id} content={editBlockBody} onChange={setEditBlockBody} />
                      <div className={styles.addFormRow}>
                        <button className={styles.btnPrimary} onClick={() => handleSaveContentBlock(block.id)}>Сохранить</button>
                        <button className={styles.btnGray} onClick={() => setEditingBlockId(null)}>Отмена</button>
                        <button className={styles.btnDanger} onClick={() => handleDeleteContentBlock(block.id)}>Удалить</button>
                      </div>
                    </div>
                  ) : (
                    <div>
                      {block.title && <h3 style={{ marginBottom: 8, fontSize: 16 }}>{block.title}</h3>}
                      {block.body ? (
                        activeContentTab === 'test' ? (
                          <QuizRenderer
                            html={block.body}
                            topicId={topicDetail.id}
                            onTestPassed={() => {
                              if (currentCourseId) loadTopics(currentCourseId);
                            }}
                          />
                        ) : (
                          <div className={styles.richContent} dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(block.body) }} />
                        )
                      ) : (
                        <div className={styles.emptyContent}>Контент не добавлен</div>
                      )}
                      {editMode && canEdit && (
                        <button className={styles.btnSm} style={{ marginTop: 8 }}
                          onClick={() => { setEditingBlockId(block.id); setEditBlockTitle(block.title || ''); setEditBlockBody(block.body || ''); }}>
                          Редактировать
                        </button>
                      )}
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className={styles.emptyContent}>{editMode ? 'Добавьте контент' : 'Материал пока не добавлен'}</div>
            )}
            {editMode && canEdit && (
              showAddContent ? (
                <div className={styles.addFormVert}>
                  <input className={styles.addInput} placeholder="Заголовок блока" value={newContentTitle}
                    onChange={e => setNewContentTitle(e.target.value)} maxLength={200} />
                  <RichEditor content={newContentBody} onChange={setNewContentBody} />
                  <div className={styles.addFormRow}>
                    <button className={styles.btnPrimary} onClick={async () => {
                      if (!selectedTopicId) return;
                      try {
                        await trainingApi.createContent(selectedTopicId, {
                          title: newContentTitle || undefined,
                          body: newContentBody || undefined,
                          content_type: activeContentTab,
                        });
                        await loadTopicDetail(selectedTopicId);
                        setNewContentTitle(''); setNewContentBody(''); setShowAddContent(false);
                      } catch { /* interceptor */ }
                    }}>Добавить</button>
                    <button className={styles.btnGray} onClick={() => { setShowAddContent(false); setNewContentTitle(''); setNewContentBody(''); }}>Отмена</button>
                  </div>
                </div>
              ) : (
                <button className={styles.addBtn} onClick={() => setShowAddContent(true)}>+ Добавить блок контента</button>
              )
            )}
          </section>


          {/* bottom */}
          <div className={styles.overlayBottom}>
            <button className={styles.btnGray} onClick={closeTopic}>← Назад</button>
          </div>
        </div>
      </div>
    );
  };

  /* ==================== RENDER: PENDING SUBMISSIONS ==================== */
  const renderPendingOverlay = () => (
    <div className={styles.overlay} onClick={() => setShowPending(false)}>
      <div className={styles.overlayBox} onClick={e => e.stopPropagation()}>
        <div className={styles.overlayTop}>
          <button className={styles.backBtn} onClick={() => setShowPending(false)}>← Назад</button>
          <h2 style={{ margin: 0, fontSize: 18 }}>Ответы на проверке</h2>
        </div>

        {pendingLoading ? (
          <div className={styles.emptyContent}>Загрузка...</div>
        ) : pendingSubmissions.length === 0 ? (
          <div className={styles.emptyContent}>Нет ответов на проверке</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {pendingSubmissions.map(sub => (
              <div key={sub.id} className={styles.reviewCard}>
                <div className={styles.reviewHeader}>
                  <div>
                    <div className={styles.reviewUser}>{sub.user_name}</div>
                    <div className={styles.reviewTask}>Задание: {sub.task_title}</div>
                  </div>
                  <span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>{fmtDate(sub.created_at)}</span>
                </div>
                {sub.content && <div className={styles.reviewContent}>{sub.content}</div>}
                {sub.file_url && (
                  <a href={sub.file_url} target="_blank" rel="noopener noreferrer" className={styles.btnSm} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginBottom: 8 }}>
                    <Paperclip size={12} /> Файл
                  </a>
                )}
                <div className={styles.reviewActions}>
                  <input className={styles.reviewComment} placeholder="Комментарий..."
                    value={reviewComments[sub.id] || ''}
                    onChange={e => setReviewComments(prev => ({ ...prev, [sub.id]: e.target.value }))} />
                  <button className={styles.btnSuccess} onClick={() => handleReview(sub.id, 'approved')}><CheckCircle2 size={14} /> Принять</button>
                  <button className={styles.btnDanger} onClick={() => handleReview(sub.id, 'rejected')}><XCircle size={14} /> Отклонить</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  /* ==================== RENDER: ASSIGNMENTS ==================== */
  const renderAssignmentModal = () => {
    const unassigned = interns.filter(i => !assignments.some(a => a.user_id === i.id));
    return (
      <div className={styles.overlay} onClick={() => setShowAssignments(false)}>
        <div className={styles.overlayBox} onClick={e => e.stopPropagation()}>
          <div className={styles.overlayTop}>
            <button className={styles.backBtn} onClick={() => setShowAssignments(false)}>← Назад</button>
            <h2 style={{ margin: 0, fontSize: 18 }}>Назначения на курс</h2>
          </div>

          {assignLoading ? (
            <div className={styles.emptyContent}>Загрузка...</div>
          ) : (
            <>
              <section className={styles.section}>
                <h3 className={styles.sectionTitle}>Назначенные стажёры ({assignments.length})</h3>
                {assignments.length > 0 ? (
                  <div className={styles.assignList}>
                    {assignments.map(a => (
                      <div key={a.id} className={styles.assignItem}>
                        <div className={styles.assignInfo}>
                          <span className={styles.assignName}>{a.user_name}</span>
                          <span className={styles.assignEmail}>{a.user_email}</span>
                          <span className={styles.assignBy}>Назначил: {a.assigned_by_name} | {fmtDate(a.created_at)}</span>
                        </div>
                        <button className={styles.btnIconDanger} onClick={() => handleUnassign(a.user_id)} title="Снять назначение" aria-label="Снять назначение">
                          <X size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className={styles.emptyContent}>Нет назначений</div>
                )}
              </section>

              <section className={styles.section}>
                <h3 className={styles.sectionTitle}>Назначить стажёров</h3>
                {unassigned.length > 0 ? (
                  <div>
                    <div className={styles.assignList}>
                      {unassigned.map(intern => (
                        <label key={intern.id} className={styles.assignItem} style={{ cursor: 'pointer' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                            <input type="checkbox" checked={selectedInterns.has(intern.id)}
                              onChange={e => {
                                setSelectedInterns(prev => {
                                  const n = new Set(prev);
                                  if (e.target.checked) n.add(intern.id); else n.delete(intern.id);
                                  return n;
                                });
                              }} />
                            <div className={styles.assignInfo}>
                              <span className={styles.assignName}>{intern.name}</span>
                              <span className={styles.assignEmail}>{intern.email}</span>
                            </div>
                          </div>
                        </label>
                      ))}
                    </div>
                    {selectedInterns.size > 0 && (
                      <button className={styles.btnPrimary} style={{ marginTop: 12 }} onClick={handleAssignInterns}>
                        Назначить ({selectedInterns.size})
                      </button>
                    )}
                  </div>
                ) : interns.length === 0 ? (
                  <div className={styles.emptyContent}>Нет стажёров (training_role = &apos;intern&apos;)</div>
                ) : (
                  <div className={styles.emptyContent}>Все стажёры уже назначены</div>
                )}
              </section>
            </>
          )}
        </div>
      </div>
    );
  };

  /* ==================== RETURN ==================== */
  return (
    <>
      <div className={styles.page}>
        {currentCourseId ? renderCourseDetail() : renderCoursesList()}
        {renderTopicOverlay()}
        {showPending && renderPendingOverlay()}
        {showAssignments && renderAssignmentModal()}
        {confirmAction && (
          <ConfirmModal
            title="Подтверждение"
            message={confirmAction.msg}
            confirmLabel="Да"
            cancelLabel="Отмена"
            variant="danger"
            onConfirm={() => { confirmAction.action(); setConfirmAction(null); }}
            onCancel={() => setConfirmAction(null)}
          />
        )}
      </div>
      <FloatingCompiler />
    </>
  );
}
