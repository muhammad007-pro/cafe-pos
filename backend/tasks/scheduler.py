import asyncio
from datetime import datetime, timedelta
from typing import Callable, Dict, Any
import logging

logger = logging.getLogger(__name__)

class TaskScheduler:
    """Vazifalarni rejalashtirish"""
    
    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.running = False
        self._task = None
    
    def add_task(
        self,
        name: str,
        func: Callable,
        interval: int = 3600,
        run_immediately: bool = False
    ):
        """Vazifa qo'shish"""
        self.tasks[name] = {
            "func": func,
            "interval": interval,
            "last_run": None,
            "next_run": datetime.now() if run_immediately else datetime.now() + timedelta(seconds=interval)
        }
        logger.info(f"Task added: {name} (interval: {interval}s)")
    
    def remove_task(self, name: str):
        """Vazifani o'chirish"""
        if name in self.tasks:
            del self.tasks[name]
            logger.info(f"Task removed: {name}")
    
    async def _run_task(self, name: str, task_info: Dict[str, Any]):
        """Vazifani bajarish"""
        try:
            logger.info(f"Running task: {name}")
            
            if asyncio.iscoroutinefunction(task_info["func"]):
                await task_info["func"]()
            else:
                task_info["func"]()
            
            task_info["last_run"] = datetime.now()
            task_info["next_run"] = datetime.now() + timedelta(seconds=task_info["interval"])
            
            logger.info(f"Task completed: {name}")
            
        except Exception as e:
            logger.error(f"Task failed: {name} - {str(e)}")
    
    async def _scheduler_loop(self):
        """Scheduler loop"""
        while self.running:
            now = datetime.now()
            
            for name, task_info in self.tasks.items():
                if task_info["next_run"] and now >= task_info["next_run"]:
                    await self._run_task(name, task_info)
            
            await asyncio.sleep(1)
    
    def start(self):
        """Schedulerni ishga tushirish"""
        if not self.running:
            self.running = True
            self._task = asyncio.create_task(self._scheduler_loop())
            logger.info("Scheduler started")
    
    def stop(self):
        """Schedulerni to'xtatish"""
        self.running = False
        if self._task:
            self._task.cancel()
        logger.info("Scheduler stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Scheduler holati"""
        tasks_status = {}
        for name, task_info in self.tasks.items():
            tasks_status[name] = {
                "last_run": task_info["last_run"].isoformat() if task_info["last_run"] else None,
                "next_run": task_info["next_run"].isoformat() if task_info["next_run"] else None,
                "interval": task_info["interval"]
            }
        
        return {
            "running": self.running,
            "tasks": tasks_status
        }


# Global scheduler
scheduler = TaskScheduler()


# Default vazifalar
async def backup_database():
    """Database zaxiralash"""
    import os
    import shutil
    from datetime import datetime
    
    backup_dir = "backup/auto"
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{backup_dir}/backup_{timestamp}.db"
    
    if os.path.exists("pos.db"):
        shutil.copy("pos.db", backup_file)
        
        # 30 kundan eski zaxiralarni o'chirish
        cutoff = datetime.now() - timedelta(days=30)
        for file in os.listdir(backup_dir):
            if file.startswith("backup_") and file.endswith(".db"):
                filepath = os.path.join(backup_dir, file)
                file_time = datetime.fromtimestamp(os.path.getctime(filepath))
                if file_time < cutoff:
                    os.remove(filepath)
        
        logger.info(f"Database backed up: {backup_file}")


async def clean_old_notifications():
    """Eski bildirishnomalarni tozalash"""
    from database import SessionLocal
    from models import Notification
    from datetime import datetime, timedelta
    
    db = SessionLocal()
    try:
        cutoff = datetime.now() - timedelta(days=30)
        db.query(Notification).filter(
            Notification.created_at < cutoff,
            Notification.is_read == True
        ).delete()
        db.commit()
        logger.info("Old notifications cleaned")
    except Exception as e:
        logger.error(f"Failed to clean notifications: {e}")
    finally:
        db.close()


async def update_inventory_from_orders():
    """Buyurtmalar asosida omborni yangilash"""
    # TODO: Implement
    pass


def start_scheduler():
    """Schedulerni boshlash"""
    # Vazifalarni qo'shish
    scheduler.add_task("backup", backup_database, interval=86400)  # Har 24 soatda
    scheduler.add_task("clean_notifications", clean_old_notifications, interval=3600)  # Har soatda
    scheduler.add_task("update_inventory", update_inventory_from_orders, interval=300)  # Har 5 daqiqada
    
    scheduler.start()


def stop_scheduler():
    """Schedulerni to'xtatish"""
    scheduler.stop()