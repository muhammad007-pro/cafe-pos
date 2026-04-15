from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from database import get_db
from models import Order, OrderItem, User, Product
from schemas import OrderInDB, MessageResponse
from deps import get_current_user, has_permission
from services.kitchen_service import KitchenService
from websocket.manager import manager

router = APIRouter()

@router.get("/orders")
async def get_kitchen_orders(
    station: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Oshxona uchun buyurtmalarni olish"""
    kitchen_service = KitchenService(db)
    
    orders = kitchen_service.get_kitchen_orders(station=station, status=status)
    
    # Buyurtmalarni status bo'yicha guruhlash
    pending = []
    preparing = []
    ready = []
    
    for order in orders:
        order_data = {
            "id": order.id,
            "order_number": order.order_number,
            "table_number": order.table.number if order.table else None,
            "order_type": "dine-in" if order.table else "takeaway",
            "waiter_name": order.waiter.full_name if order.waiter else None,
            "customer_name": order.customer.name if order.customer else None,
            "created_at": order.created_at,
            "status": order.status,
            "notes": order.notes,
            "urgent": "tez" in (order.notes or "").lower(),
            "items": [
                {
                    "id": item.id,
                    "product_id": item.product_id,
                    "product_name": item.product.name,
                    "quantity": item.quantity,
                    "notes": item.notes,
                    "status": item.status
                }
                for item in order.items
            ]
        }
        
        if order.status == "pending" or order.status == "confirmed":
            pending.append(order_data)
        elif order.status == "preparing":
            preparing.append(order_data)
        elif order.status == "ready":
            ready.append(order_data)
    
    return {
        "pending": pending,
        "preparing": preparing,
        "ready": ready,
        "completed": []  # Tarix uchun alohida endpoint
    }

@router.patch("/orders/{order_id}/start")
async def start_preparing_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Buyurtmani tayyorlashni boshlash"""
    kitchen_service = KitchenService(db)
    
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    
    if order.status not in ["pending", "confirmed"]:
        raise HTTPException(status_code=400, detail="Bu buyurtmani tayyorlashni boshlab bo'lmaydi")
    
    order.status = "preparing"
    db.commit()
    
    # WebSocket orqali xabar yuborish
    await manager.broadcast_to_pos({
        "type": "order_status_changed",
        "order_id": order_id,
        "order_number": order.order_number,
        "status": "preparing"
    })
    
    return MessageResponse(message="Buyurtma tayyorlash boshlandi")

@router.patch("/orders/{order_id}/ready")
async def mark_order_ready(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Buyurtmani tayyor deb belgilash"""
    kitchen_service = KitchenService(db)
    
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    
    if order.status != "preparing":
        raise HTTPException(status_code=400, detail="Bu buyurtma tayyorlanmoqda holatida emas")
    
    order.status = "ready"
    db.commit()
    
    # WebSocket orqali xabar yuborish
    await manager.broadcast_to_pos({
        "type": "order_ready",
        "order_id": order_id,
        "order_number": order.order_number,
        "table_number": order.table.number if order.table else None
    })
    
    # Ofitsiantga bildirishnoma
    if order.waiter_id:
        await manager.send_to_user(order.waiter_id, {
            "type": "notification",
            "title": "Buyurtma tayyor",
            "message": f"#{order.order_number} buyurtma tayyor",
            "order_id": order_id
        })
    
    return MessageResponse(message="Buyurtma tayyor")

@router.patch("/items/{item_id}/status")
async def update_item_status(
    item_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Buyurtma elementi holatini yangilash"""
    item = db.query(OrderItem).filter(OrderItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Buyurtma elementi topilmadi")
    
    valid_statuses = ["pending", "preparing", "ready", "served"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Noto'g'ri holat. Ruxsat etilgan: {valid_statuses}")
    
    item.status = status
    db.commit()
    
    # Agar barcha itemlar tayyor bo'lsa, buyurtmani tayyor deb belgilash
    order = item.order
    all_ready = all(i.status == "ready" for i in order.items)
    
    if all_ready and order.status == "preparing":
        order.status = "ready"
        db.commit()
        
        await manager.broadcast_to_pos({
            "type": "order_ready",
            "order_id": order.id,
            "order_number": order.order_number
        })
    
    return MessageResponse(message=f"Element holati yangilandi: {status}")

@router.get("/history")
async def get_kitchen_history(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    station: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Oshxona tarixini olish"""
    query = db.query(Order).filter(Order.status.in_(["completed", "cancelled"]))
    
    if date_from:
        query = query.filter(Order.created_at >= date_from)
    
    if date_to:
        query = query.filter(Order.created_at <= date_to)
    
    total = query.count()
    orders = query.order_by(Order.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    items = []
    for order in orders:
        preparation_time = None
        if order.completed_at and order.created_at:
            delta = order.completed_at - order.created_at
            preparation_time = delta.total_seconds() // 60
        
        items.append({
            "id": order.id,
            "order_number": order.order_number,
            "table_number": order.table.number if order.table else None,
            "order_type": "dine-in" if order.table else "takeaway",
            "status": order.status,
            "created_at": order.created_at,
            "completed_at": order.completed_at,
            "preparation_time": preparation_time,
            "items_count": len(order.items)
        })
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }

@router.get("/stats")
async def get_kitchen_stats(
    date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Oshxona statistikasi"""
    from sqlalchemy import func
    
    target_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now().date()
    
    query = db.query(Order).filter(
        func.date(Order.created_at) == target_date
    )
    
    total_orders = query.count()
    completed_orders = query.filter(Order.status == "completed").count()
    cancelled_orders = query.filter(Order.status == "cancelled").count()
    
    # O'rtacha tayyorlash vaqti
    completed = query.filter(Order.status == "completed").all()
    prep_times = []
    
    for order in completed:
        if order.completed_at and order.created_at:
            delta = order.completed_at - order.created_at
            prep_times.append(delta.total_seconds() // 60)
    
    avg_prep_time = sum(prep_times) / len(prep_times) if prep_times else 0
    
    return {
        "date": target_date.isoformat(),
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "cancelled_orders": cancelled_orders,
        "completion_rate": (completed_orders / total_orders * 100) if total_orders > 0 else 0,
        "average_preparation_time": round(avg_prep_time, 1)
    }