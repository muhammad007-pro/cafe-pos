from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List

from models import Order, OrderItem, Product, Table, User
from schemas import OrderCreate, OrderUpdate

class OrderService:
    def __init__(self, db: Session):
        self.db = db
    
    def generate_order_number(self) -> str:
        """Buyurtma raqamini yaratish"""
        from datetime import datetime
        import random
        
        now = datetime.now()
        year = str(now.year)[-2:]
        month = str(now.month).zfill(2)
        day = str(now.day).zfill(2)
        random_digits = str(random.randint(1000, 9999))
        
        return f"{year}{month}{day}{random_digits}"
    
    def create_order(self, order_data: OrderCreate, waiter_id: int) -> Order:
        """Yangi buyurtma yaratish"""
        # Buyurtma raqami
        order_number = self.generate_order_number()
        
        # Jami summani hisoblash
        total_amount = 0
        items_data = []
        
        for item in order_data.items:
            product = self.db.query(Product).filter(Product.id == item.product_id).first()
            if not product:
                raise ValueError(f"Mahsulot topilmadi: {item.product_id}")
            
            if not product.is_available:
                raise ValueError(f"Mahsulot mavjud emas: {product.name}")
            
            unit_price = product.price
            total_price = unit_price * item.quantity
            total_amount += total_price
            
            items_data.append({
                "product": product,
                "quantity": item.quantity,
                "unit_price": unit_price,
                "total_price": total_price,
                "notes": item.notes
            })
        
        # Buyurtmani yaratish
        order = Order(
            order_number=order_number,
            table_id=order_data.table_id,
            waiter_id=waiter_id,
            customer_id=order_data.customer_id,
            total_amount=total_amount,
            final_amount=total_amount,
            notes=order_data.notes,
            status="pending"
        )
        
        self.db.add(order)
        self.db.flush()  # ID olish uchun
        
        # Buyurtma elementlarini qo'shish
        for item_data in items_data:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item_data["product"].id,
                quantity=item_data["quantity"],
                unit_price=item_data["unit_price"],
                total_price=item_data["total_price"],
                notes=item_data["notes"]
            )
            self.db.add(order_item)
        
        self.db.commit()
        self.db.refresh(order)
        
        return order
    
    def update_order(self, order_id: int, order_data: OrderUpdate) -> Optional[Order]:
        """Buyurtmani yangilash"""
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return None
        
        update_data = order_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(order, field, value)
        
        if "status" in update_data and update_data["status"] == "completed":
            order.completed_at = datetime.now()
        
        self.db.commit()
        self.db.refresh(order)
        
        return order
    
    def add_item(self, order_id: int, product_id: int, quantity: int, notes: Optional[str] = None) -> Optional[Order]:
        """Buyurtmaga mahsulot qo'shish"""
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return None
        
        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            return None
        
        # Mavjud elementni tekshirish
        existing_item = self.db.query(OrderItem).filter(
            OrderItem.order_id == order_id,
            OrderItem.product_id == product_id
        ).first()
        
        if existing_item:
            existing_item.quantity += quantity
            existing_item.total_price = existing_item.unit_price * existing_item.quantity
        else:
            order_item = OrderItem(
                order_id=order_id,
                product_id=product_id,
                quantity=quantity,
                unit_price=product.price,
                total_price=product.price * quantity,
                notes=notes
            )
            self.db.add(order_item)
        
        # Jami summani yangilash
        self._update_order_total(order)
        
        self.db.commit()
        self.db.refresh(order)
        
        return order
    
    def remove_item(self, order_id: int, item_id: int) -> bool:
        """Buyurtmadan mahsulotni o'chirish"""
        item = self.db.query(OrderItem).filter(
            OrderItem.id == item_id,
            OrderItem.order_id == order_id
        ).first()
        
        if not item:
            return False
        
        self.db.delete(item)
        
        # Jami summani yangilash
        order = self.db.query(Order).filter(Order.id == order_id).first()
        self._update_order_total(order)
        
        self.db.commit()
        
        return True
    
    def _update_order_total(self, order: Order):
        """Buyurtma jami summasini yangilash"""
        items = self.db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
        total = sum(item.total_price for item in items)
        order.total_amount = total
        order.final_amount = total - (order.discount_amount or 0)
    
    def cancel_order(self, order_id: int, reason: Optional[str] = None) -> Optional[Order]:
        """Buyurtmani bekor qilish"""
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return None
        
        order.status = "cancelled"
        if reason:
            order.notes = f"{order.notes or ''}\nBekor qilish sababi: {reason}".strip()
        
        self.db.commit()
        self.db.refresh(order)
        
        return order
    
    def get_orders(self, page: int, page_size: int, **filters):
        """Buyurtmalarni filtrlash"""
        query = self.db.query(Order)
        
        if filters.get("status"):
            query = query.filter(Order.status == filters["status"])
        
        if filters.get("table_id"):
            query = query.filter(Order.table_id == filters["table_id"])
        
        if filters.get("date_from"):
            query = query.filter(Order.created_at >= filters["date_from"])
        
        if filters.get("date_to"):
            query = query.filter(Order.created_at <= filters["date_to"])
        
        total = query.count()
        orders = query.order_by(Order.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        
        return orders, total
    
    def apply_discount(self, order_id: int, discount_amount: float) -> Optional[Order]:
        """Buyurtmaga chegirma qo'llash"""
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return None
        
        if discount_amount > order.total_amount:
            discount_amount = order.total_amount
        
        order.discount_amount = discount_amount
        order.final_amount = order.total_amount - discount_amount
        
        self.db.commit()
        self.db.refresh(order)
        
        return order