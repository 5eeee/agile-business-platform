import { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { useAppSelector } from '../../store/hooks';
import { t } from '../../i18n';
import api from '../../api/client';
import { CardSkeleton } from '../../components/Skeleton/Skeleton';
import styles from './Places.module.css';

interface Place {
  id: string;
  name: string;
  description?: string;
  country?: string;
  city?: string;
  latitude?: number;
  longitude?: number;
  photo_url?: string;
  video_url?: string;
  is_default: boolean;
  created_at: string;
}

export default function PlacesPage() {
  const { user } = useAppSelector(s => s.auth);
  const { language } = useAppSelector(s => s.ui);
  const lang = t(language);

  const [places, setPlaces] = useState<Place[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', description: '', country: '', city: '', latitude: '', longitude: '' });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadPlaces();
  }, []);

  const loadPlaces = () => {
    setLoading(true);
    api.get('/places').then(r => setPlaces(r.data)).catch(() => {}).finally(() => setLoading(false));
  };

  const handleCreate = async () => {
    if (!form.name) return;
    await api.post('/places', {
      ...form,
      latitude: form.latitude ? parseFloat(form.latitude) : null,
      longitude: form.longitude ? parseFloat(form.longitude) : null,
    });
    setForm({ name: '', description: '', country: '', city: '', latitude: '', longitude: '' });
    setShowForm(false);
    loadPlaces();
  };

  const handleDelete = async (id: string) => {
    await api.delete(`/places/${id}`);
    loadPlaces();
  };

  const handleInitDefaults = async () => {
    await api.post('/places/init-defaults');
    loadPlaces();
  };

  return (
    <div className={`${styles.page} page-enter`}>
      <div className={styles.header}>
        <h1>{lang.places.title}</h1>
        {user?.role === 'admin' && (
          <div className={styles.actions}>
            <button className="btn btn-secondary btn-sm" onClick={handleInitDefaults}>
              {lang.places.loadDefaults}
            </button>
            <button className="btn btn-primary btn-sm" onClick={() => setShowForm(!showForm)}>
              + {lang.places.add}
            </button>
          </div>
        )}
      </div>

      {showForm && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className={styles.form}>
            <input className="input" placeholder={lang.places.name} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
            <input className="input" placeholder={lang.places.country} value={form.country} onChange={e => setForm({ ...form, country: e.target.value })} />
            <input className="input" placeholder={lang.places.city} value={form.city} onChange={e => setForm({ ...form, city: e.target.value })} />
            <textarea className="input" placeholder={lang.places.description} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} rows={3} />
            <div className={styles.formRow}>
              <input className="input" placeholder="Latitude" type="number" step="any" value={form.latitude} onChange={e => setForm({ ...form, latitude: e.target.value })} />
              <input className="input" placeholder="Longitude" type="number" step="any" value={form.longitude} onChange={e => setForm({ ...form, longitude: e.target.value })} />
            </div>
            <button className="btn btn-primary" onClick={handleCreate}>{lang.common.create}</button>
          </div>
        </div>
      )}

      <div className={styles.grid}>
        {loading ? <CardSkeleton count={4} /> : places.length === 0 ? (
          <div className="empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
            <h4>{lang.common.noData}</h4>
          </div>
        ) : (
          places.map(place => (
            <div key={place.id} className={`card ${styles.placeCard}`}>
              {place.photo_url && (
                <div className={styles.photo}>
                  <img src={place.photo_url} alt={place.name} />
                </div>
              )}
              {!place.photo_url && (
                <div className={styles.photoPlaceholder}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="32" height="32"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                </div>
              )}
              {place.video_url && (
                <div className={styles.video}>
                  <video src={place.video_url} muted autoPlay loop playsInline />
                </div>
              )}
              <div className={styles.placeInfo}>
                <h3>{place.name}</h3>
                <p className={styles.location}>
                  {[place.city, place.country].filter(Boolean).join(', ')}
                </p>
                {place.description && <p className={styles.desc}>{place.description}</p>}
                {place.latitude && place.longitude && (
                  <div className={styles.mapEmbed}>
                    <iframe
                      title={place.name}
                      width="100%"
                      height="180"
                      frameBorder="0"
                      style={{ border: 0, borderRadius: 8 }}
                      src={`https://www.openstreetmap.org/export/embed.html?bbox=${place.longitude - 0.05},${place.latitude - 0.03},${place.longitude + 0.05},${place.latitude + 0.03}&layer=mapnik&marker=${place.latitude},${place.longitude}`}
                    />
                  </div>
                )}
              </div>
              {user?.role === 'admin' && (
                <button className={styles.deleteBtn} onClick={() => handleDelete(place.id)} aria-label={lang.common.delete}>
                  <X size={14} />
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
