import type { Document } from '../../types';
import { FileText, Eye, ClipboardList, Download, Trash2 } from 'lucide-react';
import styles from './ProjectDetail.module.css';

interface Props {
  documents: Document[];
  lang: any;
  docUploading: boolean;
  onUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onLoadVersions: (docId: string) => void;
  onDelete: (docId: string) => void;
  onPreview: (url: string) => void;
}

const isPreviewable = (fn: string) => {
  const ext = fn.toLowerCase().split('.').pop();
  return ['jpg','jpeg','png','gif','webp','svg','pdf'].includes(ext || '');
};

export default function DocumentsPanel({ documents, lang, docUploading, onUpload, onLoadVersions, onDelete, onPreview }: Props) {
  return (
    <div>
      <div className={styles.docsHeader}>
        <label className={`btn btn-primary btn-sm ${docUploading ? styles.uploading : ''}`}>
          {docUploading ? <><span className={styles.spinner} /> {lang.common.loading}</> : lang.projectDetail.uploadDocument}
          <input type="file" hidden onChange={onUpload} disabled={docUploading} />
        </label>
      </div>
      {documents.length === 0 ? (
        <div className="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" style={{ width: 64, height: 64 }}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          <h4>{lang.common.noData}</h4>
        </div>
      ) : documents.map(doc => (
        <div key={doc.id} className={`card ${styles.backlogItem}`}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <h4 style={{ display: 'flex', alignItems: 'center', gap: 8 }}><FileText size={18} /> {doc.filename}</h4>
              {doc.description && <p>{doc.description}</p>}
              <small>v{doc.current_version} | {doc.file_size ? `${(doc.file_size / 1024).toFixed(0)} KB | ` : ''}{new Date(doc.created_at).toLocaleDateString()}</small>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              {isPreviewable(doc.filename) && doc.file_url && (
                <button className="btn btn-ghost btn-sm" onClick={() => onPreview(doc.file_url!)} aria-label={lang.projectDetail.documents}>
                  <Eye size={16} />
                </button>
              )}
              <button className="btn btn-ghost btn-sm" onClick={() => onLoadVersions(doc.id)} aria-label="Versions">
                <ClipboardList size={16} /> v{doc.current_version}
              </button>
              {doc.file_url && (
                <a href={doc.file_url} download={doc.filename} className="btn btn-secondary btn-sm">
                  <Download size={16} style={{ marginRight: 6 }} />
                  {lang.projectDetail.downloadBtn}
                </a>
              )}
              <button className="btn btn-ghost btn-sm" onClick={() => onDelete(doc.id)} title={lang.common.delete} aria-label={lang.common.delete}>
                <Trash2 size={16} />
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
