import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { FolderKanban, ArrowRight } from 'lucide-react';
import { useAppSelector } from '../../store/hooks';
import { t } from '../../i18n';
import api from '../../api/client';
import type { Project } from '../../types';
import { PROJECTS_LIST_CHANGED } from '../../components/Sidebar/Sidebar';
import styles from './Projects.module.css';

export default function ProjectsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAppSelector(s => s.auth);
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);

  const [projects, setProjects] = useState<Project[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: '', description: '' });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadProjects();
  }, []);

  useEffect(() => {
    const onRt = (e: Event) => {
      const d = (e as CustomEvent<unknown>).detail as { type?: string; resource?: string } | null;
      if (!d || d.type !== 'resource_changed' || d.resource !== 'project') return;
      loadProjects();
      window.dispatchEvent(new Event(PROJECTS_LIST_CHANGED));
    };
    window.addEventListener('agile-realtime', onRt);
    return () => window.removeEventListener('agile-realtime', onRt);
  }, []);

  useEffect(() => {
    const st = location.state as { openCreate?: boolean } | null;
    if (st?.openCreate) {
      setShowCreate(true);
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.state, location.pathname, navigate]);

  const loadProjects = async () => {
    try {
      const { data } = await api.get<Project[]>('/projects');
      setProjects(data);
    } catch {
      setProjects([]);
    }
    setLoading(false);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/projects', form);
      setForm({ name: '', description: '' });
      setShowCreate(false);
      await loadProjects();
      window.dispatchEvent(new Event(PROJECTS_LIST_CHANGED));
    } catch {
      /* ошибка показывается через api client (toast) */
    }
  };

  if (!user) return null;

  return (
    <div className={styles.page}>
      <div className={styles.hero}>
        <div className={styles.heroPattern} aria-hidden />
        <div className={styles.heroInner}>
          <h1 className={styles.heroTitle}>{lang.projects.hubTitle}</h1>
          <p className={styles.heroSubtitle}>{lang.projects.hubSubtitle}</p>
          <div className={styles.heroActions}>
            <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
              + {lang.projects.create}
            </button>
          </div>
        </div>
      </div>

      {loading ? (
        <p>{lang.common.loading}</p>
      ) : projects.length === 0 ? (
        <p className={styles.empty}>{lang.projects.noProjects}</p>
      ) : (
        <section className={styles.quickSection} aria-labelledby="quick-access-heading">
          <h2 id="quick-access-heading" className={styles.quickTitle}>
            {lang.projects.quickAccess}
          </h2>
          <div className={styles.quickRow}>
            {projects.map(p => (
              <button
                key={p.id}
                type="button"
                className={styles.quickCard}
                onClick={() => navigate(`/project/${p.id}`)}
              >
                <div className={styles.quickCardIcon}>
                  <FolderKanban size={22} strokeWidth={1.75} />
                </div>
                <div className={styles.quickCardBody}>
                  <div className={styles.quickCardName}>{p.name}</div>
                  <div className={styles.quickCardMeta}>
                    {lang.projects.openProject}
                    <ArrowRight size={12} style={{ display: 'inline', verticalAlign: 'middle', marginLeft: 4 }} />
                  </div>
                </div>
              </button>
            ))}
          </div>
        </section>
      )}

      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>{lang.projects.create}</h2>
            <form onSubmit={handleCreate} className={styles.form}>
              <input
                placeholder={lang.projects.name}
                value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })}
                required
              />
              <textarea
                placeholder={lang.projects.description}
                value={form.description}
                onChange={e => setForm({ ...form, description: e.target.value })}
                rows={3}
              />
              <div className={styles.formActions}>
                <button type="button" className="btn btn-secondary" onClick={() => setShowCreate(false)}>
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
    </div>
  );
}
