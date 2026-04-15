from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional

from database import get_db
from models import User
from deps import get_current_user, has_permission
from services.report_service import ReportService

router = APIRouter()

@router.get("/daily")
async def get_daily_report(
    date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("view_reports"))
):
    """Kunlik hisobot"""
    report_service = ReportService(db)
    
    target_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now().date()
    
    return report_service.generate_daily_report(target_date)

@router.get("/sales")
async def get_sales_report(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("view_reports"))
):
    """Savdo hisoboti"""
    report_service = ReportService(db)
    
    if not date_from:
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not date_to:
        date_to = datetime.now().strftime("%Y-%m-%d")
    
    from_date = datetime.strptime(date_from, "%Y-%m-%d")
    to_date = datetime.strptime(date_to, "%Y-%m-%d")
    
    return report_service.generate_sales_report(from_date, to_date)

@router.get("/products")
async def get_products_report(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("view_reports"))
):
    """Mahsulotlar hisoboti"""
    report_service = ReportService(db)
    
    if not date_from:
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not date_to:
        date_to = datetime.now().strftime("%Y-%m-%d")
    
    from_date = datetime.strptime(date_from, "%Y-%m-%d")
    to_date = datetime.strptime(date_to, "%Y-%m-%d")
    
    return report_service.generate_products_report(from_date, to_date, limit)

@router.get("/staff")
async def get_staff_report(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("view_reports"))
):
    """Xodimlar hisoboti"""
    report_service = ReportService(db)
    
    if not date_from:
        date_from = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not date_to:
        date_to = datetime.now().strftime("%Y-%m-%d")
    
    from_date = datetime.strptime(date_from, "%Y-%m-%d")
    to_date = datetime.strptime(date_to, "%Y-%m-%d")
    
    return report_service.generate_staff_report(from_date, to_date)

@router.get("/shift")
async def get_shift_report(
    shift_id: Optional[int] = None,
    user_id: Optional[int] = None,
    date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Smena hisoboti"""
    report_service = ReportService(db)
    
    return report_service.generate_shift_report(shift_id, user_id, date)

@router.get("/export")
async def export_report(
    report_type: str = Query(..., regex="^(daily|sales|products|staff|shift)$"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    format: str = Query("csv", regex="^(csv|excel|pdf)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("view_reports"))
):
    """Hisobotni eksport qilish"""
    report_service = ReportService(db)
    
    from_date = datetime.strptime(date_from, "%Y-%m-%d") if date_from else datetime.now() - timedelta(days=30)
    to_date = datetime.strptime(date_to, "%Y-%m-%d") if date_to else datetime.now()
    
    file_path = report_service.export_report(report_type, from_date, to_date, format)
    
    return {
        "file_url": file_path,
        "report_type": report_type,
        "format": format
    }