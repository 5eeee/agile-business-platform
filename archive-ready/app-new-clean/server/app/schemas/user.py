# Pydantic-схемы пользователей
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ValidationInfo, field_validator


class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v):
        if isinstance(v, str):
            return v.strip().lower()
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v):
        if isinstance(v, str):
            return v.strip().lower()
        return v


class TokenResponse(BaseModel):
    token_type: str = "bearer"
    fire_message: Optional[str] = None


class TokenRefresh(BaseModel):
    refresh_token: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6, max_length=128)


class PasswordReset(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v):
        if isinstance(v, str):
            return v.strip().lower()
        return v


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6, max_length=128)


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    last_name: Optional[str] = None
    patronymic: Optional[str] = None
    no_patronymic: Optional[bool] = None
    city: Optional[str] = None
    skills: Optional[str] = None
    about: Optional[str] = Field(None, max_length=500)
    listening_to: Optional[str] = None
    theme: Optional[str] = None
    language: Optional[str] = None
    notify_tasks: Optional[bool] = None
    notify_messages: Optional[bool] = None
    notify_events: Optional[bool] = None
    show_iterations: Optional[bool] = None


class SphereRoleOut(BaseModel):
    id: uuid.UUID
    sphere: str
    role_title: str

    class Config:
        from_attributes = True


class UserOut(BaseModel):
    id: uuid.UUID
    name: str
    last_name: Optional[str] = None
    patronymic: Optional[str] = None
    no_patronymic: bool = False
    city: Optional[str] = None
    skills: Optional[list[str]] = None
    about: Optional[str] = None
    listening_to: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    status: str
    training_role: Optional[str] = None
    is_online: bool = False
    last_seen: Optional[datetime] = None
    theme: str = "light"
    language: str = "ru"
    section_access: Optional[list[str]] = None
    show_iterations: bool = False
    totp_enabled: bool = False
    sphere_roles: list[SphereRoleOut] = []
    created_at: datetime

    @field_validator('skills', mode='before')
    @classmethod
    def parse_skills(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(',') if s.strip()]
        return v

    @field_validator('role', 'status', mode='before')
    @classmethod
    def enum_to_str(cls, v):
        if v is None:
            return v
        return v.value if hasattr(v, 'value') else str(v)

    @field_validator('is_online', 'totp_enabled', mode='before')
    @classmethod
    def bool_field_default(cls, v):
        return False if v is None else v

    @field_validator('theme', 'language', mode='before')
    @classmethod
    def str_defaults(cls, v, info: ValidationInfo):
        if v is None or (isinstance(v, str) and v.strip() == ''):
            return 'light' if info.field_name == 'theme' else 'ru'
        return v

    @field_validator('created_at', mode='before')
    @classmethod
    def created_at_default(cls, v):
        # В БД у старых строк created_at/is_online/theme могли быть NULL → без этого Pydantic давал 500 на /auth/me
        if v is None:
            return datetime(1970, 1, 1)
        return v

    class Config:
        from_attributes = True


class UserAdminOut(UserOut):
    """Расширенная модель для администратора — с email"""
    email: str
    email_confirmed: bool = False
    telegram_username: Optional[str] = None
    fire_message: Optional[str] = None
    notify_tasks: bool = True
    notify_messages: bool = True
    notify_events: bool = True

    @field_validator('email_confirmed', mode='before')
    @classmethod
    def email_confirmed_default(cls, v):
        return False if v is None else v

    @field_validator('notify_tasks', 'notify_messages', 'notify_events', mode='before')
    @classmethod
    def notify_bools_default(cls, v):
        return True if v is None else v


class UserSphereRoleCreate(BaseModel):
    user_id: uuid.UUID
    sphere: str
    role_title: str


class UserFireRequest(BaseModel):
    fire_message: Optional[str] = "Чемодан, вокзал, НАХУЙ"


class AdminUserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    city: Optional[str] = None
    fire_message: Optional[str] = None
    training_role: Optional[str] = None
