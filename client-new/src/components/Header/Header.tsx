import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell,
  ChevronDown,
  Languages,
  LogOut,
  Menu,
  Moon,
  Sun,
  UserRound,
} from 'lucide-react';
import { useAppSelector, useAppDispatch } from '../../store/hooks';
import { logout } from '../../store/slices/authSlice';
import { toggleTheme, setLanguage, toggleMobileMenu } from '../../store/slices/uiSlice';
import { t } from '../../i18n';
import api from '../../api/client';
import type { Notification } from '../../types';
import styles from './Header.module.css';

const headerLabels = {
  ru: {
    account: 'Меню профиля',
    close: 'Закрыть меню',
    darkTheme: 'Включить тёмную тему',
    home: 'На главную',
    language: 'Язык интерфейса',
    lightTheme: 'Включить светлую тему',
    menu: 'Открыть навигацию',
    unread: 'Непрочитанных уведомлений',
  },
  ka: {
    account: 'პროფილის მენიუ',
    close: 'მენიუს დახურვა',
    darkTheme: 'მუქი თემის ჩართვა',
    home: 'მთავარ გვერდზე',
    language: 'ინტერფეისის ენა',
    lightTheme: 'ღია თემის ჩართვა',
    menu: 'ნავიგაციის გახსნა',
    unread: 'წაუკითხავი შეტყობინებები',
  },
  en: {
    account: 'Profile menu',
    close: 'Close menu',
    darkTheme: 'Switch to dark theme',
    home: 'Go to home',
    language: 'Interface language',
    lightTheme: 'Switch to light theme',
    menu: 'Open navigation',
    unread: 'Unread notifications',
  },
} as const;

const languageNames = {
  ru: 'Русский',
  ka: 'ქართული',
  en: 'English',
} as const;

const localeByLanguage = {
  ru: 'ru-RU',
  ka: 'ka-GE',
  en: 'en-US',
} as const;

type HeaderPopover = 'notifications' | 'account' | null;

export default function Header() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { user } = useAppSelector(s => s.auth);
  const { theme, language, mobileMenuOpen } = useAppSelector(s => s.ui);
  const lang = t(language);
  const labels = headerLabels[language];
  const themeBtnRef = useRef<HTMLButtonElement>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [openPopover, setOpenPopover] = useState<HeaderPopover>(null);

  const changeLanguage = (code: 'ru' | 'ka' | 'en') => {
    dispatch(setLanguage(code));
    api.put('/users/profile', { language: code }).catch(() => {
      window.dispatchEvent(new CustomEvent('api-error', { detail: 'Не удалось сохранить язык профиля' }));
    });
  };

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpenPopover(null);
    };

    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, []);

  useEffect(() => {
    if (!user) return;

    const handler = (event: Event) => {
      setUnreadCount(Number((event as CustomEvent).detail) || 0);
    };

    window.addEventListener('unread-count-update', handler);
    api.get('/notifications/unread-count')
      .then(({ data }) => setUnreadCount(Number(data.count) || 0))
      .catch(() => setUnreadCount(0));

    return () => window.removeEventListener('unread-count-update', handler);
  }, [user]);

  const toggleNotifications = async () => {
    if (openPopover === 'notifications') {
      setOpenPopover(null);
      return;
    }

    setOpenPopover('notifications');
    try {
      const { data } = await api.get('/notifications');
      setNotifications(Array.isArray(data) ? data : []);
      await api.put('/notifications/read-all');
      setUnreadCount(0);
    } catch {
      setNotifications([]);
    }
  };

  const handleThemeToggle = () => {
    const rect = themeBtnRef.current?.getBoundingClientRect();
    if (rect) {
      window.dispatchEvent(new CustomEvent('theme-toggle-click', {
        detail: { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 },
      }));
    }
    dispatch(toggleTheme());
  };

  const handleLogout = () => {
    setOpenPopover(null);
    api.post('/auth/logout', null, { _silent401: true } as any).catch(() => undefined).finally(() => {
      dispatch(logout());
      navigate('/login');
    });
  };

  if (!user) return null;

  const notificationLabel = unreadCount > 0
    ? `${lang.nav.notifications}. ${labels.unread}: ${unreadCount}`
    : lang.nav.notifications;

  return (
    <header className={styles.header}>
      <div className={styles.left}>
        <button
          type="button"
          className={`${styles.iconBtn} mobile-only`}
          onClick={() => dispatch(toggleMobileMenu())}
          aria-label={mobileMenuOpen ? labels.close : labels.menu}
          aria-controls="primary-navigation"
          aria-expanded={mobileMenuOpen}
        >
          <Menu aria-hidden />
        </button>
        <button type="button" className={styles.logo} onClick={() => navigate('/')} aria-label={labels.home}>
          <img
            src={theme === 'dark' ? '/logo-light.svg' : '/logo-dark.svg'}
            alt=""
            className={styles.logoImg}
          />
        </button>
      </div>

      <div id="header-project-slot" className={styles.projectSlot} />

      <div className={styles.right}>
        <div className={styles.notifWrap}>
          <button
            type="button"
            className={styles.iconBtn}
            onClick={toggleNotifications}
            aria-label={notificationLabel}
            aria-controls="header-notifications"
            aria-expanded={openPopover === 'notifications'}
          >
            <Bell aria-hidden />
            {unreadCount > 0 ? (
              <span className={styles.notifBadge} aria-hidden>
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            ) : null}
          </button>

          {openPopover === 'notifications' ? (
            <section
              id="header-notifications"
              className={styles.notifDropdown}
              role="dialog"
              aria-labelledby="header-notifications-title"
            >
              <div className={styles.dropdownHeading}>
                <h2 id="header-notifications-title">{lang.nav.notifications}</h2>
              </div>
              {notifications.length === 0 ? (
                <p className={styles.notifEmpty}>{lang.common.noData}</p>
              ) : (
                <div className={styles.notifList}>
                  {notifications.map(notification => {
                    const isCritical = notification.type === 'deadline_overdue' || notification.type === 'critical_divergence';
                    const isWarning = notification.type === 'deadline_today' || notification.type === 'critical_warning';
                    const isInfo = notification.type === 'deadline_soon' || notification.type === 'critical_info';
                    const borderColor = isCritical ? '#dc2626' : isWarning ? '#f59e0b' : isInfo ? '#3b82f6' : 'transparent';
                    const canNavigate = typeof notification.link === 'string' && notification.link.startsWith('/');
                    const itemStyle = { '--notification-accent': borderColor } as CSSProperties;
                    const content = (
                      <>
                        <strong>{notification.title}</strong>
                        <p>{notification.message}</p>
                        <time dateTime={notification.created_at}>
                          {new Date(notification.created_at).toLocaleString(localeByLanguage[language])}
                        </time>
                      </>
                    );

                    return canNavigate ? (
                      <button
                        key={notification.id}
                        type="button"
                        className={`${styles.notifItem} ${styles.notifItemInteractive}`}
                        style={itemStyle}
                        onClick={() => {
                          navigate(notification.link as string);
                          setOpenPopover(null);
                        }}
                      >
                        {content}
                      </button>
                    ) : (
                      <article key={notification.id} className={styles.notifItem} style={itemStyle}>
                        {content}
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
          ) : null}
        </div>

        <div className={styles.accountWrap}>
          <button
            type="button"
            className={styles.accountBtn}
            onClick={() => setOpenPopover(previous => previous === 'account' ? null : 'account')}
            aria-label={`${labels.account}: ${user.name}`}
            aria-controls="header-account-menu"
            aria-expanded={openPopover === 'account'}
          >
            <span className={styles.avatar} aria-hidden>
              {user.avatar_url ? <img src={user.avatar_url} alt="" /> : (user.name || '?')[0].toUpperCase()}
            </span>
            <span className={styles.userName}>{user.name}</span>
            <ChevronDown className={styles.accountChevron} aria-hidden />
          </button>

          {openPopover === 'account' ? (
            <div
              id="header-account-menu"
              className={styles.accountMenu}
              role="dialog"
              aria-label={labels.account}
            >
              <div className={styles.accountIdentity}>
                <strong>{user.name}</strong>
                <span>{user.email}</span>
              </div>

              <button
                type="button"
                className={styles.menuRow}
                onClick={() => {
                  setOpenPopover(null);
                  navigate('/profile');
                }}
              >
                <UserRound aria-hidden />
                <span>{lang.nav.profile}</span>
              </button>

              <label className={styles.languageSelectRow}>
                <Languages aria-hidden />
                <span>{labels.language}</span>
                <select
                  className={styles.languageSelect}
                  value={language}
                  onChange={event => changeLanguage(event.target.value as 'ru' | 'ka' | 'en')}
                  aria-label={labels.language}
                >
                  {(['ru', 'ka', 'en'] as const).map(code => (
                    <option key={code} value={code}>{languageNames[code]}</option>
                  ))}
                </select>
              </label>

              <button
                ref={themeBtnRef}
                type="button"
                className={styles.menuRow}
                onClick={handleThemeToggle}
              >
                {theme === 'light' ? <Moon aria-hidden /> : <Sun aria-hidden />}
                <span>{theme === 'light' ? labels.darkTheme : labels.lightTheme}</span>
              </button>

              <button
                type="button"
                className={`${styles.menuRow} ${styles.logoutRow}`}
                onClick={handleLogout}
              >
                <LogOut aria-hidden />
                <span>{lang.nav.logout}</span>
              </button>
            </div>
          ) : null}
        </div>
      </div>

      {openPopover ? (
        <button
          type="button"
          className={styles.popoverOverlay}
          onClick={() => setOpenPopover(null)}
          aria-label={labels.close}
          tabIndex={-1}
        />
      ) : null}
    </header>
  );
}
