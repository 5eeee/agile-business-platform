import { useState, useEffect, useRef } from 'react';
import { CalendarDays, MapPin, Camera, Pencil, Trash2, UserRound } from 'lucide-react';
import { useAppSelector } from '../../store/hooks';
import { t } from '../../i18n';
import api from '../../api/client';
import { CardSkeleton } from '../../components/Skeleton/Skeleton';
import ConfirmModal from '../../components/ConfirmModal/ConfirmModal';
import type { Event } from '../../types';
import styles from './Events.module.css';

interface EventChatMsg {
  id: string;
  event_id: string;
  user_id: string;
  user_name?: string;
  content: string;
  is_deleted: boolean;
  created_at: string;
}

export default function EventsPage() {
  const { user } = useAppSelector(s => s.auth);
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);

  const [events, setEvents] = useState<Event[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    title: '',
    description: '',
    start_date: '',
    end_date: '',
    location: '',
    iteration_id: '',
  });
  const [editEvent, setEditEvent] = useState<Event | null>(null);
  const [editForm, setEditForm] = useState({
    title: '',
    description: '',
    start_date: '',
    end_date: '',
    location: '',
  });

  // Event chat  
  const [chatEventId, setChatEventId] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<EventChatMsg[]>([]);
  const [chatInput, setChatInput] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  useEffect(() => {
    loadEvents();
  }, []);

  const loadEvents = async () => {
    setLoading(true);
    try {
      const { data } = await api.get('/events');
      setEvents(data);
    } finally {
      setLoading(false);
    }
  };

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.post('/events', {
      ...form,
      end_date: form.end_date || null,
      iteration_id: form.iteration_id || null,
    });
    setShowForm(false);
    setForm({ title: '', description: '', start_date: '', end_date: '', location: '', iteration_id: '' });
    loadEvents();
  };

  const participate = async (eventId: string, status: 'attending' | 'not_attending') => {
    await api.post(`/events/${eventId}/participate`, { status });
    loadEvents();
  };

  const formatDate = (d: string) => {
    return new Date(d).toLocaleDateString(language === 'ka' ? 'ka-GE' : 'ru-RU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const uploadEventPhoto = async (eventId: string, e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.[0]) return;
    const fd = new FormData();
    fd.append('file', e.target.files[0]);
    await api.post(`/events/${eventId}/photo`, fd);
    loadEvents();
  };

  const openEditEvent = (ev: Event) => {
    setEditEvent(ev);
    setEditForm({
      title: ev.title,
      description: ev.description || '',
      start_date: ev.start_date?.slice(0, 16) || '',
      end_date: ev.end_date?.slice(0, 16) || '',
      location: ev.location || '',
    });
  };

  const saveEditEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editEvent) return;
    await api.put(`/events/${editEvent.id}`, {
      ...editForm,
      end_date: editForm.end_date || null,
    });
    setEditEvent(null);
    loadEvents();
  };

  const deleteEvent = async (eventId: string) => {
    setDeleteConfirm(eventId);
  };

  const confirmDeleteEvent = async () => {
    if (!deleteConfirm) return;
    await api.delete(`/events/${deleteConfirm}`);
    setDeleteConfirm(null);
    loadEvents();
  };

  const openChat = async (eventId: string) => {
    setChatEventId(eventId);
    const { data } = await api.get(`/events/${eventId}/chat?limit=100`);
    setChatMessages(data);
    setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
  };

  const sendEventChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || !chatEventId) return;
    const { data } = await api.post(`/events/${chatEventId}/chat`, { content: chatInput.trim() });
    setChatMessages(prev => [...prev, data]);
    setChatInput('');
    setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
  };

  return (
    <div className={`${styles.page} page-enter`}>
      <div className={styles.header}>
        <h1>{lang.events.title}</h1>
        <button className="btn btn-primary" onClick={() => setShowForm(true)}>
          + {lang.events.create}
        </button>
      </div>

      {loading ? <CardSkeleton count={3} /> : (
      <div className={styles.grid}>
        {events.map(ev => {
          const myStatus = ev.participants?.find(p => p.user_id === user?.id)?.status;
          const attendCount = ev.participants?.filter(p => p.status === 'attending').length || 0;

          return (
            <div key={ev.id} className={`card ${styles.eventCard}`}>
              <div className={styles.eventDate}>
                <CalendarDays size={16} style={{ marginRight: 6 }} />{formatDate(ev.start_date)}
                {ev.end_date && <> — {formatDate(ev.end_date)}</>}
              </div>
              <h3>{ev.title}</h3>
              {ev.description && <p className={styles.eventDesc}>{ev.description}</p>}
              {ev.location && <p className={styles.eventLocation}><MapPin size={14} style={{ marginRight: 6 }} />{ev.location}</p>}

              <div className={styles.eventMeta}>
                <span className="badge badge-primary">
                  {attendCount} {lang.events.attending}
                </span>
              </div>

              {ev.photo_url && <img src={ev.photo_url} alt="" className={styles.eventPhoto} />}

              <div className={styles.eventActions}>
                <button
                  className={`btn btn-sm ${myStatus === 'attending' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => participate(ev.id, 'attending')}
                >
                  {lang.events.attend}
                </button>
                <button
                  className={`btn btn-sm ${myStatus === 'not_attending' ? 'btn-danger' : 'btn-secondary'}`}
                  onClick={() => participate(ev.id, 'not_attending')}
                >
                  {lang.events.notAttend}
                </button>
                <button className="btn btn-sm btn-ghost" onClick={() => openChat(ev.id)}>
                  {lang.chat.title}
                </button>
                <label className="btn btn-sm btn-ghost" style={{ cursor: 'pointer' }}>
                  <Camera size={16} />
                  <input type="file" accept="image/*" hidden onChange={e => uploadEventPhoto(ev.id, e)} />
                </label>
                {(ev.creator_id === user?.id || user?.role === 'admin') && <>
                  <button className="btn btn-sm btn-ghost" onClick={() => openEditEvent(ev)} aria-label={lang.common.edit}><Pencil size={16} /></button>
                  <button className="btn btn-sm btn-ghost" onClick={() => deleteEvent(ev.id)} aria-label={lang.common.delete}><Trash2 size={16} /></button>
                </>}
              </div>

              {/* Participants list */}
              {ev.participants && ev.participants.length > 0 && (
                <div className={styles.participants}>
                  {ev.participants.filter(p => p.status === 'attending').map(p => (
                    <span key={p.user_id} className={styles.participant}>
                      <UserRound size={14} style={{ marginRight: 6 }} />{p.user_name}
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
      )}

      {!loading && events.length === 0 && (
        <div className="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
          <h4>{lang.events.noEvents}</h4>
          <p>{lang.events.create}</p>
        </div>
      )}

      {/* Create modal */}
      {showForm && (
        <div className="modal-overlay" onClick={() => setShowForm(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>{lang.events.create}</h2>
            <form onSubmit={create} className={styles.form}>
              <input placeholder={lang.events.eventTitle} value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} required />
              <textarea placeholder={lang.events.description} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} rows={3} />
              <label>{lang.events.startDate}</label>
              <input type="datetime-local" value={form.start_date} onChange={e => setForm({ ...form, start_date: e.target.value })} required />
              <label>{lang.events.endDate}</label>
              <input type="datetime-local" value={form.end_date} onChange={e => setForm({ ...form, end_date: e.target.value })} />
              <input placeholder={lang.events.location} value={form.location} onChange={e => setForm({ ...form, location: e.target.value })} />
              <div className={styles.formActions}>
                <button type="button" className="btn btn-secondary" onClick={() => setShowForm(false)}>{lang.common.cancel}</button>
                <button type="submit" className="btn btn-primary">{lang.common.create}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit event modal */}
      {editEvent && (
        <div className="modal-overlay" onClick={() => setEditEvent(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h2>{lang.events.edit}</h2>
            <form onSubmit={saveEditEvent} className={styles.form}>
              <input placeholder={lang.events.eventTitle} value={editForm.title} onChange={e => setEditForm({ ...editForm, title: e.target.value })} required />
              <textarea placeholder={lang.events.description} value={editForm.description} onChange={e => setEditForm({ ...editForm, description: e.target.value })} rows={3} />
              <label>{lang.events.startDate}</label>
              <input type="datetime-local" value={editForm.start_date} onChange={e => setEditForm({ ...editForm, start_date: e.target.value })} required />
              <label>{lang.events.endDate}</label>
              <input type="datetime-local" value={editForm.end_date} onChange={e => setEditForm({ ...editForm, end_date: e.target.value })} />
              <input placeholder={lang.events.location} value={editForm.location} onChange={e => setEditForm({ ...editForm, location: e.target.value })} />
              <div className={styles.formActions}>
                <button type="button" className="btn btn-secondary" onClick={() => setEditEvent(null)}>{lang.common.cancel}</button>
                <button type="submit" className="btn btn-primary">{lang.common.save}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Event chat modal */}
      {chatEventId && (
        <div className="modal-overlay" onClick={() => setChatEventId(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 600, maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}>
            <h2>{lang.chat.title} — {events.find(e => e.id === chatEventId)?.title}</h2>
            <div className={styles.eventChatMessages}>
              {chatMessages.map(m => (
                <div key={m.id} className={styles.eventChatMsg}>
                  <strong>{m.user_name}</strong>
                  <span className={styles.chatTime}>{new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  <p>{m.is_deleted ? <em>[Удалено]</em> : m.content}</p>
                </div>
              ))}
              <div ref={chatEndRef} />
            </div>
            <form onSubmit={sendEventChat} className={styles.eventChatForm}>
              <input
                value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                placeholder={lang.chat.sendMessage}
                autoComplete="off"
              />
              <button type="submit" className="btn btn-primary btn-sm" disabled={!chatInput.trim()}>
                {lang.common.save}
              </button>
            </form>
            <button className="btn btn-secondary btn-sm" style={{ marginTop: 8 }} onClick={() => setChatEventId(null)}>{lang.common.close}</button>
          </div>
        </div>
      )}
      {deleteConfirm && (
        <ConfirmModal
          title={lang.events.deleteConfirm}
          message={lang.events.deleteConfirm}
          confirmLabel={lang.common.delete}
          cancelLabel={lang.common.cancel}
          onConfirm={confirmDeleteEvent}
          onCancel={() => setDeleteConfirm(null)}
        />
      )}
    </div>
  );
}
