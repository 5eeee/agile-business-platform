# API маршруты для музыки
import uuid
import asyncio
import tempfile
import os
import re
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import Optional, List

from app.database import get_db, async_session
from app.models.music import Playlist, PlaylistTrack
from app.models.user import User
from app.middleware.auth import get_current_user, require_admin
from app.services.s3 import upload_file_to_s3, get_s3_client, ensure_bucket
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/music", tags=["Музыка"])


class PlaylistCreate(BaseModel):
    name: str


class TrackAdd(BaseModel):
    title: str
    artist: Optional[str] = None
    file_url: str
    duration: Optional[int] = None


@router.get("/playlists")
async def list_playlists(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Список плейлистов: системные + личные пользователя"""
    result = await db.execute(
        select(Playlist).where(
            (Playlist.is_system == True) | (Playlist.owner_id == user.id)
        ).options(selectinload(Playlist.tracks)).order_by(Playlist.created_at)
    )
    playlists = result.scalars().all()
    return [
        {
            "id": str(p.id), "name": p.name,
            "is_system": p.is_system,
            "owner_id": str(p.owner_id) if p.owner_id else None,
            "track_count": len(p.tracks) if p.tracks else 0,
            "created_at": str(p.created_at),
        }
        for p in playlists
    ]


@router.post("/playlists", status_code=201)
async def create_playlist(
    data: PlaylistCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Создание личного плейлиста"""
    playlist = Playlist(name=data.name, owner_id=user.id, is_system=False)
    db.add(playlist)
    await db.commit()
    await db.refresh(playlist)
    return {"id": str(playlist.id), "name": playlist.name}


@router.post("/playlists/system", status_code=201)
async def create_system_playlist(
    data: PlaylistCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Создание системного плейлиста (только админ)"""
    playlist = Playlist(name=data.name, is_system=True)
    db.add(playlist)
    await db.commit()
    await db.refresh(playlist)
    return {"id": str(playlist.id), "name": playlist.name}


@router.get("/playlists/{playlist_id}/tracks")
async def get_playlist_tracks(
    playlist_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Получение треков плейлиста"""
    result = await db.execute(select(Playlist).where(Playlist.id == uuid.UUID(playlist_id)))
    playlist = result.scalar_one_or_none()
    if not playlist:
        raise HTTPException(status_code=404, detail="Плейлист не найден")
    if not playlist.is_system and playlist.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")

    result = await db.execute(
        select(PlaylistTrack)
        .where(PlaylistTrack.playlist_id == uuid.UUID(playlist_id))
        .order_by(PlaylistTrack.order)
    )
    tracks = result.scalars().all()
    return [
        {
            "id": str(t.id), "title": t.title, "artist": t.artist,
            "file_url": t.file_url, "duration": t.duration, "order": t.order,
        }
        for t in tracks
    ]


@router.post("/playlists/{playlist_id}/tracks", status_code=201)
async def add_track(
    playlist_id: str,
    data: TrackAdd,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Добавление трека в плейлист"""
    result = await db.execute(select(Playlist).where(Playlist.id == uuid.UUID(playlist_id)))
    playlist = result.scalar_one_or_none()
    if not playlist:
        raise HTTPException(status_code=404, detail="Плейлист не найден")
    if playlist.is_system and user.role != "admin":
        raise HTTPException(status_code=403, detail="Только админ может редактировать системные плейлисты")
    if not playlist.is_system and playlist.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")

    # Определяем порядок
    count_result = await db.execute(
        select(PlaylistTrack).where(PlaylistTrack.playlist_id == uuid.UUID(playlist_id))
    )
    order = len(count_result.scalars().all())

    track = PlaylistTrack(
        playlist_id=uuid.UUID(playlist_id),
        title=data.title, artist=data.artist,
        file_url=data.file_url, duration=data.duration,
        order=order,
    )
    db.add(track)
    await db.commit()
    await db.refresh(track)
    return {"id": str(track.id), "title": track.title}


@router.delete("/tracks/{track_id}")
async def delete_track(
    track_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Удаление трека"""
    result = await db.execute(select(PlaylistTrack).where(PlaylistTrack.id == uuid.UUID(track_id)))
    track = result.scalar_one_or_none()
    if not track:
        raise HTTPException(status_code=404, detail="Трек не найден")
    # Проверяем владельца плейлиста
    pl_result = await db.execute(select(Playlist).where(Playlist.id == track.playlist_id))
    playlist = pl_result.scalar_one_or_none()
    if playlist and not playlist.is_system and playlist.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")
    if playlist and playlist.is_system and user.role != "admin":
        raise HTTPException(status_code=403, detail="Нет доступа")

    await db.delete(track)
    await db.commit()
    return {"message": "Трек удалён"}


@router.post("/upload")
async def upload_audio(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Загрузка аудиофайла"""
    if not file.content_type or not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Только аудиофайлы")
    url = await upload_file_to_s3(file, f"music/{user.id}")
    return {"file_url": url, "filename": file.filename}


@router.delete("/playlists/{playlist_id}")
async def delete_playlist(
    playlist_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Удаление плейлиста"""
    result = await db.execute(select(Playlist).where(Playlist.id == uuid.UUID(playlist_id)))
    playlist = result.scalar_one_or_none()
    if not playlist:
        raise HTTPException(status_code=404, detail="Плейлист не найден")
    if playlist.is_system and user.role != "admin":
        raise HTTPException(status_code=403, detail="Нет доступа")
    if not playlist.is_system and playlist.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")

    await db.delete(playlist)
    await db.commit()
    return {"message": "Плейлист удалён"}


@router.post("/init-defaults", status_code=200)
async def init_default_playlists(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Создание системных плейлистов по умолчанию (ТЗ 3.14.2)"""
    defaults = ["Рабочий фокус", "Вайб Грузии", "Балканский вечер"]
    created = []
    for name in defaults:
        existing = await db.execute(select(Playlist).where(Playlist.name == name, Playlist.is_system == True))
        if existing.scalar_one_or_none():
            continue
        pl = Playlist(name=name, is_system=True)
        db.add(pl)
        created.append(name)
    await db.commit()
    return {"message": f"Создано {len(created)} плейлистов", "created": created}


class ImportRequest(BaseModel):
    url: str
    playlist_id: str


class YandexExtractRequest(BaseModel):
    token: str
    url: str


class YandexPlaylistsRequest(BaseModel):
    token: str


class YandexPlaylistTracksRequest(BaseModel):
    token: str
    owner: str
    kind: str


async def _yandex_verify_and_get_uid(token: str) -> str:
    import httpx
    headers = {'Authorization': f'OAuth {token}'}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get('https://api.music.yandex.net/account/status', headers=headers)
        if r.status_code == 401:
            raise HTTPException(status_code=401, detail="Неверный токен Яндекс.Музыки")
        acc_data = r.json().get('result', {})
        uid = str(acc_data.get('account', {}).get('uid') or "")
        if not uid:
            raise HTTPException(status_code=401, detail="Не удалось получить uid пользователя")
        return uid


@router.post("/yandex-playlists")
async def yandex_list_playlists(data: YandexPlaylistsRequest):
    """Return user playlists to allow picker-based UX instead of raw URL parsing."""
    import httpx

    token = data.token.strip()
    uid = await _yandex_verify_and_get_uid(token)
    headers = {'Authorization': f'OAuth {token}'}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f'https://api.music.yandex.net/users/{uid}/playlists/list', headers=headers)
        if r.status_code != 200:
            raise HTTPException(status_code=400, detail="Не удалось получить плейлисты")
        playlists = r.json().get('result', [])
        out = []
        for p in playlists:
            out.append({
                "owner": str(p.get("owner", {}).get("uid", uid)),
                "kind": str(p.get("kind", "")),
                "title": p.get("title", "Без названия"),
                "track_count": int(p.get("trackCount", 0) or 0),
                "cover_uri": p.get("cover", {}).get("uri") if isinstance(p.get("cover"), dict) else None,
            })
        return {"playlists": out}


@router.post("/yandex-playlist-tracks")
async def yandex_playlist_tracks(data: YandexPlaylistTracksRequest):
    """Extract tracks from concrete owner/kind playlist selection."""
    import httpx

    token = data.token.strip()
    owner = data.owner.strip()
    kind = data.kind.strip()
    if not owner or not kind:
        raise HTTPException(status_code=400, detail="owner и kind обязательны")

    await _yandex_verify_and_get_uid(token)
    headers = {'Authorization': f'OAuth {token}'}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f'https://api.music.yandex.net/users/{owner}/playlists/{kind}',
            headers=headers,
            params={'rich-tracks': 'true'}
        )
        if r.status_code != 200:
            raise HTTPException(status_code=404, detail="Плейлист не найден")
        tracks_info = r.json().get('result', {}).get('tracks', [])
        result = []
        for t in tracks_info:
            track = t.get('track', t)
            title = track.get('title', '')
            artists = track.get('artists', [])
            artist = ', '.join(a.get('name', '') for a in artists) if artists else ''
            if title:
                result.append(f"{artist} - {title}" if artist else title)
        if not result:
            raise HTTPException(status_code=404, detail="Треки не найдены в плейлисте")
        return {"tracks": result, "text": '\n'.join(result)}


@router.post("/yandex-extract")
async def yandex_extract_tracks(data: YandexExtractRequest):
    """Extract track names from Yandex Music playlist using user's OAuth token."""
    import httpx

    token = data.token.strip()
    url = data.url.strip()
    headers = {'Authorization': f'OAuth {token}'}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Verify token
            r = await client.get('https://api.music.yandex.net/account/status', headers=headers)
            if r.status_code == 401:
                raise HTTPException(status_code=401, detail="Неверный токен Яндекс.Музыки")
            acc_data = r.json().get('result', {})
            uid = acc_data.get('account', {}).get('uid')
            if not uid:
                raise HTTPException(status_code=401, detail="Не удалось получить uid пользователя")

            # Parse URL to determine playlist type
            tracks_info = []

            # Format: /users/USER/playlists/KIND
            m = re.search(r'music\.yandex\.\w+/users/([^/]+)/playlists/(\d+)', url)
            if m:
                owner, kind = m.group(1), m.group(2)
                r = await client.get(
                    f'https://api.music.yandex.net/users/{owner}/playlists/{kind}',
                    headers=headers, params={'rich-tracks': 'true'}
                )
                if r.status_code == 200:
                    tracks_info = r.json().get('result', {}).get('tracks', [])

            # Format: /playlists/UUID (shared)
            if not tracks_info:
                m2 = re.search(r'playlists/([0-9a-f-]{36})', url)
                if m2:
                    playlist_uuid = m2.group(1)
                    # Try to find playlist via user's own playlists or API
                    r = await client.get(
                        f'https://api.music.yandex.net/users/{uid}/playlists',
                        headers=headers
                    )
                    if r.status_code == 200:
                        playlists = r.json().get('result', [])
                        for pl in playlists:
                            # Check if this playlist's UUID matches
                            pl_kind = pl.get('kind')
                            r2 = await client.get(
                                f'https://api.music.yandex.net/users/{uid}/playlists/{pl_kind}',
                                headers=headers, params={'rich-tracks': 'true'}
                            )
                            if r2.status_code == 200:
                                pl_data = r2.json().get('result', {})
                                if pl_data.get('playlistUuid') == playlist_uuid:
                                    tracks_info = pl_data.get('tracks', [])
                                    break

            # If still no tracks, try fetching all user's playlists as a fallback
            if not tracks_info and not m:
                # Maybe user just wants their liked tracks or a specific playlist
                r = await client.get(
                    f'https://api.music.yandex.net/users/{uid}/playlists',
                    headers=headers
                )
                if r.status_code == 200:
                    playlists = r.json().get('result', [])
                    playlist_list = [{'kind': p.get('kind'), 'title': p.get('title'),
                                      'track_count': p.get('trackCount', 0)} for p in playlists]
                    return {"tracks": [], "playlists": playlist_list,
                            "message": "Не удалось определить плейлист из URL. Вот список ваших плейлистов."}

            # Extract track names
            result = []
            for t in tracks_info:
                track = t.get('track', t)
                title = track.get('title', '')
                artists = track.get('artists', [])
                artist = ', '.join(a.get('name', '') for a in artists) if artists else ''
                if title:
                    result.append(f"{artist} - {title}" if artist else title)

            if not result:
                raise HTTPException(status_code=404, detail="Треки не найдены в плейлисте")

            return {"tracks": result, "text": '\n'.join(result)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Yandex extract error: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")


# Supported URL patterns for import
SUPPORTED_DOMAINS = [
    'soundcloud.com',
    'open.spotify.com',
]


def _ytdlp_extract(url: str) -> list[dict]:
    """Extract audio info from URL using yt-dlp (sync, run in thread)."""
    import yt_dlp

    entries = []
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'skip_download': True,
        'ignoreerrors': True,
        'format': 'bestaudio/best',
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if not info:
            return []

        # Playlist or single track
        items = info.get('entries', [info]) if 'entries' in info else [info]
        for item in items:
            if item is None:
                continue

            entries.append({
                'title': item.get('title', 'Unknown'),
                'artist': item.get('artist') or item.get('uploader') or item.get('creator') or '',
                'duration': item.get('duration'),
                'webpage_url': item.get('webpage_url') or item.get('url') or url,
            })

    return entries


def _spotify_get_token() -> str:
    """Get Spotify access token via Client Credentials flow."""
    import httpx
    import base64
    creds = base64.b64encode(
        f"{settings.SPOTIFY_CLIENT_ID}:{settings.SPOTIFY_CLIENT_SECRET}".encode()
    ).decode()
    with httpx.Client(timeout=15) as client:
        r = client.post(
            'https://accounts.spotify.com/api/token',
            data={'grant_type': 'client_credentials'},
            headers={'Authorization': f'Basic {creds}'},
        )
        r.raise_for_status()
        return r.json()['access_token']


def _spotify_extract(url: str) -> list[dict]:
    """Extract track metadata from Spotify URL."""
    import httpx
    token = _spotify_get_token()
    headers = {'Authorization': f'Bearer {token}'}

    # Parse Spotify URL: track, album, or playlist
    # https://open.spotify.com/track/ID
    # https://open.spotify.com/album/ID
    # https://open.spotify.com/playlist/ID
    match = re.search(r'open\.spotify\.com/(track|album|playlist)/([a-zA-Z0-9]+)', url)
    if not match:
        raise ValueError("Неверный Spotify URL")

    item_type, item_id = match.groups()
    entries = []

    with httpx.Client(timeout=15) as client:
        if item_type == 'track':
            r = client.get(f'https://api.spotify.com/v1/tracks/{item_id}', headers=headers)
            r.raise_for_status()
            t = r.json()
            entries.append({
                'title': t['name'],
                'artist': ', '.join(a['name'] for a in t.get('artists', [])),
                'duration': t.get('duration_ms', 0) // 1000,
                'search_query': f"{t['name']} {t['artists'][0]['name']}" if t.get('artists') else t['name'],
            })
        elif item_type == 'album':
            r = client.get(f'https://api.spotify.com/v1/albums/{item_id}/tracks', headers=headers, params={'limit': 50})
            r.raise_for_status()
            album_r = client.get(f'https://api.spotify.com/v1/albums/{item_id}', headers=headers)
            album_name = album_r.json().get('name', '') if album_r.status_code == 200 else ''
            for t in r.json().get('items', []):
                artist = ', '.join(a['name'] for a in t.get('artists', []))
                entries.append({
                    'title': t['name'],
                    'artist': artist,
                    'duration': t.get('duration_ms', 0) // 1000,
                    'search_query': f"{t['name']} {artist}",
                })
        elif item_type == 'playlist':
            r = client.get(f'https://api.spotify.com/v1/playlists/{item_id}/tracks', headers=headers, params={'limit': 50})
            r.raise_for_status()
            for item in r.json().get('items', []):
                t = item.get('track')
                if not t:
                    continue
                artist = ', '.join(a['name'] for a in t.get('artists', []))
                entries.append({
                    'title': t['name'],
                    'artist': artist,
                    'duration': t.get('duration_ms', 0) // 1000,
                    'search_query': f"{t['name']} {artist}",
                })

    return entries


MIN_AUDIO_SIZE = 500 * 1024  # 500 KB — reject clips/previews smaller than this


def _ytdlp_search_download(query: str) -> tuple[bytes, str]:
    """Search SoundCloud for a track by query and download it.
    Tries multiple query variations and rejects files smaller than MIN_AUDIO_SIZE."""
    import yt_dlp
    import time

    # Build query variations: original, title-only, simplified
    queries = [query]
    if ' - ' in query:
        artist, title = query.split(' - ', 1)
        queries.append(title.strip())  # just the title
        queries.append(f"{title.strip()} {artist.strip()}")  # title first, then artist

    last_err = None
    for q in queries:
        for attempt in range(2):
            if attempt > 0:
                time.sleep(2)
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    out_tmpl = os.path.join(tmpdir, '%(id)s.%(ext)s')
                    ydl_opts = {
                        'quiet': True,
                        'no_warnings': True,
                        'format': 'bestaudio/best',
                        'outtmpl': out_tmpl,
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '192',
                        }],
                        'noplaylist': True,
                        'default_search': 'scsearch',
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([q])

                    for fname in os.listdir(tmpdir):
                        if fname.endswith('.mp3'):
                            fpath = os.path.join(tmpdir, fname)
                            data = open(fpath, 'rb').read()
                            if len(data) >= MIN_AUDIO_SIZE:
                                return data, 'mp3'
                            else:
                                last_err = ValueError(f"File too small ({len(data)//1024}KB), likely a preview")
                                logger.info(f"Skipping small file for '{q}' ({len(data)//1024}KB)")
            except Exception as e:
                last_err = e
                logger.warning(f"Search download failed for '{q}': {e}")
                continue

    raise ValueError(f"Не удалось найти аудио для: {query} ({last_err})")


def _ytdlp_download_one(url: str) -> tuple[bytes, str]:
    """Download single track from URL using yt-dlp + ffmpeg, return (bytes, 'mp3')."""
    import yt_dlp

    with tempfile.TemporaryDirectory() as tmpdir:
        out_tmpl = os.path.join(tmpdir, '%(id)s.%(ext)s')
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'bestaudio/best',
            'outtmpl': out_tmpl,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'noplaylist': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Find the output mp3 file
        for fname in os.listdir(tmpdir):
            if fname.endswith('.mp3'):
                fpath = os.path.join(tmpdir, fname)
                with open(fpath, 'rb') as f:
                    return f.read(), 'mp3'

    raise ValueError("yt-dlp не смог скачать аудио")


class TextImportRequest(BaseModel):
    text: str
    playlist_id: str


@router.post("/import-text")
async def import_text_tracks(
    data: TextImportRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Import tracks by text: each line is 'Artist - Title' or just 'Title'. Searches SoundCloud."""
    result = await db.execute(select(Playlist).where(Playlist.id == uuid.UUID(data.playlist_id)))
    playlist = result.scalar_one_or_none()
    if not playlist:
        raise HTTPException(status_code=404, detail="Плейлист не найден")
    if playlist.is_system and user.role != "admin":
        raise HTTPException(status_code=403, detail="Нет доступа")
    if not playlist.is_system and playlist.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")

    lines = [l.strip() for l in data.text.strip().splitlines() if l.strip()]
    if not lines:
        raise HTTPException(status_code=400, detail="Нет треков для импорта")

    entries = []
    for line in lines[:50]:
        # Parse "Artist - Title" or just "Title"
        if ' - ' in line:
            artist, title = line.split(' - ', 1)
            entries.append({'title': title.strip(), 'artist': artist.strip(), 'search_query': line})
        else:
            entries.append({'title': line, 'artist': '', 'search_query': line})

    playlist_id = playlist.id
    user_id = user.id

    async def generate():
        yield f"data: {json.dumps({'type': 'start', 'total': len(entries)})}\n\n"

        imported = []
        s3 = get_s3_client()
        ensure_bucket()

        async with async_session() as session:
            count_result = await session.execute(
                select(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist_id)
            )
            order = len(count_result.scalars().all())

            for i, entry in enumerate(entries):
                if await request.is_disconnected():
                    break

                yield f"data: {json.dumps({'type': 'progress', 'current': i + 1, 'total': len(entries), 'title': entry['title']})}\n\n"

                try:
                    query = entry['search_query']
                    content, ext = await asyncio.to_thread(_ytdlp_search_download, query)
                    key = f"music/{user_id}/{uuid.uuid4().hex}.{ext}"
                    s3.put_object(
                        Bucket=settings.S3_BUCKET,
                        Key=key,
                        Body=content,
                        ContentType="audio/mpeg",
                    )
                    file_url = f"/files/{key}"

                    track = PlaylistTrack(
                        playlist_id=playlist_id,
                        title=entry['title'],
                        artist=entry.get('artist'),
                        file_url=file_url,
                        duration=entry.get('duration'),
                        order=order,
                    )
                    session.add(track)
                    order += 1
                    imported.append(entry['title'])
                except Exception as e:
                    logger.warning(f"Failed to import track {entry.get('title', '?')}: {e}")
                    yield f"data: {json.dumps({'type': 'skip', 'title': entry.get('title', '?'), 'reason': str(e)})}\n\n"
                    continue

            await session.commit()

        msg = f"Импортировано {len(imported)} из {len(entries)} треков"
        yield f"data: {json.dumps({'type': 'done', 'message': msg, 'imported_count': len(imported), 'total_found': len(entries), 'imported_titles': imported})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/import")
async def import_tracks(
    data: ImportRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Import tracks from Spotify, Yandex Music, SoundCloud. Returns SSE stream."""
    # Check playlist access
    result = await db.execute(select(Playlist).where(Playlist.id == uuid.UUID(data.playlist_id)))
    playlist = result.scalar_one_or_none()
    if not playlist:
        raise HTTPException(status_code=404, detail="Плейлист не найден")
    if playlist.is_system and user.role != "admin":
        raise HTTPException(status_code=403, detail="Нет доступа")
    if not playlist.is_system and playlist.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")

    url = data.url.strip()
    is_spotify = 'open.spotify.com' in url
    is_yandex = 'music.yandex.' in url

    # Extract track info based on source
    try:
        if is_spotify:
            entries = await asyncio.to_thread(_spotify_extract, url)
        else:
            # SoundCloud or Yandex — try yt-dlp first
            try:
                entries = await asyncio.to_thread(_ytdlp_extract, url)
            except Exception:
                entries = []
            # If Yandex failed (geo-block), return clear error
            if not entries and is_yandex:
                raise HTTPException(
                    status_code=422,
                    detail='Яндекс Музыка недоступна с сервера (гео-блокировка). Используйте режим "Текст" — скопируйте названия треков из Яндекса и вставьте вручную.'
                )
    except Exception as e:
        logger.error(f"Extract error: {e}")
        raise HTTPException(status_code=400, detail=f"Не удалось получить треки: {str(e)}")

    if not entries:
        raise HTTPException(status_code=404, detail="Треки не найдены по этой ссылке")

    # Limit to 50 tracks per import
    entries = entries[:50]
    playlist_id = playlist.id
    user_id = user.id
    # Spotify/Yandex entries use search_query for SoundCloud download
    use_search = is_spotify or (is_yandex and entries[0].get('search_query'))

    async def generate():
        yield f"data: {json.dumps({'type': 'start', 'total': len(entries)})}\n\n"

        imported = []
        s3 = get_s3_client()
        ensure_bucket()

        async with async_session() as session:
            count_result = await session.execute(
                select(PlaylistTrack).where(PlaylistTrack.playlist_id == playlist_id)
            )
            order = len(count_result.scalars().all())

            for i, entry in enumerate(entries):
                if await request.is_disconnected():
                    break

                yield f"data: {json.dumps({'type': 'progress', 'current': i + 1, 'total': len(entries), 'title': entry['title']})}\n\n"

                try:
                    if use_search:
                        # Search and download from SoundCloud
                        query = entry.get('search_query', f"{entry['title']} {entry.get('artist', '')}")
                        content, ext = await asyncio.to_thread(_ytdlp_search_download, query)
                    else:
                        # Direct download (SoundCloud URL)
                        content, ext = await asyncio.to_thread(
                            _ytdlp_download_one, entry['webpage_url']
                        )

                    key = f"music/{user_id}/{uuid.uuid4().hex}.{ext}"
                    s3.put_object(
                        Bucket=settings.S3_BUCKET,
                        Key=key,
                        Body=content,
                        ContentType="audio/mpeg",
                    )
                    file_url = f"/files/{key}"

                    track = PlaylistTrack(
                        playlist_id=playlist_id,
                        title=entry['title'],
                        artist=entry.get('artist'),
                        file_url=file_url,
                        duration=entry.get('duration'),
                        order=order,
                    )
                    session.add(track)
                    order += 1
                    imported.append(entry['title'])
                except Exception as e:
                    logger.warning(f"Failed to import track {entry.get('title', '?')}: {e}")
                    continue

            await session.commit()

        msg = f"Импортировано {len(imported)} из {len(entries)} треков"
        yield f"data: {json.dumps({'type': 'done', 'message': msg, 'imported_count': len(imported), 'total_found': len(entries), 'imported_titles': imported})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
