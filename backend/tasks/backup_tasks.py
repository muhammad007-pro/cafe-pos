import os
import shutil
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

async def backup_database():
    """Database ni zaxiralash"""
    try:
        backup_dir = "backup/auto"
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{backup_dir}/backup_{timestamp}.db"
        
        if os.path.exists("pos.db"):
            shutil.copy("pos.db", backup_file)
            logger.info(f"Database backed up: {backup_file}")
            
            # Eski zaxiralarni tozalash
            await cleanup_old_backups(backup_dir, keep_days=30)
            
            return {"success": True, "file": backup_file}
        else:
            logger.warning("Database file not found")
            return {"success": False, "error": "Database file not found"}
            
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        return {"success": False, "error": str(e)}

async def cleanup_old_backups(backup_dir: str, keep_days: int = 30):
    """Eski zaxiralarni o'chirish"""
    cutoff = datetime.now() - timedelta(days=keep_days)
    
    for filename in os.listdir(backup_dir):
        if filename.startswith("backup_") and filename.endswith(".db"):
            filepath = os.path.join(backup_dir, filename)
            file_time = datetime.fromtimestamp(os.path.getctime(filepath))
            
            if file_time < cutoff:
                os.remove(filepath)
                logger.info(f"Old backup removed: {filename}")

async def backup_media_files():
    """Media fayllarni zaxiralash"""
    try:
        media_dirs = ["static/uploads", "static/receipts"]
        backup_media_dir = "backup/media"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for media_dir in media_dirs:
            if os.path.exists(media_dir):
                dest_dir = f"{backup_media_dir}/{timestamp}/{media_dir}"
                os.makedirs(dest_dir, exist_ok=True)
                
                for root, dirs, files in os.walk(media_dir):
                    for file in files:
                        src_path = os.path.join(root, file)
                        rel_path = os.path.relpath(src_path, media_dir)
                        dest_path = os.path.join(dest_dir, rel_path)
                        
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        shutil.copy2(src_path, dest_path)
        
        logger.info(f"Media files backed up: {timestamp}")
        return {"success": True, "timestamp": timestamp}
        
    except Exception as e:
        logger.error(f"Media backup failed: {e}")
        return {"success": False, "error": str(e)}

async def restore_database(backup_file: str):
    """Database ni tiklash"""
    try:
        backup_path = f"backup/auto/{backup_file}"
        
        if not os.path.exists(backup_path):
            return {"success": False, "error": "Backup file not found"}
        
        # Hozirgi database ni zaxiralash
        if os.path.exists("pos.db"):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy("pos.db", f"backup/auto/pre_restore_{timestamp}.db")
        
        # Tiklash
        shutil.copy(backup_path, "pos.db")
        logger.info(f"Database restored from: {backup_file}")
        
        return {"success": True, "message": "Database restored successfully"}
        
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        return {"success": False, "error": str(e)}

async def get_backup_list():
    """Zaxiralar ro'yxati"""
    backup_dir = "backup/auto"
    
    if not os.path.exists(backup_dir):
        return []
    
    backups = []
    for filename in os.listdir(backup_dir):
        if filename.startswith("backup_") and filename.endswith(".db"):
            filepath = os.path.join(backup_dir, filename)
            stat = os.stat(filepath)
            
            backups.append({
                "name": filename,
                "size": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "created_display": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
            })
    
    return sorted(backups, key=lambda x: x["created"], reverse=True)