import type { BacklogItem, Iteration } from '../../types';
import { Trash2 } from 'lucide-react';
import styles from './ProjectDetail.module.css';

interface Props {
  backlog: BacklogItem[];
  selectedIteration: Iteration | null;
  lang: any;
  onShowForm: () => void;
  onConvert: (itemId: string) => void;
  onDelete: (itemId: string) => void;
}

export default function BacklogList({ backlog, selectedIteration, lang, onShowForm, onConvert, onDelete }: Props) {
  return (
    <div>
      <button className="btn btn-primary btn-sm" onClick={onShowForm} style={{ marginBottom: 16 }}>+ {lang.projects.backlog}</button>
      {backlog.length === 0 ? (
        <div className="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" style={{ width: 64, height: 64 }}><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="12" y2="17"/></svg>
          <h4>{lang.common.noData}</h4>
        </div>
      ) : backlog.map(item => (
        <div key={item.id} className={`card ${styles.backlogItem}`}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div><h4>{item.title}</h4>{item.description && <p>{item.description}</p>}<small>{item.creator_name} | {new Date(item.created_at).toLocaleDateString()}</small></div>
            <div style={{ display: 'flex', gap: 6 }}>
              {selectedIteration?.status === 'active' && <button className="btn btn-primary btn-sm" onClick={() => onConvert(item.id)}>{lang.projectDetail.toTask}</button>}
              <button className="btn btn-ghost btn-sm" onClick={() => onDelete(item.id)} title={lang.common.delete} aria-label={lang.common.delete}>
                <Trash2 size={16} />
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
