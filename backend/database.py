from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import os

from config import settings

# Engine yaratish
if "sqlite" in settings.DATABASE_URL:
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
        echo=settings.DEBUG
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        echo=settings.DEBUG,
        pool_size=10,
        max_overflow=20
    )

# Session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """Database session olish"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Ma'lumotlar bazasini yaratish va boshlang'ich ma'lumotlarni qo'shish"""
    from models import (
        User, Role, Permission, Category, Product, Table,
        Customer, Discount, Inventory, Shift
    )
    from core.security import get_password_hash
    from datetime import datetime
    
    # Jadvallarni yaratish
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Permissions yaratish
        permissions_data = [
            ("manage_users", "Foydalanuvchilarni boshqarish"),
            ("manage_roles", "Rollar boshqaruvi"),
            ("view_analytics", "Analitikani ko'rish"),
            ("manage_menu", "Menyuni boshqarish"),
            ("manage_tables", "Stollar boshqaruvi"),
            ("process_orders", "Buyurtmalarni qayta ishlash"),
            ("manage_inventory", "Omborni boshqarish"),
            ("view_reports", "Hisobotlarni ko'rish"),
            ("manage_settings", "Sozlamalar boshqaruvi"),
            ("manage_customers", "Mijozlar boshqaruvi"),
            ("manage_discounts", "Chegirmalar boshqaruvi"),
            ("process_payments", "To'lovlarni qayta ishlash"),
            ("manage_shifts", "Smenalar boshqaruvi"),
            ("manage_reservations", "Bronlar boshqaruvi"),
        ]
        
        permissions = {}
        for code, desc in permissions_data:
            perm = db.query(Permission).filter(Permission.code == code).first()
            if not perm:
                perm = Permission(code=code, description=desc)
                db.add(perm)
                db.flush()
            permissions[code] = perm
        
        # Admin roli
        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            admin_role = Role(name="admin", description="Administrator")
            admin_role.permissions = list(permissions.values())
            db.add(admin_role)
            db.flush()
        
        # Ofitsiant roli
        waiter_role = db.query(Role).filter(Role.name == "waiter").first()
        if not waiter_role:
            waiter_role = Role(name="waiter", description="Ofitsiant")
            waiter_role.permissions = [
                permissions["process_orders"],
                permissions["view_reports"],
            ]
            db.add(waiter_role)
            db.flush()
        
        # Oshpaz roli
        kitchen_role = db.query(Role).filter(Role.name == "kitchen").first()
        if not kitchen_role:
            kitchen_role = Role(name="kitchen", description="Oshpaz")
            kitchen_role.permissions = []
            db.add(kitchen_role)
            db.flush()
        
        # Kassir roli
        cashier_role = db.query(Role).filter(Role.name == "cashier").first()
        if not cashier_role:
            cashier_role = Role(name="cashier", description="Kassir")
            cashier_role.permissions = [
                permissions["process_payments"],
                permissions["view_reports"],
            ]
            db.add(cashier_role)
            db.flush()
        
        # Admin foydalanuvchi
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin_user = User(
                username="admin",
                email="admin@restaurant.uz",
                full_name="Administrator",
                phone="+998901234567",
                hashed_password=get_password_hash("admin123"),
                role_id=admin_role.id,
                is_active=True,
                is_superuser=True
            )
            db.add(admin_user)
        
        # Test foydalanuvchilar
        if settings.DEBUG:
            # Ofitsiant
            waiter = db.query(User).filter(User.username == "waiter").first()
            if not waiter:
                waiter = User(
                    username="waiter",
                    email="waiter@restaurant.uz",
                    full_name="Alisher Ofitsiant",
                    phone="+998901234568",
                    hashed_password=get_password_hash("waiter123"),
                    role_id=waiter_role.id,
                    is_active=True
                )
                db.add(waiter)
            
            # Oshpaz
            kitchen = db.query(User).filter(User.username == "kitchen").first()
            if not kitchen:
                kitchen = User(
                    username="kitchen",
                    email="kitchen@restaurant.uz",
                    full_name="Bahodir Oshpaz",
                    phone="+998901234569",
                    hashed_password=get_password_hash("kitchen123"),
                    role_id=kitchen_role.id,
                    is_active=True
                )
                db.add(kitchen)
        
        # Default kategoriyalar
        default_categories = [
            {"name": "Taomlar", "display_order": 1},
            {"name": "Salatlar", "display_order": 2},
            {"name": "Sho'rvalar", "display_order": 3},
            {"name": "Ichimliklar", "display_order": 4},
            {"name": "Desertlar", "display_order": 5},
            {"name": "Grill", "display_order": 6},
            {"name": "Fast Food", "display_order": 7},
        ]
        
        categories = {}
        for cat_data in default_categories:
            cat = db.query(Category).filter(Category.name == cat_data["name"]).first()
            if not cat:
                cat = Category(**cat_data)
                db.add(cat)
                db.flush()
            categories[cat_data["name"]] = cat
        
        # Default stollar
        table_count = db.query(Table).count()
        if table_count == 0:
            for i in range(1, 11):
                table = Table(
                    number=str(i),
                    name=f"Stol {i}",
                    capacity=4 if i <= 8 else 6,
                    section="Asosiy zal" if i <= 8 else "VIP",
                    status="free"
                )
                db.add(table)
        
        db.commit()
        print("✅ Ma'lumotlar bazasi va boshlang'ich ma'lumotlar yaratildi!")
        
    except Exception as e:
        print(f"❌ Xatolik: {e}")
        db.rollback()
    finally:
        db.close()