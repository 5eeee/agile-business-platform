# API для геймификации: Agile.Coins, магазин, KPI, тесты, лидерборд
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserRole
from app.models.training import TrainingTopic, TopicProgress, CourseAssignment
from app.models.gamification import (
    CoinTransaction, CoinTransactionType,
    ShopItem, ShopPurchase,
    TopicTestResult, UserSession, UserShopEquip,
)
from app.models.task import TaskHistory
from app.schemas.gamification import (
    CoinBalanceOut, CoinTransactionOut, AdminCoinGrant,
    ShopItemCreate, ShopItemUpdate, ShopItemOut, ShopPurchaseOut,
    ShopShowcaseItemOut, EquippedItemOut, AchievementOut,
    TestSubmit, TestResultOut,
    UserKPIOut, LeaderboardEntry,
    SectionAccessGrant, UserSectionAccessOut,
)

router = APIRouter(prefix="/gamification", tags=["gamification"])


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
    if user.role != UserRole.ADMIN:
        raise HTTPException(403, "Только администраторы")
    return user


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
    if user.role != UserRole.ADMIN:
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
    return await _build_kpi(db, user.id, user.name, user.avatar_url)


@router.get("/kpi/user/{user_id}", response_model=UserKPIOut)
async def user_kpi(user_id: uuid.UUID, db: AsyncSession = Depends(get_db), admin: User = Depends(require_admin)):
    target = await db.get(User, user_id)
    if not target:
        raise HTTPException(404, "Пользователь не найден")
    return await _build_kpi(db, target.id, target.name, target.avatar_url)


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

    return UserKPIOut(
        user_id=user_id, user_name=name, avatar_url=avatar_url,
        total_time_minutes=total_time, topics_completed=topics_completed,
        topics_total=topics_total, tests_passed=tests_passed, tests_total=tests_total,
        avg_test_score=avg_test_score, coins_balance=float(balance),
        completion_pct=completion_pct, speed_topics_per_day=speed,
        retention_pct=avg_test_score,
    )


# ===================== LEADERBOARD =====================

@router.get("/leaderboard", response_model=list[LeaderboardEntry])
async def leaderboard(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    from app.models.task import Task
    from app.models.training import TopicProgress, TrainingTopic, CourseAssignment

    now = datetime.utcnow()
    today = now.date()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    year_ago = now - timedelta(days=365)

    # All users (or only interns for non-admins)
    q = select(User)
    if user.role != UserRole.ADMIN:
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
