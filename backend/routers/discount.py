from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from database import get_db
from models import Discount, Product, Category, User
from schemas import DiscountCreate, DiscountInDB, PaginatedResponse, MessageResponse
from deps import get_current_user, has_permission

router = APIRouter()

@router.get("/", response_model=PaginatedResponse)
async def get_discounts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Barcha chegirmalarni olish"""
    query = db.query(Discount)
    
    if is_active is not None:
        query = query.filter(Discount.is_active == is_active)
    
    total = query.count()
    discounts = query.order_by(Discount.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedResponse(
        items=[DiscountInDB.model_validate(d) for d in discounts],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )

@router.get("/active", response_model=list[DiscountInDB])
async def get_active_discounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Faol chegirmalarni olish"""
    now = datetime.now()
    
    discounts = db.query(Discount).filter(
        Discount.is_active == True,
        (Discount.valid_from.is_(None) | (Discount.valid_from <= now)),
        (Discount.valid_to.is_(None) | (Discount.valid_to >= now))
    ).all()
    
    return [DiscountInDB.model_validate(d) for d in discounts]

@router.post("/", response_model=DiscountInDB)
async def create_discount(
    discount_data: DiscountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_discounts"))
):
    """Yangi chegirma yaratish"""
    # Mahsulot tekshirish
    if discount_data.product_id:
        product = db.query(Product).filter(Product.id == discount_data.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Mahsulot topilmadi")
    
    # Kategoriya tekshirish
    if discount_data.category_id:
        category = db.query(Category).filter(Category.id == discount_data.category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Kategoriya topilmadi")
    
    discount = Discount(**discount_data.model_dump())
    db.add(discount)
    db.commit()
    db.refresh(discount)
    
    return DiscountInDB.model_validate(discount)

@router.get("/{discount_id}", response_model=DiscountInDB)
async def get_discount(
    discount_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Chegirma ma'lumotlarini olish"""
    discount = db.query(Discount).filter(Discount.id == discount_id).first()
    if not discount:
        raise HTTPException(status_code=404, detail="Chegirma topilmadi")
    
    return DiscountInDB.model_validate(discount)

@router.patch("/{discount_id}/toggle")
async def toggle_discount(
    discount_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_discounts"))
):
    """Chegirmani yoqish/o'chirish"""
    discount = db.query(Discount).filter(Discount.id == discount_id).first()
    if not discount:
        raise HTTPException(status_code=404, detail="Chegirma topilmadi")
    
    discount.is_active = not discount.is_active
    db.commit()
    
    return MessageResponse(
        message=f"Chegirma { 'faollashtirildi' if discount.is_active else 'o\'chirildi' }"
    )

@router.delete("/{discount_id}")
async def delete_discount(
    discount_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_discounts"))
):
    """Chegirmani o'chirish"""
    discount = db.query(Discount).filter(Discount.id == discount_id).first()
    if not discount:
        raise HTTPException(status_code=404, detail="Chegirma topilmadi")
    
    db.delete(discount)
    db.commit()
    
    return MessageResponse(message="Chegirma o'chirildi")

@router.post("/validate")
async def validate_discount(
    code: str,
    order_amount: float,
    product_ids: Optional[list[int]] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Chegirmani tekshirish"""
    now = datetime.now()
    
    discount = db.query(Discount).filter(
        Discount.name == code,
        Discount.is_active == True,
        (Discount.valid_from.is_(None) | (Discount.valid_from <= now)),
        (Discount.valid_to.is_(None) | (Discount.valid_to >= now))
    ).first()
    
    if not discount:
        return {"valid": False, "message": "Chegirma topilmadi yoki muddati o'tgan"}
    
    # Minimal summa tekshirish
    if order_amount < discount.min_order_amount:
        return {
            "valid": False, 
            "message": f"Minimal buyurtma summasi {discount.min_order_amount:,.0f} UZS bo'lishi kerak"
        }
    
    # Foydalanish limiti tekshirish
    if discount.usage_limit and discount.used_count >= discount.usage_limit:
        return {"valid": False, "message": "Chegirma limiti tugagan"}
    
    # Mahsulot/kategoriya tekshirish
    if discount.product_id and product_ids:
        if discount.product_id not in product_ids:
            return {"valid": False, "message": "Bu chegirma boshqa mahsulot uchun"}
    
    # Chegirma summasini hisoblash
    discount_amount = 0
    if discount.type == "percentage":
        discount_amount = order_amount * (discount.value / 100)
    else:
        discount_amount = min(discount.value, order_amount)
    
    return {
        "valid": True,
        "discount_id": discount.id,
        "discount_name": discount.name,
        "discount_type": discount.type,
        "discount_value": discount.value,
        "discount_amount": discount_amount,
        "final_amount": order_amount - discount_amount
    }