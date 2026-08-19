import type { Retrospective } from '../../types';
import { FileText, Pencil, Check, AlertTriangle, ArrowRight } from 'lucide-react';
import styles from './ProjectDetail.module.css';

interface Props {
  retro: Retrospective | null;
  retroSubmitted: boolean;
  retroForm: { went_well: string; to_improve: string; to_try: string };
  editingRetro: boolean;
  iterationStatus: string;
  lang: any;
  onRetroFormChange: (form: { went_well: string; to_improve: string; to_try: string }) => void;
  onSubmit: (e: React.FormEvent) => void;
  onUpdate: (e: React.FormEvent) => void;
  onEditToggle: (val: boolean) => void;
  onExportPdf: () => void;
}

export default function RetrospectivePanel({ retro, retroSubmitted, retroForm, editingRetro, iterationStatus, lang, onRetroFormChange, onSubmit, onUpdate, onEditToggle, onExportPdf }: Props) {
  if (!retro) {
    return <div className={styles.chatLoading}>{iterationStatus === 'active' ? lang.projectDetail.retroNotAvailable : lang.projectDetail.retroNotFound}</div>;
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'center' }}>
        <h3>{lang.retro.title}</h3>
        <button className="btn btn-secondary btn-sm" onClick={onExportPdf}>
          <FileText size={16} style={{ marginRight: 6 }} /> PDF
        </button>
      </div>

      {!retroSubmitted && (
        <form onSubmit={onSubmit} className={`card ${styles.form}`} style={{ marginBottom: 24 }}>
          <label>{lang.retro.wentWell}</label>
          <textarea rows={3} value={retroForm.went_well} onChange={e => onRetroFormChange({ ...retroForm, went_well: e.target.value })} required />
          <label>{lang.retro.toImprove}</label>
          <textarea rows={3} value={retroForm.to_improve} onChange={e => onRetroFormChange({ ...retroForm, to_improve: e.target.value })} required />
          <label>{lang.retro.toTry}</label>
          <textarea rows={3} value={retroForm.to_try} onChange={e => onRetroFormChange({ ...retroForm, to_try: e.target.value })} required />
          <button type="submit" className="btn btn-primary">{lang.retro.submit}</button>
        </form>
      )}

      {retroSubmitted && !editingRetro && (
        <div className="card" style={{ marginBottom: 24, padding: 16 }}>
          <p style={{ color: 'var(--color-text-muted)', marginBottom: 8 }}>{lang.retro.submitted}</p>
          <button className="btn btn-secondary btn-sm" onClick={() => onEditToggle(true)}>
            <Pencil size={16} style={{ marginRight: 6 }} />
            {lang.retro.edit}
          </button>
        </div>
      )}

      {editingRetro && (
        <form onSubmit={onUpdate} className={`card ${styles.form}`} style={{ marginBottom: 24 }}>
          <label>{lang.retro.wentWell}</label>
          <textarea rows={3} value={retroForm.went_well} onChange={e => onRetroFormChange({ ...retroForm, went_well: e.target.value })} required />
          <label>{lang.retro.toImprove}</label>
          <textarea rows={3} value={retroForm.to_improve} onChange={e => onRetroFormChange({ ...retroForm, to_improve: e.target.value })} required />
          <label>{lang.retro.toTry}</label>
          <textarea rows={3} value={retroForm.to_try} onChange={e => onRetroFormChange({ ...retroForm, to_try: e.target.value })} required />
          <div className={styles.formActions}>
            <button type="button" className="btn btn-secondary" onClick={() => onEditToggle(false)}>{lang.common.cancel}</button>
            <button type="submit" className="btn btn-primary">{lang.common.save}</button>
          </div>
        </form>
      )}

      {retro.answers?.map(a => (
        <div key={a.id} className={`card ${styles.backlogItem}`}>
          <strong>{a.user_name}</strong>
          <small style={{ marginLeft: 8 }}>{new Date(a.created_at).toLocaleDateString()}</small>
          <div style={{ marginTop: 8 }}>
            <p style={{ display: 'flex', alignItems: 'center', gap: 6 }}><Check size={16} color="var(--color-success)" /> {a.went_well}</p>
            <p style={{ display: 'flex', alignItems: 'center', gap: 6 }}><AlertTriangle size={16} color="var(--color-warning)" /> {a.to_improve}</p>
            <p style={{ display: 'flex', alignItems: 'center', gap: 6 }}><ArrowRight size={16} color="var(--color-primary)" /> {a.to_try}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
