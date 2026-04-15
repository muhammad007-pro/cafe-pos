from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional, List
import os
import uuid

from database import get_db
from models import Product, Category, User
from schemas import ProductCreate, ProductUpdate, ProductInDB, PaginatedResponse, MessageResponse
from deps import get_current_user, has_permission
from config import settings

router = APIRouter()

@router.get("/", response_model=PaginatedResponse)
async def get_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: Optional[int] = None,
    is_active: Optional[bool] = True,
    is_available: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Barcha mahsulotlarni olish"""
    query = db.query(Product)
    
    if category_id:
        query = query.filter(Product.category_id == category_id)
    
    if is_active is not None:
        query = query.filter(Product.is_active == is_active)
    
    if is_available is not None:
        query = query.filter(Product.is_available == is_available)
    
    if search:
        query = query.filter(
            Product.name.ilike(f"%{search}%") | 
            Product.barcode.ilike(f"%{search}%") |
            Product.sku.ilike(f"%{search}%")
        )
    
    total = query.count()
    products = query.order_by(Product.name).offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedResponse(
        items=[ProductInDB.model_validate(p) for p in products],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )

@router.get("/all", response_model=List[ProductInDB])
async def get_all_products(
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Barcha mahsulotlarni paginatsiyasiz olish"""
    query = db.query(Product).filter(Product.is_active == True, Product.is_available == True)
    
    if category_id:
        query = query.filter(Product.category_id == category_id)
    
    products = query.order_by(Product.name).all()
    return [ProductInDB.model_validate(p) for p in products]

@router.post("/", response_model=ProductInDB)
async def create_product(
    product_data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_menu"))
):
    """Yangi mahsulot yaratish"""
    # Kategoriya tekshirish
    category = db.query(Category).filter(Category.id == product_data.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Kategoriya topilmadi")
    
    # Barcode tekshirish
    if product_data.barcode:
        existing = db.query(Product).filter(Product.barcode == product_data.barcode).first()
        if existing:
            raise HTTPException(status_code=400, detail="Bu barcode band")
    
    product = Product(**product_data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    
    return ProductInDB.model_validate(product)

@router.get("/{product_id}", response_model=ProductInDB)
async def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mahsulot ma'lumotlarini olish"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")
    
    return ProductInDB.model_validate(product)

@router.patch("/{product_id}", response_model=ProductInDB)
async def update_product(
    product_id: int,
    product_data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_menu"))
):
    """Mahsulotni yangilash"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")
    
    update_data = product_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)
    
    db.commit()
    db.refresh(product)
    
    return ProductInDB.model_validate(product)

@router.delete("/{product_id}", response_model=MessageResponse)
async def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_menu"))
):
    """Mahsulotni o'chirish"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")
    
    # Soft delete - faqat nofaol qilish
    product.is_active = False
    product.is_available = False
    db.commit()
    
    return MessageResponse(message="Mahsulot o'chirildi")

@router.post("/{product_id}/image")
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_menu"))
):
    """Mahsulot rasmini yuklash"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")
    
    # Fayl kengaytmasini tekshirish
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.webp']
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Faqat rasm fayllari yuklash mumkin")
    
    # Fayl nomini yaratish
    filename = f"product_{product_id}_{uuid.uuid4().hex[:8]}{file_ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, "products", filename)
    
    # Papkani yaratish
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Faylni saqlash
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    # URL ni saqlash
    product.image_url = f"/uploads/products/{filename}"
    db.commit()
    
    return {"message": "Rasm yuklandi", "image_url": product.image_url}

@router.get("/barcode/{barcode}", response_model=ProductInDB)
async def get_product_by_barcode(
    barcode: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Barcode bo'yicha mahsulotni topish"""
    product = db.query(Product).filter(Product.barcode == barcode).first()
    if not product:
        raise HTTPException(status_code=404, detail="Mahsulot topilmadi")
    
    return ProductInDB.model_validate(product)