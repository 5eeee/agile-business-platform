# API для геймификации: Agile.Coins, магазин, KPI, тесты, лидерборд
import uuid
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, case, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserRole, ADMIN_ROLES
from app.models.training import TrainingTopic, TopicProgress, CourseAssignment
from app.models.gamification import (
    CoinTransaction, CoinTransactionType,
    ShopItem, ShopPurchase,
    TopicTestResult, UserSession, UserShopEquip,
    KPIDrop, PerformanceReview, ManagerKPI2Cache, KPIManagerHistory, ManagerOvertimeCounter, ManagerOvertimeAction,
    AttentivenessLog, ManagerKPI4Points, ActionTypesWithMandatoryFields, ManagerResponsibility,
    EmployeeKPI8Points, KPI7ManagerPoints, KPI7ReviewImpact, EmployeeIdea
)
from app.models.task import TaskHistory
from app.models.notification import Notification
from app.schemas.gamification import (
    CoinBalanceOut, CoinTransactionOut, AdminCoinGrant,
    ShopItemCreate, ShopItemUpdate, ShopItemOut, ShopPurchaseOut,
    ShopShowcaseItemOut, EquippedItemOut, AchievementOut,
    TestSubmit, TestResultOut,
    UserKPIOut, LeaderboardEntry,
    SectionAccessGrant, UserSectionAccessOut,
    KPIDropOut, PerformanceReviewCreate, PerformanceReviewOut, ManagerKPIDetailsOut,
    DepartmentKPIHealthOut, ManagerReactivityOut,
)

router = APIRouter(prefix="/gamification", tags=["gamification"])


class SimpleMemoryCache:
    def __init__(self, default_ttl=30):
        self.default_ttl = default_ttl
        self.cache = {}

    def get(self, key):
        if key in self.cache:
            val, expire_time = self.cache[key]
            if time.time() < expire_time:
                return val
            else:
                del self.cache[key]
        return None

    def set(self, key, value, ttl=None):
        ttl = ttl if ttl is not None else self.default_ttl
        self.cache[key] = (value, time.time() + ttl)

    def clear(self):
        self.cache.clear()


kpi_cache = SimpleMemoryCache()

# Кэш сбрасывается автоматически по TTL (15-30 секунд), что существенно повышает производительность.



# ===================== HELPERS =====================

def _to_decimal(value: float | int | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


async def get_coin_balance(db: AsyncSession, user_id: uuid.UUID) -> Decimal:
    result = await db.execute(
        select(func.coalesce(func.sum(CoinTransaction.amount), 0.0))
        .where(CoinTransaction.user_id == user_id)
    )
    return _to_decimal(result.scalar() or 0)


async def add_coins(db: AsyncSession, user_id: uuid.UUID, amount: float | int | Decimal,
                    tx_type: CoinTransactionType, reason: Optional[str] = None,
                    reference_id: Optional[uuid.UUID] = None, granted_by: Optional[uuid.UUID] = None):
    tx = CoinTransaction(
        user_id=user_id, amount=_to_decimal(amount), tx_type=tx_type,
        reason=reason, reference_id=reference_id, granted_by=granted_by,
    )
    db.add(tx)
    await db.flush()
    return tx


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in ADMIN_ROLES:
        raise HTTPException(403, "Только администраторы")
    return user


def _can_manage_employee(manager: User, employee: User) -> bool:
    """Проверить управленческий доступ без возможности разбирать собственное падение."""
    if manager.id == employee.id:
        return False
    if manager.role in {UserRole.OWNER, UserRole.DEPUTY_OWNER}:
        return True
    return bool(
        manager.role == UserRole.ADMIN
        and (
            employee.manager_id == manager.id
            or (
                manager.department_id
                and employee.department_id == manager.department_id
            )
        )
    )


# ===================== COINS =====================

@router.get("/coins/balance", response_model=CoinBalanceOut)
async def get_my_balance(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    earned = await db.execute(
        select(func.coalesce(func.sum(CoinTransaction.amount), 0.0))
        .where(CoinTransaction.user_id == user.id, CoinTransaction.amount > 0)
    )
    spent = await db.execute(
        select(func.coalesce(func.sum(func.abs(CoinTransaction.amount)), 0.0))
        .where(CoinTransaction.user_id == user.id, CoinTransaction.amount < 0)
    )
    total_earned = _to_decimal(earned.scalar() or 0)
    total_spent = _to_decimal(spent.scalar() or 0)
    return CoinBalanceOut(
        balance=float(total_earned - total_spent),
        total_earned=float(total_earned),
        total_spent=float(total_spent),
    )


@router.get("/coins/history", response_model=list[CoinTransactionOut])
async def get_coin_history(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(CoinTransaction)
        .where(CoinTransaction.user_id == user.id)
        .order_by(CoinTransaction.created_at.desc())
        .limit(100)
    )
    txs = result.scalars().all()
    out: list[CoinTransactionOut] = []
    for tx in txs:
        granter_name = None
        if tx.granted_by:
            g = await db.get(User, tx.granted_by)
            granter_name = g.name if g else None
        out.append(CoinTransactionOut(
            id=tx.id, amount=float(tx.amount), tx_type=tx.tx_type.value,
            reason=tx.reason, granted_by_name=granter_name, created_at=tx.created_at,
        ))
    return out


@router.post("/coins/grant", response_model=CoinTransactionOut)
async def admin_grant_coins(data: AdminCoinGrant, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    target = await db.get(User, data.user_id)
    if not target:
        raise HTTPException(404, "Пользователь не найден")
    tx = await add_coins(db, data.user_id, data.amount, CoinTransactionType.ADMIN_GRANT,
                         reason=data.reason, granted_by=admin.id)
    await db.commit()
    return CoinTransactionOut(
        id=tx.id, amount=float(tx.amount), tx_type=tx.tx_type.value,
        reason=tx.reason, granted_by_name=admin.name, created_at=tx.created_at,
    )


# ===================== SHOP =====================

@router.get("/shop/items", response_model=list[ShopItemOut])
async def list_shop_items(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rarity_weight = case(
        (ShopItem.rarity == "legendary", 4),
        (ShopItem.rarity == "epic", 3),
        (ShopItem.rarity == "rare", 2),
        else_=1,
    )
    q = select(ShopItem).order_by(ShopItem.is_featured.desc(), rarity_weight.desc(), ShopItem.price)
    if user.role not in ADMIN_ROLES:
        q = q.where(ShopItem.is_active == True)
    result = await db.execute(q)
    return [ShopItemOut.model_validate(item) for item in result.scalars().all()]


@router.post("/shop/items", response_model=ShopItemOut)
async def create_shop_item(data: ShopItemCreate, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    item = ShopItem(**data.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return ShopItemOut.model_validate(item)


@router.put("/shop/items/{item_id}", response_model=ShopItemOut)
async def update_shop_item(item_id: uuid.UUID, data: ShopItemUpdate, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    item = await db.get(ShopItem, item_id)
    if not item:
        raise HTTPException(404, "Товар не найден")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    await db.commit()
    await db.refresh(item)
    return ShopItemOut.model_validate(item)


@router.delete("/shop/items/{item_id}")
async def delete_shop_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    item = await db.get(ShopItem, item_id)
    if not item:
        raise HTTPException(404, "Товар не найден")
    await db.delete(item)
    await db.commit()
    return {"ok": True}


@router.post("/shop/buy/{item_id}", response_model=ShopPurchaseOut)
async def buy_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    item = await db.get(ShopItem, item_id)
    if not item or not item.is_active:
        raise HTTPException(404, "Товар не найден или неактивен")
    if item.stock is not None and item.stock <= 0:
        raise HTTPException(400, "Товар закончился")

    balance = await get_coin_balance(db, user.id)
    # Простая progression-модель уровня по заработанным монетам.
    earned_res = await db.execute(
        select(func.coalesce(func.sum(CoinTransaction.amount), 0.0))
        .where(CoinTransaction.user_id == user.id, CoinTransaction.amount > 0)
    )
    total_earned = float(earned_res.scalar() or 0)
    user_level = max(1, int(total_earned // 100) + 1)
    if item.level_required > user_level:
        raise HTTPException(400, f"Нужен уровень {item.level_required}, ваш уровень {user_level}")

    if item.rarity == "legendary":
        already_owned = await db.execute(
            select(ShopPurchase)
            .where(ShopPurchase.user_id == user.id, ShopPurchase.item_id == item.id)
            .limit(1)
        )
        if already_owned.scalar_one_or_none():
            raise HTTPException(400, "Легендарный товар можно купить только один раз")

    if balance < item.price:
        raise HTTPException(400, f"Недостаточно Agile.Coins (нужно {item.price}, у вас {float(balance):.2f})")

    # Списание
    await add_coins(db, user.id, -item.price, CoinTransactionType.SHOP_PURCHASE,
                    reason=f"Покупка: {item.title}", reference_id=item.id)

    # Уменьшаем stock
    if item.stock is not None:
        item.stock -= 1

    purchase = ShopPurchase(user_id=user.id, item_id=item.id, price_paid=item.price)
    db.add(purchase)
    await db.commit()
    await db.refresh(purchase)

    return ShopPurchaseOut(id=purchase.id, item_id=purchase.item_id,
                          item_title=item.title, price_paid=float(purchase.price_paid),
                          rarity=item.rarity, category=item.category,
                          created_at=purchase.created_at)


@router.get("/shop/my-purchases", response_model=list[ShopPurchaseOut])
async def my_purchases(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(ShopPurchase).where(ShopPurchase.user_id == user.id)
        .order_by(ShopPurchase.created_at.desc())
    )
    out: list[ShopPurchaseOut] = []
    for p in result.scalars().all():
        item = await db.get(ShopItem, p.item_id)
        out.append(ShopPurchaseOut(
            id=p.id, item_id=p.item_id,
            item_title=item.title if item else "Удалён",
            price_paid=float(p.price_paid),
            rarity=item.rarity if item else "common",
            category=item.category if item else "status",
            created_at=p.created_at,
        ))
    return out


@router.get("/shop/showcase", response_model=list[ShopShowcaseItemOut])
async def shop_showcase(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    items_res = await db.execute(
        select(ShopItem)
        .where(ShopItem.is_active == True)
        .order_by(ShopItem.is_featured.desc(), ShopItem.price)
    )
    items = items_res.scalars().all()

    owned_res = await db.execute(
        select(ShopPurchase.item_id, func.count())
        .where(ShopPurchase.user_id == user.id)
        .group_by(ShopPurchase.item_id)
    )
    owned_map = {row[0]: row[1] for row in owned_res.all()}

    earned_res = await db.execute(
        select(func.coalesce(func.sum(CoinTransaction.amount), 0.0))
        .where(CoinTransaction.user_id == user.id, CoinTransaction.amount > 0)
    )
    total_earned = float(earned_res.scalar() or 0)
    user_level = max(1, int(total_earned // 100) + 1)
    balance = await get_coin_balance(db, user.id)

    rarity_tier_target = {"common": 1, "rare": 2, "epic": 3, "legendary": 1}
    out: list[ShopShowcaseItemOut] = []
    for item in items:
        owned = int(owned_map.get(item.id, 0) or 0)
        target = rarity_tier_target.get(item.rarity, 1)
        is_locked = user_level < item.level_required
        can_buy = (not is_locked) and (float(balance) >= float(item.price))
        out.append(ShopShowcaseItemOut(
            **ShopItemOut.model_validate(item).model_dump(),
            owned_count=owned,
            can_buy=can_buy,
            is_locked=is_locked,
            next_tier_required=max(target, owned + 1),
        ))
    return out


@router.get("/shop/achievements", response_model=list[AchievementOut])
async def shop_achievements(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = await db.execute(
        select(ShopItem.category, ShopItem.rarity, func.count(ShopPurchase.id))
        .join(ShopPurchase, ShopPurchase.item_id == ShopItem.id)
        .where(ShopPurchase.user_id == user.id)
        .group_by(ShopItem.category, ShopItem.rarity)
    )

    rarity_rank = {"common": 1, "rare": 2, "epic": 3, "legendary": 4}
    targets = {"common": 3, "rare": 3, "epic": 2, "legendary": 1}

    out: list[AchievementOut] = []
    for category, rarity, count in rows.all():
        progress = int(count or 0)
        target = targets.get(rarity, 3)
        level = min(5, max(1, (progress // max(1, target)) + 1))
        out.append(AchievementOut(
            id=f"{category}:{rarity}",
            title=f"{category.title()} {rarity.title()} Collector",
            category=category,
            rarity=rarity,
            level=level,
            progress=progress,
            target=target,
            unlocked=progress >= target,
            icon="Award",
        ))

    out.sort(key=lambda x: (rarity_rank.get(x.rarity, 0), x.progress), reverse=True)
    return out


@router.post("/shop/equip/{purchase_id}", response_model=EquippedItemOut)
async def equip_purchase(purchase_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    purchase = await db.get(ShopPurchase, purchase_id)
    if not purchase or purchase.user_id != user.id:
        raise HTTPException(404, "Покупка не найдена")
    item = await db.get(ShopItem, purchase.item_id)
    if not item:
        raise HTTPException(404, "Товар не найден")

    existing_res = await db.execute(
        select(UserShopEquip).where(UserShopEquip.user_id == user.id, UserShopEquip.category == item.category)
    )
    existing = existing_res.scalar_one_or_none()
    if existing:
        existing.purchase_id = purchase.id
        existing.equipped_at = datetime.utcnow()
        equip = existing
    else:
        equip = UserShopEquip(user_id=user.id, purchase_id=purchase.id, category=item.category)
        db.add(equip)

    await db.commit()
    await db.refresh(equip)
    return EquippedItemOut(
        category=equip.category,
        purchase_id=equip.purchase_id,
        item_id=item.id,
        item_title=item.title,
        rarity=item.rarity,
        equipped_at=equip.equipped_at,
    )


@router.get("/shop/equipped", response_model=list[EquippedItemOut])
async def list_equipped(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    equips_res = await db.execute(
        select(UserShopEquip).where(UserShopEquip.user_id == user.id).order_by(UserShopEquip.equipped_at.desc())
    )
    equips = equips_res.scalars().all()
    out: list[EquippedItemOut] = []
    for e in equips:
        purchase = await db.get(ShopPurchase, e.purchase_id)
        item = await db.get(ShopItem, purchase.item_id) if purchase else None
        if not purchase or not item:
            continue
        out.append(EquippedItemOut(
            category=e.category,
            purchase_id=e.purchase_id,
            item_id=item.id,
            item_title=item.title,
            rarity=item.rarity,
            equipped_at=e.equipped_at,
        ))
    return out


# ===================== TEST RESULTS =====================

@router.post("/test/submit", response_model=TestResultOut)
async def submit_test(data: TestSubmit, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    passed = (data.score / data.total) >= 0.7 if data.total > 0 else False

    # Проверяем существующий результат
    existing = await db.execute(
        select(TopicTestResult)
        .where(TopicTestResult.topic_id == data.topic_id, TopicTestResult.user_id == user.id)
    )
    old = existing.scalar_one_or_none()

    old_passed_before = bool(old.passed) if old else False

    if old:
        # Обновляем результат (перепрохождение)
        old.score = data.score
        old.total = data.total
        old.passed = passed
        old.attempt += 1
        old.created_at = datetime.utcnow()
        await db.flush()
        result_obj = old
    else:
        result_obj = TopicTestResult(
            topic_id=data.topic_id, user_id=user.id,
            score=data.score, total=data.total, passed=passed, attempt=1,
        )
        db.add(result_obj)
        await db.flush()

    # Начисляем коины за первое прохождение теста
    if passed and not old_passed_before:
        coins_reward = 10 if passed else 0
        await add_coins(db, user.id, coins_reward, CoinTransactionType.TEST_PASS,
                        reason=f"Тест пройден", reference_id=data.topic_id)

    await db.commit()
    await db.refresh(result_obj)
    return TestResultOut.model_validate(result_obj)


@router.get("/test/results", response_model=list[TestResultOut])
async def my_test_results(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(TopicTestResult).where(TopicTestResult.user_id == user.id)
        .order_by(TopicTestResult.created_at.desc())
    )
    return [TestResultOut.model_validate(r) for r in result.scalars().all()]


@router.get("/test/topic/{topic_id}", response_model=TestResultOut)
async def get_topic_test_result(topic_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(
        select(TopicTestResult)
        .where(TopicTestResult.topic_id == topic_id, TopicTestResult.user_id == user.id)
    )
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Результат теста не найден")
    return TestResultOut.model_validate(r)


# ===================== SESSION / KPI =====================

@router.post("/session/ping")
async def session_ping(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Heartbeat каждые 5 минут для учёта времени на платформе"""
    now = datetime.utcnow()
    # Ищем активную сессию (не закрытая, last ping < 10 мин назад)
    result = await db.execute(
        select(UserSession)
        .where(
            UserSession.user_id == user.id,
            UserSession.ended_at.is_(None),
            UserSession.started_at > now - timedelta(hours=12),
        )
        .order_by(UserSession.started_at.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()

    if session:
        # Обновляем длительность
        session.duration_minutes = int((now - session.started_at).total_seconds() / 60)
    else:
        # Создаём новую сессию
        session = UserSession(user_id=user.id, started_at=now, duration_minutes=0)
        db.add(session)

    await db.commit()
    return {"ok": True}


@router.post("/session/end")
async def session_end(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Закрыть текущую сессию (при уходе со страницы)"""
    now = datetime.utcnow()
    result = await db.execute(
        select(UserSession)
        .where(UserSession.user_id == user.id, UserSession.ended_at.is_(None))
        .order_by(UserSession.started_at.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()
    if session:
        session.ended_at = now
        session.duration_minutes = int((now - session.started_at).total_seconds() / 60)
        await db.commit()
    return {"ok": True}


@router.get("/kpi/me", response_model=UserKPIOut)
async def my_kpi(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    cache_key = f"kpi_user:{user.id}"
    cached_data = kpi_cache.get(cache_key)
    if cached_data is not None:
        return cached_data
    res = await _build_kpi(db, user.id, user.name, user.avatar_url)
    kpi_cache.set(cache_key, res, ttl=15)
    return res


@router.get("/kpi/user/{user_id}", response_model=UserKPIOut)
async def user_kpi(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    viewer: User = Depends(get_current_user),
):
    """KPI сотрудника с доступом по организационной иерархии.

    Сотрудник видит только себя, руководитель — себя, прямых подчинённых и
    сотрудников своего отдела, заместитель и владелец — всю организацию.
    """
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(404, "Пользователь не найден")

    can_view_all = viewer.role in {UserRole.OWNER, UserRole.DEPUTY_OWNER}
    is_self = viewer.id == target.id
    is_direct_report = target.manager_id == viewer.id
    is_same_department = bool(
        viewer.role == UserRole.ADMIN
        and viewer.department_id
        and target.department_id == viewer.department_id
    )
    if not (can_view_all or is_self or is_direct_report or is_same_department):
        raise HTTPException(403, "KPI доступны только сотруднику и его руководителям")

    cache_key = f"kpi_user:{user_id}"
    cached_data = kpi_cache.get(cache_key)
    if cached_data is not None:
        return cached_data
    res = await _build_kpi(db, target.id, target.name, target.avatar_url)
    kpi_cache.set(cache_key, res, ttl=15)
    return res


# Helper to calculate working days (standard Mon-Fri 9:00 - 18:00)
def calculate_working_days(start_ts: datetime, end_ts: datetime) -> Decimal:
    if start_ts >= end_ts:
        return Decimal("0.1")
    
    total_minutes = 0
    current_date = start_ts.date()
    end_date = end_ts.date()
    
    while current_date <= end_date:
        if current_date.weekday() < 5:  # Monday-Friday
            work_start = datetime.combine(current_date, datetime.min.time()) + timedelta(hours=9)
            work_end = datetime.combine(current_date, datetime.min.time()) + timedelta(hours=18)
            
            intersect_start = max(start_ts, work_start)
            intersect_end = min(end_ts, work_end)
            
            if intersect_start < intersect_end:
                overlap = (intersect_end - intersect_start).total_seconds() / 60
                total_minutes += overlap
                
        current_date += timedelta(days=1)
        
    days = Decimal(str(total_minutes / 480.0)).quantize(Decimal("0.1"))
    return max(days, Decimal("0.1"))


def is_overtime_review(review_date: datetime) -> bool:
    # Weekend is overtime
    if review_date.weekday() >= 5:
        return True
    # Before 9:00 or after 18:00 is overtime
    time_of_day = review_date.time()
    if time_of_day < datetime.strptime("09:00", "%H:%M").time() or time_of_day > datetime.strptime("18:00", "%H:%M").time():
        return True
    return False


@router.get("/kpi/drops/active", response_model=list[KPIDropOut])
async def get_active_drops(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Получить активные падения KPI сотрудников"""
    if user.role in {UserRole.OWNER, UserRole.DEPUTY_OWNER}:
        q = select(KPIDrop).where(KPIDrop.resolved == False).order_by(KPIDrop.drop_date.desc())
    elif user.role == UserRole.ADMIN:
        scope = [User.manager_id == user.id]
        if user.department_id:
            scope.append(User.department_id == user.department_id)
        q = (
            select(KPIDrop)
            .join(User, User.id == KPIDrop.employee_id)
            .where(
                KPIDrop.resolved == False,
                KPIDrop.employee_id != user.id,
                or_(*scope),
            )
            .order_by(KPIDrop.drop_date.desc())
        )
    else:
        q = select(KPIDrop).where(KPIDrop.employee_id == user.id, KPIDrop.resolved == False).order_by(KPIDrop.drop_date.desc())
        
    res = await db.execute(q)
    drops = res.scalars().all()
    
    out = []
    for d in drops:
        emp = await db.get(User, d.employee_id)
        out.append(KPIDropOut(
            id=d.id,
            employee_id=d.employee_id,
            employee_name=emp.name if emp else "Сотрудник",
            kpi_type=d.kpi_type,
            drop_value=float(d.drop_value),
            drop_date=d.drop_date,
            resolved=d.resolved,
            notification_sent=d.notification_sent
        ))
    return out


@router.post("/kpi/reviews", response_model=PerformanceReviewOut)
async def submit_performance_review(
    data: PerformanceReviewCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin)
):
    """Создать разбор падения KPI сотрудника"""
    drop_obj = None
    if data.drop_id:
        drop_obj = await db.get(KPIDrop, data.drop_id)
        if not drop_obj:
            raise HTTPException(status_code=404, detail="Падение KPI не найдено")
        employee = await db.get(User, drop_obj.employee_id)
        if not employee or not _can_manage_employee(user, employee):
            raise HTTPException(status_code=403, detail="Разбор доступен только руководителю этого сотрудника")

    errors = []
    if not data.kpi_type or data.kpi_type.strip() == "":
        errors.append("KPI")
    if not data.reason or data.reason.strip() == "":
        errors.append("причина")
    if not data.action or data.action.strip() == "":
        errors.append("мера")
        
    now = datetime.utcnow()
    is_ot = is_overtime_review(now)
    
    action_id_str = str(data.drop_id) if data.drop_id else data.kpi_type
    
    # Ищем максимальный attempt_number для этого действия
    attempt_q = select(func.max(AttentivenessLog.attempt_number)).where(
        AttentivenessLog.user_id == user.id,
        AttentivenessLog.action_type == "kpi_review",
        AttentivenessLog.action_id == action_id_str
    )
    attempt_res = await db.execute(attempt_q)
    max_attempt = attempt_res.scalar() or 0
    next_attempt = max_attempt + 1
    
    if errors:
        # Логируем неудачную попытку
        att_log = AttentivenessLog(
            user_id=user.id,
            action_type="kpi_review",
            action_id=action_id_str,
            attempt_number=next_attempt,
            success=False,
            is_overtime=is_ot,
            penalty_points=Decimal("-1.0") if not is_ot else Decimal("-0.25"),
            created_at=now
        )
        db.add(att_log)
        await db.commit()
        
        raise HTTPException(
            status_code=400,
            detail=f"Вы не заполнили обязательные поля: {', '.join(errors)}. Пожалуйста, заполните их перед сохранением."
        )
        
    # Валидация пройдена!
    if data.drop_id:
        exists_q = select(PerformanceReview).where(PerformanceReview.drop_id == data.drop_id)
        exists_res = await db.execute(exists_q)
        if exists_res.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Разбор по этому падению уже проведен")
            
    reaction_days_dec = Decimal("1.0")
    if data.drop_id:
        reaction_days_dec = calculate_working_days(drop_obj.drop_date, now)
        drop_obj.resolved = True
            
    review = PerformanceReview(
        drop_id=data.drop_id,
        manager_id=user.id,
        review_date=now,
        kpi_type=data.kpi_type,
        reason=data.reason,
        action=data.action,
        comment=data.comment,
        reaction_days=reaction_days_dec,
        is_overtime=is_ot,
        created_at=now
    )
    db.add(review)
    await db.flush()
    
    has_failed_q = select(func.count(AttentivenessLog.id)).where(
        AttentivenessLog.user_id == user.id,
        AttentivenessLog.action_type == "kpi_review",
        AttentivenessLog.action_id == action_id_str,
        AttentivenessLog.success == False
    )
    has_failed_res = await db.execute(has_failed_q)
    has_failed = (has_failed_res.scalar() or 0) > 0
    
    points_awarded = Decimal("0.5")
    if has_failed:
        points_awarded = Decimal("-1.0") if not is_ot else Decimal("-0.25")
    else:
        points_awarded = Decimal("0.5") if not is_ot else Decimal("1.0")
        
    att_log = AttentivenessLog(
        user_id=user.id,
        action_type="kpi_review",
        action_id=action_id_str,
        attempt_number=next_attempt,
        success=True,
        is_overtime=is_ot,
        penalty_points=points_awarded,
        created_at=now
    )
    db.add(att_log)
    await db.flush() # Получаем ID att_log
    
    # Начисляем баллы в должностной KPI4
    month_start = datetime(now.year, now.month, 1)
    kpi4_q = select(ManagerKPI4Points).where(
        ManagerKPI4Points.manager_id == user.id,
        ManagerKPI4Points.month == month_start
    )
    kpi4_res = await db.execute(kpi4_q)
    kpi4_obj = kpi4_res.scalar_one_or_none()
    if kpi4_obj:
        kpi4_obj.total_points += points_awarded
    else:
        kpi4_obj = ManagerKPI4Points(
            manager_id=user.id,
            month=month_start,
            total_points=points_awarded,
            updated_at=now
        )
        db.add(kpi4_obj)
        
    # Начисляем баллы в общий KPI8
    emp_kpi8 = EmployeeKPI8Points(
        employee_id=user.id,
        month=month_start,
        points=points_awarded,
        source_action_id=att_log.id
    )
    db.add(emp_kpi8)
    
    if is_ot:
        count_q = select(func.count(ManagerOvertimeCounter.id)).where(
            ManagerOvertimeCounter.manager_id == user.id,
            ManagerOvertimeCounter.month == month_start
        )
        count_res = await db.execute(count_q)
        ot_count = count_res.scalar() or 0
        order_number = ot_count + 1
        
        pct = 6
        if order_number == 1:
            pct = 20
        elif order_number == 2:
            pct = 15
        elif order_number == 3:
            pct = 12
        elif order_number == 4:
            pct = 10
        elif order_number == 5:
            pct = 8
            
        ot_counter = ManagerOvertimeCounter(
            manager_id=user.id,
            month=month_start,
            order_number=order_number,
            review_id=review.id,
            percent_awarded=pct,
            awarded_at=now
        )
        db.add(ot_counter)
        
        resp = ManagerResponsibility(
            manager_id=user.id,
            date=now,
            event_type="overtime_review",
            points=Decimal("1.0"),
            description=f"Сверхурочный разбор #{order_number} падения {data.kpi_type}",
            source_id=review.id
        )
        db.add(resp)
        
    kpi7_points = Decimal("2.0")
    if reaction_days_dec > Decimal("1.0"):
        kpi7_points = Decimal("1.0")
        
    kpi7_impact = KPI7ReviewImpact(
        manager_id=user.id,
        review_id=review.id,
        points=kpi7_points,
        created_at=now
    )
    db.add(kpi7_impact)
    
    kpi7_tot_q = select(KPI7ManagerPoints).where(
        KPI7ManagerPoints.manager_id == user.id,
        KPI7ManagerPoints.month == month_start
    )
    kpi7_tot_res = await db.execute(kpi7_tot_q)
    kpi7_tot_obj = kpi7_tot_res.scalar_one_or_none()
    if kpi7_tot_obj:
        kpi7_tot_obj.total_points += kpi7_points
    else:
        kpi7_tot_obj = KPI7ManagerPoints(
            manager_id=user.id,
            month=month_start,
            total_points=kpi7_points,
            updated_at=now
        )
        db.add(kpi7_tot_obj)
        
    await db.commit()
    
    # Пересчитываем KPI2 среднее время реакции
    all_reviews_q = select(PerformanceReview.reaction_days).where(
        PerformanceReview.manager_id == user.id,
        PerformanceReview.review_date >= month_start
    )
    all_reviews_res = await db.execute(all_reviews_q)
    reaction_days_list = [r[0] for r in all_reviews_res.fetchall() if r[0] is not None]
    
    avg_kpi2 = None
    sum_days = Decimal("0.0")
    count_reviews = len(reaction_days_list)
    if count_reviews > 0:
        sum_days = sum(reaction_days_list)
        avg_kpi2 = (sum_days / Decimal(str(count_reviews))).quantize(Decimal("0.1"))
        
    cache_q = select(ManagerKPI2Cache).where(
        ManagerKPI2Cache.manager_id == user.id,
        ManagerKPI2Cache.month == month_start
    )
    cache_res = await db.execute(cache_q)
    cache_obj = cache_res.scalar_one_or_none()
    if cache_obj:
        cache_obj.current_kpi2 = avg_kpi2
        cache_obj.total_days = sum_days
        cache_obj.reviews_count = count_reviews
        cache_obj.updated_at = now
    else:
        cache_obj = ManagerKPI2Cache(
            manager_id=user.id,
            month=month_start,
            current_kpi2=avg_kpi2,
            total_days=sum_days,
            reviews_count=count_reviews,
            updated_at=now
        )
        db.add(cache_obj)
        
    await db.commit()
    await db.refresh(review)
    
    return PerformanceReviewOut(
        id=review.id,
        drop_id=review.drop_id,
        manager_id=review.manager_id,
        manager_name=user.name,
        review_date=review.review_date,
        kpi_type=review.kpi_type,
        reason=review.reason,
        action=review.action,
        comment=review.comment,
        reaction_days=float(review.reaction_days) if review.reaction_days is not None else None,
        is_overtime=review.is_overtime,
        created_at=review.created_at
    )


@router.get("/kpi/manager/details", response_model=ManagerKPIDetailsOut)
async def get_manager_kpi_details(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Получить детальные KPI показатели руководителя"""
    cache_key = f"manager_kpi_details:{user.id}"
    cached_data = kpi_cache.get(cache_key)
    if cached_data is not None:
        return cached_data
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    
    cache_q = select(ManagerKPI2Cache).where(
        ManagerKPI2Cache.manager_id == user.id,
        ManagerKPI2Cache.month == month_start
    )
    cache_res = await db.execute(cache_q)
    cache_obj = cache_res.scalar_one_or_none()
    
    current_kpi2 = float(cache_obj.current_kpi2) if cache_obj and cache_obj.current_kpi2 is not None else None
    reviews_count = cache_obj.reviews_count if cache_obj else 0
    total_days = float(cache_obj.total_days) if cache_obj else 0.0
    
    ot_count_q = select(func.count(ManagerOvertimeCounter.id)).where(
        ManagerOvertimeCounter.manager_id == user.id,
        ManagerOvertimeCounter.month == month_start
    )
    ot_count_res = await db.execute(ot_count_q)
    action_count_res = await db.execute(
        select(func.count(ManagerOvertimeAction.id)).where(
            ManagerOvertimeAction.manager_id == user.id,
            ManagerOvertimeAction.month == month_start,
        )
    )
    overtime_reviews_count = (ot_count_res.scalar() or 0) + (action_count_res.scalar() or 0)
    
    ot_pct_q = select(func.sum(ManagerOvertimeCounter.percent_awarded)).where(
        ManagerOvertimeCounter.manager_id == user.id,
        ManagerOvertimeCounter.month == month_start
    )
    ot_pct_res = await db.execute(ot_pct_q)
    action_pct_res = await db.execute(
        select(func.sum(ManagerOvertimeAction.percent_awarded)).where(
            ManagerOvertimeAction.manager_id == user.id,
            ManagerOvertimeAction.month == month_start,
        )
    )
    total_overtime_percent = (ot_pct_res.scalar() or 0) + (action_pct_res.scalar() or 0)
    total_overtime_percent = min(100, total_overtime_percent)
    
    active_drops_res = await get_active_drops(db, user)
    
    recent_q = select(PerformanceReview).where(
        PerformanceReview.manager_id == user.id
    ).order_by(PerformanceReview.review_date.desc()).limit(10)
    recent_res = await db.execute(recent_q)
    recent_reviews = recent_res.scalars().all()
    
    recent_out = []
    for r in recent_reviews:
        recent_out.append(PerformanceReviewOut(
            id=r.id,
            drop_id=r.drop_id,
            manager_id=r.manager_id,
            manager_name=user.name,
            review_date=r.review_date,
            kpi_type=r.kpi_type,
            reason=r.reason,
            action=r.action,
            comment=r.comment,
            reaction_days=float(r.reaction_days) if r.reaction_days is not None else None,
            is_overtime=r.is_overtime,
            created_at=r.created_at
        ))
        
    res_out = ManagerKPIDetailsOut(
        manager_id=user.id,
        current_kpi2=current_kpi2,
        reviews_count=reviews_count,
        total_days=total_days,
        overtime_reviews_count=overtime_reviews_count,
        total_overtime_percent=total_overtime_percent,
        active_drops=active_drops_res,
        recent_reviews=recent_out
    )
    kpi_cache.set(cache_key, res_out, ttl=15)
    return res_out


@router.post("/kpi/drops/simulate")
async def simulate_kpi_drop(
    kpi_type: str,
    drop_value: float,
    employee_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Симулировать падение KPI сотрудника для демонстрации/тестов (только админы)"""
    if not employee_id:
        target_q = select(User).where(User.role != UserRole.ADMIN).limit(1)
        target_res = await db.execute(target_q)
        target = target_res.scalar_one_or_none()
        if not target:
            raise HTTPException(400, "Нет пользователей для симуляции падения")
        employee_id = target.id
        
    drop = KPIDrop(
        employee_id=employee_id,
        kpi_type=kpi_type,
        drop_value=Decimal(str(drop_value)),
        drop_date=datetime.utcnow() - timedelta(hours=12),
        resolved=False,
        notification_sent=False
    )
    db.add(drop)
    await db.commit()
    await db.refresh(drop)
    return {"ok": True, "drop_id": str(drop.id), "employee_id": str(employee_id)}


async def _build_kpi(db: AsyncSession, user_id: uuid.UUID, name: str, avatar_url: Optional[str] = None) -> UserKPIOut:
    # Время на платформе
    time_res = await db.execute(
        select(func.coalesce(func.sum(UserSession.duration_minutes), 0))
        .where(UserSession.user_id == user_id)
    )
    total_time = time_res.scalar() or 0

    # Прогресс обучения
    completed_res = await db.execute(
        select(func.count()).where(TopicProgress.user_id == user_id, TopicProgress.status == "completed")
    )
    topics_completed = completed_res.scalar() or 0

    # Кол-во назначенных тем
    assigned_courses = await db.execute(
        select(CourseAssignment.course_id).where(CourseAssignment.user_id == user_id)
    )
    course_ids = [r[0] for r in assigned_courses.fetchall()]
    topics_total = 0
    if course_ids:
        tt_res = await db.execute(
            select(func.count()).where(TrainingTopic.course_id.in_(course_ids))
        )
        topics_total = tt_res.scalar() or 0

    # Тесты
    tests_res = await db.execute(
        select(
            func.count(),
            func.sum(case((TopicTestResult.passed == True, 1), else_=0)),
            func.avg(case((TopicTestResult.total > 0, TopicTestResult.score * 100.0 / TopicTestResult.total), else_=0)),
        ).where(TopicTestResult.user_id == user_id)
    )
    row = tests_res.one()
    tests_total = row[0] or 0
    tests_passed = row[1] or 0
    avg_test_score = round(float(row[2] or 0), 1)

    # Баланс коинов
    balance = await get_coin_balance(db, user_id)

    # Скорость (тем в день за последние 30 дней)
    month_ago = datetime.utcnow() - timedelta(days=30)
    speed_res = await db.execute(
        select(func.count())
        .where(TopicProgress.user_id == user_id, TopicProgress.status == "completed", TopicProgress.updated_at >= month_ago)
    )
    completed_last_month = speed_res.scalar() or 0
    speed = round(completed_last_month / 30, 2)

    completion_pct = round(topics_completed / topics_total * 100, 1) if topics_total > 0 else 0

    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)
    current_week_start = datetime.combine((now - timedelta(days=now.weekday())).date(), datetime.min.time())
    two_week_start = current_week_start - timedelta(days=7)

    from app.services import kpi_calculator

    # KPI1 по документу накопительный по всем финально принятым задачам.
    k1 = await kpi_calculator.calculate_kpi1_deadlines(db, user_id, datetime(2000, 1, 1), month_end)
    k2 = await kpi_calculator.calculate_kpi2_punctuality(db, user_id, month_start, month_end)
    k3 = await kpi_calculator.calculate_kpi3_initiative(db, user_id, month_start, month_end)
    k4 = await kpi_calculator.calculate_kpi4_overtime_load(db, user_id, month_start, month_end)
    k5 = await kpi_calculator.calculate_kpi5_quality(db, user_id, two_week_start, now)
    k8 = await kpi_calculator.calculate_kpi8_attentiveness(db, user_id, month_start, month_end)
    k9, k9_carryover = await kpi_calculator.calculate_kpi9_bonus_breakdown(db, user_id, month_start, month_end)
    k10 = await kpi_calculator.calculate_kpi10_responsibility(db, user_id, month_start, month_end)
    customer_satisfaction = await kpi_calculator.calculate_customer_satisfaction(db, user_id, two_week_start, now)

    # Check manager status
    usr_res = await db.execute(select(User).where(User.id == user_id))
    usr = usr_res.scalar_one_or_none()
    
    mgr_k1, mgr_k2, mgr_k3, mgr_k4, mgr_k5, mgr_k6, mgr_k7 = None, None, None, None, None, None, None
    subordinates_count = 0
    if usr:
        subordinates_res = await db.execute(select(func.count()).where(User.manager_id == user_id))
        subordinates_count = int(subordinates_res.scalar() or 0)
    if usr and (usr.role in [UserRole.ADMIN, UserRole.OWNER, UserRole.DEPUTY_OWNER] or subordinates_count > 0):
        mgr_k1 = await kpi_calculator.calculate_manager_kpi1_reaction_index(db, user_id, month_start, month_end)
        mgr_k2 = await kpi_calculator.calculate_manager_kpi2_reaction_days(db, user_id, month_start, month_end)
        mgr_k3 = await kpi_calculator.calculate_manager_kpi3_responsibility(db, user_id, month_start, month_end)
        mgr_k4 = await kpi_calculator.calculate_manager_kpi4_attentiveness(db, user_id, month_start, month_end)
        mgr_k5 = await kpi_calculator.calculate_manager_kpi5_idea_reaction(db, user_id, month_start, month_end)
        mgr_k6 = await kpi_calculator.calculate_manager_kpi6_overtime(db, user_id, month_start, month_end)
        mgr_k7 = await kpi_calculator.calculate_manager_kpi7_department_control(db, user_id, month_start, month_end)

    general_values = [k1, k2, k3, k4, k5, k8, k10, customer_satisfaction]
    general_values = [Decimal(str(value)) for value in general_values if value is not None]
    general_score = (
        sum(general_values, Decimal("0")) / Decimal(len(general_values))
        if general_values else None
    )

    # KPI2 руководителя — длительность в днях, поэтому он показывается как SLA,
    # но не смешивается с процентами. Должностной итог состоит из шести
    # процентных показателей: M1, M3, M4, M5, M6 и M7.
    occupational_values = [mgr_k1, mgr_k3, mgr_k4, mgr_k5, mgr_k6, mgr_k7]
    occupational_values = [Decimal(str(value)) for value in occupational_values if value is not None]
    occupational_score = (
        sum(occupational_values, Decimal("0")) / Decimal(len(occupational_values))
        if occupational_values else None
    )
    has_occupational_kpi = bool(
        usr and (
            usr.role in {UserRole.ADMIN, UserRole.OWNER, UserRole.DEPUTY_OWNER}
            or subordinates_count > 0
        )
    )
    score_groups = [value for value in [general_score, occupational_score if has_occupational_kpi else None] if value is not None]
    overall_score = (
        sum(score_groups, Decimal("0")) / Decimal(len(score_groups))
        if score_groups else None
    )

    return UserKPIOut(
        user_id=user_id, user_name=name, avatar_url=avatar_url,
        role=usr.role.value if usr else UserRole.USER.value,
        department_id=usr.department_id if usr else None,
        has_occupational_kpi=has_occupational_kpi,
        general_score=float(general_score.quantize(Decimal("0.1"))) if general_score is not None else None,
        occupational_score=float(occupational_score.quantize(Decimal("0.1"))) if occupational_score is not None else None,
        overall_score=float(overall_score.quantize(Decimal("0.1"))) if overall_score is not None else None,
        total_time_minutes=total_time, topics_completed=topics_completed,
        topics_total=topics_total, tests_passed=tests_passed, tests_total=tests_total,
        avg_test_score=avg_test_score, coins_balance=float(balance),
        completion_pct=completion_pct, speed_topics_per_day=speed,
        retention_pct=avg_test_score,
        
        kpi1_deadlines=float(k1) if k1 is not None else None,
        kpi2_punctuality=float(k2) if k2 is not None else None,
        kpi3_initiative=float(k3) if k3 is not None else None,
        kpi4_overtime=float(k4) if k4 is not None else None,
        kpi5_quality=float(k5) if k5 is not None else None,
        kpi8_attentiveness=float(k8) if k8 is not None else None,
        kpi9_bonus=float(k9) if k9 is not None else None,
        kpi9_carryover=float(k9_carryover),
        kpi10_responsibility=float(k10) if k10 is not None else None,
        kpi_customer_satisfaction=float(customer_satisfaction) if customer_satisfaction is not None else None,
        
        manager_kpi1_reaction_index=float(mgr_k1) if mgr_k1 is not None else None,
        manager_kpi2_reaction_days=float(mgr_k2) if mgr_k2 is not None else None,
        manager_kpi3_responsibility=float(mgr_k3) if mgr_k3 is not None else None,
        manager_kpi4_attentiveness=float(mgr_k4) if mgr_k4 is not None else None,
        manager_kpi5_idea_reaction=float(mgr_k5) if mgr_k5 is not None else None,
        manager_kpi6_overtime=float(mgr_k6) if mgr_k6 is not None else None,
        manager_kpi7_department_control=float(mgr_k7) if mgr_k7 is not None else None,
    )


# ===================== LEADERBOARD =====================

@router.get("/leaderboard", response_model=list[LeaderboardEntry])
async def leaderboard(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    is_admin = user.role in ADMIN_ROLES
    cache_key = f"leaderboard:{is_admin}"
    cached_data = kpi_cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    from app.models.task import Task
    from app.models.training import TopicProgress, TrainingTopic, CourseAssignment

    now = datetime.utcnow()
    today = now.date()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    year_ago = now - timedelta(days=365)

    # All users (or only interns for non-admins)
    q = select(User)
    if user.role not in ADMIN_ROLES:
        q = q.where(User.training_role == "intern")
    result = await db.execute(q.order_by(User.name))
    users_list = result.scalars().all()

    entries: list[LeaderboardEntry] = []
    for u in users_list:
        balance = await get_coin_balance(db, u.id)
        completed = await db.execute(
            select(func.count()).where(TopicProgress.user_id == u.id, TopicProgress.status == "completed")
        )
        topics_done = completed.scalar() or 0

        test_res = await db.execute(
            select(func.avg(case((TopicTestResult.total > 0, TopicTestResult.score * 100.0 / TopicTestResult.total), else_=0)))
            .where(TopicTestResult.user_id == u.id)
        )
        avg_score = round(float(test_res.scalar() or 0), 1)

        time_res = await db.execute(
            select(func.coalesce(func.sum(UserSession.duration_minutes), 0))
            .where(UserSession.user_id == u.id)
        )
        total_minutes = time_res.scalar() or 0

        # Task statistics
        tasks_assigned_res = await db.execute(
            select(func.count()).where(Task.assignee_id == u.id, Task.is_completed == False)
        )
        tasks_assigned = tasks_assigned_res.scalar() or 0

        tasks_day_res = await db.execute(
            select(func.count()).where(Task.assignee_id == u.id, Task.is_completed == True,
                                        Task.updated_at >= datetime.combine(today, datetime.min.time()))
        )
        tasks_completed_day = tasks_day_res.scalar() or 0

        tasks_week_res = await db.execute(
            select(func.count()).where(Task.assignee_id == u.id, Task.is_completed == True, Task.updated_at >= week_ago)
        )
        tasks_completed_week = tasks_week_res.scalar() or 0

        tasks_month_res = await db.execute(
            select(func.count()).where(Task.assignee_id == u.id, Task.is_completed == True, Task.updated_at >= month_ago)
        )
        tasks_completed_month = tasks_month_res.scalar() or 0

        tasks_year_res = await db.execute(
            select(func.count()).where(Task.assignee_id == u.id, Task.is_completed == True, Task.updated_at >= year_ago)
        )
        tasks_completed_year = tasks_year_res.scalar() or 0

        tasks_overdue_res = await db.execute(
            select(func.count()).where(
                Task.assignee_id == u.id, Task.is_completed == False,
                Task.deadline != None, Task.deadline < now
            )
        )
        tasks_overdue = tasks_overdue_res.scalar() or 0

        # Training progress
        assigned_courses = await db.execute(
            select(CourseAssignment.course_id).where(CourseAssignment.user_id == u.id)
        )
        course_ids = [r[0] for r in assigned_courses.fetchall()]
        training_pct = 0.0
        if course_ids:
            tt_res = await db.execute(
                select(func.count()).where(TrainingTopic.course_id.in_(course_ids))
            )
            topics_total = tt_res.scalar() or 0
            if topics_total > 0:
                training_pct = round(topics_done / topics_total * 100, 1)

        # Coins from task completions
        coins_tasks_res = await db.execute(
            select(func.coalesce(func.sum(CoinTransaction.amount), 0.0))
            .where(CoinTransaction.user_id == u.id, CoinTransaction.tx_type == CoinTransactionType.TASK_APPROVED)
        )
        coins_earned_tasks = float(coins_tasks_res.scalar() or 0)

        # Anti-cheat heuristics
        anti_flags: list[str] = []
        anti_score = 100

        toggles_res = await db.execute(
            select(func.count())
            .where(
                TaskHistory.user_id == u.id,
                TaskHistory.field == "is_completed",
                TaskHistory.created_at >= week_ago,
            )
        )
        completion_toggles_week = int(toggles_res.scalar() or 0)
        if completion_toggles_week > 18:
            anti_flags.append("too_many_completion_toggles")
            anti_score -= 20

        if tasks_completed_day >= 30:
            anti_flags.append("abnormal_daily_throughput")
            anti_score -= 25

        if total_minutes < 120 and tasks_completed_day >= 12:
            anti_flags.append("high_output_low_online_time")
            anti_score -= 25

        if coins_earned_tasks > (tasks_completed_year * 2.5):
            anti_flags.append("task_coins_vs_completed_mismatch")
            anti_score -= 20

        anti_score = max(0, anti_score)

        entries.append(LeaderboardEntry(
            rank=0, user_id=u.id, user_name=u.name, avatar_url=u.avatar_url,
            coins_balance=float(balance), topics_completed=topics_done,
            avg_test_score=avg_score, total_time_hours=round(total_minutes / 60, 1),
            tasks_assigned=tasks_assigned, tasks_completed_day=tasks_completed_day,
            tasks_completed_week=tasks_completed_week, tasks_completed_month=tasks_completed_month,
            tasks_completed_year=tasks_completed_year, tasks_overdue=tasks_overdue,
            training_progress_pct=training_pct, coins_earned_tasks=coins_earned_tasks,
            anti_cheat_score=anti_score, anti_cheat_flags=anti_flags,
        ))

    # Sort by anti-cheat adjusted coins, then weekly task output.
    entries.sort(
        key=lambda e: (e.coins_balance * (e.anti_cheat_score / 100.0), e.tasks_completed_week),
        reverse=True,
    )
    for i, e in enumerate(entries):
        e.rank = i + 1

    kpi_cache.set(cache_key, entries, ttl=30)
    return entries


# ===================== SECTION ACCESS =====================

@router.post("/access/grant")
async def grant_section_access(data: SectionAccessGrant, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)) -> dict[str, object]:
    """Выдать пользователю доступы к разделам платформы"""
    target = await db.get(User, data.user_id)
    if not target:
        raise HTTPException(404, "Пользователь не найден")
    raw_current = target.section_access if isinstance(target.section_access, list) else []
    current = [str(k) for k in raw_current]
    target.section_access = list(set(current + data.section_keys))
    await db.commit()
    section_keys = [str(k) for k in (target.section_access or [])]
    return {"ok": True, "section_keys": section_keys}


@router.put("/access/{user_id}")
async def set_section_access(user_id: uuid.UUID, data: SectionAccessGrant, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)) -> dict[str, object]:
    """Полностью перезаписать доступы пользователя (для чекбоксов)"""
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(404, "Пользователь не найден")
    target.section_access = list(data.section_keys)
    await db.commit()
    section_keys = [str(k) for k in (target.section_access or [])]
    return {"ok": True, "section_keys": section_keys}


@router.get("/access/{user_id}", response_model=UserSectionAccessOut)
async def get_section_access(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(404, "Пользователь не найден")
    keys = [str(k) for k in (target.section_access or [])]
    return UserSectionAccessOut(user_id=user_id, section_keys=keys)


async def run_kpi_cron_jobs(db: AsyncSession):
    """Периодические cron задачи для обновления KPI2 и создания срезов истории в конце месяца"""
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    
    # 1. Ежечасный пересчет KPI2 для всех начальников/админов
    managers_q = select(User).where(User.role.in_([UserRole.ADMIN, UserRole.OWNER, UserRole.DEPUTY_OWNER]))
    res = await db.execute(managers_q)
    managers = res.scalars().all()
    
    for mgr in managers:
        all_reviews_q = select(PerformanceReview.reaction_days).where(
            PerformanceReview.manager_id == mgr.id,
            PerformanceReview.review_date >= month_start
        )
        all_reviews_res = await db.execute(all_reviews_q)
        reaction_days_list = [r[0] for r in all_reviews_res.fetchall() if r[0] is not None]
        
        avg_kpi2 = None
        sum_days = Decimal("0.0")
        count_reviews = len(reaction_days_list)
        if count_reviews > 0:
            sum_days = sum(reaction_days_list)
            avg_kpi2 = (sum_days / Decimal(str(count_reviews))).quantize(Decimal("0.1"))
            
        cache_q = select(ManagerKPI2Cache).where(
            ManagerKPI2Cache.manager_id == mgr.id,
            ManagerKPI2Cache.month == month_start
        )
        cache_res = await db.execute(cache_q)
        cache_obj = cache_res.scalar_one_or_none()
        if cache_obj:
            cache_obj.current_kpi2 = avg_kpi2
            cache_obj.total_days = sum_days
            cache_obj.reviews_count = count_reviews
            cache_obj.updated_at = now
        else:
            cache_obj = ManagerKPI2Cache(
                manager_id=mgr.id,
                month=month_start,
                current_kpi2=avg_kpi2,
                total_days=sum_days,
                reviews_count=count_reviews,
                updated_at=now
            )
            db.add(cache_obj)
            
    # 2. Просроченные более чем на 5 календарных дней идеи: единоразовый штраф и эскалация.
    overdue_result = await db.execute(
        select(EmployeeIdea).where(
            EmployeeIdea.status == "submitted",
            EmployeeIdea.created_at <= now - timedelta(days=5),
        )
    )
    escalation_recipients = await db.execute(
        select(User.id).where(User.role.in_([UserRole.OWNER, UserRole.DEPUTY_OWNER]))
    )
    recipient_ids = list(escalation_recipients.scalars().all())
    for idea in overdue_result.scalars().all():
        if not idea.manager_id:
            continue
        exists = await db.execute(
            select(ManagerResponsibility.id).where(
                ManagerResponsibility.event_type == "idea_overdue",
                ManagerResponsibility.source_id == idea.id,
            )
        )
        if exists.scalar_one_or_none():
            continue
        db.add(ManagerResponsibility(
            manager_id=idea.manager_id,
            date=now,
            event_type="idea_overdue",
            points=Decimal("-1"),
            description="Идея не рассмотрена за 5 календарных дней",
            source_id=idea.id,
        ))
        for recipient_id in recipient_ids:
            db.add(Notification(
                user_id=recipient_id,
                title="Просрочено решение по идее",
                message="Идея сотрудника не рассмотрена руководителем в течение 5 дней.",
                type="kpi",
                link="/kpi",
            ))

    # 3. Финальный срез в конце месяца (если до конца месяца осталось менее суток)
    tomorrow = now + timedelta(days=1)
    if tomorrow.month != now.month and now.hour == 23 and now.minute >= 50:
        history_q = select(KPIManagerHistory).where(KPIManagerHistory.month == month_start)
        history_res = await db.execute(history_q)
        if not history_res.scalars().all():
            for mgr in managers:
                cache_q = select(ManagerKPI2Cache).where(
                    ManagerKPI2Cache.manager_id == mgr.id,
                    ManagerKPI2Cache.month == month_start
                )
                cache_res = await db.execute(cache_q)
                cache_obj = cache_res.scalar_one_or_none()
                
                kpi2_val = cache_obj.current_kpi2 if cache_obj else None
                rev_count = cache_obj.reviews_count if cache_obj else 0
                tot_days = cache_obj.total_days if cache_obj else Decimal("0.0")
                
                history = KPIManagerHistory(
                    manager_id=mgr.id,
                    month=month_start,
                    kpi2_value=kpi2_val,
                    reviews_count=rev_count,
                    total_days=tot_days,
                    calculated_at=now
                )
                db.add(history)
                
    await db.commit()


# ===================== ADMIN DASHBOARD ENDPOINTS =====================

@router.get("/admin/department-kpi-health", response_model=list[DepartmentKPIHealthOut])
async def get_department_kpi_health(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
) -> list[DepartmentKPIHealthOut]:
    """Получить агрегированное здоровье по KPI в разрезе отделов компании"""
    cache_key = "admin_department_kpi_health"
    cached_data = kpi_cache.get(cache_key)
    if cached_data is not None:
        return cached_data
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)

    # Получаем список всех сотрудников с их department_id
    users_q = select(User).where(User.role != UserRole.ADMIN)
    users_res = await db.execute(users_q)
    users = users_res.scalars().all()

    # Группируем по отделу
    from collections import defaultdict
    dept_users = defaultdict(list)
    for u in users:
        dept_id = u.department_id or "unassigned"
        dept_users[dept_id].append(u)

    from app.services import kpi_calculator

    out = []
    for dept_id, u_list in dept_users.items():
        k1_list, k2_list, k3_list, k4_list, k5_list, k8_list, k9_list, k10_list = [], [], [], [], [], [], [], []
        
        for u in u_list:
            k1 = await kpi_calculator.calculate_kpi1_deadlines(db, u.id, month_start, month_end)
            k2 = await kpi_calculator.calculate_kpi2_punctuality(db, u.id, month_start, month_end)
            k3 = await kpi_calculator.calculate_kpi3_initiative(db, u.id, month_start, month_end)
            k4 = await kpi_calculator.calculate_kpi4_overtime_load(db, u.id, month_start, month_end)
            k5 = await kpi_calculator.calculate_kpi5_quality(db, u.id, month_start, month_end)
            k8 = await kpi_calculator.calculate_kpi8_attentiveness(db, u.id, month_start, month_end)
            k9 = await kpi_calculator.calculate_kpi9_bonus(db, u.id, month_start, month_end)
            k10 = await kpi_calculator.calculate_kpi10_responsibility(db, u.id, month_start, month_end)

            if k1 is not None: k1_list.append(k1)
            if k2 is not None: k2_list.append(k2)
            if k3 is not None: k3_list.append(k3)
            if k4 is not None: k4_list.append(k4)
            if k5 is not None: k5_list.append(k5)
            if k8 is not None: k8_list.append(k8)
            if k9 is not None: k9_list.append(k9)
            if k10 is not None: k10_list.append(k10)

        def avg_or_none(lst):
            return float(sum(lst) / len(lst)) if lst else None

        out.append(DepartmentKPIHealthOut(
            department_id=dept_id if dept_id != "unassigned" else None,
            employee_count=len(u_list),
            avg_kpi1_deadlines=avg_or_none(k1_list),
            avg_kpi2_punctuality=avg_or_none(k2_list),
            avg_kpi3_initiative=avg_or_none(k3_list),
            avg_kpi4_overtime=avg_or_none(k4_list),
            avg_kpi5_quality=avg_or_none(k5_list),
            avg_kpi8_attentiveness=avg_or_none(k8_list),
            avg_kpi9_bonus=avg_or_none(k9_list),
            avg_kpi10_responsibility=avg_or_none(k10_list)
        ))

    kpi_cache.set(cache_key, out, ttl=60)
    return out


@router.get("/admin/manager-reactivity", response_model=list[ManagerReactivityOut])
async def get_manager_reactivity(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
) -> list[ManagerReactivityOut]:
    """Получить показатели оперативности реагирования и дисциплины руководителей"""
    cache_key = "admin_manager_reactivity"
    cached_data = kpi_cache.get(cache_key)
    if cached_data is not None:
        return cached_data
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)

    # Находим всех менеджеров/админов
    manager_ids = select(User.manager_id).where(User.manager_id != None)
    managers_res = await db.execute(
        select(User).where(or_(
            User.role.in_([UserRole.ADMIN, UserRole.OWNER, UserRole.DEPUTY_OWNER]),
            User.id.in_(manager_ids),
        ))
    )
    managers = managers_res.scalars().all()

    from app.services import kpi_calculator

    out = []
    for mgr in managers:
        # Подчиненные
        sub_res = await db.execute(select(User.id).where(User.manager_id == mgr.id))
        sub_ids = [r[0] for r in sub_res.fetchall()]

        active_drops_count = 0
        if sub_ids:
            drops_res = await db.execute(
                select(func.count(KPIDrop.id)).where(
                    KPIDrop.employee_id.in_(sub_ids),
                    KPIDrop.resolved == False
                )
            )
            active_drops_count = drops_res.scalar() or 0

        # Количество проведенных разборов за месяц
        rev_count_res = await db.execute(
            select(func.count(PerformanceReview.id)).where(
                PerformanceReview.manager_id == mgr.id,
                PerformanceReview.review_date >= month_start,
                PerformanceReview.review_date <= month_end
            )
        )
        reviews_count = rev_count_res.scalar() or 0

        # KPI1–KPI7 руководителя (кроме зарезервированных показателей)
        k1 = await kpi_calculator.calculate_manager_kpi1_reaction_index(db, mgr.id, month_start, month_end)
        k2 = await kpi_calculator.calculate_manager_kpi2_reaction_days(db, mgr.id, month_start, month_end)
        k3 = await kpi_calculator.calculate_manager_kpi3_responsibility(db, mgr.id, month_start, month_end)
        k4 = await kpi_calculator.calculate_manager_kpi4_attentiveness(db, mgr.id, month_start, month_end)
        k5 = await kpi_calculator.calculate_manager_kpi5_idea_reaction(db, mgr.id, month_start, month_end)
        k6 = await kpi_calculator.calculate_manager_kpi6_overtime(db, mgr.id, month_start, month_end)
        k7 = await kpi_calculator.calculate_manager_kpi7_department_control(db, mgr.id, month_start, month_end)

        out.append(ManagerReactivityOut(
            manager_id=mgr.id,
            manager_name=mgr.name,
            active_drops_count=active_drops_count,
            conducted_reviews_count=reviews_count,
            avg_reaction_days=float(k2) if k2 is not None else None,
            manager_kpi1_reaction_index=float(k1) if k1 is not None else None,
            manager_kpi3_responsibility=float(k3) if k3 is not None else None,
            manager_kpi4_attentiveness=float(k4) if k4 is not None else None,
            manager_kpi5_idea_reaction=float(k5) if k5 is not None else None,
            manager_kpi6_overtime=float(k6),
            manager_kpi7_department_control=float(k7),
        ))

    kpi_cache.set(cache_key, out, ttl=60)
    return out

