from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import os
import csv

from models import Order, OrderItem, Payment, Product, Category, User, Shift

class ReportService:
    def __init__(self, db: Session):
        self.db = db
    
    def generate_daily_report(self, date: datetime) -> Dict[str, Any]:
        """Kunlik hisobot"""
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        # Buyurtmalar
        orders = self.db.query(Order).filter(
            Order.created_at >= start_of_day,
            Order.created_at < end_of_day
        ).all()
        
        # To'lovlar
        payments = self.db.query(Payment).filter(
            Payment.created_at >= start_of_day,
            Payment.created_at < end_of_day,
            Payment.status == "paid"
        ).all()
        
        total_sales = sum(p.amount for p in payments)
        cash_sales = sum(p.amount for p in payments if p.method == "cash")
        card_sales = sum(p.amount for p in payments if p.method == "card")
        
        completed_orders = [o for o in orders if o.status == "completed"]
        cancelled_orders = [o for o in orders if o.status == "cancelled"]
        
        # Ommabop mahsulotlar
        popular_items = self.db.query(
            Product.name,
            func.sum(OrderItem.quantity).label('quantity')
        ).join(OrderItem, OrderItem.product_id == Product.id).join(
            Order, Order.id == OrderItem.order_id
        ).filter(
            Order.created_at >= start_of_day,
            Order.created_at < end_of_day
        ).group_by(Product.id, Product.name).order_by(
            func.sum(OrderItem.quantity).desc()
        ).limit(5).all()
        
        return {
            "date": date.strftime("%Y-%m-%d"),
            "total_sales": total_sales,
            "cash_sales": cash_sales,
            "card_sales": card_sales,
            "orders_count": len(orders),
            "completed_orders": len(completed_orders),
            "cancelled_orders": len(cancelled_orders),
            "avg_check": total_sales / len(completed_orders) if completed_orders else 0,
            "popular_items": [
                {"name": item.name, "quantity": int(item.quantity)}
                for item in popular_items
            ],
            "orders": [
                {
                    "id": o.id,
                    "order_number": o.order_number,
                    "table_number": o.table.number if o.table else None,
                    "waiter_name": o.waiter.full_name if o.waiter else None,
                    "total_amount": o.total_amount,
                    "final_amount": o.final_amount,
                    "status": o.status,
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                    "payment_method": o.payments[0].method if o.payments else None
                }
                for o in orders
            ]
        }
    
    def generate_sales_report(self, date_from: datetime, date_to: datetime) -> Dict[str, Any]:
        """Savdo hisoboti"""
        payments = self.db.query(Payment).filter(
            Payment.created_at >= date_from,
            Payment.created_at <= date_to,
            Payment.status == "paid"
        )
        
        total_sales = payments.with_entities(func.sum(Payment.amount)).scalar() or 0
        
        # Kunlik taqsimot
        daily_sales = self.db.query(
            func.date(Payment.created_at).label('date'),
            func.sum(Payment.amount).label('total')
        ).filter(
            Payment.created_at >= date_from,
            Payment.created_at <= date_to,
            Payment.status == "paid"
        ).group_by(func.date(Payment.created_at)).order_by('date').all()
        
        # To'lov usullari bo'yicha
        payment_methods = payments.with_entities(
            Payment.method,
            func.sum(Payment.amount).label('total'),
            func.count(Payment.id).label('count')
        ).group_by(Payment.method).all()
        
        return {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "total_sales": float(total_sales),
            "daily_sales": [
                {"date": str(d.date), "total": float(d.total)}
                for d in daily_sales
            ],
            "payment_methods": [
                {"method": p.method, "total": float(p.total), "count": p.count}
                for p in payment_methods
            ]
        }
    
    def generate_products_report(self, date_from: datetime, date_to: datetime, limit: int = 50) -> Dict[str, Any]:
        """Mahsulotlar hisoboti"""
        products = self.db.query(
            Product.id,
            Product.name,
            Category.name.label('category'),
            func.sum(OrderItem.quantity).label('quantity'),
            func.sum(OrderItem.total_price).label('revenue'),
            func.count(func.distinct(Order.id)).label('orders_count')
        ).join(Category, Category.id == Product.category_id).join(
            OrderItem, OrderItem.product_id == Product.id
        ).join(Order, Order.id == OrderItem.order_id).filter(
            Order.created_at >= date_from,
            Order.created_at <= date_to,
            Order.status == "completed"
        ).group_by(Product.id, Product.name, Category.name).order_by(
            func.sum(OrderItem.quantity).desc()
        ).limit(limit).all()
        
        return {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "products": [
                {
                    "id": p.id,
                    "name": p.name,
                    "category": p.category,
                    "quantity": int(p.quantity or 0),
                    "revenue": float(p.revenue or 0),
                    "orders_count": p.orders_count
                }
                for p in products
            ]
        }
    
    def generate_staff_report(self, date_from: datetime, date_to: datetime) -> Dict[str, Any]:
        """Xodimlar hisoboti"""
        staff = self.db.query(
            User.id,
            User.full_name,
            func.count(Order.id).label('orders_count'),
            func.sum(Order.final_amount).label('total_sales'),
            func.avg(Order.final_amount).label('avg_check')
        ).join(Order, Order.waiter_id == User.id).filter(
            Order.created_at >= date_from,
            Order.created_at <= date_to,
            Order.status == "completed"
        ).group_by(User.id, User.full_name).order_by(
            func.sum(Order.final_amount).desc()
        ).all()
        
        return {
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "staff": [
                {
                    "id": s.id,
                    "name": s.full_name,
                    "orders_count": s.orders_count,
                    "total_sales": float(s.total_sales or 0),
                    "avg_check": float(s.avg_check or 0)
                }
                for s in staff
            ]
        }
    
    def generate_shift_report(self, shift_id: Optional[int] = None, user_id: Optional[int] = None, date: Optional[str] = None) -> Dict[str, Any]:
        """Smena hisoboti"""
        query = self.db.query(Shift)
        
        if shift_id:
            query = query.filter(Shift.id == shift_id)
        elif user_id and date:
            target_date = datetime.strptime(date, "%Y-%m-%d")
            query = query.filter(
                Shift.user_id == user_id,
                func.date(Shift.start_time) == target_date.date()
            )
        
        shifts = query.all()
        
        result = []
        for shift in shifts:
            # Smena davomidagi buyurtmalar
            orders = self.db.query(Order).filter(
                Order.waiter_id == shift.user_id,
                Order.created_at >= shift.start_time,
                Order.created_at <= (shift.end_time or datetime.now())
            ).all()
            
            total_sales = sum(o.final_amount for o in orders if o.status == "completed")
            
            result.append({
                "id": shift.id,
                "user_name": shift.user.full_name if shift.user else None,
                "start_time": shift.start_time.isoformat() if shift.start_time else None,
                "end_time": shift.end_time.isoformat() if shift.end_time else None,
                "starting_cash": shift.starting_cash,
                "ending_cash": shift.ending_cash,
                "total_sales": total_sales,
                "orders_count": len(orders),
                "cash_sales": shift.cash_sales,
                "card_sales": shift.card_sales
            })
        
        return {"shifts": result}
    
    def export_report(self, report_type: str, date_from: datetime, date_to: datetime, format: str) -> str:
        """Hisobotni eksport qilish"""
        import os
        from datetime import datetime
        
        # Hisobot ma'lumotlarini olish
        if report_type == "daily":
            data = self.generate_daily_report(date_from)
            filename = f"daily_report_{date_from.strftime('%Y%m%d')}"
        elif report_type == "sales":
            data = self.generate_sales_report(date_from, date_to)
            filename = f"sales_report_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}"
        elif report_type == "products":
            data = self.generate_products_report(date_from, date_to)
            filename = f"products_report_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}"
        else:
            data = self.generate_staff_report(date_from, date_to)
            filename = f"staff_report_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}"
        
        filename = f"{filename}_{datetime.now().strftime('%H%M%S')}.{format}"
        filepath = os.path.join("static", "exports", filename)
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        if format == "csv":
            self._export_csv(data, filepath, report_type)
        
        return f"/static/exports/{filename}"
    
    def _export_csv(self, data: Dict, filepath: str, report_type: str):
        """CSV formatda eksport"""
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            
            if report_type == "daily":
                writer.writerow(["Kunlik hisobot", data.get('date', '')])
                writer.writerow([])
                writer.writerow(["Jami savdo", "Naqd", "Karta", "Buyurtmalar", "O'rtacha chek"])
                writer.writerow([
                    data.get('total_sales', 0),
                    data.get('cash_sales', 0),
                    data.get('card_sales', 0),
                    data.get('orders_count', 0),
                    data.get('avg_check', 0)
                ])
                
                writer.writerow([])
                writer.writerow(["Ommabop mahsulotlar"])
                writer.writerow(["Mahsulot", "Soni"])
                for item in data.get('popular_items', []):
                    writer.writerow([item.get('name', ''), item.get('quantity', 0)])
                
                writer.writerow([])
                writer.writerow(["Buyurtmalar"])
                writer.writerow(["#", "Stol", "Ofitsiant", "Summa", "Holat", "Vaqt"])
                for order in data.get('orders', []):
                    writer.writerow([
                        order.get('order_number', ''),
                        order.get('table_number', ''),
                        order.get('waiter_name', ''),
                        order.get('final_amount', 0),
                        order.get('status', ''),
                        order.get('created_at', '')
                    ])