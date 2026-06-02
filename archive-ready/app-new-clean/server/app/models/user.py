# Модель пользователя
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text, Enum as SAEnum, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


class UserStatus(str, enum.Enum):
    PENDING = "pending"           # На модерации
    ACTIVE = "active"             # Активен
    REJECTED = "rejected"         # Отклонён
    FIRED = "fired"               # Уволен
    BLOCKED = "blocked"           # Заблокирован


class UserRole(str, enum.Enum):
    ADMIN = "admin"               # Администратор сайта
    USER = "user"                 # Обычный пользователь
    INTERN = "intern"             # Стажёр


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str] = mapped_column(String(255), nullable=True)
    patronymic: Mapped[str] = mapped_column(String(255), nullable=True)
    no_patronymic: Mapped[bool] = mapped_column(Boolean, default=False)
    city: Mapped[str] = mapped_column(String(255), nullable=True)
    skills: Mapped[str] = mapped_column(Text, nullable=True)  # Теги через запятую
    about: Mapped[str] = mapped_column(String(500), nullable=True)
    listening_to: Mapped[str] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str] = mapped_column(String(500), nullable=True)
    
    # Section access (list of section keys user can see)
    section_access: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, default=None)
    
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole, values_callable=lambda e: [m.value for m in e]), default=UserRole.USER, nullable=False)
    status: Mapped[UserStatus] = mapped_column(SAEnum(UserStatus, values_callable=lambda e: [m.value for m in e]), default=UserStatus.PENDING, nullable=False)
    
    email_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_id: Mapped[str] = mapped_column(String(100), nullable=True)
    telegram_username: Mapped[str] = mapped_column(String(100), nullable=True)
    
    # Настройки уведомлений Telegram
    notify_tasks: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_messages: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_events: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Сообщение при увольнении (настраивается админом)
    fire_message: Mapped[str] = mapped_column(Text, nullable=True, default="Чемодан, вокзал, НАХУЙ")
    
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Выбранная тема
    theme: Mapped[str] = mapped_column(String(10), default="light")  # light / dark
    # Язык интерфейса
    language: Mapped[str] = mapped_column(String(5), default="ru")  # ru / ka
    # Показывать итерации в проектах
    show_iterations: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Дополнительная роль обучения (intern / training_editor / None)
    training_role: Mapped[str] = mapped_column(String(50), nullable=True, default=None)
    
    # 2FA TOTP
    totp_secret: Mapped[str] = mapped_column(String(64), nullable=True, default=None)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Отношения
    sphere_roles: Mapped[list["UserSphereRole"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user", cascade="all, delete-orphan", foreign_keys="Notification.user_id")


class UserSphereRole(Base):
    """Роли пользователя внутри сфер деятельности"""
    __tablename__ = "user_sphere_roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    sphere: Mapped[str] = mapped_column(String(100), nullable=False)  # Название сферы
    role_title: Mapped[str] = mapped_column(String(100), nullable=False)  # Рядовой/Старший/Руководитель
    
    user: Mapped["User"] = relationship(back_populates="sphere_roles")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
