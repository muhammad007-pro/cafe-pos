from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional

from database import get_db
from models import Order, Payment, Product, Customer, User
from deps import get_current_user, has_permission
from services.analytics_service import AnalyticsService

router = APIRouter()

@router.get("/dashboard")
async def get_dashboard_data(
    range: str = Query("today", regex="^(today|week|month|year)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Dashboard uchun ma'lumotlar"""
    analytics_service = AnalyticsService(db)
    
    # Vaqt oralig'ini aniqlash
    now = datetime.now()
    
    if range == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now
        previous_start = start_date - timedelta(days=1)
        previous_end = start_date - timedelta(seconds=1)
    elif range == "week":
        start_date = now - timedelta(days=7)
        end_date = now
        previous_start = start_date - timedelta(days=7)
        previous_end = start_date - timedelta(seconds=1)
    elif range == "month":
        start_date = now - timedelta(days=30)
        end_date = now
        previous_start = start_date - timedelta(days=30)
        previous_end = start_date - timedelta(seconds=1)
    else:  # year
        start_date = now - timedelta(days=365)
        end_date = now
        previous_start = start_date - timedelta(days=365)
        previous_end = start_date - timedelta(seconds=1)
    
    # Joriy davr ma'lumotlari
    current_data = analytics_service.get_period_data(start_date, end_date)
    previous_data = analytics_service.get_period_data(previous_start, previous_end)
    
    # Trendlarni hisoblash
    def calc_trend(current, previous):
        if previous == 0:
            return 100 if current > 0 else 0
        return round((current - previous) / previous * 100, 1)
    
    # Daromad grafigi
    revenue_data = analytics_service.get_revenue_chart_data(start_date, end_date, range)
    
    # Ommabop mahsulotlar
    popular_products = analytics_service.get_popular_products(start_date, end_date, limit=5)
    
    # Kategoriyalar bo'yicha savdo
    categories_data = analytics_service.get_sales_by_category(start_date, end_date)
    
    # To'lov usullari
    payment_methods = analytics_service.get_payment_methods_data(start_date, end_date)
    
    # So'nggi buyurtmalar
    recent_orders = analytics_service.get_recent_orders(limit=10)
    
    return {
        "total_revenue": current_data["total_revenue"],
        "total_orders": current_data["total_orders"],
        "total_customers": current_data["total_customers"],
        "average_check": current_data["average_check"],
        "revenue_trend": calc_trend(current_data["total_revenue"], previous_data["total_revenue"]),
        "orders_trend": calc_trend(current_data["total_orders"], previous_data["total_orders"]),
        "customers_trend": calc_trend(current_data["total_customers"], previous_data["total_customers"]),
        "avg_check_trend": calc_trend(current_data["average_check"], previous_data["average_check"]),
        "revenue_data": revenue_data,
        "popular_products": popular_products,
        "categories_data": categories_data,
        "payment_methods": payment_methods,
        "recent_orders": recent_orders
    }

@router.get("/sales")
async def get_sales_report(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    group_by: str = Query("day", regex="^(hour|day|week|month)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("view_analytics"))
):
    """Savdo hisoboti"""
    analytics_service = AnalyticsService(db)
    
    if not date_from:
        date_from = datetime.now() - timedelta(days=30)
    if not date_to:
        date_to = datetime.now()
    
    sales_data = analytics_service.get_sales_report(date_from, date_to, group_by)
    
    # Xulosa
    summary = analytics_service.get_sales_summary(date_from, date_to)
    
    return {
        "date_from": date_from,
        "date_to": date_to,
        "group_by": group_by,
        "data": sales_data,
        "summary": summary
    }

@router.get("/products")
async def get_product_analytics(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("view_analytics"))
):
    """Mahsulotlar analitikasi"""
    analytics_service = AnalyticsService(db)
    
    if not date_from:
        date_from = datetime.now() - timedelta(days=30)
    if not date_to:
        date_to = datetime.now()
    
    products = analytics_service.get_product_analytics(date_from, date_to, limit)
    
    return {
        "date_from": date_from,
        "date_to": date_to,
        "products": products
    }

@router.get("/categories")
async def get_category_analytics(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("view_analytics"))
):
    """Kategoriyalar analitikasi"""
    analytics_service = AnalyticsService(db)
    
    if not date_from:
        date_from = datetime.now() - timedelta(days=30)
    if not date_to:
        date_to = datetime.now()
    
    categories = analytics_service.get_category_analytics(date_from, date_to)
    
    return {
        "date_from": date_from,
        "date_to": date_to,
        "categories": categories
    }

@router.get("/customers")
async def get_customer_analytics(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("view_analytics"))
):
    """Mijozlar analitikasi"""
    analytics_service = AnalyticsService(db)
    
    if not date_from:
        date_from = datetime.now() - timedelta(days=30)
    if not date_to:
        date_to = datetime.now()
    
    return analytics_service.get_customer_analytics(date_from, date_to)

@router.get("/employees")
async def get_employee_performance(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("view_analytics"))
):
    """Xodimlar samaradorligi"""
    analytics_service = AnalyticsService(db)
    
    if not date_from:
        date_from = datetime.now() - timedelta(days=30)
    if not date_to:
        date_to = datetime.now()
    
    return analytics_service.get_employee_performance(date_from, date_to)

@router.get("/hourly")
async def get_hourly_stats(
    date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Soatlik statistika"""
    analytics_service = AnalyticsService(db)
    
    target_date = date or datetime.now()
    
    return analytics_service.get_hourly_stats(target_date)

@router.get("/export")
async def export_analytics(
    report_type: str = Query(..., regex="^(sales|products|categories|customers)$"),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    format: str = Query("csv", regex="^(csv|excel|pdf)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("view_analytics"))
):
    """Analitikani eksport qilish"""
    analytics_service = AnalyticsService(db)
    
    if not date_from:
        date_from = datetime.now() - timedelta(days=30)
    if not date_to:
        date_to = datetime.now()
    
    file_path = analytics_service.export_report(report_type, date_from, date_to, format)
    
    return {
        "file_url": file_path,
        "report_type": report_type,
        "format": format
    }