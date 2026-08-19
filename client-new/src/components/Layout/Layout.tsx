import { useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import Header from '../Header/Header';
import Sidebar from '../Sidebar/Sidebar';
import { gamificationApi } from '../../api/gamification';
import { useAppDispatch, useAppSelector } from '../../store/hooks';
import { toggleSidebar } from '../../store/slices/uiSlice';
import { PanelRightOpen } from 'lucide-react';
import styles from './Layout.module.css';

export default function Layout() {
  const dispatch = useAppDispatch();
  const { sidebarOpen, sidebarNarrow } = useAppSelector(s => s.ui);

  useEffect(() => {
    // Heartbeat for KPI/session tracking.
    const ping = () => { gamificationApi.sessionPing().catch(() => undefined); };
    ping();
    const id = window.setInterval(ping, 5 * 60 * 1000);

    const onUnload = () => {
      gamificationApi.sessionEnd().catch(() => undefined);
    };
    window.addEventListener('beforeunload', onUnload);

    return () => {
      window.clearInterval(id);
      window.removeEventListener('beforeunload', onUnload);
      gamificationApi.sessionEnd().catch(() => undefined);
    };
  }, []);

  return (
    <div className={styles.layout}>
      <Header />
      <div className={styles.body}>
        <Sidebar />
        <main
          className={`${styles.main} ${!sidebarOpen ? styles.mainExpanded : ''} ${sidebarOpen && sidebarNarrow ? styles.mainSidebarNarrow : ''}`}
        >
          {!sidebarOpen && (
            <button
              type="button"
              className={styles.sidebarOpenBtn}
              onClick={() => dispatch(toggleSidebar())}
              aria-controls="primary-navigation"
              aria-expanded="false"
            >
              <PanelRightOpen size={16} /> Открыть категории
            </button>
          )}
          <Outlet />
        </main>
      </div>
    </div>
  );
}
