import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate, useLocation } from 'react-router-dom';
import { Plus, FolderInput, ListTodo, ChevronsLeftRight, MoreHorizontal, Pencil, Trash2, Archive, ChevronDown } from 'lucide-react';
import { useAppSelector, useAppDispatch } from '../../store/hooks';
import { toggleMobileMenu, toggleSidebarNarrow } from '../../store/slices/uiSlice';
import { t } from '../../i18n';
import api from '../../api/client';
import ConfirmModal from '../ConfirmModal/ConfirmModal';
import type { Project } from '../../types';
import styles from './Sidebar.module.css';

export const PROJECTS_LIST_CHANGED = 'agile-projects-list-changed';

const HomeIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
);
const CalendarIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
);
const UserIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
);
const SettingsIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
);
const MapPinIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
);
const MusicIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
);
const ShopIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M6 2l1.5 4H22l-2 11H7L4 4H2"/><circle cx="9" cy="20" r="2"/><circle cx="18" cy="20" r="2"/></svg>
);
const BarChartIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/></svg>
);
const BookIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
);
const ClipboardCheckIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/><path d="M9 14l2 2 4-4"/></svg>
);
const TargetIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>
);
const KPIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/></svg>
);
const LeaderboardIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M8 21h8"/><path d="M12 17v4"/><path d="M7 4h10l-1 6a4 4 0 0 1-4 3 4 4 0 0 1-4-3z"/></svg>
);
const BuildingIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M3 21h18"/><path d="M5 21V7l8-4v18"/><path d="M19 21V11l-6-4"/><line x1="9" y1="9" x2="9" y2="9.01"/><line x1="9" y1="12" x2="9" y2="12.01"/><line x1="9" y1="15" x2="9" y2="15.01"/><line x1="9" y1="18" x2="9" y2="18.01"/></svg>
);

const MyTasksIcon = () => (
  <span className={styles.icon} aria-hidden><ListTodo size={18} strokeWidth={1.8} /></span>
);

const iconMap: Record<string, () => JSX.Element> = {
  home: HomeIcon,
  events: CalendarIcon,
  places: MapPinIcon,
  music: MusicIcon,
  shop: ShopIcon,
  analytics: BarChartIcon,
  training: BookIcon,
  assessment: ClipboardCheckIcon,
  competency: TargetIcon,
  kpi: KPIcon,
  leaderboard: LeaderboardIcon,
  profile: UserIcon,
  myProfile: UserIcon,
  myCompany: BuildingIcon,
};

const topNavItems = [
  { path: '/profile', key: 'myProfile' as const },
  { path: '/projects', key: 'myTasks' as const },
  { path: '/', key: 'myCompany' as const },
];

const secondaryNavItems = [
  { path: '/leaderboard', key: 'leaderboard' as const },
  { path: '/events', key: 'events' as const },
  { path: '/training', key: 'training' as const, children: [
    { path: '/assessment', key: 'assessment' as const },
    { path: '/competency', key: 'competency' as const },
  ]},
  { path: '/music', key: 'music' as const },
];

/** Старый плоский список — для стажёров обучения */
const internNavItems = [
  { path: '/training', key: 'training' as const },
  { path: '/assessment', key: 'assessment' as const },
  { path: '/competency', key: 'competency' as const },
  { path: '/kpi', key: 'kpi' as const },
  { path: '/leaderboard', key: 'leaderboard' as const },
  { path: '/profile', key: 'profile' as const },
  { path: '/shop', key: 'shop' as const },
];

function NavButton({
  path,
  navKey,
  active,
  onNavigate,
  label,
  iconWrap,
}: {
  path: string;
  navKey: string;
  active: boolean;
  onNavigate: () => void;
  label: string;
  iconWrap?: ReactNode;
}) {
  const Icon = iconMap[navKey];
  return (
    <button
      type="button"
      className={`${styles.navItem} ${active ? styles.active : ''}`}
      onClick={onNavigate}
      aria-label={label}
      title={label}
    >
      {iconWrap ?? (
        <span className={styles.icon} aria-hidden="true">
          <Icon />
        </span>
      )}
      <span className={styles.label}>{label}</span>
    </button>
  );
}

export default function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const dispatch = useAppDispatch();
  const { user } = useAppSelector(s => s.auth);
  const { language, sidebarOpen, sidebarNarrow, mobileMenuOpen } = useAppSelector(s => s.ui);
  const lang = t(language);

  const [projectList, setProjectList] = useState<Project[]>([]);
  const [inlineProjectName, setInlineProjectName] = useState('');
  const [showInlineCreate, setShowInlineCreate] = useState(false);

  /* ── project context menu state ── */
  const [ctxProject, setCtxProject] = useState<Project | null>(null);
  const [ctxPos, setCtxPos] = useState<{ x: number; y: number } | null>(null);
  const [renamingProjectId, setRenamingProjectId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState('');
  const [confirmDeleteProject, setConfirmDeleteProject] = useState<Project | null>(null);
  const [archivedList, setArchivedList] = useState<Project[]>([]);
  const [showArchived, setShowArchived] = useState(false);
  const [trainingOpen, setTrainingOpen] = useState(false);
  const ctxMenuRef = useRef<HTMLDivElement>(null);

  const isTrainingIntern = user?.training_role === 'intern' && user?.role !== 'admin';

  const loadProjects = useCallback(async () => {
    if (!user || isTrainingIntern) return;
    try {
      const { data } = await api.get<Project[]>('/projects');
      setProjectList(data);
    } catch {
      setProjectList([]);
    }
  }, [user, isTrainingIntern]);

  const loadArchived = useCallback(async () => {
    if (!user || isTrainingIntern) return;
    try {
      const { data } = await api.get<Project[]>('/projects/archived/list');
      setArchivedList(data);
    } catch {
      setArchivedList([]);
    }
  }, [user, isTrainingIntern]);

  useEffect(() => {
    loadProjects();
    loadArchived();
  }, [loadProjects, loadArchived]);

  useEffect(() => {
    const onChanged = () => { loadProjects(); loadArchived(); };
    window.addEventListener(PROJECTS_LIST_CHANGED, onChanged);
    return () => window.removeEventListener(PROJECTS_LIST_CHANGED, onChanged);
  }, [loadProjects, loadArchived]);

  const closeMobile = () => {
    if (mobileMenuOpen) dispatch(toggleMobileMenu());
  };

  const createInlineProject = async () => {
    const name = inlineProjectName.trim();
    if (!name) {
      setShowInlineCreate(false);
      setInlineProjectName('');
      return;
    }
    try {
      const { data } = await api.post('/projects', { name, description: '' });
      setInlineProjectName('');
      setShowInlineCreate(false);
      await loadProjects();
      window.dispatchEvent(new Event(PROJECTS_LIST_CHANGED));
      navigate(`/project/${data.id}`);
    } catch {
      setShowInlineCreate(false);
      setInlineProjectName('');
    }
  };

  const go = (path: string) => {
    navigate(path);
    closeMobile();
  };

  /* ── project context menu handlers ── */
  const openProjectCtx = (e: React.MouseEvent, p: Project) => {
    e.stopPropagation();
    e.preventDefault();
    const btn = e.currentTarget as HTMLElement;
    const rect = btn.getBoundingClientRect();
    setCtxProject(p);
    setCtxPos({ x: rect.right + 4, y: rect.top });
  };

  const closeProjectCtx = () => {
    setCtxProject(null);
    setCtxPos(null);
  };

  const startRename = (p: Project) => {
    closeProjectCtx();
    setRenamingProjectId(p.id);
    setRenameDraft(p.name);
  };

  const commitRename = async (p: Project) => {
    const next = renameDraft.trim();
    setRenamingProjectId(null);
    if (!next || next === p.name) return;
    try {
      await api.put(`/projects/${p.id}`, { name: next });
      await loadProjects();
      window.dispatchEvent(new Event(PROJECTS_LIST_CHANGED));
    } catch { /* */ }
  };

  const deleteProject = async (p: Project) => {
    try {
      await api.delete(`/projects/${p.id}`);
      await loadProjects();
      await loadArchived();
      window.dispatchEvent(new Event(PROJECTS_LIST_CHANGED));
      if (projectIdFromPath === p.id) navigate('/projects');
    } catch { /* */ }
    setConfirmDeleteProject(null);
  };

  const archiveProject = async (p: Project) => {
    closeProjectCtx();
    try {
      await api.delete(`/projects/${p.id}`);
      await loadProjects();
      await loadArchived();
      window.dispatchEvent(new Event(PROJECTS_LIST_CHANGED));
      if (projectIdFromPath === p.id) navigate('/projects');
    } catch { /* */ }
  };

  const restoreProject = async (p: Project) => {
    try {
      await api.post(`/projects/${p.id}/restore`);
      await loadProjects();
      await loadArchived();
      window.dispatchEvent(new Event(PROJECTS_LIST_CHANGED));
    } catch { /* */ }
  };

  // close ctx menu on outside click
  useEffect(() => {
    if (!ctxProject) return;
    const onClick = (e: MouseEvent) => {
      if (ctxMenuRef.current && !ctxMenuRef.current.contains(e.target as Node)) closeProjectCtx();
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [ctxProject]);

  const projectIdFromPath =
    location.pathname.startsWith('/project/') ? location.pathname.split('/')[2] : null;

  if (!user) return null;

  if (isTrainingIntern) {
    return (
      <>
        {mobileMenuOpen && <div className={styles.overlay} onClick={() => dispatch(toggleMobileMenu())} />}
        <aside className={`${styles.sidebar} ${mobileMenuOpen ? styles.open : ''} ${!sidebarOpen ? styles.collapsed : ''}`}>
          <nav className={styles.nav}>
            {internNavItems.map(item => {
              const Icon = iconMap[item.key];
              return (
                <button
                  key={item.path + item.key}
                  className={`${styles.navItem} ${location.pathname === item.path ? styles.active : ''}`}
                  onClick={() => go(item.path)}
                  aria-label={(lang.nav as Record<string, string>)[item.key]}
                >
                  <span className={styles.icon} aria-hidden="true">
                    <Icon />
                  </span>
                  <span className={styles.label}>{(lang.nav as Record<string, string>)[item.key]}</span>
                </button>
              );
            })}
            {user.role === 'admin' && (
              <button
                type="button"
                className={`${styles.navItem} ${location.pathname === '/admin' ? styles.active : ''}`}
                onClick={() => go('/admin')}
              >
                <span className={styles.icon}>
                  <SettingsIcon />
                </span>
                <span className={styles.label}>{lang.nav.admin}</span>
              </button>
            )}
          </nav>
        </aside>
      </>
    );
  }

  const navLabel = (key: string) => (lang.nav as Record<string, string>)[key] ?? key;

  const isTopActive = (path: string, key: string) => {
    if (key === 'myTasks') return location.pathname === '/projects';
    if (key === 'myCompany') return location.pathname === '/';
    return location.pathname === path;
  };

  return (
    <>
      {mobileMenuOpen && <div className={styles.overlay} onClick={() => dispatch(toggleMobileMenu())} />}
      <aside
        className={`${styles.sidebar} ${mobileMenuOpen ? styles.open : ''} ${!sidebarOpen ? styles.collapsed : ''} ${sidebarNarrow ? styles.sidebarNarrow : ''}`}
      >
        <nav className={styles.nav}>
          {topNavItems.map(item => {
            if (item.key === 'myTasks') {
              return (
                <NavButton
                  key="myTasks"
                  path={item.path}
                  navKey="myTasks"
                  active={isTopActive(item.path, item.key)}
                  onNavigate={() => go('/projects')}
                  label={navLabel('myTasks')}
                  iconWrap={<MyTasksIcon />}
                />
              );
            }
            return (
              <NavButton
                key={item.key + item.path}
                path={item.path}
                navKey={item.key}
                active={isTopActive(item.path, item.key)}
                onNavigate={() => go(item.path)}
                label={navLabel(item.key)}
              />
            );
          })}

          <div className={styles.section}>
            <div className={styles.sectionHeader}>
              <span className={styles.sectionTitle}>{lang.sidebar.projectsHeading}</span>
              <button
                type="button"
                className={styles.sectionAdd}
                title={lang.sidebar.addProject}
                aria-label={lang.sidebar.addProject}
                onClick={() => {
                  setShowInlineCreate(true);
                  setInlineProjectName('');
                }}
              >
                <Plus size={16} strokeWidth={2.2} />
              </button>
            </div>
            <div className={styles.projectList}>
              {projectList.map(p => (
                renamingProjectId === p.id ? (
                  <div key={p.id} className={styles.inlineCreateWrap}>
                    <FolderInput className={styles.projectFolderIcon} size={18} strokeWidth={1.75} />
                    <input
                      className={styles.inlineCreateInput}
                      value={renameDraft}
                      onChange={e => setRenameDraft(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') commitRename(p);
                        if (e.key === 'Escape') setRenamingProjectId(null);
                      }}
                      onBlur={() => commitRename(p)}
                      autoFocus
                    />
                  </div>
                ) : (
                  <div
                    key={p.id}
                    className={`${styles.projectRow} ${projectIdFromPath === p.id ? styles.projectItemActive : ''}`}
                  >
                    <button
                      type="button"
                      title={p.name}
                      className={styles.projectItem}
                      onClick={() => go(`/project/${p.id}`)}
                    >
                      <FolderInput className={styles.projectFolderIcon} size={18} strokeWidth={1.75} />
                      <span className={styles.projectName}>{p.name}</span>
                    </button>
                    <button
                      type="button"
                      className={styles.projectCtxBtn}
                      onClick={e => openProjectCtx(e, p)}
                      aria-label="Menu"
                    >
                      <MoreHorizontal size={15} strokeWidth={2} />
                    </button>
                  </div>
                )
              ))}
              {showInlineCreate && (
                <div className={styles.inlineCreateWrap}>
                  <FolderInput className={styles.projectFolderIcon} size={18} strokeWidth={1.75} />
                  <input
                    className={styles.inlineCreateInput}
                    placeholder={lang.projects.name}
                    value={inlineProjectName}
                    onChange={e => setInlineProjectName(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter') createInlineProject();
                      if (e.key === 'Escape') { setShowInlineCreate(false); setInlineProjectName(''); }
                    }}
                    onBlur={() => createInlineProject()}
                    autoFocus
                  />
                </div>
              )}
            </div>

            {archivedList.length > 0 && (
              <div className={styles.archiveSection}>
                <button
                  type="button"
                  className={styles.archiveToggle}
                  onClick={() => setShowArchived(v => !v)}
                >
                  <Archive size={14} strokeWidth={1.75} />
                  <span>Архив ({archivedList.length})</span>
                </button>
                {showArchived && (
                  <div className={styles.archiveList}>
                    {archivedList.map(p => (
                      <div key={p.id} className={styles.archiveItem}>
                        <FolderInput className={styles.projectFolderIcon} size={16} strokeWidth={1.75} />
                        <span className={styles.archiveName}>{p.name}</span>
                        <button
                          type="button"
                          className={styles.archiveRestoreBtn}
                          onClick={() => restoreProject(p)}
                          title="Восстановить"
                        >
                          ↩
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className={styles.navDivider} />

          {secondaryNavItems.map(item => {
            // Section access filtering: admin sees all; non-admin needs section_access grant for assessment/competency
            const restrictedSections = ['assessment', 'competency'];
            const isAdmin = user.role === 'admin';
            if (!isAdmin && restrictedSections.includes(item.key) && !(user.section_access || []).includes(item.key)) return null;

            const Icon = iconMap[item.key];
            if (item.children) {
              const visibleChildren = item.children.filter(c =>
                isAdmin || !restrictedSections.includes(c.key) || (user.section_access || []).includes(c.key)
              );
              const isChildActive = visibleChildren.some(c => location.pathname === c.path);
              return (
                <div key={item.key} className={styles.navGroup}>
                  <button
                    type="button"
                    className={`${styles.navItem} ${(location.pathname === item.path || isChildActive) ? styles.active : ''}`}
                    onClick={() => go(item.path)}
                    aria-label={navLabel(item.key)}
                    title={navLabel(item.key)}
                  >
                    <span className={styles.icon} aria-hidden="true"><Icon /></span>
                    <span className={styles.label}>{navLabel(item.key)}</span>
                    {visibleChildren.length > 0 && (
                    <span
                      className={`${styles.chevron} ${trainingOpen ? styles.chevronOpen : ''}`}
                      onClick={e => { e.stopPropagation(); setTrainingOpen(v => !v); }}
                    >
                      <ChevronDown size={14} />
                    </span>
                    )}
                  </button>
                  {trainingOpen && visibleChildren.map(child => {
                    const CIcon = iconMap[child.key];
                    return (
                      <button
                        key={child.path}
                        type="button"
                        className={`${styles.navItem} ${styles.navSubItem} ${location.pathname === child.path ? styles.active : ''}`}
                        onClick={() => go(child.path)}
                        aria-label={navLabel(child.key)}
                        title={navLabel(child.key)}
                      >
                        <span className={styles.icon} aria-hidden="true"><CIcon /></span>
                        <span className={styles.label}>{navLabel(child.key)}</span>
                      </button>
                    );
                  })}
                </div>
              );
            }
            return (
              <button
                key={item.path}
                type="button"
                className={`${styles.navItem} ${location.pathname === item.path ? styles.active : ''}`}
                onClick={() => go(item.path)}
                aria-label={navLabel(item.key)}
                title={navLabel(item.key)}
              >
                <span className={styles.icon} aria-hidden="true"><Icon /></span>
                <span className={styles.label}>{navLabel(item.key)}</span>
              </button>
            );
          })}

          {user.role === 'admin' && (
            <button
              type="button"
              className={`${styles.navItem} ${location.pathname === '/admin' ? styles.active : ''}`}
              onClick={() => go('/admin')}
            >
              <span className={styles.icon}>
                <SettingsIcon />
              </span>
              <span className={styles.label}>{lang.nav.admin}</span>
            </button>
          )}
        </nav>

        <div className={styles.sidebarFooter}>
          <button
            type="button"
            className={styles.railToggle}
            onClick={() => dispatch(toggleSidebarNarrow())}
            title={sidebarNarrow ? lang.sidebar.railExpand : lang.sidebar.railCollapse}
            aria-label={sidebarNarrow ? lang.sidebar.railExpand : lang.sidebar.railCollapse}
          >
            <ChevronsLeftRight size={18} strokeWidth={1.75} aria-hidden />
            <span className={styles.railToggleLabel}>
              {sidebarNarrow ? lang.sidebar.railExpand : lang.sidebar.railCollapse}
            </span>
          </button>
          <span className={styles.workspaceBadge}>{lang.sidebar.workspace}</span>
        </div>
      </aside>

      {/* project context menu portal */}
      {ctxProject && ctxPos && createPortal(
        <div
          ref={ctxMenuRef}
          className={styles.projectCtxMenu}
          style={{ top: ctxPos.y, left: ctxPos.x }}
        >
          <button type="button" className={styles.projectCtxMenuItem} onClick={() => startRename(ctxProject)}>
            <Pencil size={14} /> Переименовать
          </button>
          <button type="button" className={styles.projectCtxMenuItem} onClick={() => archiveProject(ctxProject)}>
            <Archive size={14} /> Архивировать
          </button>
          <button
            type="button"
            className={`${styles.projectCtxMenuItem} ${styles.projectCtxMenuDanger}`}
            onClick={() => { closeProjectCtx(); setConfirmDeleteProject(ctxProject); }}
          >
            <Trash2 size={14} /> Удалить
          </button>
        </div>,
        document.body
      )}

      {/* delete confirm modal */}
      {confirmDeleteProject && (
        <ConfirmModal
          title="Удалить проект"
          message={`Вы уверены что хотите удалить проект «${confirmDeleteProject.name}»?`}
          confirmLabel="Удалить"
          cancelLabel="Отмена"
          variant="danger"
          onConfirm={() => deleteProject(confirmDeleteProject)}
          onCancel={() => setConfirmDeleteProject(null)}
        />
      )}
    </>
  );
}
