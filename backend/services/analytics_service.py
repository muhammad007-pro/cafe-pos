from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from models import Order, OrderItem, Payment, Product, Category, Customer, User, Table

class AnalyticsService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_period_data(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Davr uchun asosiy ko'rsatkichlar"""
        # Buyurtmalar
        orders_query = self.db.query(Order).filter(
            Order.created_at >= start_date,
            Order.created_at <= end_date
        )
        
        total_orders = orders_query.count()
        completed_orders = orders_query.filter(Order.status == "completed").count()
        
        # Daromad
        payments_query = self.db.query(Payment).filter(
            Payment.created_at >= start_date,
            Payment.created_at <= end_date,
            Payment.status == "paid"
        )
        
        total_revenue = payments_query.with_entities(func.sum(Payment.amount)).scalar() or 0
        
        # Mijozlar
        customers_query = self.db.query(Customer).filter(
            Customer.created_at >= start_date,
            Customer.created_at <= end_date
        )
        total_customers = customers_query.count()
        
        # O'rtacha chek
        average_check = total_revenue / completed_orders if completed_orders > 0 else 0
        
        return {
            "total_revenue": total_revenue,
            "total_orders": total_orders,
            "total_customers": total_customers,
            "average_check": average_check,
            "completed_orders": completed_orders
        }
    
    def get_revenue_chart_data(self, start_date: datetime, end_date: datetime, range_type: str) -> Dict[str, List]:
        """Daromad grafigi uchun ma'lumotlar"""
        # Format string aniqlash
        if range_type == "today":
            date_format = "%H:00"
            group_by = func.date_format(Order.created_at, '%Y-%m-%d %H:00')
        elif range_type == "week":
            date_format = "%d.%m"
            group_by = func.date_format(Order.created_at, '%Y-%m-%d')
        elif range_type == "month":
            date_format = "%d.%m"
            group_by = func.date_format(Order.created_at, '%Y-%m-%d')
        else:
            date_format = "%b"
            group_by = func.date_format(Order.created_at, '%Y-%m')
        
        results = self.db.query(
            group_by.label('period'),
            func.sum(Payment.amount).label('revenue')
        ).join(Payment, Payment.order_id == Order.id).filter(
            Order.created_at >= start_date,
            Order.created_at <= end_date,
            Payment.status == "paid"
        ).group_by('period').order_by('period').all()
        
        return {
            "labels": [r.period for r in results],
            "values": [float(r.revenue or 0) for r in results]
        }
    
    def get_popular_products(self, start_date: datetime, end_date: datetime, limit: int = 5) -> List[Dict]:
        """Ommabop mahsulotlar"""
        results = self.db.query(
            Product.id,
            Product.name,
            func.sum(OrderItem.quantity).label('total_quantity'),
            func.sum(OrderItem.total_price).label('total_revenue')
        ).join(OrderItem, OrderItem.product_id == Product.id).join(
            Order, Order.id == OrderItem.order_id
        ).filter(
            Order.created_at >= start_date,
            Order.created_at <= end_date,
            Order.status == "completed"
        ).group_by(Product.id, Product.name).order_by(
            func.sum(OrderItem.quantity).desc()
        ).limit(limit).all()
        
        return [
            {
                "id": r.id,
                "name": r.name,
                "quantity": int(r.total_quantity or 0),
                "revenue": float(r.total_revenue or 0)
            }
            for r in results
        ]
    
    def get_sales_by_category(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Kategoriyalar bo'yicha savdo"""
        results = self.db.query(
            Category.id,
            Category.name,
            func.sum(OrderItem.total_price).label('total_revenue')
        ).join(Product, Product.category_id == Category.id).join(
            OrderItem, OrderItem.product_id == Product.id
        ).join(Order, Order.id == OrderItem.order_id).filter(
            Order.created_at >= start_date,
            Order.created_at <= end_date,
            Order.status == "completed"
        ).group_by(Category.id, Category.name).order_by(
            func.sum(OrderItem.total_price).desc()
        ).all()
        
        return [
            {
                "id": r.id,
                "name": r.name,
                "revenue": float(r.total_revenue or 0)
            }
            for r in results
        ]
    
    def get_payment_methods_data(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """To'lov usullari bo'yicha ma'lumot"""
        results = self.db.query(
            Payment.method,
            func.sum(Payment.amount).label('total'),
            func.count(Payment.id).label('count')
        ).filter(
            Payment.created_at >= start_date,
            Payment.created_at <= end_date,
            Payment.status == "paid"
        ).group_by(Payment.method).all()
        
        return [
            {
                "method": r.method,
                "total": float(r.total or 0),
                "count": r.count
            }
            for r in results
        ]
    
    def get_recent_orders(self, limit: int = 10) -> List[Dict]:
        """So'nggi buyurtmalar"""
        orders = self.db.query(Order).order_by(Order.created_at.desc()).limit(limit).all()
        
        result = []
        for order in orders:
            result.append({
                "id": order.id,
                "order_number": order.order_number,
                "table_number": order.table.number if order.table else None,
                "waiter_name": order.waiter.full_name if order.waiter else None,
                "total_amount": order.total_amount,
                "final_amount": order.final_amount,
                "status": order.status,
                "created_at": order.created_at.isoformat() if order.created_at else None
            })
        
        return result
    
    def get_sales_report(self, date_from: datetime, date_to: datetime, group_by: str) -> List[Dict]:
        """Savdo hisoboti"""
        if group_by == "hour":
            format_str = "%Y-%m-%d %H:00"
            group_column = func.date_format(Order.created_at, format_str)
        elif group_by == "day":
            format_str = "%Y-%m-%d"
            group_column = func.date_format(Order.created_at, format_str)
        elif group_by == "week":
            group_column = func.week(Order.created_at)
        else:  # month
            format_str = "%Y-%m"
            group_column = func.date_format(Order.created_at, format_str)
        
        results = self.db.query(
            group_column.label('period'),
            func.count(Order.id).label('orders_count'),
            func.sum(Payment.amount).label('revenue'),
            func.avg(Payment.amount).label('avg_check')
        ).join(Payment, Payment.order_id == Order.id).filter(
            Order.created_at >= date_from,
            Order.created_at <= date_to,
            Payment.status == "paid"
        ).group_by('period').order_by('period').all()
        
        return [
            {
                "period": r.period,
                "orders_count": r.orders_count,
                "revenue": float(r.revenue or 0),
                "avg_check": float(r.avg_check or 0)
            }
            for r in results
        ]
    
    def get_sales_summary(self, date_from: datetime, date_to: datetime) -> Dict[str, Any]:
        """Savdo xulosasi"""
        payments = self.db.query(Payment).filter(
            Payment.created_at >= date_from,
            Payment.created_at <= date_to,
            Payment.status == "paid"
        )
        
        total_revenue = payments.with_entities(func.sum(Payment.amount)).scalar() or 0
        
        # Naqd va karta bo'yicha
        cash_total = payments.filter(Payment.method == "cash").with_entities(
            func.sum(Payment.amount)
        ).scalar() or 0
        
        card_total = payments.filter(Payment.method == "card").with_entities(
            func.sum(Payment.amount)
        ).scalar() or 0
        
        orders_count = self.db.query(Order).filter(
            Order.created_at >= date_from,
            Order.created_at <= date_to
        ).count()
        
        return {
            "total_revenue": float(total_revenue),
            "cash_total": float(cash_total),
            "card_total": float(card_total),
            "orders_count": orders_count
        }
    
    def get_product_analytics(self, date_from: datetime, date_to: datetime, limit: int = 20) -> List[Dict]:
        """Mahsulotlar analitikasi"""
        results = self.db.query(
            Product.id,
            Product.name,
            Category.name.label('category_name'),
            func.sum(OrderItem.quantity).label('total_quantity'),
            func.sum(OrderItem.total_price).label('total_revenue'),
            func.count(func.distinct(Order.id)).label('orders_count')
        ).join(Category, Category.id == Product.category_id).join(
            OrderItem, OrderItem.product_id == Product.id
        ).join(Order, Order.id == OrderItem.order_id).filter(
            Order.created_at >= date_from,
            Order.created_at <= date_to,
            Order.status == "completed"
        ).group_by(Product.id, Product.name, Category.name).order_by(
            func.sum(OrderItem.total_price).desc()
        ).limit(limit).all()
        
        return [
            {
                "id": r.id,
                "name": r.name,
                "category": r.category_name,
                "quantity": int(r.total_quantity or 0),
                "revenue": float(r.total_revenue or 0),
                "orders_count": r.orders_count
            }
            for r in results
        ]
    
    def get_category_analytics(self, date_from: datetime, date_to: datetime) -> List[Dict]:
        """Kategoriyalar analitikasi"""
        results = self.db.query(
            Category.id,
            Category.name,
            func.count(func.distinct(Product.id)).label('products_count'),
            func.sum(OrderItem.quantity).label('total_quantity'),
            func.sum(OrderItem.total_price).label('total_revenue')
        ).join(Product, Product.category_id == Category.id).join(
            OrderItem, OrderItem.product_id == Product.id
        ).join(Order, Order.id == OrderItem.order_id).filter(
            Order.created_at >= date_from,
            Order.created_at <= date_to,
            Order.status == "completed"
        ).group_by(Category.id, Category.name).order_by(
            func.sum(OrderItem.total_price).desc()
        ).all()
        
        return [
            {
                "id": r.id,
                "name": r.name,
                "products_count": r.products_count,
                "quantity": int(r.total_quantity or 0),
                "revenue": float(r.total_revenue or 0)
            }
            for r in results
        ]
    
    def get_customer_analytics(self, date_from: datetime, date_to: datetime) -> Dict[str, Any]:
        """Mijozlar analitikasi"""
        # Yangi mijozlar
        new_customers = self.db.query(Customer).filter(
            Customer.created_at >= date_from,
            Customer.created_at <= date_to
        ).count()
        
        # Qaytgan mijozlar
        returning_customers = self.db.query(
            func.count(func.distinct(Order.customer_id))
        ).filter(
            Order.created_at >= date_from,
            Order.created_at <= date_to,
            Order.customer_id.isnot(None)
        ).scalar() or 0
        
        # Top mijozlar
        top_customers = self.db.query(
            Customer.id,
            Customer.name,
            Customer.phone,
            func.count(Order.id).label('orders_count'),
            func.sum(Order.final_amount).label('total_spent')
        ).join(Order, Order.customer_id == Customer.id).filter(
            Order.created_at >= date_from,
            Order.created_at <= date_to,
            Order.status == "completed"
        ).group_by(Customer.id, Customer.name, Customer.phone).order_by(
            func.sum(Order.final_amount).desc()
        ).limit(10).all()
        
        return {
            "new_customers": new_customers,
            "returning_customers": returning_customers,
            "top_customers": [
                {
                    "id": c.id,
                    "name": c.name,
                    "phone": c.phone,
                    "orders_count": c.orders_count,
                    "total_spent": float(c.total_spent or 0)
                }
                for c in top_customers
            ]
        }
    
    def get_employee_performance(self, date_from: datetime, date_to: datetime) -> List[Dict]:
        """Xodimlar samaradorligi"""
        results = self.db.query(
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
        
        return [
            {
                "id": r.id,
                "name": r.full_name,
                "orders_count": r.orders_count,
                "total_sales": float(r.total_sales or 0),
                "avg_check": float(r.avg_check or 0)
            }
            for r in results
        ]
    
    def get_hourly_stats(self, date: datetime) -> List[Dict]:
        """Soatlik statistika"""
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        results = self.db.query(
            func.hour(Order.created_at).label('hour'),
            func.count(Order.id).label('orders_count'),
            func.sum(Payment.amount).label('revenue')
        ).join(Payment, Payment.order_id == Order.id).filter(
            Order.created_at >= start_of_day,
            Order.created_at < end_of_day,
            Payment.status == "paid"
        ).group_by(func.hour(Order.created_at)).order_by('hour').all()
        
        # Barcha soatlar uchun to'ldirish
        hourly_data = []
        for hour in range(24):
            result = next((r for r in results if r.hour == hour), None)
            hourly_data.append({
                "hour": hour,
                "orders_count": result.orders_count if result else 0,
                "revenue": float(result.revenue) if result and result.revenue else 0
            })
        
        return hourly_data
    
    def export_report(self, report_type: str, date_from: datetime, date_to: datetime, format: str) -> str:
        """Hisobotni eksport qilish"""
        import csv
        import os
        from datetime import datetime
        
        filename = f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format}"
        filepath = os.path.join("static", "exports", filename)
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        if report_type == "sales":
            data = self.get_sales_report(date_from, date_to, "day")
            
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=["period", "orders_count", "revenue", "avg_check"])
                writer.writeheader()
                writer.writerows(data)
        
        return f"/static/exports/{filename}"