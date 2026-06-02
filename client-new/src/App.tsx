import { useEffect, useRef, useCallback, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAppSelector, useAppDispatch } from './store/hooks';
import { fetchMe, setFired } from './store/slices/authSlice';
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
const MusicPage = lazy(() => import('./pages/Music/Music'));
const TrainingPage = lazy(() => import('./pages/Training/Training'));
const AssessmentPage = lazy(() => import('./pages/Assessment/Assessment'));
const CompetencyPage = lazy(() => import('./pages/Competency/Competency'));
const ShopPage = lazy(() => import('./pages/Shop/Shop'));
const KPIPage = lazy(() => import('./pages/KPI/KPI'));
const LeaderboardPage = lazy(() => import('./pages/Leaderboard/Leaderboard'));

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAppSelector(s => s.auth);
  if (loading) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>Loading...</div>;
  return user ? <>{children}</> : <Navigate to="/login" />;
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAppSelector(s => s.auth);
  if (loading) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>Loading...</div>;
  return user?.role === 'admin' ? <>{children}</> : <Navigate to="/" />;
}

function InternGuard({ children }: { children: React.ReactNode }) {
  const { user } = useAppSelector(s => s.auth);
  if (user?.training_role === 'intern' && user?.role !== 'admin') return <Navigate to="/training" />;
  return <>{children}</>;
}

export default function App() {
  const dispatch = useAppDispatch();
  const { isFired, fireMessage } = useAppSelector(s => s.auth);
  const { theme } = useAppSelector(s => s.ui);
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (window.location.pathname !== '/login') {
      dispatch(fetchMe());
    } else {
      // На странице логина не дёргаем /auth/me — сразу снимаем loading
      dispatch({ type: 'auth/fetchMe/rejected' });
    }
  }, [dispatch]);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // Ripple theme transition
  const handleThemeToggleClick = useCallback((e: Event) => {
    const { x, y } = (e as CustomEvent).detail;
    const overlay = overlayRef.current;
    if (!overlay) return;

    // Capture the OLD theme's colors for the overlay
    const oldBg = getComputedStyle(document.documentElement).getPropertyValue('--color-bg').trim();
    overlay.style.background = oldBg;

    // Instantly expand overlay to cover screen (no transition)
    overlay.style.transition = 'none';
    overlay.style.clipPath = `circle(150% at ${x}px ${y}px)`;

    // Force reflow so the instant clip-path is applied
    void overlay.offsetWidth;

    // Now shrink the overlay to reveal the new theme underneath
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

  // Listen for fired event from api client
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
    <BrowserRouter>
      <NotificationToast />
      <div ref={overlayRef} className="theme-transition-overlay" />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
          <Route index element={<Suspense fallback={<Spinner />}><InternGuard><HomePage /></InternGuard></Suspense>} />
          <Route path="projects" element={<Suspense fallback={<Spinner />}><InternGuard><ProjectsPage /></InternGuard></Suspense>} />
          <Route path="project/:id" element={<Suspense fallback={<Spinner />}><InternGuard><ProjectDetailPage /></InternGuard></Suspense>} />
          <Route path="events" element={<Suspense fallback={<Spinner />}><InternGuard><EventsPage /></InternGuard></Suspense>} />
          <Route path="music" element={<Suspense fallback={<Spinner />}><InternGuard><MusicPage /></InternGuard></Suspense>} />
          <Route path="shop" element={<Suspense fallback={<Spinner />}><InternGuard><ShopPage /></InternGuard></Suspense>} />
          <Route path="kpi" element={<Suspense fallback={<Spinner />}><KPIPage /></Suspense>} />
          <Route path="leaderboard" element={<Suspense fallback={<Spinner />}><LeaderboardPage /></Suspense>} />
          <Route path="training" element={<Suspense fallback={<Spinner />}><TrainingPage /></Suspense>} />
          <Route path="assessment" element={<Suspense fallback={<Spinner />}><AssessmentPage /></Suspense>} />
          <Route path="competency" element={<Suspense fallback={<Spinner />}><CompetencyPage /></Suspense>} />
          <Route path="profile" element={<Suspense fallback={<Spinner />}><ProfilePage /></Suspense>} />
          <Route path="admin" element={<Suspense fallback={<Spinner />}><AdminRoute><AdminPage /></AdminRoute></Suspense>} />
        </Route>
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </BrowserRouter>
  );
}
