"""
Seed script: Add ~20 diverse shop items (status, badge, perk) with colorful variety.
Run: python seed_shop_items.py (from server dir, with DB running)
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select, delete
from app.database import async_session, init_db
from app.models.user import User, UserRole
from app.models.gamification import ShopItem

# 20 items: status, badge, perk — разноцветные, интересные
SHOP_ITEMS = [
    # status
    {"title": "VIP Статус", "description": "Золотая метка VIP в профиле на 30 дней", "price": 150, "icon": "Crown", "category": "status"},
    {"title": "Профессионал", "description": "Статус профессионала с синей иконкой", "price": 80, "icon": "Briefcase", "category": "status"},
    {"title": "Новичок Pro", "description": "Серебряный значок для активных новичков", "price": 50, "icon": "Sparkles", "category": "status"},
    {"title": "Fullstack Master", "description": "Эксклюзивный статус Fullstack разработчика", "price": 200, "icon": "Code2", "category": "status"},
    {"title": "Амбассадор курса", "description": "Особый статус для лидеров сообщества", "price": 120, "icon": "Users", "category": "status"},
    # badge
    {"title": "Заслуженный выпускник", "description": "Бейдж за успешное прохождение курса", "price": 300, "icon": "GraduationCap", "category": "badge"},
    {"title": "100% практика", "description": "Все практические задания выполнены", "price": 100, "icon": "CheckCircle2", "category": "badge"},
    {"title": "Тестовик", "description": "Бейдж за прохождение всех тестов", "price": 90, "icon": "ClipboardCheck", "category": "badge"},
    {"title": "Ранняя пташка", "description": "Начал курс в первую неделю запуска", "price": 60, "icon": "Sunrise", "category": "badge"},
    {"title": "Стремительный рост", "description": "Бейдж за быстрый прогресс (50% за неделю)", "price": 110, "icon": "TrendingUp", "category": "badge"},
    {"title": "Командный игрок", "description": "Помог другим в обсуждениях 10+ раз", "price": 75, "icon": "MessageCircle", "category": "badge"},
    {"title": "Код-ревьюер", "description": "Провёл 5+ ревью заданий коллег", "price": 130, "icon": "Eye", "category": "badge"},
    # perk
    {"title": "Бустер монет x2", "description": "Удвоенные монеты за темы на 7 дней", "price": 250, "icon": "Coins", "category": "perk"},
    {"title": "Приоритет поддержки", "description": "Быстрые ответы в чате поддержки 14 дней", "price": 180, "icon": "Headphones", "category": "perk"},
    {"title": "Сертификат PDF", "description": "Официальный PDF-сертификат о прохождении", "price": 200, "icon": "FileText", "category": "perk"},
    {"title": "Расширенный профиль", "description": "Доп. поля в профиле навсегда", "price": 95, "icon": "User", "category": "perk"},
    {"title": "Эксклюзивный аватар", "description": "Особая рамка аватара на 30 дней", "price": 70, "icon": "Image", "category": "perk"},
    {"title": "Доступ к бонусным материалам", "description": "Доп. уроки и шаблоны на 1 месяц", "price": 160, "icon": "BookOpen", "category": "perk"},
    {"title": "Пожизненная скидка 10%", "description": "10% скидка на все будущие курсы", "price": 500, "icon": "Percent", "category": "perk"},
    {"title": "Медаль «Первая тема»", "description": "Специальная медаль за первую пройденную тему", "price": 25, "icon": "Medal", "category": "badge"},
]


async def seed():
    await init_db()
    async with async_session() as db:
        result = await db.execute(select(User).where(User.role == UserRole.ADMIN).limit(1))
        admin = result.scalar_one_or_none()
        if not admin:
            print("WARNING: No admin user. Shop items will be created without owner context.")
        # Delete existing shop items (optional - comment out to append)
        await db.execute(delete(ShopItem))
        await db.commit()
        # Create items
        for i, item_data in enumerate(SHOP_ITEMS):
            item = ShopItem(
                title=item_data["title"],
                description=item_data.get("description"),
                price=item_data["price"],
                icon=item_data.get("icon"),
                category=item_data["category"],
                is_active=True,
            )
            db.add(item)
        await db.commit()
        print("Created %d shop items." % len(SHOP_ITEMS))


if __name__ == "__main__":
    asyncio.run(seed())
