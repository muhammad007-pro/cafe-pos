from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from models import Table, User, Order
from schemas import TableCreate, TableUpdate, TableInDB, PaginatedResponse, MessageResponse
from deps import get_current_user, has_permission

router = APIRouter()

@router.get("/", response_model=PaginatedResponse)
async def get_tables(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    section: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Barcha stollarni olish"""
    query = db.query(Table)
    
    if section:
        query = query.filter(Table.section == section)
    
    if status:
        query = query.filter(Table.status == status)
    
    total = query.count()
    tables = query.order_by(Table.number).offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedResponse(
        items=[TableInDB.model_validate(t) for t in tables],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )

@router.get("/all", response_model=list[TableInDB])
async def get_all_tables(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Barcha stollarni paginatsiyasiz olish"""
    tables = db.query(Table).order_by(Table.number).all()
    return [TableInDB.model_validate(t) for t in tables]

@router.post("/", response_model=TableInDB)
async def create_table(
    table_data: TableCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_tables"))
):
    """Yangi stol yaratish"""
    existing = db.query(Table).filter(Table.number == table_data.number).first()
    if existing:
        raise HTTPException(status_code=400, detail="Bu raqamli stol mavjud")
    
    table = Table(**table_data.model_dump())
    db.add(table)
    db.commit()
    db.refresh(table)
    
    return TableInDB.model_validate(table)

@router.get("/{table_id}", response_model=TableInDB)
async def get_table(
    table_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Stol ma'lumotlarini olish"""
    table = db.query(Table).filter(Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Stol topilmadi")
    
    return TableInDB.model_validate(table)

@router.patch("/{table_id}", response_model=TableInDB)
async def update_table(
    table_id: int,
    table_data: TableUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Stolni yangilash"""
    table = db.query(Table).filter(Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Stol topilmadi")
    
    update_data = table_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(table, field, value)
    
    db.commit()
    db.refresh(table)
    
    return TableInDB.model_validate(table)

@router.delete("/{table_id}", response_model=MessageResponse)
async def delete_table(
    table_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_tables"))
):
    """Stolni o'chirish"""
    table = db.query(Table).filter(Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Stol topilmadi")
    
    # Buyurtmalar mavjudligini tekshirish
    active_orders = db.query(Order).filter(
        Order.table_id == table_id,
        Order.status.in_(["pending", "confirmed", "preparing", "ready"])
    ).count()
    
    if active_orders > 0:
        raise HTTPException(status_code=400, detail="Bu stolda faol buyurtmalar mavjud")
    
    db.delete(table)
    db.commit()
    
    return MessageResponse(message="Stol o'chirildi")

@router.get("/{table_id}/orders")
async def get_table_orders(
    table_id: int,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Stolga tegishli buyurtmalarni olish"""
    from schemas import OrderInDB
    
    table = db.query(Table).filter(Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Stol topilmadi")
    
    query = db.query(Order).filter(Order.table_id == table_id)
    
    if active_only:
        query = query.filter(Order.status.in_(["pending", "confirmed", "preparing", "ready", "served"]))
    
    orders = query.order_by(Order.created_at.desc()).all()
    
    return [OrderInDB.model_validate(o) for o in orders]

@router.post("/{table_id}/free")
async def free_table(
    table_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Stolni bo'shatish"""
    table = db.query(Table).filter(Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Stol topilmadi")
    
    table.status = "free"
    db.commit()
    
    return MessageResponse(message="Stol bo'shatildi")