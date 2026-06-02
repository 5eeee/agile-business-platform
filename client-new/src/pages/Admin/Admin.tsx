import { useState, useEffect } from 'react';
import { Settings, Pencil, Flame, Trash2, Frown, Coins, ShieldCheck, Trophy } from 'lucide-react';
import { useAppSelector } from '../../store/hooks';
import { t } from '../../i18n';
import api from '../../api/client';
import { gamificationApi, type LeaderboardEntry } from '../../api/gamification';
import { MetricsSkeleton } from '../../components/Skeleton/Skeleton';
import ConfirmModal from '../../components/ConfirmModal/ConfirmModal';
import type { User } from '../../types';
import { SPHERES } from '../../types';
import styles from './Admin.module.css';

type Tab = 'users' | 'pending';

export default function AdminPage() {
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);

  const [tab, setTab] = useState<Tab>('users');
  const [users, setUsers] = useState<User[]>([]);
  const [pendingUsers, setPendingUsers] = useState<User[]>([]);
  const [stats, setStats] = useState<{ total_users: number; active_users: number; pending_users: number; total_projects: number } | null>(null);
  const [editUser, setEditUser] = useState<User | null>(null);
  const [editForm, setEditForm] = useState({ name: '', email: '', role: 'user', training_role: '' as string });

  // Fire popup
  const [fireTarget, setFireTarget] = useState<User | null>(null);
  const [fireMessage, setFireMessage] = useState('');

  // Sphere roles
  const [sphereTarget, setSphereTarget] = useState<User | null>(null);
  const [sphereForm, setSphereForm] = useState({ sphere: SPHERES[0] as string, role_title: '' });
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [grantLoading, setGrantLoading] = useState(false);
  const [accessLoading, setAccessLoading] = useState(false);
  const [coinGrant, setCoinGrant] = useState({ user_id: '', amount: 10, reason: '' });
  const [accessUserId, setAccessUserId] = useState('');
  const [accessSections, setAccessSections] = useState<Record<string, boolean>>({});

  useEffect(() => {
    loadAll();
  }, []);

  const loadAll = async () => {
    setLoading(true);
    const [usersRes, pendingRes, statsRes] = await Promise.allSettled([
      api.get('/admin/users'),
      api.get('/admin/users/pending'),
      api.get('/admin/stats'),
    ]);
    if (usersRes.status === 'fulfilled') setUsers(usersRes.value.data);
    if (pendingRes.status === 'fulfilled') setPendingUsers(pendingRes.value.data);
    if (statsRes.status === 'fulfilled') setStats(statsRes.value.data);

    try {
      const { data } = await gamificationApi.getLeaderboard();
      setLeaderboard(data);
    } catch {
      setLeaderboard([]);
    }

    setLoading(false);
  };

  const submitCoinGrant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!coinGrant.user_id || !coinGrant.reason.trim() || coinGrant.amount <= 0) return;
    setGrantLoading(true);
    try {
      await gamificationApi.grantCoins({
        user_id: coinGrant.user_id,
        amount: coinGrant.amount,
        reason: coinGrant.reason.trim(),
      });
      setCoinGrant({ user_id: '', amount: 10, reason: '' });
      await loadAll();
    } finally {
      setGrantLoading(false);
    }
  };

  const ALL_SECTIONS = [
    { key: 'projects', label: 'Проекты' },
    { key: 'events', label: 'События' },
    { key: 'places', label: 'Места силы' },
    { key: 'music', label: 'Музыка' },
    { key: 'analytics', label: 'Аналитика' },
    { key: 'training', label: 'Обучение' },
    { key: 'leaderboard', label: 'Лидерборд' },
    { key: 'shop', label: 'Магазин' },
    { key: 'competency', label: 'Компетенции' },
    { key: 'assessment', label: 'Тестирование' },
  ];

  const loadUserAccess = async (userId: string) => {
    if (!userId) {
      setAccessSections({});
      return;
    }
    try {
      const { data } = await gamificationApi.getAccess(userId);
      const map: Record<string, boolean> = {};
      ALL_SECTIONS.forEach(s => { map[s.key] = (data.section_keys || []).includes(s.key); });
      setAccessSections(map);
    } catch {
      const map: Record<string, boolean> = {};
      ALL_SECTIONS.forEach(s => { map[s.key] = false; });
      setAccessSections(map);
    }
  };

  const submitAccessGrant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!accessUserId) return;
    const keys = Object.entries(accessSections).filter(([, v]) => v).map(([k]) => k);
    setAccessLoading(true);
    try {
      await gamificationApi.setAccess(accessUserId, keys);
    } finally {
      setAccessLoading(false);
    }
  };

  const approveUser = async (userId: string) => {
    await api.post(`/admin/users/${userId}/approve`);
    loadAll();
  };

  const rejectUser = async (userId: string) => {
    await api.post(`/admin/users/${userId}/reject`);
    loadAll();
  };

  const deleteUser = async (userId: string) => {
    setDeleteConfirm(userId);
  };

  const confirmDeleteUser = async () => {
    if (!deleteConfirm) return;
    await api.delete(`/admin/users/${deleteConfirm}`);
    setDeleteConfirm(null);
    loadAll();
  };

  const openEdit = (u: User) => {
    setEditUser(u);
    setEditForm({ name: u.name, email: u.email, role: u.role, training_role: u.training_role || '' });
  };

  const saveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editUser) return;
    const payload = { ...editForm, training_role: editForm.training_role || null };
    await api.put(`/admin/users/${editUser.id}`, payload);
    setEditUser(null);
    loadAll();
  };

  const openFire = (u: User) => {
    setFireTarget(u);
    setFireMessage('');
  };

  const fireUser = async () => {
    if (!fireTarget) return;
    await api.post(`/admin/users/${fireTarget.id}/fire`, { fire_message: fireMessage || undefined });
    setFireTarget(null);
    loadAll();
  };

  const assignSphereRole = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sphereTarget) return;
    await api.post(`/admin/users/${sphereTarget.id}/sphere-roles`, sphereForm);
    setSphereTarget(null);
    loadAll();
  };

  const statusBadge = (status: string) => {
    const cls = status === 'active' ? 'badge-success' : status === 'pending' ? 'badge-warning' : status === 'fired' ? 'badge-error' : 'badge-primary';
    return <span className={`badge ${cls}`}>{status}</span>;
  };

  return (
    <div className={`${styles.page} page-enter`}>
      <h1>{lang.admin.title}</h1>

      {/* Статистика */}
      {loading ? <MetricsSkeleton count={4} /> : stats && (
        <div className={styles.statsRow}>
          <div className="card"><strong>{stats.total_users}</strong><span>{lang.admin.totalUsers}</span></div>
          <div className="card"><strong>{stats.active_users}</strong><span>{lang.admin.activeUsers}</span></div>
          <div className="card"><strong>{stats.pending_users}</strong><span>{lang.admin.pendingUsers}</span></div>
          <div className="card"><strong>{stats.total_projects}</strong><span>{lang.admin.totalProjects}</span></div>
        </div>
      )}

      {/* Вкладки */}
      <div className={styles.tabs}>
        <button className={`${styles.tabBtn} ${tab === 'users' ? styles.tabActive : ''}`} onClick={() => setTab('users')}>
          {lang.admin.users}
        </button>
        <button className={`${styles.tabBtn} ${tab === 'pending' ? styles.tabActive : ''}`} onClick={() => setTab('pending')}>
          {lang.admin.pending} {pendingUsers.length > 0 && <span className="badge badge-error">{pendingUsers.length}</span>}
        </button>
      </div>

      {/* Список пользователей */}
      {tab === 'users' && (
        <>
          <div className={styles.tableWrap}>
            <input
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder={lang.admin.search}
              style={{ width: '100%', padding: '8px 12px', marginBottom: 12, borderRadius: 8, border: '1px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)', fontSize: 14 }}
            />
            <table className={styles.table}>
            <thead>
              <tr>
                <th>{lang.admin.name}</th>
                <th>Email</th>
                <th>{lang.admin.role}</th>
                <th>{(lang.training as Record<string, string>).trainingRole}</th>
                <th>{lang.admin.status}</th>
                <th>{lang.admin.sphereRoles}</th>
                <th>{lang.admin.actions}</th>
              </tr>
            </thead>
            <tbody>
              {users.filter(u => {
                if (!searchQuery.trim()) return true;
                const q = searchQuery.toLowerCase();
                return u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q) || u.status.toLowerCase().includes(q) || u.role.toLowerCase().includes(q);
              }).map(u => (
                <tr key={u.id}>
                  <td>
                    <div className={styles.userCell}>
                      {u.avatar_url ? <img src={u.avatar_url} className={styles.tinyAvatar} alt="" /> : <div className={styles.tinyAvatarPlaceholder}>{(u.name || '?')[0]}</div>}
                      {u.name}
                    </div>
                  </td>
                  <td>{u.email}</td>
                  <td><span className={`badge ${u.role === 'admin' ? 'badge-error' : u.role === 'intern' ? 'badge-warning' : 'badge-primary'}`}>{u.role}</span></td>
                  <td>{u.training_role ? <span className="badge badge-warning" style={{ fontSize: 11 }}>{u.training_role === 'training_editor' ? (lang.training as Record<string, string>).trainingEditor : (lang.training as Record<string, string>).intern}</span> : '—'}</td>
                  <td>{statusBadge(u.status)}</td>
                  <td>
                    {u.sphere_roles?.map(sr => (
                      <span key={`${sr.sphere}-${sr.role_title}`} className="badge badge-primary" style={{ marginRight: 4, fontSize: 11 }}>
                        {sr.sphere}: {sr.role_title}
                      </span>
                    ))}
                    <button className="btn btn-ghost btn-sm" onClick={() => setSphereTarget(u)} title={lang.admin.assignSphereRole} aria-label={lang.admin.assignSphereRole}>
                      <Settings size={16} />
                    </button>
                  </td>
                  <td>
                    <div className={styles.actionBtns}>
                      <button className="btn btn-ghost btn-sm" onClick={() => openEdit(u)} aria-label={lang.common.edit}>
                        <Pencil size={16} />
                      </button>
                      {u.status !== 'fired' && (
                        <button className="btn btn-ghost btn-sm" onClick={() => openFire(u)} title={lang.admin.fire} aria-label={lang.admin.fire}>
                          <Flame size={16} />
                        </button>
                      )}
                      <button className="btn btn-ghost btn-sm" onClick={() => deleteUser(u.id)} title={lang.admin.delete} aria-label={lang.admin.delete}>
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
            </table>
          </div>

          <div className={styles.toolsGrid}>
            <div className={styles.toolCard}>
              <h3><Coins size={16} /> Начислить Agile.Coins</h3>
              <form onSubmit={submitCoinGrant} className={styles.form}>
                <select value={coinGrant.user_id} onChange={e => setCoinGrant({ ...coinGrant, user_id: e.target.value })} required>
                  <option value="">Выберите пользователя</option>
                  {users.map(u => <option key={u.id} value={u.id}>{u.name} ({u.email})</option>)}
                </select>
                <input type="number" min={1} max={10000} value={coinGrant.amount} onChange={e => setCoinGrant({ ...coinGrant, amount: Number(e.target.value) })} required />
                <textarea value={coinGrant.reason} onChange={e => setCoinGrant({ ...coinGrant, reason: e.target.value })} rows={3} placeholder="Обязательно укажите за что и когда" required />
                <button className="btn btn-primary btn-sm" type="submit" disabled={grantLoading}>{grantLoading ? 'Сохранение...' : 'Начислить'}</button>
              </form>
            </div>

            <div className={styles.toolCard}>
              <h3><ShieldCheck size={16} /> Доступы к разделам</h3>
              <form onSubmit={submitAccessGrant} className={styles.form}>
                <select value={accessUserId} onChange={e => { setAccessUserId(e.target.value); loadUserAccess(e.target.value); }} required>
                  <option value="">Выберите пользователя</option>
                  {users.map(u => <option key={u.id} value={u.id}>{u.name} ({u.email})</option>)}
                </select>
                {accessUserId && (
                  <div className={styles.checkboxGrid}>
                    {ALL_SECTIONS.map(s => (
                      <label key={s.key} className={styles.checkItem}>
                        <input type="checkbox" checked={!!accessSections[s.key]} onChange={e => setAccessSections({ ...accessSections, [s.key]: e.target.checked })} />
                        {s.label}
                      </label>
                    ))}
                  </div>
                )}
                <button className="btn btn-primary btn-sm" type="submit" disabled={accessLoading || !accessUserId}>{accessLoading ? 'Сохранение...' : 'Сохранить доступы'}</button>
              </form>
            </div>

            <div className={styles.toolCard}>
              <h3><Trophy size={16} /> Топ стажёров по KPI</h3>
              {leaderboard.length === 0 ? (
                <p className={styles.empty}>Нет данных</p>
              ) : (
                <div className={styles.leaderboardMini}>
                  {leaderboard.slice(0, 10).map(r => (
                    <div key={r.user_id} className={styles.leaderRow}>
                      <span>#{r.rank} {r.user_name}</span>
                      <span>{r.coins_balance} coins</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* Ожидающие */}
      {tab === 'pending' && (
        <div className={styles.pendingList}>
          {pendingUsers.length === 0 && <p className={styles.empty}>{lang.admin.noPending}</p>}
          {pendingUsers.map(u => (
            <div key={u.id} className={`card ${styles.pendingCard}`}>
              <div>
                <strong>{u.name}</strong>
                <span className={styles.pendingEmail}>{u.email}</span>
                {u.city && <span> | {u.city}</span>}
              </div>
              <div className={styles.pendingActions}>
                <button className="btn btn-primary btn-sm" onClick={() => approveUser(u.id)}>{lang.admin.approve}</button>
                <button className="btn btn-danger btn-sm" onClick={() => rejectUser(u.id)}>{lang.admin.reject}</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Edit modal */}
      {editUser && (
        <div className="modal-overlay" onClick={() => setEditUser(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>{lang.admin.editUser}</h2>
            <form onSubmit={saveEdit} className={styles.form}>
              <input value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} placeholder={lang.admin.name} required />
              <input value={editForm.email} onChange={e => setEditForm({ ...editForm, email: e.target.value })} placeholder="Email" type="email" required />
              <select value={editForm.role} onChange={e => setEditForm({ ...editForm, role: e.target.value })}>
                <option value="user">{lang.roles.user}</option>
                <option value="intern">{lang.roles.intern}</option>
                <option value="admin">{lang.roles.admin}</option>
              </select>
              <select value={editForm.training_role} onChange={e => setEditForm({ ...editForm, training_role: e.target.value })}>
                <option value="">{(lang.training as Record<string, string>).noRole}</option>
                <option value="intern">{(lang.training as Record<string, string>).intern}</option>
                <option value="training_editor">{(lang.training as Record<string, string>).trainingEditor}</option>
              </select>
              <div className={styles.formActions}>
                <button type="button" className="btn btn-secondary" onClick={() => setEditUser(null)}>{lang.common.cancel}</button>
                <button type="submit" className="btn btn-primary">{lang.common.save}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Fire modal */}
      {fireTarget && (
        <div className="modal-overlay" onClick={() => setFireTarget(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ textAlign: 'center' }}>
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 12 }}><Frown size={64} strokeWidth={1.25} /></div>
            <h2>{lang.admin.fireTitle}</h2>
            <p>{lang.admin.fireConfirm} <strong>{fireTarget.name}</strong>?</p>
            <textarea
              placeholder={lang.admin.fireMessagePlaceholder}
              value={fireMessage}
              onChange={e => setFireMessage(e.target.value)}
              rows={3}
              style={{ width: '100%', marginTop: 12, padding: 10, borderRadius: 8, border: '1px solid var(--color-border)', background: 'var(--color-bg)', color: 'var(--color-text)', fontFamily: 'var(--font-mono)', fontSize: 14 }}
            />
            <div className={styles.formActions} style={{ marginTop: 16 }}>
              <button className="btn btn-secondary" onClick={() => setFireTarget(null)}>{lang.common.cancel}</button>
              <button className="btn btn-danger" onClick={fireUser}>
                <Flame size={16} style={{ marginRight: 6 }} />
                {lang.admin.fire}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Sphere role modal */}
      {sphereTarget && (
        <div className="modal-overlay" onClick={() => setSphereTarget(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>{lang.admin.assignSphereRole}</h2>
            <p>{sphereTarget.name}</p>
            <form onSubmit={assignSphereRole} className={styles.form}>
              <select value={sphereForm.sphere} onChange={e => setSphereForm({ ...sphereForm, sphere: e.target.value })}>
                {SPHERES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              <input placeholder={lang.admin.roleTitle} value={sphereForm.role_title} onChange={e => setSphereForm({ ...sphereForm, role_title: e.target.value })} required />
              <div className={styles.formActions}>
                <button type="button" className="btn btn-secondary" onClick={() => setSphereTarget(null)}>{lang.common.cancel}</button>
                <button type="submit" className="btn btn-primary">{lang.common.save}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {deleteConfirm && (
        <ConfirmModal
          title={lang.admin.confirmDelete}
          message={lang.admin.confirmDelete}
          confirmLabel={lang.admin.delete}
          cancelLabel={lang.common.cancel}
          onConfirm={confirmDeleteUser}
          onCancel={() => setDeleteConfirm(null)}
        />
      )}
    </div>
  );
}
