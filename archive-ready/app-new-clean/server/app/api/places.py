# API маршруты для мест силы
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.place import Place
from app.models.user import User
from app.middleware.auth import get_current_user, require_admin
from app.services.s3 import upload_file_to_s3

router = APIRouter(prefix="/places", tags=["Места силы"])


class PlaceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    photo_url: Optional[str] = None
    video_url: Optional[str] = None


class PlaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    photo_url: Optional[str] = None
    video_url: Optional[str] = None


# Места по умолчанию
DEFAULT_PLACES = [
    # Грузия: Казбек, Тбилиси, Мцхета
    {"name": "Казбек", "country": "Грузия", "city": "Степанцминда", "latitude": 42.6562, "longitude": 44.5139,
     "description": "Священная гора Кавказа — величественный пик, ледники и монастырь Гергети на высоте 2170 м"},
    {"name": "Тбилиси", "country": "Грузия", "city": "Тбилиси", "latitude": 41.7151, "longitude": 44.8271,
     "description": "Столица Грузии — город с богатой историей, термальными источниками и уникальной архитектурой"},
    {"name": "Мцхета", "country": "Грузия", "city": "Мцхета", "latitude": 41.8420, "longitude": 44.7188,
     "description": "Древняя столица Грузии и духовный центр — собор Светицховели, монастырь Джвари"},
    # Болгария: София, Варна, Рила
    {"name": "София", "country": "Болгария", "city": "София", "latitude": 42.6977, "longitude": 23.3219,
     "description": "Столица Болгарии у подножия горы Витоша, один из старейших городов Европы"},
    {"name": "Варна", "country": "Болгария", "city": "Варна", "latitude": 43.2141, "longitude": 27.9147,
     "description": "Морская столица Болгарии — золотые пляжи Чёрного моря и древняя история"},
    {"name": "Рила", "country": "Болгария", "city": "Рила", "latitude": 42.1337, "longitude": 23.3404,
     "description": "Рильский монастырь в горах — крупнейший православный монастырь Болгарии, объект ЮНЕСКО"},
    # Дагестан: горы, побережье
    {"name": "Горный Дагестан", "country": "Россия", "city": "Гуниб", "latitude": 42.3833, "longitude": 46.9667,
     "description": "Горный край Кавказа — глубокие каньоны, древние аулы и неприступные крепости"},
    {"name": "Побережье Дагестана", "country": "Россия", "city": "Дербент", "latitude": 42.0588, "longitude": 48.2978,
     "description": "Каспийское побережье и Дербент — древнейший город России с крепостью Нарын-Кала"},
    # Казахстан: степи, Алматы
    {"name": "Степи Казахстана", "country": "Казахстан", "city": "Нур-Султан", "latitude": 51.1694, "longitude": 71.4491,
     "description": "Бескрайние степи Центральной Азии — кочевая культура, юрты и бесконечный горизонт"},
    {"name": "Алматы", "country": "Казахстан", "city": "Алматы", "latitude": 43.2380, "longitude": 76.9458,
     "description": "Южная столица Казахстана у подножия Тянь-Шаня — горы, парки и современный бизнес"},
]


@router.get("")
async def list_places(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Список всех мест силы"""
    result = await db.execute(select(Place).order_by(Place.created_at.desc()))
    places = result.scalars().all()
    return [
        {
            "id": str(p.id), "name": p.name, "description": p.description,
            "country": p.country, "city": p.city,
            "latitude": p.latitude, "longitude": p.longitude,
            "photo_url": p.photo_url, "video_url": p.video_url,
            "is_default": p.is_default,
            "created_at": str(p.created_at),
        }
        for p in places
    ]


@router.post("", status_code=201)
async def create_place(
    data: PlaceCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Создание нового места (только админ)"""
    place = Place(
        name=data.name, description=data.description,
        country=data.country, city=data.city,
        latitude=data.latitude, longitude=data.longitude,
        photo_url=data.photo_url, video_url=data.video_url,
        creator_id=user.id,
    )
    db.add(place)
    await db.commit()
    await db.refresh(place)
    return {"id": str(place.id), "name": place.name}


@router.put("/{place_id}")
async def update_place(
    place_id: str,
    data: PlaceUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Редактирование места (только админ)"""
    result = await db.execute(select(Place).where(Place.id == uuid.UUID(place_id)))
    place = result.scalar_one_or_none()
    if not place:
        raise HTTPException(status_code=404, detail="Место не найдено")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(place, field, value)
    await db.commit()
    return {"message": "Место обновлено"}


@router.delete("/{place_id}")
async def delete_place(
    place_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Удаление места (только админ)"""
    result = await db.execute(select(Place).where(Place.id == uuid.UUID(place_id)))
    place = result.scalar_one_or_none()
    if not place:
        raise HTTPException(status_code=404, detail="Место не найдено")
    await db.delete(place)
    await db.commit()
    return {"message": "Место удалено"}


@router.post("/init-defaults")
async def init_default_places(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Инициализация мест по умолчанию (Грузия, Болгария и т.д.)"""
    result = await db.execute(select(Place).where(Place.is_default == True))
    existing = result.scalars().all()
    if existing:
        return {"message": "Места по умолчанию уже существуют", "count": len(existing)}

    for p_data in DEFAULT_PLACES:
        place = Place(is_default=True, creator_id=user.id, **p_data)
        db.add(place)
    await db.commit()
    return {"message": f"Создано {len(DEFAULT_PLACES)} мест по умолчанию"}


@router.post("/{place_id}/photo")
async def upload_place_photo(
    place_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Загрузка фото для места"""
    result = await db.execute(select(Place).where(Place.id == uuid.UUID(place_id)))
    place = result.scalar_one_or_none()
    if not place:
        raise HTTPException(status_code=404, detail="Место не найдено")

    url = await upload_file_to_s3(file, f"places/{place_id}")
    place.photo_url = url
    await db.commit()
    return {"photo_url": url}
