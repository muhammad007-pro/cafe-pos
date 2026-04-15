from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime

from database import get_db
from models import Order, OrderItem, Product, Table, User
from schemas import OrderCreate, OrderUpdate, OrderInDB, PaginatedResponse, MessageResponse
from deps import get_current_user
from services.order_service import OrderService
from services.kitchen_service import KitchenService
from services.printer_service import PrinterService
from websocket.manager import manager

router = APIRouter()

@router.get("/", response_model=PaginatedResponse)
async def get_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    table_id: Optional[int] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Barcha buyurtmalarni olish"""
    order_service = OrderService(db)
    orders, total = order_service.get_orders(
        page=page,
        page_size=page_size,
        status=status,
        table_id=table_id,
        date_from=date_from,
        date_to=date_to
    )
    
    return PaginatedResponse(
        items=[OrderInDB.model_validate(o) for o in orders],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )

@router.post("/", response_model=OrderInDB)
async def create_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Yangi buyurtma yaratish"""
    order_service = OrderService(db)
    kitchen_service = KitchenService(db)
    
    # Stolni tekshirish
    table = db.query(Table).filter(Table.id == order_data.table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Stol topilmadi")
    
    # Buyurtmani yaratish
    order = order_service.create_order(
        order_data=order_data,
        waiter_id=current_user.id
    )
    
    # Stol statusini yangilash
    table.status = "occupied"
    db.commit()
    
    # Oshxonaga yuborish
    kitchen_service.send_order_to_kitchen(order)
    
    # WebSocket orqali xabar yuborish
    await manager.broadcast_to_kitchen({
        "type": "new_order",
        "order_id": order.id,
        "order_number": order.order_number,
        "table": table.number,
        "items": [{"name": item.product.name, "quantity": item.quantity} for item in order.items]
    })
    
    # Printerga yuborish
    if PrinterService.is_available():
        PrinterService.print_kitchen_receipt(order)
    
    return OrderInDB.model_validate(order)

@router.get("/{order_id}", response_model=OrderInDB)
async def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Buyurtma ma'lumotlarini olish"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    
    return OrderInDB.model_validate(order)

@router.patch("/{order_id}", response_model=OrderInDB)
async def update_order(
    order_id: int,
    order_data: OrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Buyurtmani yangilash"""
    order_service = OrderService(db)
    
    order = order_service.update_order(order_id, order_data)
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    
    # Agar buyurtma yakunlangan bo'lsa, stolni bo'shatish
    if order_data.status == "completed" or order_data.status == "cancelled":
        table = order.table
        table.status = "free"
        db.commit()
        
        await manager.broadcast({
            "type": "table_freed",
            "table_id": table.id,
            "table_number": table.number
        })
    
    return OrderInDB.model_validate(order)

@router.post("/{order_id}/items")
async def add_item_to_order(
    order_id: int,
    product_id: int,
    quantity: int = 1,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Buyurtmaga mahsulot qo'shish"""
    order_service = OrderService(db)
    
    order = order_service.add_item(order_id, product_id, quantity, notes)
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma yoki mahsulot topilmadi")
    
    # Oshxonaga yangi item haqida xabar yuborish
    product = db.query(Product).filter(Product.id == product_id).first()
    await manager.broadcast_to_kitchen({
        "type": "item_added",
        "order_id": order_id,
        "order_number": order.order_number,
        "item": {
            "product_id": product_id,
            "product_name": product.name,
            "quantity": quantity,
            "notes": notes
        }
    })
    
    return MessageResponse(message="Mahsulot qo'shildi")

@router.delete("/{order_id}/items/{item_id}")
async def remove_item_from_order(
    order_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Buyurtmadan mahsulotni o'chirish"""
    order_service = OrderService(db)
    
    success = order_service.remove_item(order_id, item_id)
    if not success:
        raise HTTPException(status_code=404, detail="Buyurtma elementi topilmadi")
    
    return MessageResponse(message="Mahsulot o'chirildi")

@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: int,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Buyurtmani bekor qilish"""
    order_service = OrderService(db)
    
    order = order_service.cancel_order(order_id, reason)
    if not order:
        raise HTTPException(status_code=404, detail="Buyurtma topilmadi")
    
    # Stolnni bo'shatish
    if order.table:
        order.table.status = "free"
        db.commit()
    
    # Oshxonaga xabar
    await manager.broadcast_to_kitchen({
        "type": "order_cancelled",
        "order_id": order_id,
        "order_number": order.order_number,
        "reason": reason
    })
    
    return MessageResponse(message="Buyurtma bekor qilindi")

@router.get("/table/{table_id}/active")
async def get_active_order_for_table(
    table_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Stolning faol buyurtmasini olish"""
    order = db.query(Order).filter(
        Order.table_id == table_id,
        Order.status.in_(["pending", "confirmed", "preparing", "ready", "served"])
    ).first()
    
    if not order:
        return None
    
    return OrderInDB.model_validate(order)