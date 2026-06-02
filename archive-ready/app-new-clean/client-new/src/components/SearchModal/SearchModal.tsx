import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { FolderOpen, ListChecks, UserRound, CalendarDays } from 'lucide-react';
import { useAppSelector } from '../../store/hooks';
import { t } from '../../i18n';
import api from '../../api/client';
import styles from './SearchModal.module.css';

interface SearchResult {
  type: 'project' | 'task' | 'user' | 'event';
  id: string;
  title: string;
  subtitle?: string;
  link: string;
}

const SearchIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
);

export default function SearchModal({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [activeIdx, setActiveIdx] = useState(0);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const search = useCallback(async (q: string) => {
    if (!q.trim()) { setResults([]); return; }
    const items: SearchResult[] = [];
    try {
      const [projects, users, events] = await Promise.allSettled([
        api.get('/projects'),
        api.get('/users'),
        api.get('/events'),
      ]);
      const qLow = q.toLowerCase();
      if (projects.status === 'fulfilled') {
        projects.value.data
          .filter((p: any) => p.name?.toLowerCase().includes(qLow) || p.description?.toLowerCase().includes(qLow))
          .slice(0, 5)
          .forEach((p: any) => items.push({ type: 'project', id: p.id, title: p.name, link: `/project/${p.id}` }));
      }
      if (users.status === 'fulfilled') {
        users.value.data
          .filter((u: any) => u.name?.toLowerCase().includes(qLow) || u.email?.toLowerCase().includes(qLow))
          .slice(0, 5)
          .forEach((u: any) => items.push({ type: 'user', id: u.id, title: u.name, subtitle: u.email, link: '/profile' }));
      }
      if (events.status === 'fulfilled') {
        events.value.data
          .filter((e: any) => e.title?.toLowerCase().includes(qLow))
          .slice(0, 5)
          .forEach((e: any) => items.push({ type: 'event', id: e.id, title: e.title, subtitle: e.location, link: '/events' }));
      }
    } catch { /* ignore */ }
    setResults(items);
    setActiveIdx(0);
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => search(query), 300);
    return () => clearTimeout(timer);
  }, [query, search]);

  const go = (r: SearchResult) => {
    navigate(r.link);
    onClose();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { onClose(); return; }
    if (results.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx(i => Math.min(i + 1, results.length - 1));
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx(i => Math.max(i - 1, 0));
    }
    if (e.key === 'Enter' && results[activeIdx]) { go(results[activeIdx]); }
  };

  const iconMap: Record<SearchResult['type'], JSX.Element> = {
    project: <FolderOpen size={16} />,
    task: <ListChecks size={16} />,
    user: <UserRound size={16} />,
    event: <CalendarDays size={16} />,
  };
  const labelMap: Record<string, string> = { project: lang.nav.projects, user: lang.admin?.users || 'Users', event: lang.events?.title || 'Events' };

  const grouped = results.reduce<Record<string, SearchResult[]>>((acc, r) => {
    (acc[r.type] ||= []).push(r);
    return acc;
  }, {});

  let flatIdx = 0;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={e => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="Search">
        <div className={styles.inputWrap}>
          <div className={styles.searchIcon}><SearchIcon /></div>
          <input
            ref={inputRef}
            className={styles.input}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={lang.common?.search || 'Поиск...'}
            autoComplete="off"
          />
          <span className={styles.hint}>ESC</span>
        </div>
        <div className={styles.results}>
          {query && results.length === 0 && (
            <div className={styles.empty}>{lang.common.noData}</div>
          )}
          {Object.entries(grouped).map(([type, items]) => (
            <div key={type} className={styles.group}>
              <div className={styles.groupLabel}>{labelMap[type] || type}</div>
              {items.map(r => {
                const idx = flatIdx++;
                return (
                  <div
                    key={r.id}
                    className={`${styles.item} ${idx === activeIdx ? styles.itemActive : ''}`}
                    onClick={() => go(r)}
                    onMouseEnter={() => setActiveIdx(idx)}
                  >
                    <span className={styles.itemIcon}>{iconMap[r.type]}</span>
                    <span className={styles.itemTitle}>{r.title}</span>
                    {r.subtitle && <span className={styles.itemSub}>{r.subtitle}</span>}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
