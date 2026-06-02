# Модель плейлистов и треков
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # None = системный
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    owner = relationship("User")
    tracks: Mapped[list["PlaylistTrack"]] = relationship(back_populates="playlist", cascade="all, delete-orphan")


class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    playlist_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("playlists.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    artist: Mapped[str] = mapped_column(String(255), nullable=True)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=True)  # В секундах
    order: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    playlist: Mapped["Playlist"] = relationship(back_populates="tracks")
