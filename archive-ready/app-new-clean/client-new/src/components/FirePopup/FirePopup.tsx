// Всплывающее окно при увольнении
import { useAppDispatch, useAppSelector } from '../../store/hooks';
import { logout } from '../../store/slices/authSlice';
import { t } from '../../i18n';
import { Frown } from 'lucide-react';
import api from '../../api/client';
import styles from './FirePopup.module.css';

interface Props {
  message?: string;
}

export default function FirePopup({ message }: Props) {
  const dispatch = useAppDispatch();
  const { isFired, fireMessage } = useAppSelector(s => s.auth);
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);
  const text = message || fireMessage;

  if (!isFired && !message) return null;

  const handleLogout = () => {
    api.post('/auth/logout').catch(() => {}).finally(() => {
      dispatch(logout());
      window.location.href = '/login';
    });
  };

  return (
    <div className={styles.overlay}>
      <div className={styles.popup}>
        <div className={styles.sadFace}><Frown size={56} /></div>
        <p className={styles.message}>{text || lang.firePopup.message}</p>
        <p className={styles.title}>{lang.firePopup.title}</p>
        <button className={styles.logoutBtn} onClick={handleLogout}>{lang.firePopup.logoutBtn}</button>
      </div>
    </div>
  );
}
