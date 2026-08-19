import { useMemo, useState } from 'react';
import { ExternalLink, Maximize2, PhoneCall, RefreshCcw, ShieldCheck } from 'lucide-react';
import { useAppSelector } from '../../store/hooks';
import styles from './Call.module.css';

export default function CallPage() {
  const { user } = useAppSelector(state => state.auth);
  const [frameKey, setFrameKey] = useState(0);
  const callUrl = useMemo(() => {
    const base = import.meta.env.VITE_AGILE_CALL_URL || 'https://agile-coll.vercel.app/';
    const url = new URL(base, window.location.origin);
    url.searchParams.set('embed', '1');
    if (user?.name) url.searchParams.set('displayName', user.name);
    return url.toString();
  }, [user?.name]);

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.titleBlock}>
          <span className={styles.icon}><PhoneCall size={22} /></span>
          <div>
            <h1>Agile Call</h1>
            <p>Созвоны, демонстрация экрана и рабочие комнаты внутри единого центра.</p>
          </div>
        </div>
        <div className={styles.actions}>
          <span className={styles.secure}><ShieldCheck size={14} /> Защищённая комната</span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setFrameKey(value => value + 1)}>
            <RefreshCcw size={14} /> Перезапустить
          </button>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => window.open(callUrl, '_blank', 'noopener,noreferrer')}>
            <ExternalLink size={14} /> Отдельное окно
          </button>
        </div>
      </header>
      <div className={styles.frameShell}>
        <div className={styles.frameTopline}>
          <span><Maximize2 size={13} /> Agile Call подключён как модуль платформы</span>
        </div>
        <iframe
          key={frameKey}
          className={styles.frame}
          src={callUrl}
          title="Agile Call"
          allow="camera; microphone; display-capture; fullscreen; clipboard-read; clipboard-write"
          referrerPolicy="strict-origin-when-cross-origin"
        />
      </div>
    </div>
  );
}
