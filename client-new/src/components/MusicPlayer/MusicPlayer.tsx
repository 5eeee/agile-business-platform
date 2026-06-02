import { useRef, useEffect, useCallback, useState, useMemo } from 'react';
import { useAppSelector, useAppDispatch } from '../../store/hooks';
import { togglePlay, nextTrack, prevTrack, setVolume, pause } from '../../store/slices/musicSlice';
import api from '../../api/client';
import styles from './MusicPlayer.module.css';

function debounce<T extends (...args: any[]) => any>(fn: T, ms: number) {
  let timer: ReturnType<typeof setTimeout>;
  return (...args: Parameters<T>) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

function fmt(sec: number) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export default function MusicPlayer() {
  const dispatch = useAppDispatch();
  const { tracks, currentIndex, isPlaying, volume, playlistName } = useAppSelector(s => s.music);
  const track = currentIndex >= 0 ? tracks[currentIndex] : null;
  const audioRef = useRef<HTMLAudioElement>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  // Sync audio play/pause with state
  useEffect(() => {
    const a = audioRef.current;
    if (!a || !track) return;
    if (isPlaying) {
      a.play().catch(() => {
        // If playback fails (e.g. 403/404), skip to next track
        dispatch(nextTrack());
      });
    } else {
      a.pause();
    }
  }, [isPlaying, track]);

  // Set volume
  useEffect(() => {
    if (audioRef.current) audioRef.current.volume = volume;
  }, [volume]);

  // Debounced listening_to status update via WebSocket + API fallback
  const updateListeningTo = useMemo(
    () => debounce((label: string) => {
      // Try WebSocket first (real-time broadcast to other users)
      try {
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        // Singleton WS stored on window to avoid reconnections
        const key = '__listeningWs';
        let ws = (window as any)[key] as WebSocket | undefined;
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'listening', track: label }));
        }
      } catch {}
      // API fallback for persistence
      api.put('/users/profile', { listening_to: label }).catch(() => {});
    }, 2000),
    []
  );

  useEffect(() => {
    if (track && isPlaying) {
      const label = track.artist ? `${track.artist} — ${track.title}` : track.title;
      updateListeningTo(label);
    } else if (!isPlaying) {
      updateListeningTo('');
    }
  }, [track, isPlaying, updateListeningTo]);

  // Throttle timeupdate to ~1/sec to avoid excessive re-renders
  const lastTimeRef = useRef(0);
  const handleTimeUpdate = useCallback(() => {
    const a = audioRef.current;
    if (!a) return;
    const now = performance.now();
    if (now - lastTimeRef.current < 1000) return;
    lastTimeRef.current = now;
    setCurrentTime(a.currentTime);
    setDuration(a.duration || 0);
  }, []);

  const handleSeek = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const a = audioRef.current;
    if (!a || !a.duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    a.currentTime = ratio * a.duration;
  }, []);

  if (!track) return null;

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className={styles.player}>
      {/* Track info */}
      <div className={styles.info}>
        <span className={styles.title}>{track.title}</span>
        {track.artist && <span className={styles.artist}>{track.artist}</span>}
      </div>

      {/* Controls */}
      <div className={styles.controls}>
        <button className={styles.ctrlBtn} onClick={() => dispatch(prevTrack())}>
          <svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14"><polygon points="19 20 9 12 19 4 19 20"/><line x1="5" y1="19" x2="5" y2="5" stroke="currentColor" strokeWidth="2"/></svg>
        </button>
        <button className={styles.playBtn} onClick={() => dispatch(togglePlay())}>
          {isPlaying ? (
            <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
          ) : (
            <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          )}
        </button>
        <button className={styles.ctrlBtn} onClick={() => dispatch(nextTrack())}>
          <svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19" stroke="currentColor" strokeWidth="2"/></svg>
        </button>
      </div>

      {/* Progress */}
      <div className={styles.progress}>
        <span className={styles.time}>{fmt(currentTime)}</span>
        <div className={styles.bar} onClick={handleSeek}>
          <div className={styles.barFill} style={{ width: `${progress}%` }} />
        </div>
        <span className={styles.time}>{fmt(duration)}</span>
      </div>

      {/* Volume */}
      <div className={styles.volume}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="14" height="14"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
        <input
          type="range" min="0" max="1" step="0.05" value={volume}
          onChange={e => dispatch(setVolume(parseFloat(e.target.value)))}
          className={styles.volSlider}
        />
      </div>

      {playlistName && <span className={styles.plBadge}>{playlistName}</span>}

      <audio
        ref={audioRef}
        src={track.file_url}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleTimeUpdate}
        onEnded={() => dispatch(nextTrack())}
        onError={() => dispatch(nextTrack())}
      />
    </div>
  );
}
