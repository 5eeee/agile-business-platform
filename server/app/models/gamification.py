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


# ===================== NEW KPI MODELS =====================

class KPIDrop(Base):
    """Падения KPI сотрудников (для KPI1 / Manager KPI1 & KPI2)"""
    __tablename__ = "kpi_drops"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kpi_type: Mapped[str] = mapped_column(String(10), nullable=False) # e.g., 'KPI1', 'KPI2'
    drop_value: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    drop_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notification_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    employee = relationship("User", foreign_keys=[employee_id])


class PerformanceReview(Base):
    """Разборы падений KPI, проведенные руководителями (Manager KPI2)"""
    __tablename__ = "performance_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    drop_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("kpi_drops.id", ondelete="SET NULL"), nullable=True)
    manager_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    review_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    kpi_type: Mapped[str] = mapped_column(String(10), nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reaction_days: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    is_overtime: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    drop = relationship("KPIDrop", foreign_keys=[drop_id])
    manager = relationship("User", foreign_keys=[manager_id])


class ManagerKPI2Cache(Base):
    """Текущее кэшированное значение KPI2 для руководителей"""
    __tablename__ = "manager_kpi2_cache"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    manager_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    month: Mapped[datetime] = mapped_column(DateTime, nullable=False) # первое число текущего месяца
    current_kpi2: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    total_days: Mapped[Decimal] = mapped_column(Numeric(8, 1), default=0.0, nullable=False)
    reviews_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    manager = relationship("User", foreign_keys=[manager_id])


class KPIManagerHistory(Base):
    """История финальных значений KPI для руководителей на конец месяца"""
    __tablename__ = "kpi_manager_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    manager_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    month: Mapped[datetime] = mapped_column(DateTime, nullable=False) # первое число месяца
    kpi2_value: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    reviews_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_days: Mapped[Decimal] = mapped_column(Numeric(8, 1), default=0.0, nullable=False)
    kpi4_points: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True) # для KPI4
    kpi7_value: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True) # для KPI7
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    manager = relationship("User", foreign_keys=[manager_id])


class ManagerOvertimeCounter(Base):
    """Счетчик сверхурочных разборов для начисления процентов в KPI6 руководителей"""
    __tablename__ = "manager_overtime_counters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    manager_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    month: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    order_number: Mapped[int] = mapped_column(Integer, nullable=False)
    review_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("performance_reviews.id", ondelete="CASCADE"), nullable=False)
    percent_awarded: Mapped[int] = mapped_column(Integer, nullable=False)
    awarded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    manager = relationship("User", foreign_keys=[manager_id])
    review = relationship("PerformanceReview", foreign_keys=[review_id])


class ManagerOvertimeAction(Base):
    """Сверхурочные управленческие действия вне карточки разбора KPI."""
    __tablename__ = "manager_overtime_actions"
    __table_args__ = (
        UniqueConstraint("manager_id", "action_type", "source_id", name="uq_manager_overtime_action_source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    manager_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    month: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    percent_awarded: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    awarded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    manager = relationship("User", foreign_keys=[manager_id])


class AttendanceLog(Base):
    """Журнал явки/дисциплины для KPI2"""
    __tablename__ = "attendance_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False) # День события
    check_in: Mapped[datetime | None] = mapped_column(DateTime, nullable=True) # Фактическое время прихода
    check_out: Mapped[datetime | None] = mapped_column(DateTime, nullable=True) # Фактическое время ухода
    is_penalty_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attendance_fulfilled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False) # Выполнена ли явка
    late_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    early_leave_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    penalty_points: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=0.0, nullable=False) # Начисленные баллы нарушений
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    employee = relationship("User", foreign_keys=[employee_id])


class AttentivenessLog(Base):
    """Универсальный лог попыток сохранения для контроля внимательности (KPI8 и должностной KPI4)"""
    __tablename__ = "attentiveness_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False) # e.g., 'kpi_review', 'idea_decision'
    action_id: Mapped[str] = mapped_column(String(50), nullable=False) # UUID или иной ID сущности как строка
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_overtime: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    penalty_points: Mapped[Decimal] = mapped_column(Numeric(3, 1), default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", foreign_keys=[user_id])


class ManagerKPI4Points(Base):
    """Накопленные баллы внимательности для KPI4 начальника"""
    __tablename__ = "manager_kpi4_points"
    __table_args__ = (UniqueConstraint("manager_id", "month", name="uq_manager_kpi4_month"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    manager_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    month: Mapped[datetime] = mapped_column(DateTime, nullable=False) # первое число месяца
    total_points: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    manager = relationship("User", foreign_keys=[manager_id])


class ActionTypesWithMandatoryFields(Base):
    """Администрируемый справочник типов действий с обязательными полями для внимательности"""
    __tablename__ = "action_types_with_mandatory_fields"

    code: Mapped[str] = mapped_column(String(50), primary_key=True) # e.g., 'kpi_review'
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    mandatory_fields: Mapped[str] = mapped_column(Text, nullable=False) # JSON-строка, например '["reason", "action"]'
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ManagerResponsibility(Base):
    """Баллы ответственности руководителя для KPI3"""
    __tablename__ = "manager_responsibility"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    manager_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    points: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    manager = relationship("User", foreign_keys=[manager_id])


class EmployeeKPI8Points(Base):
    """Баллы внимательности для общего KPI8 сотрудников"""
    __tablename__ = "employee_kpi8_points"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    month: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    points: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)
    source_action_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("attentiveness_log.id", ondelete="SET NULL"), nullable=True)

    employee = relationship("User", foreign_keys=[employee_id])
    source_action = relationship("AttentivenessLog", foreign_keys=[source_action_id])


class KPI7ManagerPoints(Base):
    """Баллы контроля отдела KPI7 для руководителя"""
    __tablename__ = "kpi7_manager_points"
    __table_args__ = (UniqueConstraint("manager_id", "month", name="uq_manager_kpi7_month"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    manager_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    month: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    total_points: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    manager = relationship("User", foreign_keys=[manager_id])


class KPI7ReviewImpact(Base):
    """Баллы за разборы (положительные/отрицательные) для KPI7"""
    __tablename__ = "kpi7_review_impact"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    manager_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    review_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("performance_reviews.id", ondelete="CASCADE"), nullable=False)
    points: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    manager = relationship("User", foreign_keys=[manager_id])
    review = relationship("PerformanceReview", foreign_keys=[review_id])


# ===================== EMPLOYEE IDEAS & ACTIVITIES (KPI3) =====================

class EmployeeIdea(Base):
    """Идеи сотрудников для KPI3"""
    __tablename__ = "employee_ideas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    manager_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    idea_type: Mapped[str] = mapped_column(String(50), nullable=False) # e.g. Technical, Process, Product...
    sphere: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True) # Комментарий руководителя
    status: Mapped[str] = mapped_column(String(20), default="approved", nullable=False) # approved, testing, success, fail
    testing_start_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decision: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reaction_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reaction_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    is_counted_in_manager_kpi5: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    employee = relationship("User", foreign_keys=[employee_id])
    manager = relationship("User", foreign_keys=[manager_id])


class EmployeeActivityLog(Base):
    """Журнал мероприятий и интересов сотрудника для KPI3"""
    __tablename__ = "employee_activity_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_type: Mapped[str] = mapped_column(String(20), nullable=False) # event / interest
    sub_type: Mapped[str] = mapped_column(String(100), nullable=False) # вид мероприятия или тип заинтересованности
    title: Mapped[str | None] = mapped_column(String(255), nullable=True) # Название мероприятия
    comment: Mapped[str | None] = mapped_column(Text, nullable=True) # Комментарий руководителя
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    employee = relationship("User", foreign_keys=[employee_id])


# ===================== TASK RETURNS (KPI5) =====================

class TaskReturn(Base):
    """Возвраты задач на доработку (KPI5 и сверхурочные исправления)"""
    __tablename__ = "task_returns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    return_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    resend_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    error_category: Mapped[str] = mapped_column(String(50), nullable=False) # critical / medium / small / regular
    reason_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    base_weight: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False) # e.g. 1.0, 0.5, 0.2
    extra_penalty: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=0.0, nullable=False)
    total_weight: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    return_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    is_iterative: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_external: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    effective_hours: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True) # чистые рабочие часы на исправление
    
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    task = relationship("Task", foreign_keys=[task_id])
    employee = relationship("User", foreign_keys=[employee_id])
    creator = relationship("User", foreign_keys=[created_by])


# ===================== OVERTIME EVENTS (KPI4 & KPI9) =====================

class OvertimeEvent(Base):
    """События сверхурочных исправлений сотрудников"""
    __tablename__ = "overtime_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    month: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    order_number: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False) # quality / poor
    percent_awarded: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    employee = relationship("User", foreign_keys=[employee_id])


# ===================== HELP LOG (KPI9) =====================

class HelpLog(Base):
    """Лог помощи коллеге (для бонусного индекса KPI9)"""
    __tablename__ = "help_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    helper_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    helper = relationship("User", foreign_keys=[helper_id])
    recipient = relationship("User", foreign_keys=[recipient_id])
    confirmer = relationship("User", foreign_keys=[confirmed_by])


# ===================== KPI9 BONUS INDEX =====================

class KPI9Bonus(Base):
    """Начисленные бонусы в KPI9 сотрудника"""
    __tablename__ = "kpi9_bonuses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    month: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False) # help, course_complete, extra_task, etc.
    percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    employee = relationship("User", foreign_keys=[employee_id])


class KPI9Cache(Base):
    """Кэш текущей суммы процентов по KPI9 для сотрудника за месяц"""
    __tablename__ = "kpi9_cache"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    month: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    total_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee = relationship("User", foreign_keys=[employee_id])


# ===================== WEEKLY REPORTS (KPI7) =====================

class WeeklyReport(Base):
    """Еженедельные отчеты сотрудников (для KPI7 руководителя)"""
    __tablename__ = "weekly_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    manager_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    report_data: Mapped[str] = mapped_column(Text, nullable=False) # JSON c ответами по критериям 1-6
    status: Mapped[str] = mapped_column(String(50), default="draft") # draft / on_review / approved / rework
    week_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    employee = relationship("User", foreign_keys=[employee_id])
    manager = relationship("User", foreign_keys=[manager_id])


class WeeklyReportReview(Base):
    """Разборы и утверждения отчетов (KPI7)"""
    __tablename__ = "weekly_report_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("weekly_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    checked_criteria: Mapped[str] = mapped_column(Text, nullable=False) # JSON список проверенных критериев [1, 2, 3, 4, 5]
    comment: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False) # approved / rework
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    report = relationship("WeeklyReport", foreign_keys=[report_id])
    reviewer = relationship("User", foreign_keys=[reviewer_id])


# ===================== EMPLOYEE KPI HISTORY =====================

class EmployeeKPIHistory(Base):
    """Финальные срезы KPI сотрудников за период (2-недели для KPI5, месяц для остальных)"""
    __tablename__ = "employee_kpi_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    kpi_type: Mapped[str] = mapped_column(String(10), nullable=False) # KPI1, KPI2, KPI3, KPI4, KPI5, KPI7, KPI8, KPI9, KPI10
    value: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False) # Значение в процентах (0-100)
    
    total_tasks: Mapped[int | None] = mapped_column(Integer, nullable=True) # Метаданные (например, сдано задач)
    total_penalty: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True) # Сумма штрафов
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    employee = relationship("User", foreign_keys=[employee_id])
