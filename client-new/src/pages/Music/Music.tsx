import { useState, useEffect, useRef } from 'react';
import { X, Loader2, CheckCircle2, AlertCircle, Info } from 'lucide-react';
import { useAppSelector, useAppDispatch } from '../../store/hooks';
import { setPlaylist, playTrack, pause } from '../../store/slices/musicSlice';
import { t } from '../../i18n';
import api from '../../api/client';
import styles from './Music.module.css';

interface Playlist {
  id: string;
  name: string;
  is_system: boolean;
  owner_id?: string;
  track_count: number;
}

interface Track {
  id: string;
  title: string;
  artist?: string;
  file_url: string;
  duration?: number;
  order: number;
}

export default function MusicPage() {
  const dispatch = useAppDispatch();
  const { user } = useAppSelector(s => s.auth);
  const { language } = useAppSelector(s => s.ui);
  const { currentIndex, isPlaying, playlistId: activeGlobalPl } = useAppSelector(s => s.music);
  const lang = t(language);

  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [activePl, setActivePl] = useState<string | null>(null);
  const [tracks, setTracks] = useState<Track[]>([]);
  const [newPlName, setNewPlName] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [search, setSearch] = useState('');
  const [showImport, setShowImport] = useState(false);
  const [importUrl, setImportUrl] = useState('');
  const [importText, setImportText] = useState('');
  const [importMode, setImportMode] = useState<'link' | 'text' | 'yandex'>('link');
  const [importYandexText, setImportYandexText] = useState('');
  const [yandexToken, setYandexToken] = useState('');
  const [yandexUrl, setYandexUrl] = useState('');
  const [yandexPlaylists, setYandexPlaylists] = useState<Array<{ owner: string; kind: string; title: string; track_count: number }>>([]);
  const [yandexSelected, setYandexSelected] = useState<{ owner: string; kind: string } | null>(null);
  const [yandexLoading, setYandexLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);
  const [importStatus, setImportStatus] = useState<'success' | 'error' | 'info' | 'warning' | null>(null);
  const [importProgress, setImportProgress] = useState<{current: number, total: number, title: string} | null>(null);
  const [importSkipped, setImportSkipped] = useState<string[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => { loadPlaylists(); }, []);

  useEffect(() => {
    if (playlists.length > 0 && !activePl) loadTracks(playlists[0].id);
  }, [playlists]);

  const loadPlaylists = () => {
    api.get('/music/playlists').then(r => setPlaylists(r.data)).catch(() => {});
  };

  const loadTracks = (plId: string) => {
    setActivePl(plId);
    api.get(`/music/playlists/${plId}/tracks`).then(r => setTracks(r.data)).catch(() => {});
  };

  const handleCreatePlaylist = async () => {
    if (!newPlName.trim()) return;
    await api.post('/music/playlists', { name: newPlName.trim() });
    setNewPlName('');
    setShowCreate(false);
    loadPlaylists();
  };

  const handleDeletePlaylist = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await api.delete(`/music/playlists/${id}`);
    if (activePl === id) { setActivePl(null); setTracks([]); }
    loadPlaylists();
  };

  const handleDeleteTrack = async (trackId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await api.delete(`/music/tracks/${trackId}`);
    if (activePl) loadTracks(activePl);
  };

  const handlePlay = (index: number) => {
    if (!activePl) return;
    const pl = playlists.find(p => p.id === activePl);
    dispatch(setPlaylist({ id: activePl, name: pl?.name || '', tracks }));
    dispatch(playTrack(index));
  };

  const handleImport = async () => {
    if (importMode === 'link' && !importUrl.trim()) return;
    if (importMode === 'text' && !importText.trim()) return;
    if (importMode === 'yandex' && !importYandexText.trim()) return;
    if (!activePl) return;
    const controller = new AbortController();
    abortRef.current = controller;
    setImporting(true);
    setImportResult(null);
    setImportStatus(null);
    setImportProgress(null);
    setImportSkipped([]);
    try {
      const isText = importMode === 'text' || importMode === 'yandex';
      const textBody = importMode === 'yandex' ? importYandexText.trim() : importText.trim();
      const response = await fetch(isText ? '/api/music/import-text' : '/api/music/import', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(isText
          ? { text: textBody, playlist_id: activePl }
          : { url: importUrl.trim(), playlist_id: activePl }),
        signal: controller.signal,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || lang.music.importError);
      }

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith('data: ')) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.type === 'progress') {
              setImportProgress({ current: event.current, total: event.total, title: event.title });
            } else if (event.type === 'skip') {
              setImportSkipped(prev => [...prev, event.title]);
            } else if (event.type === 'done') {
              setImportStatus('success');
              setImportResult(event.message);
              loadTracks(activePl);
              loadPlaylists();
            }
          } catch {}
        }
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        setImportResult(lang.music.importCancelled);
      } else {
        setImportStatus('error');
        setImportResult(err.message || lang.music.importError);
      }
    } finally {
      setImporting(false);
      setImportProgress(null);
      abortRef.current = null;
    }
  };

  const handleCancelImport = () => {
    abortRef.current?.abort();
    setImporting(false);
    setImportStatus('warning');
    setImportResult(lang.music.importCancelled);
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length || !activePl) return;
    const file = e.target.files[0];
    const fd = new FormData();
    fd.append('file', file);
    const uploadRes = await api.post('/music/upload', fd);
    await api.post(`/music/playlists/${activePl}/tracks`, {
      title: file.name.replace(/\.[^.]+$/, ''),
      file_url: uploadRes.data.file_url,
    });
    loadTracks(activePl);
  };

  const fmt = (sec?: number) => {
    if (!sec) return '';
    return `${Math.floor(sec / 60)}:${(sec % 60).toString().padStart(2, '0')}`;
  };

  const isActive = (idx: number) =>
    activeGlobalPl === activePl && currentIndex === idx && isPlaying;

  const filtered = search
    ? tracks.filter(t => t.title.toLowerCase().includes(search.toLowerCase()) || t.artist?.toLowerCase().includes(search.toLowerCase()))
    : tracks;

  const activePlObj = playlists.find(p => p.id === activePl);

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.topBar}>
        <h1 className={styles.title}>{lang.music.title}</h1>
        <div className={styles.actions}>
          {activePl && (
            <label className={styles.actionBtn} title={lang.music.upload}>
              <input type="file" accept="audio/*" onChange={handleUpload} hidden />
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="18" height="18"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            </label>
          )}
          {activePl && (
            <button className={styles.actionBtn} onClick={() => { setShowImport(true); setImportResult(null); setImportUrl(''); }} title={lang.music.import}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="18" height="18"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            </button>
          )}
          <button className={styles.actionBtn} onClick={() => { setShowCreate(!showCreate); }} title={lang.music.newPlaylist}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="18" height="18"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          </button>
        </div>
      </div>

      {/* Search */}
      <div className={styles.searchWrap}>
        <svg className={styles.searchIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor" width="16" height="16"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input
          className={styles.searchInput}
          placeholder={lang.music.searchMusic}
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {/* Create playlist */}
      {showCreate && (
        <div className={styles.createForm}>
          <input
            className={styles.createInput}
            placeholder={lang.music.playlistName}
            value={newPlName}
            onChange={e => setNewPlName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleCreatePlaylist()}
            autoFocus
          />
          <button className="btn btn-primary btn-sm" onClick={handleCreatePlaylist}>{lang.common.create}</button>
          <button className="btn btn-ghost btn-sm" onClick={() => setShowCreate(false)} aria-label={lang.common.close}><X size={14} /></button>
        </div>
      )}

      {/* Playlists */}
      <div className={styles.section}>
        <div className={styles.sectionHead}>
          <h2 className={styles.sectionTitle}>{lang.music.playlists}</h2>
        </div>
        <div className={styles.plGrid}>
          {playlists.map(pl => (
            <div
              key={pl.id}
              className={`${styles.plCard} ${activePl === pl.id ? styles.plCardActive : ''}`}
              onClick={() => loadTracks(pl.id)}
            >
              <div className={styles.plCover}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="32" height="32" className={styles.plCoverIcon}><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
                {activePl === pl.id && isPlaying && (
                  <div className={styles.plOverlay}><div className={styles.eqBars}><span /><span /><span /></div></div>
                )}
              </div>
              <div className={styles.plCardBody}>
                <span className={styles.plCardName}>{pl.name}</span>
                <span className={styles.plCardSub}>
                  {pl.is_system && <span className={styles.sysBadge}>SYS</span>}
                  {pl.track_count} {lang.music.tracks}
                </span>
              </div>
              {!pl.is_system && pl.owner_id === user?.id && (
                <button className={styles.plCardDel} onClick={(e) => handleDeletePlaylist(pl.id, e)} aria-label={lang.common.delete}>
                  <X size={14} />
                </button>
              )}
            </div>
          ))}
          {playlists.length === 0 && <p className={styles.empty}>{lang.common.noData}</p>}
        </div>
      </div>

      {/* Tracks */}
      <div className={styles.section}>
        {activePlObj && (
          <div className={styles.sectionHead}>
            <h2 className={styles.sectionTitle}>{activePlObj.name}</h2>
            <span className={styles.countBadge}>{tracks.length} {lang.music.tracks}</span>
          </div>
        )}
        <div className={styles.trackList}>
          {filtered.map((track, i) => {
            const realIdx = tracks.indexOf(track);
            const act = isActive(realIdx);
            return (
              <div
                key={track.id}
                className={`${styles.trackRow} ${act ? styles.trackRowActive : ''}`}
                onClick={() => act ? dispatch(pause()) : handlePlay(realIdx)}
              >
                <div className={styles.trackThumb}>
                  {act ? (
                    <div className={styles.eqBars}><span /><span /><span /></div>
                  ) : (
                    <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16" className={styles.playIcon}><polygon points="5 3 19 12 5 21 5 3"/></svg>
                  )}
                </div>
                <div className={styles.trackMeta}>
                  <span className={styles.trackName}>{track.title}</span>
                  {track.artist && <span className={styles.trackArtist}>{track.artist}</span>}
                </div>
                <span className={styles.trackDur}>{fmt(track.duration)}</span>
                <button className={styles.trackDel} onClick={(e) => handleDeleteTrack(track.id, e)}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="14" height="14"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                </button>
              </div>
            );
          })}
          {activePl && filtered.length === 0 && (
            <p className={styles.empty}>{search ? lang.music.nothingFound : lang.music.noTracks}</p>
          )}
          {!activePl && <p className={styles.empty}>{lang.music.selectPlaylist}</p>}
        </div>
      </div>

      {/* Import Modal */}
      {showImport && (
        <div className="modal-overlay" onClick={() => !importing && setShowImport(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 520 }}>
            <h2>{lang.music.importMusic}</h2>
            {/* Mode toggle */}
            <div style={{ display: 'flex', gap: 0, marginBottom: 12, borderRadius: 8, overflow: 'hidden', border: '1px solid var(--color-border)' }}>
              {(['link', 'text', 'yandex'] as const).map(mode => (
                <button
                  key={mode}
                  onClick={() => { setImportMode(mode); setImportResult(null); }}
                  disabled={importing}
                  style={{
                    flex: 1, padding: '6px 0', fontSize: 13, border: 'none', cursor: importing ? 'default' : 'pointer',
                    background: importMode === mode ? 'var(--color-primary, #e53e3e)' : 'transparent',
                    color: importMode === mode ? '#fff' : 'var(--color-text-muted)',
                    fontWeight: importMode === mode ? 600 : 400,
                    transition: 'all 0.2s',
                  }}
                >
                  {mode === 'link'
                    ? lang.music.link
                    : mode === 'text'
                    ? lang.music.text
                    : lang.music.yandexTab}
                </button>
              ))}
            </div>
            {importMode === 'yandex' ? (
              <>
                <div style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 10, lineHeight: 1.6 }}>
                  <b>1.</b> <a href="https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d" target="_blank" rel="noopener" style={{ color: 'var(--color-primary, #e53e3e)' }}>{lang.music.yandexClickHere}</a> {lang.music.yandexAllowAccess}<br/>
                  <b>2.</b> {lang.music.yandexCopyToken} (<code>access_token=</code>)<br/>
                  <b>3.</b> {lang.music.yandexPasteToken}
                </div>
                <input
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid var(--color-border)', marginBottom: 8, fontSize: 13 }}
                  placeholder={lang.music.yandexTokenPlaceholder}
                  value={yandexToken}
                  onChange={e => setYandexToken(e.target.value)}
                  disabled={importing || yandexLoading}
                  type="password"
                  autoFocus
                />
                <input
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid var(--color-border)', marginBottom: 8, fontSize: 13 }}
                  placeholder={lang.music.yandexPlaylistPlaceholder}
                  value={yandexUrl}
                  onChange={e => setYandexUrl(e.target.value)}
                  disabled={importing || yandexLoading}
                />
                <button
                  className="btn btn-secondary btn-sm"
                  style={{ marginTop: 4, marginBottom: 8 }}
                  disabled={!yandexToken.trim() || yandexLoading || importing}
                  onClick={async () => {
                    setYandexLoading(true);
                    setImportResult(null);
                    try {
                      const listRes = await fetch('/api/music/yandex-playlists', {
                        method: 'POST',
                        credentials: 'include',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ token: yandexToken.trim() }),
                      });
                      const listData = await listRes.json();
                      if (!listRes.ok) throw new Error(listData.detail || lang.common.error);
                      if (listData.playlists && listData.playlists.length > 0) {
                        setYandexPlaylists(listData.playlists);
                        setYandexSelected({ owner: listData.playlists[0].owner, kind: listData.playlists[0].kind });
                        setImportStatus('info');
                        setImportResult(`Найдено плейлистов: ${listData.playlists.length}. Выберите плейлист и нажмите "${lang.music.yandexExtract}".`);
                      } else {
                        setImportStatus('warning');
                        setImportResult('Плейлисты не найдены в аккаунте.');
                      }
                    } catch (err: any) {
                      setImportStatus('error');
                      setImportResult(err.message);
                    } finally {
                      setYandexLoading(false);
                    }
                  }}
                >
                  {yandexLoading ? lang.music.yandexLoading : 'Получить плейлисты'}
                </button>
                {yandexPlaylists.length > 0 && (
                  <select
                    style={{ width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid var(--color-border)', marginBottom: 8, fontSize: 13 }}
                    value={yandexSelected ? `${yandexSelected.owner}:${yandexSelected.kind}` : ''}
                    onChange={(e) => {
                      const [owner, kind] = e.target.value.split(':');
                      setYandexSelected({ owner, kind });
                    }}
                  >
                    {yandexPlaylists.map((p) => (
                      <option key={`${p.owner}:${p.kind}`} value={`${p.owner}:${p.kind}`}>
                        {p.title} ({p.track_count})
                      </option>
                    ))}
                  </select>
                )}
                <button
                  className="btn btn-secondary btn-sm"
                  style={{ marginBottom: 8 }}
                  disabled={!yandexToken.trim() || yandexLoading || importing || (!yandexSelected && !yandexUrl.trim())}
                  onClick={async () => {
                    setYandexLoading(true);
                    setImportResult(null);
                    try {
                      let r: Response;
                      if (yandexSelected) {
                        r = await fetch('/api/music/yandex-playlist-tracks', {
                          method: 'POST',
                          credentials: 'include',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ token: yandexToken.trim(), owner: yandexSelected.owner, kind: yandexSelected.kind }),
                        });
                      } else {
                        r = await fetch('/api/music/yandex-extract', {
                          method: 'POST',
                          credentials: 'include',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ token: yandexToken.trim(), url: yandexUrl.trim() }),
                        });
                      }
                      const data = await r.json();
                      if (!r.ok) throw new Error(data.detail || lang.common.error);
                      if (data.tracks && data.tracks.length > 0) {
                        setImportYandexText(data.tracks.join('\n'));
                        setImportStatus('success');
                        setImportResult(lang.music.yandexFoundTracks.replace('{count}', String(data.tracks.length)));
                      } else {
                        setImportStatus('warning');
                        setImportResult(lang.music.yandexNoTracks);
                      }
                    } catch (err: any) {
                      setImportStatus('error');
                      setImportResult(err.message);
                    } finally {
                      setYandexLoading(false);
                    }
                  }}
                >
                  {yandexLoading ? lang.music.yandexLoading : lang.music.yandexExtract}
                </button>
                {importYandexText && (
                  <textarea
                    style={{ width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid var(--color-border)', marginBottom: 8, fontSize: 13, minHeight: 100, resize: 'vertical', fontFamily: 'inherit' }}
                    value={importYandexText}
                    onChange={e => setImportYandexText(e.target.value)}
                    disabled={importing}
                  />
                )}
              </>
            ) : importMode === 'link' ? (
              <>
                <input
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid var(--color-border)', marginBottom: 8, fontSize: 13 }}
                  placeholder={lang.music.linkPlaceholder}
                  value={importUrl}
                  onChange={e => setImportUrl(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleImport()}
                  disabled={importing}
                  autoFocus
                />
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
                  {[
                    { color: '#22c55e', name: 'Spotify', host: 'open.spotify.com' },
                    { color: '#38bdf8', name: 'SoundCloud', host: 'soundcloud.com' },
                  ].map(s => (
                    <span key={s.host} style={{ fontSize: 11, padding: '3px 8px', borderRadius: 12, background: 'var(--color-bg-secondary, rgba(255,255,255,0.06))', color: 'var(--color-text-muted)', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: s.color }} /> {s.name}
                    </span>
                  ))}
                </div>
              </>
            ) : (
              <>
                <p style={{ fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 8 }}>
                  {lang.music.textFormatHint}
                </p>
                <textarea
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid var(--color-border)', marginBottom: 8, fontSize: 13, minHeight: 120, resize: 'vertical', fontFamily: 'inherit' }}
                  placeholder={language === 'ka'
                    ? 'Queen - Bohemian Rhapsody\nNirvana - Smells Like Teen Spirit\n...'
                    : 'Queen - Bohemian Rhapsody\nNirvana - Smells Like Teen Spirit\n...'}
                  value={importText}
                  onChange={e => setImportText(e.target.value)}
                  disabled={importing}
                  autoFocus
                />
                <p style={{ fontSize: 11, color: 'var(--color-text-muted)', marginBottom: 12, lineHeight: 1.5 }}>
                  {lang.music.soundcloudSearch}
                </p>
              </>
            )}
            {importResult && (
              <div style={{ padding: '8px 12px', borderRadius: 6, background:
                importStatus === 'success' ? 'var(--color-success-bg, rgba(34,197,94,0.1))'
                : importStatus === 'warning' ? 'var(--color-warning-bg, rgba(234,179,8,0.12))'
                : importStatus === 'info' ? 'var(--color-surface, rgba(148,163,184,0.12))'
                : 'var(--color-error-bg, rgba(239,68,68,0.1))',
                marginBottom: 12, fontSize: 13, display: 'flex', alignItems: 'center', gap: 8 }}>
                {importStatus === 'success' && <CheckCircle2 size={16} color="#16a34a" />}
                {importStatus === 'warning' && <AlertCircle size={16} color="#eab308" />}
                {importStatus === 'info' && <Info size={16} color="#3b82f6" />}
                {importStatus === 'error' && <AlertCircle size={16} color="#ef4444" />}
                <span>{importResult}</span>
              </div>
            )}
            {importSkipped.length > 0 && (
              <div style={{ padding: '8px 12px', borderRadius: 6, background: 'var(--color-warning-bg, rgba(234,179,8,0.12))', marginBottom: 12, fontSize: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, fontWeight: 500 }}>
                  <AlertCircle size={14} color="#eab308" />
                  <span>Не найдены ({importSkipped.length}):</span>
                </div>
                <div style={{ color: 'var(--color-text-muted)', lineHeight: 1.6 }}>
                  {importSkipped.map((name, i) => <div key={i}>{name}</div>)}
                </div>
              </div>
            )}
            {importing && importProgress && (
              <div style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 6 }}>
                  <span>Progress: {importProgress.current} / {importProgress.total}</span>
                  <span style={{ maxWidth: '60%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{importProgress.title}</span>
                </div>
                <div style={{ height: 6, borderRadius: 3, background: 'var(--color-bg-secondary, rgba(255,255,255,0.1))' }}>
                  <div style={{
                    height: '100%',
                    borderRadius: 3,
                    background: 'var(--color-primary, #e53e3e)',
                    width: `${(importProgress.current / importProgress.total) * 100}%`,
                    transition: 'width 0.3s ease',
                  }} />
                </div>
              </div>
            )}
            {importing && !importProgress && (
              <div style={{ padding: '8px 12px', fontSize: 13, color: 'var(--color-text-muted)', marginBottom: 12 }}>
                {lang.music.analyzing}
              </div>
            )}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary btn-sm" onClick={importing ? handleCancelImport : () => setShowImport(false)}>
                {importing ? lang.common.cancel : lang.common.close}
              </button>
              <button className="btn btn-primary btn-sm" onClick={handleImport} disabled={importing || (importMode === 'link' ? !importUrl.trim() : importMode === 'text' ? !importText.trim() : !importYandexText.trim())}>
                {importing ? <Loader2 size={16} style={{ verticalAlign: 'middle' }} /> : lang.music.importBtn}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
