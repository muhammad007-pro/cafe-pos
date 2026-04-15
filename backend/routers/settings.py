from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Any, Dict
from datetime import datetime  # ← QO'SHILDI

from database import get_db
from models import User
from deps import get_current_user, has_permission
from schemas import MessageResponse
from core.config_loader import config_loader

router = APIRouter()

@router.get("/")
async def get_all_settings(
    current_user: User = Depends(has_permission("manage_settings"))
):
    """Barcha sozlamalarni olish"""
    return {
        "app": config_loader.get("app"),
        "printer": config_loader.get("printer"),
        "kitchen": config_loader.get("kitchen"),
        "payment": config_loader.get("payment")
    }

@router.get("/{config_name}")
async def get_settings(
    config_name: str,
    current_user: User = Depends(has_permission("manage_settings"))
):
    """Sozlamalarni olish"""
    config = config_loader.get(config_name)
    if not config:
        raise HTTPException(status_code=404, detail="Sozlamalar topilmadi")
    return config

@router.patch("/{config_name}")
async def update_settings(
    config_name: str,
    settings: Dict[str, Any],
    current_user: User = Depends(has_permission("manage_settings"))
):
    """Sozlamalarni yangilash"""
    success = True
    for key, value in settings.items():
        if not config_loader.set_value(config_name, key, value):
            success = False
    
    if success:
        return MessageResponse(message="Sozlamalar yangilandi")
    else:
        raise HTTPException(status_code=500, detail="Sozlamalarni saqlashda xatolik")

@router.post("/printer/test")
async def test_printer(
    current_user: User = Depends(has_permission("manage_settings"))
):
    """Printerni test qilish"""
    from services.printer_service import PrinterService
    
    result = PrinterService.test_printer()
    return result

@router.post("/backup/create")
async def create_backup(
    current_user: User = Depends(has_permission("manage_settings"))
):
    """Zaxira nusxasini yaratish"""
    import os
    import shutil
    from datetime import datetime  # ← YOKI SHU YERDA HAM IMPORT QILISH MUMLIN
    
    backup_dir = "backup/auto"
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{backup_dir}/backup_{timestamp}.db"
    
    # Database faylni nusxalash
    if os.path.exists("pos.db"):
        shutil.copy("pos.db", backup_file)
        
        return {
            "success": True,
            "file": backup_file,
            "size": os.path.getsize(backup_file)
        }
    
    raise HTTPException(status_code=404, detail="Database fayli topilmadi")

@router.get("/backup/list")
async def list_backups(
    current_user: User = Depends(has_permission("manage_settings"))
):
    """Zaxira nusxalari ro'yxati"""
    import os
    from datetime import datetime
    
    backup_dir = "backup/auto"
    if not os.path.exists(backup_dir):
        return []
    
    backups = []
    for file in os.listdir(backup_dir):
        if file.endswith(".db"):
            filepath = os.path.join(backup_dir, file)
            stat = os.stat(filepath)
            
            backups.append({
                "name": file,
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat()
            })
    
    return sorted(backups, key=lambda x: x["created"], reverse=True)

@router.post("/backup/restore/{filename}")
async def restore_backup(
    filename: str,
    current_user: User = Depends(has_permission("manage_settings"))
):
    """Zaxira nusxasini tiklash"""
    import os
    import shutil
    from datetime import datetime
    
    backup_path = f"backup/auto/{filename}"
    
    if not os.path.exists(backup_path):
        raise HTTPException(status_code=404, detail="Zaxira fayli topilmadi")
    
    # Hozirgi database ni zaxiralash
    if os.path.exists("pos.db"):
        shutil.copy("pos.db", f"pos_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    
    # Tiklash
    shutil.copy(backup_path, "pos.db")
    
    return MessageResponse(message="Database tiklandi")