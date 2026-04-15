from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from database import get_db
from models import Payment, Order, User, Table
from schemas import PaymentCreate, PaymentInDB, PaginatedResponse, MessageResponse
from deps import get_current_user, has_permission
from services.payment_service import PaymentService

router = APIRouter()

@router.get("/", response_model=PaginatedResponse)
async def get_payments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    order_id: Optional[int] = None,
    method: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Barcha to'lovlarni olish"""
    query = db.query(Payment)
    
    if order_id:
        query = query.filter(Payment.order_id == order_id)
    
    if method:
        query = query.filter(Payment.method == method)
    
    if status:
        query = query.filter(Payment.status == status)
    
    if date_from:
        query = query.filter(Payment.created_at >= date_from)
    
    if date_to:
        query = query.filter(Payment.created_at <= date_to)
    
    total = query.count()
    payments = query.order_by(Payment.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedResponse(
        items=[PaymentInDB.model_validate(p) for p in payments],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )

@router.post("/", response_model=PaymentInDB)
async def create_payment(
    payment_data: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Yangi to'lov yaratish"""
    payment_service = PaymentService(db)
    
    # Buyurtmani tekshirish
    order = db.query(Order).filter(Order.id == payment_data.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    
    # To'lovni qayta ishlash
    payment = payment_service.process_payment(
        order=order,
        amount=payment_data.amount,
        method=payment_data.method,
        cashier_id=current_user.id,
        reference=payment_data.reference
    )
    
    # Agar to'liq to'langan bo'lsa, buyurtmani yakunlash
    total_paid = sum(p.amount for p in order.payments if p.status == "paid")
    if total_paid >= order.final_amount:
        order.status = "completed"
        order.completed_at = datetime.now()
        
        # Stolni bo'shatish
        if order.table:
            order.table.status = "free"
        
        db.commit()
    
    return PaymentInDB.model_validate(payment)

@router.get("/{payment_id}", response_model=PaymentInDB)
async def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """To'lov ma'lumotlarini olish"""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="To'lov topilmadi")
    
    return PaymentInDB.model_validate(payment)

@router.post("/{payment_id}/refund", response_model=MessageResponse)
async def refund_payment(
    payment_id: int,
    amount: Optional[float] = None,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("process_payments"))
):
    """To'lovni qaytarish"""
    payment_service = PaymentService(db)
    
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="To'lov topilmadi")
    
    if payment.status != "paid":
        raise HTTPException(status_code=400, detail="Faqat to'langan to'lovlarni qaytarish mumkin")
    
    refund_amount = amount or payment.amount
    
    if refund_amount > payment.amount:
        raise HTTPException(status_code=400, detail="Qaytarish summasi to'lov summasidan ko'p bo'lishi mumkin emas")
    
    success = payment_service.refund_payment(payment, refund_amount, reason)
    
    if success:
        # Buyurtma holatini yangilash
        order = payment.order
        if refund_amount == payment.amount:
            payment.status = "refunded"
        
        # Agar barcha to'lovlar qaytarilgan bo'lsa
        all_refunded = all(p.status == "refunded" for p in order.payments)
        if all_refunded and order.status == "completed":
            order.status = "cancelled"
        
        db.commit()
        
        return MessageResponse(message="To'lov qaytarildi")
    
    raise HTTPException(status_code=500, detail="To'lovni qaytarishda xatolik")

@router.get("/methods/summary")
async def get_payment_methods_summary(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """To'lov usullari bo'yicha xulosa"""
    from sqlalchemy import func
    
    query = db.query(
        Payment.method,
        func.sum(Payment.amount).label('total'),
        func.count(Payment.id).label('count')
    ).filter(Payment.status == "paid")
    
    if date_from:
        query = query.filter(Payment.created_at >= date_from)
    
    if date_to:
        query = query.filter(Payment.created_at <= date_to)
    
    results = query.group_by(Payment.method).all()
    
    return [
        {
            "method": r.method,
            "total": float(r.total or 0),
            "count": r.count
        }
        for r in results
    ]