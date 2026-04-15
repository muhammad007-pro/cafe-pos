from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from database import get_db
from models import Inventory, Product, User
from schemas import InventoryCreate, InventoryUpdate, InventoryInDB, PaginatedResponse, MessageResponse
from deps import get_current_user, has_permission

router = APIRouter()

@router.get("/", response_model=PaginatedResponse)
async def get_inventory_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    low_stock_only: bool = False,
    category_id: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ombor ma'lumotlarini olish"""
    query = db.query(Inventory).join(Product)
    
    if low_stock_only:
        query = query.filter(Inventory.quantity <= Inventory.min_threshold)
    
    if category_id:
        query = query.filter(Product.category_id == category_id)
    
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    
    total = query.count()
    items = query.order_by(Product.name).offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedResponse(
        items=[InventoryInDB.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )

@router.get("/low-stock", response_model=list[InventoryInDB])
async def get_low_stock_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Kam qolgan mahsulotlar"""
    items = db.query(Inventory).join(Product).filter(
        Inventory.quantity <= Inventory.min_threshold
    ).order_by(Product.name).all()
    
    return [InventoryInDB.model_validate(i) for i in items]

@router.get("/{inventory_id}", response_model=InventoryInDB)
async def get_inventory_item(
    inventory_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ombor elementi ma'lumotlarini olish"""
    item = db.query(Inventory).filter(Inventory.id == inventory_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Ombor elementi topilmadi")
    
    return InventoryInDB.model_validate(item)

@router.post("/", response_model=InventoryInDB)
async def create_inventory_item(
    inventory_data: InventoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_inventory"))
):
    """Yangi ombor elementi yaratish"""
    # Mahsulot tekshirish
    product = db.query(Product).filter(Product.id == inventory_data.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")
    
    # Mavjud elementni tekshirish
    existing = db.query(Inventory).filter(Inventory.product_id == inventory_data.product_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Bu mahsulot uchun ombor elementi allaqachon mavjud")
    
    inventory = Inventory(**inventory_data.model_dump())
    db.add(inventory)
    db.commit()
    db.refresh(inventory)
    
    return InventoryInDB.model_validate(inventory)

@router.patch("/{inventory_id}", response_model=InventoryInDB)
async def update_inventory_item(
    inventory_id: int,
    inventory_data: InventoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_inventory"))
):
    """Ombor elementini yangilash"""
    inventory = db.query(Inventory).filter(Inventory.id == inventory_id).first()
    if not inventory:
        raise HTTPException(status_code=404, detail="Ombor elementi topilmadi")
    
    update_data = inventory_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(inventory, field, value)
    
    inventory.updated_at = datetime.now()
    db.commit()
    db.refresh(inventory)
    
    return InventoryInDB.model_validate(inventory)

@router.post("/{inventory_id}/add-stock")
async def add_stock(
    inventory_id: int,
    quantity: float,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_inventory"))
):
    """Omborga mahsulot qo'shish"""
    inventory = db.query(Inventory).filter(Inventory.id == inventory_id).first()
    if not inventory:
        raise HTTPException(status_code=404, detail="Ombor elementi topilmadi")
    
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Miqdor musbat bo'lishi kerak")
    
    inventory.quantity += quantity
    inventory.last_restock = datetime.now()
    inventory.updated_at = datetime.now()
    
    # TODO: Kirim tarixini saqlash
    
    db.commit()
    db.refresh(inventory)
    
    return MessageResponse(message=f"{quantity} {inventory.unit} qo'shildi. Yangi miqdor: {inventory.quantity} {inventory.unit}")

@router.post("/{inventory_id}/remove-stock")
async def remove_stock(
    inventory_id: int,
    quantity: float,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_inventory"))
):
    """Omborni kamaytirish"""
    inventory = db.query(Inventory).filter(Inventory.id == inventory_id).first()
    if not inventory:
        raise HTTPException(status_code=404, detail="Ombor elementi topilmadi")
    
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Miqdor musbat bo'lishi kerak")
    
    if inventory.quantity < quantity:
        raise HTTPException(status_code=400, detail=f"Yetarli miqdor mavjud emas. Mavjud: {inventory.quantity} {inventory.unit}")
    
    inventory.quantity -= quantity
    inventory.updated_at = datetime.now()
    
    # TODO: Chiqim tarixini saqlash
    
    db.commit()
    db.refresh(inventory)
    
    return MessageResponse(message=f"{quantity} {inventory.unit} chiqarildi. Qoldiq: {inventory.quantity} {inventory.unit}")

@router.get("/product/{product_id}", response_model=InventoryInDB)
async def get_inventory_by_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mahsulot bo'yicha ombor ma'lumotini olish"""
    inventory = db.query(Inventory).filter(Inventory.product_id == product_id).first()
    
    if not inventory:
        # Agar ombor elementi bo'lmasa, avtomatik yaratish
        product = db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Mahsulot topilmadi")
        
        inventory = Inventory(
            product_id=product_id,
            quantity=0,
            unit="dona",
            min_threshold=5,
            max_threshold=100
        )
        db.add(inventory)
        db.commit()
        db.refresh(inventory)
    
    return InventoryInDB.model_validate(inventory)

@router.post("/sync-from-orders")
async def sync_inventory_from_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_inventory"))
):
    """Buyurtmalar asosida omborni yangilash"""
    # Bu funksiya buyurtmalar asosida omborni avtomatik kamaytirish uchun
    # Odatda order_service orqali avtomatik chaqiriladi
    
    return MessageResponse(message="Ombor sinxronizatsiyasi bajarildi")