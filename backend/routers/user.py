from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from database import get_db
from models import User, Role
from schemas import UserCreate, UserUpdate, UserInDB, PaginatedResponse, MessageResponse
from deps import get_current_user, has_permission, get_current_active_user
from core.security import get_password_hash

router = APIRouter()

@router.get("/", response_model=PaginatedResponse)
async def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    role_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_users"))
):
    """Barcha foydalanuvchilarni olish"""
    query = db.query(User)
    
    if search:
        query = query.filter(
            User.full_name.ilike(f"%{search}%") |
            User.username.ilike(f"%{search}%") |
            User.email.ilike(f"%{search}%")
        )
    
    if role_id:
        query = query.filter(User.role_id == role_id)
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    total = query.count()
    users = query.order_by(User.full_name).offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedResponse(
        items=[UserInDB.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )

@router.get("/me", response_model=UserInDB)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """Joriy foydalanuvchi ma'lumotlari"""
    return UserInDB.model_validate(current_user)

@router.post("/", response_model=UserInDB)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_users"))
):
    """Yangi foydalanuvchi yaratish"""
    # Username tekshirish
    existing = db.query(User).filter(User.username == user_data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Bu username band")
    
    # Email tekshirish
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Bu email band")
    
    # Rol tekshirish
    if user_data.role_id:
        role = db.query(Role).filter(Role.id == user_data.role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="Rol topilmadi")
    
    user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        phone=user_data.phone,
        hashed_password=get_password_hash(user_data.password),
        role_id=user_data.role_id,
        is_active=True
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return UserInDB.model_validate(user)

@router.get("/{user_id}", response_model=UserInDB)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_users"))
):
    """Foydalanuvchi ma'lumotlarini olish"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    
    return UserInDB.model_validate(user)

@router.patch("/{user_id}", response_model=UserInDB)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_users"))
):
    """Foydalanuvchini yangilash"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    
    update_data = user_data.model_dump(exclude_unset=True)
    
    # Parol alohida yangilanadi
    if "password" in update_data:
        user.hashed_password = get_password_hash(update_data.pop("password"))
    
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    
    return UserInDB.model_validate(user)

@router.patch("/me", response_model=UserInDB)
async def update_current_user(
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Joriy foydalanuvchi profilini yangilash"""
    update_data = user_data.model_dump(exclude_unset=True)
    
    # Oddiy foydalanuvchi rolini o'zgartira olmaydi
    update_data.pop("role_id", None)
    update_data.pop("is_active", None)
    update_data.pop("is_superuser", None)
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    db.commit()
    db.refresh(current_user)
    
    return UserInDB.model_validate(current_user)

@router.delete("/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_users"))
):
    """Foydalanuvchini o'chirish"""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="O'zingizni o'chira olmaysiz")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    
    # Soft delete - faqat nofaol qilish
    user.is_active = False
    db.commit()
    
    return MessageResponse(message="Foydalanuvchi o'chirildi")

@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    new_password: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_users"))
):
    """Foydalanuvchi parolini tiklash (admin uchun)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    
    user.hashed_password = get_password_hash(new_password)
    db.commit()
    
    return MessageResponse(message="Parol yangilandi")