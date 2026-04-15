from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from database import get_db
from models import Shift, User, Order, Payment
from schemas import ShiftCreate, ShiftUpdate, ShiftInDB, MessageResponse
from deps import get_current_user, has_permission

router = APIRouter()

@router.get("/", response_model=list[ShiftInDB])
async def get_shifts(
    user_id: Optional[int] = None,
    date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Smenalarni olish"""
    query = db.query(Shift)
    
    if user_id:
        query = query.filter(Shift.user_id == user_id)
    
    if date:
        target_date = datetime.strptime(date, "%Y-%m-%d")
        query = query.filter(
            Shift.start_time >= target_date,
            Shift.start_time < target_date.replace(hour=23, minute=59, second=59)
        )
    
    shifts = query.order_by(Shift.start_time.desc()).all()
    return [ShiftInDB.model_validate(s) for s in shifts]

@router.post("/", response_model=ShiftInDB)
async def create_shift(
    shift_data: ShiftCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Yangi smena ochish"""
    # Faol smena mavjudligini tekshirish
    active_shift = db.query(Shift).filter(
        Shift.user_id == shift_data.user_id,
        Shift.end_time.is_(None)
    ).first()
    
    if active_shift:
        raise HTTPException(status_code=400, detail="Bu foydalanuvchida faol smena mavjud")
    
    shift = Shift(
        user_id=shift_data.user_id,
        start_time=datetime.now(),
        starting_cash=shift_data.starting_cash
    )
    
    db.add(shift)
    db.commit()
    db.refresh(shift)
    
    return ShiftInDB.model_validate(shift)

@router.post("/{shift_id}/close", response_model=ShiftInDB)
async def close_shift(
    shift_id: int,
    ending_cash: float,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Smenani yopish"""
    shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Smena topilmadi")
    
    if shift.end_time:
        raise HTTPException(status_code=400, detail="Smena allaqachon yopilgan")
    
    # Smena davomidagi savdolarni hisoblash
    orders = db.query(Order).filter(
        Order.waiter_id == shift.user_id,
        Order.created_at >= shift.start_time,
        Order.created_at <= datetime.now()
    ).all()
    
    total_sales = sum(o.final_amount for o in orders if o.status == "completed")
    
    payments = db.query(Payment).filter(
        Payment.created_at >= shift.start_time,
        Payment.created_at <= datetime.now(),
        Payment.status == "paid"
    ).all()
    
    cash_sales = sum(p.amount for p in payments if p.method == "cash")
    card_sales = sum(p.amount for p in payments if p.method == "card")
    
    shift.end_time = datetime.now()
    shift.ending_cash = ending_cash
    shift.total_sales = total_sales
    shift.cash_sales = cash_sales
    shift.card_sales = card_sales
    shift.notes = notes
    
    db.commit()
    db.refresh(shift)
    
    return ShiftInDB.model_validate(shift)

@router.get("/active")
async def get_active_shift(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Joriy foydalanuvchining faol smenasini olish"""
    shift = db.query(Shift).filter(
        Shift.user_id == current_user.id,
        Shift.end_time.is_(None)
    ).first()
    
    if not shift:
        return None
    
    return ShiftInDB.model_validate(shift)