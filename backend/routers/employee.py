from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from models import User, Shift
from schemas import UserInDB, ShiftInDB, PaginatedResponse
from deps import get_current_user, has_permission

router = APIRouter()

@router.get("/", response_model=PaginatedResponse)
async def get_employees(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("manage_users"))
):
    """Barcha xodimlarni olish"""
    query = db.query(User)
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    total = query.count()
    employees = query.order_by(User.full_name).offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedResponse(
        items=[UserInDB.model_validate(e) for e in employees],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )

@router.get("/{employee_id}/shifts")
async def get_employee_shifts(
    employee_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("view_reports"))
):
    """Xodim smenalari"""
    query = db.query(Shift).filter(Shift.user_id == employee_id)
    
    total = query.count()
    shifts = query.order_by(Shift.start_time.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return PaginatedResponse(
        items=[ShiftInDB.model_validate(s) for s in shifts],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    )

@router.get("/{employee_id}/performance")
async def get_employee_performance(
    employee_id: int,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(has_permission("view_reports"))
):
    """Xodim samaradorligi"""
    from services.analytics_service import AnalyticsService
    from datetime import datetime, timedelta
    
    if not date_from:
        date_from = (datetime.now() - timedelta(days=30)).isoformat()
    if not date_to:
        date_to = datetime.now().isoformat()
    
    analytics_service = AnalyticsService(db)
    return analytics_service.get_employee_performance(
        datetime.fromisoformat(date_from),
        datetime.fromisoformat(date_to)
    )