from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime  # ← SHU QO'SHILDI
from typing import Optional, List

from database import get_db
from models import User
from deps import get_current_user, has_permission
from schemas import MessageResponse

router = APIRouter()

# Yetkazib beruvchilar (real loyihada database da)
suppliers = []

@router.get("/")
async def get_suppliers(
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Yetkazib beruvchilar ro'yxati"""
    if search:
        return [s for s in suppliers if search.lower() in s.get("name", "").lower()]
    return suppliers

@router.post("/")
async def create_supplier(
    name: str,
    contact_person: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    address: Optional[str] = None,
    current_user: User = Depends(has_permission("manage_inventory"))
):
    """Yangi yetkazib beruvchi qo'shish"""
    supplier = {
        "id": len(suppliers) + 1,
        "name": name,
        "contact_person": contact_person,
        "phone": phone,
        "email": email,
        "address": address,
        "created_at": datetime.now().isoformat()  # datetime ishlatilgan
    }
    suppliers.append(supplier)
    return supplier

@router.patch("/{supplier_id}")
async def update_supplier(
    supplier_id: int,
    name: Optional[str] = None,
    contact_person: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    address: Optional[str] = None,
    current_user: User = Depends(has_permission("manage_inventory"))
):
    """Yetkazib beruvchini yangilash"""
    for s in suppliers:
        if s["id"] == supplier_id:
            if name:
                s["name"] = name
            if contact_person:
                s["contact_person"] = contact_person
            if phone:
                s["phone"] = phone
            if email:
                s["email"] = email
            if address:
                s["address"] = address
            return s
    
    raise HTTPException(status_code=404, detail="Yetkazib beruvchi topilmadi")

@router.delete("/{supplier_id}")
async def delete_supplier(
    supplier_id: int,
    current_user: User = Depends(has_permission("manage_inventory"))
):
    """Yetkazib beruvchini o'chirish"""
    global suppliers
    suppliers = [s for s in suppliers if s["id"] != supplier_id]
    return MessageResponse(message="Yetkazib beruvchi o'chirildi") 