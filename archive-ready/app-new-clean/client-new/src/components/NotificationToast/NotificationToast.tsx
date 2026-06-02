import { useState, useEffect, useRef, useCallback } from 'react';
import { useAppSelector } from '../../store/hooks';
import api from '../../api/client';
import styles from './NotificationToast.module.css';

interface Toast {
  id: string;
  title: string;
  message: string;
  type?: string;
}

const POLL_INTERVAL = 15000;
const WS_BASE = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`;

export default function NotificationToast() {
  const { user } = useAppSelector(s => s.auth);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const lastCountRef = useRef<number | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const addToast = useCallback((title: string, message: string, type?: string) => {
    setToasts(prev => [...prev, { id: Date.now().toString(), title, message, type }]);
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  // WebSocket connection for real-time push
  useEffect(() => {
    if (!user) return;

    let retryDelay = 1000;
    const MAX_RETRY_DELAY = 60000;
    let retryTimeout: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      const ws = new WebSocket(`${WS_BASE}/ws/status`);
      wsRef.current = ws;
      // Store globally so MusicPlayer can send listening_to messages
      (window as any).__listeningWs = ws;

      ws.onopen = () => {
        retryDelay = 1000; // reset on successful connect
      };

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (data.type === 'notification') {
            addToast(data.title, data.message, data.notification_type);
          }
        } catch { /* ignore */ }
      };

      ws.onclose = () => {
        wsRef.current = null;
        // Reconnect with exponential backoff
        retryTimeout = setTimeout(() => {
          if (user) connect();
        }, retryDelay);
        retryDelay = Math.min(retryDelay * 2, MAX_RETRY_DELAY);
      };

      // Heartbeat every 30s
      const hb = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping');
        }
      }, 30000);

      ws.addEventListener('close', () => clearInterval(hb));
    };

    connect();

    return () => {
      if (retryTimeout) clearTimeout(retryTimeout);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [user, addToast]);

  // Polling fallback for unread count — skip when WebSocket is connected
  useEffect(() => {
    if (!user) return;

    const poll = async () => {
      // Skip polling if WebSocket is already connected
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

      try {
        const { data } = await api.get('/notifications/unread-count');
        const count = data.count as number;

        if (lastCountRef.current !== null && count > lastCountRef.current) {
          const { data: notifs } = await api.get('/notifications?limit=5');
          const newOnes = notifs
            .filter((n: any) => !n.is_read)
            .slice(0, count - lastCountRef.current);

          if (newOnes.length > 0) {
            setToasts(prev => [...prev, ...newOnes.map((n: any) => ({
              id: n.id,
              title: n.title,
              message: n.message,
              type: n.type,
            }))]);
          }
        }
        lastCountRef.current = count;
        // Broadcast unread count to Header (removes need for double polling)
        window.dispatchEvent(new CustomEvent('unread-count-update', { detail: count }));
      } catch { /* ignore */ }
    };

    poll();
    const interval = setInterval(poll, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [user]);

  // Auto-dismiss after 5 seconds
  useEffect(() => {
    if (toasts.length === 0) return;
    const timer = setTimeout(() => {
      setToasts(prev => prev.slice(1));
    }, 5000);
    return () => clearTimeout(timer);
  }, [toasts]);

  // Listen for API errors
  useEffect(() => {
    const handler = (e: Event) => {
      const msg = (e as CustomEvent).detail;
      addToast('Ошибка', typeof msg === 'string' ? msg : 'Произошла ошибка');
    };
    window.addEventListener('api-error', handler);
    return () => window.removeEventListener('api-error', handler);
  }, [addToast]);

  if (toasts.length === 0) return null;

  const toastClass = (type?: string) => {
    if (type === 'deadline_overdue') return `${styles.toast} ${styles.toastError}`;
    if (type === 'deadline_today') return `${styles.toast} ${styles.toastWarning}`;
    if (type === 'deadline_soon') return `${styles.toast} ${styles.toastInfo}`;
    return styles.toast;
  };

  return (
    <div className={styles.container}>
      {toasts.map(t => (
        <div key={t.id} className={toastClass(t.type)} onClick={() => dismiss(t.id)}>
          <div className={styles.title}>{t.title}</div>
          <div className={styles.message}>{t.message}</div>
        </div>
      ))}
    </div>
  );
}
