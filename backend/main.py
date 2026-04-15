from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
import logging

from config import settings
from database import init_db
from core.logger import setup_logger
from core.middleware import LoggingMiddleware, ErrorHandlingMiddleware
from routers import (
    auth, user, role, category, product, table, order, payment,
    customer, reservation, report, analytics, inventory, kitchen,
    notification, discount, shift, settings as settings_router, upload
)
from websocket.routes import router as ws_router
from tasks.scheduler import start_scheduler, stop_scheduler

# Logger sozlash
setup_logger()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Tizim ishga tushmoqda...")
    
    # Database ni yaratish
    init_db()
    
    # Schedulerni ishga tushirish
    start_scheduler()
    
    # Papkalarni yaratish
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs("static/receipts", exist_ok=True)
    os.makedirs("backup/auto", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    
    logger.info("✅ Tizim tayyor!")
    
    yield
    
    # Shutdown
    logger.info("👋 Tizim to'xtatilmoqda...")
    stop_scheduler()

# FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Middleware
app.add_middleware(LoggingMiddleware)
app.add_middleware(ErrorHandlingMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# API Routerlar
api_prefix = settings.API_V1_STR

app.include_router(auth.router, prefix=f"{api_prefix}/auth", tags=["Authentication"])
app.include_router(user.router, prefix=f"{api_prefix}/users", tags=["Users"])
app.include_router(role.router, prefix=f"{api_prefix}/roles", tags=["Roles"])
app.include_router(category.router, prefix=f"{api_prefix}/categories", tags=["Categories"])
app.include_router(product.router, prefix=f"{api_prefix}/products", tags=["Products"])
app.include_router(table.router, prefix=f"{api_prefix}/tables", tags=["Tables"])
app.include_router(order.router, prefix=f"{api_prefix}/orders", tags=["Orders"])
app.include_router(payment.router, prefix=f"{api_prefix}/payments", tags=["Payments"])
app.include_router(customer.router, prefix=f"{api_prefix}/customers", tags=["Customers"])
app.include_router(reservation.router, prefix=f"{api_prefix}/reservations", tags=["Reservations"])
app.include_router(report.router, prefix=f"{api_prefix}/reports", tags=["Reports"])
app.include_router(analytics.router, prefix=f"{api_prefix}/analytics", tags=["Analytics"])
app.include_router(inventory.router, prefix=f"{api_prefix}/inventory", tags=["Inventory"])
app.include_router(kitchen.router, prefix=f"{api_prefix}/kitchen", tags=["Kitchen"])
app.include_router(notification.router, prefix=f"{api_prefix}/notifications", tags=["Notifications"])
app.include_router(discount.router, prefix=f"{api_prefix}/discounts", tags=["Discounts"])
app.include_router(shift.router, prefix=f"{api_prefix}/shifts", tags=["Shifts"])
app.include_router(settings_router.router, prefix=f"{api_prefix}/settings", tags=["Settings"])
app.include_router(upload.router, prefix=f"{api_prefix}/upload", tags=["Upload"])

# WebSocket
app.include_router(ws_router, prefix="/ws", tags=["WebSocket"])

@app.get("/")
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "database": "connected"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )