from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
import logging
from typing import Callable

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    """So'rovlarni loglash middleware"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # So'rov ma'lumotlari
        logger.info(f"➡️ {request.method} {request.url.path}")
        
        response = await call_next(request)
        
        # Javob vaqti
        process_time = time.time() - start_time
        
        logger.info(
            f"⬅️ {request.method} {request.url.path} - "
            f"Status: {response.status_code} - "
            f"Time: {process_time:.3f}s"
        )
        
        response.headers["X-Process-Time"] = str(process_time)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware"""
    
    def __init__(self, app: ASGIApp, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}
    
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        
        # IP bo'yicha so'rovlarni tekshirish
        current_time = time.time()
        
        if client_ip in self.requests:
            # Eski so'rovlarni tozalash
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip]
                if current_time - req_time < self.window_seconds
            ]
            
            if len(self.requests[client_ip]) >= self.max_requests:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Please try again later."}
                )
            
            self.requests[client_ip].append(current_time)
        else:
            self.requests[client_ip] = [current_time]
        
        return await call_next(request)


class CORSMiddleware(BaseHTTPMiddleware):
    """CORS middleware"""
    
    def __init__(
        self,
        app: ASGIApp,
        allow_origins: list = None,
        allow_methods: list = None,
        allow_headers: list = None
    ):
        super().__init__(app)
        self.allow_origins = allow_origins or ["*"]
        self.allow_methods = allow_methods or ["*"]
        self.allow_headers = allow_headers or ["*"]
    
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            response = JSONResponse(content={})
            response.headers["Access-Control-Allow-Origin"] = ", ".join(self.allow_origins)
            response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allow_methods)
            response.headers["Access-Control-Allow-Headers"] = ", ".join(self.allow_headers)
            return response
        
        response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = ", ".join(self.allow_origins)
        
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Xatoliklarni qayta ishlash middleware"""
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail}
            )
        except Exception as e:
            logger.error(f"Unhandled error: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )


class AuthMiddleware(BaseHTTPMiddleware):
    """Autentifikatsiya middleware"""
    
    async def dispatch(self, request: Request, call_next):
        # Token tekshirish
        token = request.headers.get("Authorization")
        
        if token:
            token = token.replace("Bearer ", "")
            # TODO: Token validatsiyasi
            
        return await call_next(request)