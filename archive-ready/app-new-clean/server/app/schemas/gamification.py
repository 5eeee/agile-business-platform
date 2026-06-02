# Pydantic-схемы геймификации
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# --- Coins ---
class CoinBalanceOut(BaseModel):
    balance: float = 0
    total_earned: float = 0
    total_spent: float = 0


class CoinTransactionOut(BaseModel):
    id: uuid.UUID
    amount: float
    tx_type: str
    reason: Optional[str] = None
    granted_by_name: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True


class AdminCoinGrant(BaseModel):
    user_id: uuid.UUID
    amount: float = Field(..., gt=0, le=10000)
    reason: str = Field(..., min_length=3, max_length=500)


# --- Shop ---
class ShopItemCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    price: int = Field(..., gt=0)
    icon: Optional[str] = None
    category: str = Field(default="status", pattern="^(status|badge|perk)$")
    image_url: Optional[str] = None
    stock: Optional[int] = None
    rarity: str = Field(default="common", pattern="^(common|rare|epic|legendary)$")
    level_required: int = Field(default=1, ge=1, le=100)
    is_featured: bool = False


class ShopItemUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    price: Optional[int] = Field(None, gt=0)
    icon: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    stock: Optional[int] = None
    is_active: Optional[bool] = None
    rarity: Optional[str] = None
    level_required: Optional[int] = None
    is_featured: Optional[bool] = None


class ShopItemOut(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str] = None
    price: int
    icon: Optional[str] = None
    category: str
    image_url: Optional[str] = None
    is_active: bool
    stock: Optional[int] = None
    rarity: str = "common"
    level_required: int = 1
    is_featured: bool = False
    created_at: datetime
    class Config:
        from_attributes = True


class ShopPurchaseOut(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    item_title: str = ""
    price_paid: float
    rarity: str = "common"
    category: str = "status"
    created_at: datetime
    class Config:
        from_attributes = True


class ShopShowcaseItemOut(ShopItemOut):
    owned_count: int = 0
    can_buy: bool = True
    is_locked: bool = False
    next_tier_required: int = 1


class EquipRequest(BaseModel):
    purchase_id: uuid.UUID


class EquippedItemOut(BaseModel):
    category: str
    purchase_id: uuid.UUID
    item_id: uuid.UUID
    item_title: str
    rarity: str = "common"
    equipped_at: datetime


class AchievementOut(BaseModel):
    id: str
    title: str
    category: str
    rarity: str
    level: int
    progress: int
    target: int
    unlocked: bool
    icon: Optional[str] = None


# --- Test Results ---
class TestSubmit(BaseModel):
    topic_id: uuid.UUID
    score: int = Field(..., ge=0)
    total: int = Field(..., gt=0)


class TestResultOut(BaseModel):
    id: uuid.UUID
    topic_id: uuid.UUID
    score: int
    total: int
    passed: bool
    attempt: int
    created_at: datetime
    class Config:
        from_attributes = True


# --- KPI ---
class UserKPIOut(BaseModel):
    user_id: uuid.UUID
    user_name: str
    avatar_url: Optional[str] = None
    total_time_minutes: int = 0
    topics_completed: int = 0
    topics_total: int = 0
    tests_passed: int = 0
    tests_total: int = 0
    avg_test_score: float = 0.0
    coins_balance: float = 0
    completion_pct: float = 0.0
    speed_topics_per_day: float = 0.0  # Скорость прохождения
    retention_pct: float = 0.0  # Усвоение материала (avg тест %)


class SessionPing(BaseModel):
    """Heartbeat для отслеживания времени на платформе"""
    pass


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: uuid.UUID
    user_name: str
    avatar_url: Optional[str] = None
    coins_balance: float = 0
    topics_completed: int = 0
    avg_test_score: float = 0.0
    total_time_hours: float = 0.0
    # Detailed task stats
    tasks_assigned: int = 0
    tasks_completed_week: int = 0
    tasks_completed_day: int = 0
    tasks_completed_month: int = 0
    tasks_completed_year: int = 0
    tasks_overdue: int = 0
    training_progress_pct: float = 0.0
    coins_earned_tasks: float = 0
    anti_cheat_score: int = 100
    anti_cheat_flags: list[str] = Field(default_factory=list)


# --- Section Access ---
class SectionAccessGrant(BaseModel):
    user_id: uuid.UUID
    section_keys: list[str] = Field(..., min_length=1)


class UserSectionAccessOut(BaseModel):
    user_id: uuid.UUID
    section_keys: list[str] = Field(default_factory=list)
