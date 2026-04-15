from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from models import Customer, User, Order
from schemas import CustomerCreate, CustomerUpdate, CustomerInDB, PaginatedResponse, MessageResponse
from deps import get_current_user, has_permission

router = APIRouter()

@router.get("/", response_model=PaginatedResponse)
async def get_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Barcha mijozlarni olish"""
    query = db.query(Customer)
    
    if search:
        query = query.filter(
            Customer.name.ilike(f"%{search}%") | 
            Customer.phone.ilike(f"%{search}%") |
            Customer.email.ilike(f"%{search}%")
        )
    
    total = query.count()
    customers = query.order_by(Customer.name).offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedResponse(
        items=[CustomerInDB.model_validate(c) for c in customers],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )

@router.get("/all", response_model=list[CustomerInDB])
async def get_all_customers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Barcha mijozlarni paginatsiyasiz olish"""
    customers = db.query(Customer).order_by(Customer.name).all()
    return [CustomerInDB.model_validate(c) for c in customers]

@router.post("/", response_model=CustomerInDB)
async def create_customer(
    customer_data: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Yangi mijoz yaratish"""
    # Telefon raqam tekshirish
    if customer_data.phone:
        existing = db.query(Customer).filter(Customer.phone == customer_data.phone).first()
        if existing:
            raise HTTPException(status_code=400, detail="Bu telefon raqam band")
    
    # Email tekshirish
    if customer_data.email:
        existing = db.query(Customer).filter(Customer.email == customer_data.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Bu email band")
    
    customer = Customer(**customer_data.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    
    return CustomerInDB.model_validate(customer)

@router.get("/{customer_id}", response_model=CustomerInDB)
async def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mijoz ma'lumotlarini olish"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Mijoz topilmadi")
    
    return CustomerInDB.model_validate(customer)

@router.patch("/{customer_id}", response_model=CustomerInDB)
async def update_customer(
    customer_id: int,
    customer_data: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mijozni yangilash"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Mijoz topilmadi")
    
    update_data = customer_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(customer, field, value)
    
    db.commit()
    db.refresh(customer)
    
    return CustomerInDB.model_validate(customer)

@router.delete("/{customer_id}", response_model=MessageResponse)
async def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_customers"))
):
    """Mijozni o'chirish"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Mijoz topilmadi")
    
    # Buyurtmalar mavjudligini tekshirish
    if customer.orders:
        raise HTTPException(status_code=400, detail="Bu mijozda buyurtmalar mavjud, o'chirib bo'lmaydi")
    
    db.delete(customer)
    db.commit()
    
    return MessageResponse(message="Mijoz o'chirildi")

@router.get("/{customer_id}/orders")
async def get_customer_orders(
    customer_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mijozning buyurtmalarini olish"""
    from schemas import OrderInDB, PaginatedResponse
    
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Mijoz topilmadi")
    
    query = db.query(Order).filter(Order.customer_id == customer_id)
    total = query.count()
    orders = query.order_by(Order.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedResponse(
        items=[OrderInDB.model_validate(o) for o in orders],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )

@router.get("/{customer_id}/stats")
async def get_customer_stats(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mijoz statistikasi"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Mijoz topilmadi")
    
    orders = customer.orders
    
    total_spent = sum(o.final_amount for o in orders if o.status == "completed")
    total_visits = len([o for o in orders if o.status == "completed"])
    average_check = total_spent / total_visits if total_visits > 0 else 0
    last_visit = max([o.created_at for o in orders]) if orders else None
    
    return {
        "customer_id": customer_id,
        "customer_name": customer.name,
        "total_spent": total_spent,
        "total_visits": total_visits,
        "average_check": average_check,
        "points": customer.points,
        "last_visit": last_visit
    }

@router.post("/search")
async def search_customers(
    query: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mijozlarni qidirish"""
    customers = db.query(Customer).filter(
        Customer.name.ilike(f"%{query}%") | 
        Customer.phone.ilike(f"%{query}%")
    ).limit(10).all()
    
    return [CustomerInDB.model_validate(c) for c in customers]