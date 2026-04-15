#!/usr/bin/env python
"""PremiumPOS tizimini ishga tushirish"""

import os
import sys
import subprocess
import webbrowser
from pathlib import Path

def check_dependencies():
    """Kerakli kutubxonalarni tekshirish"""
    print("📦 Kutubxonalar tekshirilmoqda...")
    
    try:
        import fastapi
        import uvicorn
        import sqlalchemy
        import pydantic
        print("✅ Barcha asosiy kutubxonalar mavjud")
        return True
    except ImportError as e:
        print(f"❌ Kutubxona topilmadi: {e}")
        print("\nKutubxonalarni o'rnatish uchun:")
        print("  pip install -r backend/requirements.txt")
        return False

def init_database():
    """Ma'lumotlar bazasini yaratish"""
    print("🗄️ Ma'lumotlar bazasi tekshirilmoqda...")
    
    os.chdir("backend")
    
    try:
        from database import init_db
        init_db()
        return True
    except Exception as e:
        print(f"❌ Database xatosi: {e}")
        return False
    finally:
        os.chdir("..")

def start_backend():
    """Backend serverni ishga tushirish"""
    print("🚀 Backend server ishga tushirilmoqda...")
    
    os.chdir("backend")
    
    try:
        subprocess.Popen([
            sys.executable, "-m", "uvicorn",
            "main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload"
        ])
        print("✅ Backend server: http://localhost:8000")
        print("📚 API hujjatlari: http://localhost:8000/docs")
        return True
    except Exception as e:
        print(f"❌ Backend xatosi: {e}")
        return False
    finally:
        os.chdir("..")

def start_frontend():
    """Frontend serverni ishga tushirish (Live Server orqali)"""
    print("🎨 Frontend ochilmoqda...")
    
    frontend_path = Path("frontend/index.html").resolve()
    
    if frontend_path.exists():
        webbrowser.open(f"file://{frontend_path}")
        print(f"✅ Frontend: {frontend_path}")
        
        # Live server tavsiyasi
        print("\n💡 Tavsiya: VS Code Live Server kengaytmasini o'rnating")
        print("   va frontend/index.html faylini Live Server orqali oching")
        return True
    else:
        print("❌ Frontend fayli topilmadi")
        return False

def main():
    """Asosiy funksiya"""
    print("=" * 50)
    print("🍽️  PremiumPOS Restaurant Management System")
    print("=" * 50)
    print()
    
    # 1. Kutubxonalarni tekshirish
    if not check_dependencies():
        return
    
    print()
    
    # 2. Database ni yaratish
    if not init_database():
        return
    
    print()
    
    # 3. Backend ni ishga tushirish
    if not start_backend():
        return
    
    print()
    
    # 4. Frontend ni ochish
    start_frontend()
    
    print()
    print("=" * 50)
    print("✨ Tizim ishga tushdi!")
    print("=" * 50)
    print()
    print("Kirish ma'lumotlari:")
    print("  Admin: admin / admin123")
    print("  Ofitsiant: waiter / waiter123")
    print("  Oshpaz: kitchen / kitchen123")
    print()
    print("CTRL+C bosish orqali to'xtating")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Tizim to'xtatildi")
    except Exception as e:
        print(f"\n❌ Xatolik: {e}")