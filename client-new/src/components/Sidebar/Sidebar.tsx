import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate, useLocation } from 'react-router-dom';
import { Plus, FolderInput, ListTodo, ChevronsLeftRight, MoreHorizontal, Pencil, Trash2, Archive, ChevronDown, FileText, Video, RotateCcw, X } from 'lucide-react';
import { useAppSelector, useAppDispatch } from '../../store/hooks';
import { toggleMobileMenu, toggleSidebarNarrow } from '../../store/slices/uiSlice';
import { t } from '../../i18n';
import api from '../../api/client';
import ConfirmModal from '../ConfirmModal/ConfirmModal';
import type { Project } from '../../types';
import { canAccessSection } from '../../utils/access';
import styles from './Sidebar.module.css';

export const PROJECTS_LIST_CHANGED = 'agile-projects-list-changed';

const navigationLabels = {
  ru: { close: 'Закрыть навигацию', title: 'Навигация' },
  ka: { close: 'ნავიგაციის დახურვა', title: 'ნავიგაცია' },
  en: { close: 'Close navigation', title: 'Navigation' },
} as const;

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
const KPIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/></svg>
);
const LeaderboardIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M8 21h8"/><path d="M12 17v4"/><path d="M7 4h10l-1 6a4 4 0 0 1-4 3 4 4 0 0 1-4-3z"/></svg>
);
const BuildingIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M3 21h18"/><path d="M5 21V7l8-4v18"/><path d="M19 21V11l-6-4"/><line x1="9" y1="9" x2="9" y2="9.01"/><line x1="9" y1="12" x2="9" y2="12.01"/><line x1="9" y1="15" x2="9" y2="15.01"/><line x1="9" y1="18" x2="9" y2="18.01"/></svg>
);
const ApplicationsIcon = () => (
  <span className={styles.icon} aria-hidden><FileText size={18} strokeWidth={1.75} /></span>
);

const MyTasksIcon = () => (
  <span className={styles.icon} aria-hidden><ListTodo size={18} strokeWidth={1.8} /></span>
);

const iconMap: Record<string, () => JSX.Element> = {
  home: HomeIcon,
  events: CalendarIcon,
  places: MapPinIcon,
  analytics: BarChartIcon,
  kpi: KPIcon,
  leaderboard: LeaderboardIcon,
  applications: ApplicationsIcon,
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
      aria-current={active ? 'page' : undefined}
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
  const mobileLabels = navigationLabels[language];
  const drawerCloseRef = useRef<HTMLButtonElement>(null);
  const sidebarRef = useRef<HTMLElement>(null);
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== 'undefined' && window.matchMedia('(max-width: 768px)').matches
  );
  const sidebarHidden = isMobile ? !mobileMenuOpen : !sidebarOpen;

  const [projectList, setProjectList] = useState<Project[]>([]);
  const [inlineProjectName, setInlineProjectName] = useState('');
  const [showInlineCreate, setShowInlineCreate] = useState(false);

  const [conferenceActive, setConferenceActive] = useState(false);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(max-width: 768px)');
    const updateViewport = (event: MediaQueryListEvent) => setIsMobile(event.matches);
    setIsMobile(mediaQuery.matches);
    mediaQuery.addEventListener('change', updateViewport);
    return () => mediaQuery.removeEventListener('change', updateViewport);
  }, []);

  useEffect(() => {
    if (!isMobile || !mobileMenuOpen) return;

    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const handleDrawerKeyboard = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        dispatch(toggleMobileMenu());
        return;
      }

      if (event.key !== 'Tab' || !sidebarRef.current) return;
      const focusable = Array.from(sidebarRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), a[href]'
      )).filter(element => element.offsetParent !== null);
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    window.addEventListener('keydown', handleDrawerKeyboard);
    window.requestAnimationFrame(() => drawerCloseRef.current?.focus());

    return () => {
      window.removeEventListener('keydown', handleDrawerKeyboard);
      document.body.style.overflow = previousOverflow;
      previouslyFocused?.focus();
    };
  }, [dispatch, isMobile, mobileMenuOpen]);

  useEffect(() => {
    const sidebar = sidebarRef.current;
    if (!sidebar) return;
    if (sidebarHidden) sidebar.setAttribute('inert', '');
    else sidebar.removeAttribute('inert');
  }, [sidebarHidden, user]);

  const fetchConferenceStatus = useCallback(async () => {
    if (!user) return;
    try {
      const { data } = await api.get('/conference');
      setConferenceActive(data.active);
    } catch (e) {
      console.error('Failed to fetch conference status:', e);
    }
  }, [user]);

  useEffect(() => {
    if (!user) return;
    fetchConferenceStatus();
    const interval = setInterval(fetchConferenceStatus, 10000);
    return () => clearInterval(interval);
  }, [user, fetchConferenceStatus]);

  const handleCreateConference = async () => {
    try {
      await api.post('/conference');
      setConferenceActive(true);
      go('/call');
    } catch (e) {
      console.error('Failed to create conference:', e);
    }
  };

  const handleStopConference = async () => {
    try {
      await api.delete('/conference');
      setConferenceActive(false);
    } catch (e) {
      console.error('Failed to stop conference:', e);
    }
  };

  const handleJoinConference = () => {
    go('/call');
  };

  /* ── project context menu state ── */
  const [ctxProject, setCtxProject] = useState<Project | null>(null);
  const [ctxPos, setCtxPos] = useState<{ x: number; y: number } | null>(null);
  const [renamingProjectId, setRenamingProjectId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState('');
  const [confirmDeleteProject, setConfirmDeleteProject] = useState<Project | null>(null);
  const [archivedList, setArchivedList] = useState<Project[]>([]);
  const [showArchived, setShowArchived] = useState(false);
  const ctxMenuRef = useRef<HTMLDivElement>(null);

  const loadProjects = useCallback(async () => {
    if (!user) return;
    try {
      const { data } = await api.get<Project[]>('/projects');
      setProjectList(data);
    } catch {
      setProjectList([]);
    }
  }, [user]);

  const loadArchived = useCallback(async () => {
    if (!user) return;
    try {
      const { data } = await api.get<Project[]>('/projects/archived/list');
      setArchivedList(data);
    } catch {
      setArchivedList([]);
    }
  }, [user]);

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
    const menuWidth = 188;
    const menuHeight = 132;
    const preferredX = rect.right + 4;
    const preferredY = rect.top;
    setCtxProject(p);
    setCtxPos({
      x: Math.max(8, Math.min(preferredX, window.innerWidth - menuWidth - 8)),
      y: Math.max(8, Math.min(preferredY, window.innerHeight - menuHeight - 8)),
    });
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
      await api.post(`/projects/${p.id}/archive`);
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

  const navLabel = (key: string) => (lang.nav as Record<string, string>)[key] ?? key;
  const isLeadership = ['admin', 'owner', 'deputy_owner'].includes(user.role);
  const isConsultant = user.role === 'consultant';

  const isTopActive = (path: string, key: string) => {
    if (key === 'myTasks') return location.pathname === '/projects';
    if (key === 'myCompany') return location.pathname === '/';
    return location.pathname === path;
  };

  return (
    <>
      {mobileMenuOpen && (
        <div className={styles.overlay} onClick={() => dispatch(toggleMobileMenu())} aria-hidden="true" />
      )}
      <aside
        ref={sidebarRef}
        id="primary-navigation"
        className={`${styles.sidebar} ${mobileMenuOpen ? styles.open : ''} ${!sidebarOpen ? styles.collapsed : ''} ${sidebarNarrow ? styles.sidebarNarrow : ''}`}
        aria-label={mobileLabels.title}
        aria-hidden={sidebarHidden ? true : undefined}
      >
        <div className={styles.mobileDrawerHeader}>
          <strong>{mobileLabels.title}</strong>
          <button
            ref={drawerCloseRef}
            type="button"
            className={styles.mobileDrawerClose}
            onClick={() => dispatch(toggleMobileMenu())}
            aria-label={mobileLabels.close}
          >
            <X size={20} strokeWidth={2} aria-hidden />
          </button>
        </div>

        <nav className={styles.nav} aria-label={mobileLabels.title}>
          {topNavItems.filter(item => {
            if (item.key === 'myCompany') return isLeadership && canAccessSection(user, 'company');
            if (item.key === 'myTasks') return !isConsultant && canAccessSection(user, 'projects');
            return true;
          }).map(item => {
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
            if (item.key === 'myCompany') {
              const isOwner = user.role === 'owner';
              return (
                <NavButton
                  key="myCompany"
                  path={item.path}
                  navKey={isOwner ? 'myCompany' : 'home'}
                  active={isTopActive(item.path, item.key)}
                  onNavigate={() => go('/')}
                  label={isOwner ? navLabel('myCompany') : navLabel('home')}
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

          {!isConsultant && canAccessSection(user, 'kpi') && (
            <NavButton
              path="/kpi"
              navKey="kpi"
              active={location.pathname === '/kpi'}
              onNavigate={() => go('/kpi')}
              label="Мои KPI"
            />
          )}

          {canAccessSection(user, 'applications') && (
            <button
              type="button"
              className={`${styles.navItem} ${location.pathname.startsWith('/applications') ? styles.active : ''}`}
              onClick={() => go('/applications')}
              aria-label={lang.nav.applications}
              aria-current={location.pathname.startsWith('/applications') ? 'page' : undefined}
              title={lang.nav.applications}
              style={{ marginBottom: '8px' }}
            >
              <ApplicationsIcon />
              <span className={styles.label}>{lang.nav.applications}</span>
            </button>
          )}

          {isLeadership && canAccessSection(user, 'projects') && <div className={styles.section}>
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
                      aria-label={`Новое название проекта «${p.name}»`}
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
                      aria-current={projectIdFromPath === p.id ? 'page' : undefined}
                    >
                      <FolderInput className={styles.projectFolderIcon} size={18} strokeWidth={1.75} />
                      <span className={styles.projectName}>{p.name}</span>
                    </button>
                    <button
                      type="button"
                      className={styles.projectCtxBtn}
                      onClick={e => openProjectCtx(e, p)}
                      aria-label={`Действия проекта «${p.name}»`}
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
                    aria-label={lang.projects.name}
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
                  aria-expanded={showArchived}
                  aria-controls="archived-projects-list"
                >
                  <Archive size={14} strokeWidth={1.75} />
                  <span>Архив ({archivedList.length})</span>
                </button>
                {showArchived && (
                  <div id="archived-projects-list" className={styles.archiveList}>
                    {archivedList.map(p => (
                      <div key={p.id} className={styles.archiveItem}>
                        <FolderInput className={styles.projectFolderIcon} size={16} strokeWidth={1.75} />
                        <span className={styles.archiveName}>{p.name}</span>
                        <button
                          type="button"
                          className={styles.archiveRestoreBtn}
                          onClick={() => restoreProject(p)}
                          title="Восстановить"
                          aria-label={`Восстановить проект «${p.name}»`}
                        >
                          <RotateCcw size={15} strokeWidth={1.9} aria-hidden />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>}

          {secondaryNavItems.some(item => canAccessSection(user, item.key)) && <div className={styles.navDivider} />}

          {secondaryNavItems.map(item => {
            if (!canAccessSection(user, item.key)) return null;

            const Icon = iconMap[item.key];
            return (
              <button
                key={item.path}
                type="button"
                className={`${styles.navItem} ${location.pathname === item.path ? styles.active : ''}`}
                onClick={() => go(item.path)}
                aria-label={navLabel(item.key)}
                aria-current={location.pathname === item.path ? 'page' : undefined}
                title={navLabel(item.key)}
              >
                <span className={styles.icon} aria-hidden="true"><Icon /></span>
                <span className={styles.label}>{navLabel(item.key)}</span>
              </button>
            );
          })}

          {/* Блок Видеоконференции */}
          {canAccessSection(user, 'call') && (conferenceActive ? (
            <>
              <button
                type="button"
                className={`${styles.navItem} ${location.pathname === '/call' ? styles.active : ''}`}
                onClick={handleJoinConference}
                aria-current={location.pathname === '/call' ? 'page' : undefined}
                title="Присоединиться к конференции"
              >
                <span className={styles.icon} style={{ color: '#10b981' }}>
                  <Video style={{ animation: 'pulse 2s infinite' }} />
                </span>
                <span className={styles.label} style={{ color: '#10b981', fontWeight: 'bold' }}>Войти в звонок</span>
              </button>
              {['admin', 'owner', 'deputy_owner'].includes(user.role) && (
                <button
                  type="button"
                  className={styles.navItem}
                  onClick={handleStopConference}
                  title="Завершить конференцию"
                  style={{ color: '#ef4444' }}
                >
                  <span className={styles.icon} style={{ color: '#ef4444' }}>
                    <Video />
                  </span>
                  <span className={styles.label}>Завершить звонок</span>
                </button>
              )}
            </>
          ) : (
            isLeadership ? (
              <button
                type="button"
                className={styles.navItem}
                onClick={handleCreateConference}
                title="Создать видеоконференцию"
              >
                <span className={styles.icon}>
                  <Video />
                </span>
                <span className={styles.label}>Создать конференцию</span>
              </button>
            ) : (
              <button
                type="button"
                className={styles.navItem}
                onClick={() => go('/call')}
                title="Расписание конференций"
              >
                <span className={styles.icon}><Video /></span>
                <span className={styles.label}>Конференции</span>
              </button>
            )
          ))}

          {isLeadership && canAccessSection(user, 'admin') && (
            <>
              <div className={styles.navDivider} />
              <button
                type="button"
                className={`${styles.navItem} ${location.pathname === '/admin' ? styles.active : ''}`}
                onClick={() => go('/admin')}
                aria-current={location.pathname === '/admin' ? 'page' : undefined}
              >
                <span className={styles.icon}>
                  <SettingsIcon />
                </span>
                <span className={styles.label}>{lang.nav.admin}</span>
              </button>
            </>
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
        </div>
      </aside>

      {/* project context menu portal */}
      {ctxProject && ctxPos && createPortal(
        <div
          ref={ctxMenuRef}
          className={styles.projectCtxMenu}
          style={{ top: ctxPos.y, left: ctxPos.x }}
          role="menu"
          aria-label={`Действия проекта «${ctxProject.name}»`}
        >
          <button type="button" className={styles.projectCtxMenuItem} role="menuitem" onClick={() => startRename(ctxProject)}>
            <Pencil size={14} /> Переименовать
          </button>
          <button type="button" className={styles.projectCtxMenuItem} role="menuitem" onClick={() => archiveProject(ctxProject)}>
            <Archive size={14} /> Архивировать
          </button>
          <button
            type="button"
            className={`${styles.projectCtxMenuItem} ${styles.projectCtxMenuDanger}`}
            role="menuitem"
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
          message={`Удалить проект «${confirmDeleteProject.name}» безвозвратно? Все задачи, итерации и чаты по проекту будут стёрты. Чтобы только скрыть проект, используйте «Архивировать».`}
          confirmLabel="Удалить навсегда"
          cancelLabel="Отмена"
          variant="danger"
          onConfirm={() => deleteProject(confirmDeleteProject)}
          onCancel={() => setConfirmDeleteProject(null)}
        />
      )}
    </>
  );
}
