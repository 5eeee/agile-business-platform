import { useEffect, useRef, useCallback, lazy, Suspense } from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAppSelector, useAppDispatch } from './store/hooks';
import { fetchMe, setFired } from './store/slices/authSlice';
import { setLanguage } from './store/slices/uiSlice';
import Layout from './components/Layout/Layout';
import LoginPage from './pages/Login/Login';
import FirePopup from './components/FirePopup/FirePopup';
import NotificationToast from './components/NotificationToast/NotificationToast';
import Spinner from './components/Spinner/Spinner';

const HomePage = lazy(() => import('./pages/Home/Home'));
const ProjectsPage = lazy(() => import('./pages/Projects/Projects'));
const ProjectDetailPage = lazy(() => import('./pages/ProjectDetail/ProjectDetail'));
const AdminPage = lazy(() => import('./pages/Admin/Admin'));
const ProfilePage = lazy(() => import('./pages/Profile/Profile'));
const EventsPage = lazy(() => import('./pages/Events/Events'));
const PlacesPage = lazy(() => import('./pages/Places/Places'));
const MusicPage = lazy(() => import('./pages/Music/Music'));
const AnalyticsPage = lazy(() => import('./pages/Analytics/Analytics'));
const ShopPage = lazy(() => import('./pages/Shop/Shop'));
const KPIPage = lazy(() => import('./pages/KPI/KPI'));
const LeaderboardPage = lazy(() => import('./pages/Leaderboard/Leaderboard'));
const ApplicationsPage = lazy(() => import('./pages/Applications/Applications'));
const ApplicationDetailPage = lazy(() => import('./pages/Applications/ApplicationDetail'));
const FinancePage = lazy(() => import('./pages/Finance/Finance'));
const CallPage = lazy(() => import('./pages/Call/Call'));
const CustomerReviewPage = lazy(() => import('./pages/CustomerReview/CustomerReview'));

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAppSelector(s => s.auth);
  if (loading) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>Loading...</div>;
  return user ? <>{children}</> : <Navigate to="/login" />;
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAppSelector(s => s.auth);
  if (loading) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>Loading...</div>;
  const allowed = ['admin', 'owner', 'deputy_owner'];
  return user && allowed.includes(user.role) ? <>{children}</> : <Navigate to="/" />;
}

function ProjectsGuard({ children }: { children: React.ReactNode }) {
  const { user } = useAppSelector(s => s.auth);
  if (user?.role === 'consultant') return <Navigate to="/applications" />;
  return <>{children}</>;
}

function ApplicationsGuard({ children }: { children: React.ReactNode }) {
  const { user } = useAppSelector(s => s.auth);
  const allowed = ['admin', 'owner', 'deputy_owner', 'consultant'];
  if (!user || !allowed.includes(user.role)) return <Navigate to="/" />;
  return <>{children}</>;
}

export default function App() {
  const dispatch = useAppDispatch();
  const { isFired, fireMessage, user } = useAppSelector(s => s.auth);
  const { theme } = useAppSelector(s => s.ui);
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (window.location.hash !== '#/login' && !window.location.hash.startsWith('#/review/')) {
      dispatch(fetchMe());
    } else {
      dispatch({ type: 'auth/fetchMe/rejected' });
    }
  }, [dispatch]);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    if (user?.language === 'ru' || user?.language === 'ka' || user?.language === 'en') {
      dispatch(setLanguage(user.language));
    }
  }, [dispatch, user?.language]);

  const handleThemeToggleClick = useCallback((e: Event) => {
    const { x, y } = (e as CustomEvent).detail;
    const overlay = overlayRef.current;
    if (!overlay) return;

    const oldBg = getComputedStyle(document.documentElement).getPropertyValue('--color-bg').trim();
    overlay.style.background = oldBg;

    overlay.style.transition = 'none';
    overlay.style.clipPath = `circle(150% at ${x}px ${y}px)`;

    void overlay.offsetWidth;

    overlay.style.transition = 'clip-path 0.7s cubic-bezier(0.4, 0, 0.2, 1)';
    overlay.style.clipPath = `circle(0% at ${x}px ${y}px)`;

    const onEnd = () => {
      overlay.style.clipPath = 'circle(0% at 0px 0px)';
      overlay.style.transition = '';
      overlay.style.background = '';
      overlay.removeEventListener('transitionend', onEnd);
    };
    overlay.addEventListener('transitionend', onEnd);
  }, []);

  useEffect(() => {
    window.addEventListener('theme-toggle-click', handleThemeToggleClick);
    return () => window.removeEventListener('theme-toggle-click', handleThemeToggleClick);
  }, [handleThemeToggleClick]);

  useEffect(() => {
    const handler = (e: Event) => {
      const msg = (e as CustomEvent).detail;
      dispatch(setFired(typeof msg === 'string' ? msg : msg?.message || ''));
    };
    window.addEventListener('user-fired', handler);
    return () => window.removeEventListener('user-fired', handler);
  }, [dispatch]);

  if (isFired) {
    return <FirePopup message={fireMessage || ''} />;
  }

  return (
    <HashRouter>
      <NotificationToast />
      <div ref={overlayRef} className="theme-transition-overlay" />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/review/:token" element={<Suspense fallback={<Spinner />}><CustomerReviewPage /></Suspense>} />
        <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
          <Route index element={<Suspense fallback={<Spinner />}><HomePage /></Suspense>} />
          <Route path="projects" element={<Suspense fallback={<Spinner />}><ProjectsGuard><ProjectsPage /></ProjectsGuard></Suspense>} />
          <Route path="project/:id" element={<Suspense fallback={<Spinner />}><ProjectsGuard><ProjectDetailPage /></ProjectsGuard></Suspense>} />
          <Route path="events" element={<Suspense fallback={<Spinner />}><EventsPage /></Suspense>} />
          <Route path="places" element={<Suspense fallback={<Spinner />}><PlacesPage /></Suspense>} />
          <Route path="music" element={<Suspense fallback={<Spinner />}><MusicPage /></Suspense>} />
          <Route path="analytics" element={<Suspense fallback={<Spinner />}><AnalyticsPage /></Suspense>} />
          <Route path="finance" element={<Suspense fallback={<Spinner />}><FinancePage /></Suspense>} />
          <Route path="shop" element={<Suspense fallback={<Spinner />}><ShopPage /></Suspense>} />
          <Route path="kpi" element={<Suspense fallback={<Spinner />}><KPIPage /></Suspense>} />
          <Route path="call" element={<Suspense fallback={<Spinner />}><CallPage /></Suspense>} />
          <Route path="leaderboard" element={<Suspense fallback={<Spinner />}><LeaderboardPage /></Suspense>} />
          <Route path="profile" element={<Suspense fallback={<Spinner />}><ProfilePage /></Suspense>} />
          <Route path="applications" element={<Suspense fallback={<Spinner />}><ApplicationsGuard><ApplicationsPage /></ApplicationsGuard></Suspense>} />
          <Route path="applications/:id" element={<Suspense fallback={<Spinner />}><ApplicationsGuard><ApplicationDetailPage /></ApplicationsGuard></Suspense>} />
          <Route path="admin" element={<Suspense fallback={<Spinner />}><AdminRoute><AdminPage /></AdminRoute></Suspense>} />
        </Route>
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </HashRouter>
  );
}
