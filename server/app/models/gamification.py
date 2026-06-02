# Модели геймификации: Agile.Coins, магазин, KPI, тестирование
import uuid
import enum
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Text, DateTime, Integer, Boolean, ForeignKey, Enum as SAEnum, UniqueConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


# ===================== COIN TRANSACTIONS =====================

class CoinTransactionType(str, enum.Enum):
    TOPIC_COMPLETE = "topic_complete"      # Прошёл подтему
    TEST_PASS = "test_pass"                # Сдал тест
    TASK_APPROVED = "task_approved"         # Задание принято
    ADMIN_GRANT = "admin_grant"            # Начислено администратором
    SHOP_PURCHASE = "shop_purchase"        # Покупка в магазине (расход)
    DAILY_LOGIN = "daily_login"            # Ежедневный бонус за вход


def _coin_transaction_enum_values(_: type[CoinTransactionType]) -> list[str]:
    return [
        CoinTransactionType.TOPIC_COMPLETE.value,
        CoinTransactionType.TEST_PASS.value,
        CoinTransactionType.TASK_APPROVED.value,
        CoinTransactionType.ADMIN_GRANT.value,
        CoinTransactionType.SHOP_PURCHASE.value,
        CoinTransactionType.DAILY_LOGIN.value,
    ]


class CoinTransaction(Base):
    """Транзакция Agile.Coins"""
    __tablename__ = "coin_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)  # + начисление, - списание
    tx_type: Mapped[CoinTransactionType] = mapped_column(
        SAEnum(CoinTransactionType, values_callable=_coin_transaction_enum_values),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=True)  # Пояснение (обязательно для admin_grant)
    reference_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)  # ID связанной сущности (тема, покупка)
    granted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # Кто начислил (для admin_grant)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id])
    granter = relationship("User", foreign_keys=[granted_by])


# ===================== SHOP =====================

class ShopItem(Base):
    """Товар в магазине Agile.Coins"""
    __tablename__ = "shop_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    icon: Mapped[str] = mapped_column(String(100), nullable=True)  # lucide icon name
    category: Mapped[str] = mapped_column(String(50), default="status")  # status, badge, perk
    image_url: Mapped[str] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    stock: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = безлимитно
    rarity: Mapped[str] = mapped_column(String(20), default="common")  # common, rare, epic, legendary
    level_required: Mapped[int] = mapped_column(Integer, default=1)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    purchases: Mapped[list["ShopPurchase"]] = relationship(back_populates="item", cascade="all, delete-orphan")


class ShopPurchase(Base):
    """Покупка товара из магазина"""
    __tablename__ = "shop_purchases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shop_items.id", ondelete="CASCADE"), nullable=False)
    price_paid: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id])
    item: Mapped["ShopItem"] = relationship(back_populates="purchases")


class UserShopEquip(Base):
    """Экипированные виртуальные товары пользователя по категориям."""
    __tablename__ = "user_shop_equips"
    __table_args__ = (UniqueConstraint("user_id", "category", name="uq_user_shop_category_equip"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    purchase_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shop_purchases.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    equipped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", foreign_keys=[user_id])
    purchase = relationship("ShopPurchase", foreign_keys=[purchase_id])


# ===================== TEST RESULTS =====================

class TopicTestResult(Base):
    """Результат тестирования по подтеме"""
    __tablename__ = "topic_test_results"
    __table_args__ = (UniqueConstraint("topic_id", "user_id", name="uq_topic_user_test"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("training_topics.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)      # Правильных ответов
    total: Mapped[int] = mapped_column(Integer, nullable=False)      # Всего вопросов
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)    # >= 70% = passed
    attempt: Mapped[int] = mapped_column(Integer, default=1)         # Номер попытки

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    topic = relationship("TrainingTopic", foreign_keys=[topic_id])
    user = relationship("User", foreign_keys=[user_id])


# ===================== SESSION TRACKING (KPI) =====================

class UserSession(Base):
    """Сессия пользователя на платформе (для KPI)"""
    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0)

    user = relationship("User", foreign_keys=[user_id])
