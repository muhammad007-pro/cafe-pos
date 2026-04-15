from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from typing import Optional
import json

from websocket.manager import manager
from core.security import verify_access_token
from database import SessionLocal
from models import User

router = APIRouter()

async def get_user_from_token(token: Optional[str]) -> Optional[User]:
    """Token orqali foydalanuvchini olish"""
    if not token:
        return None
    
    payload = verify_access_token(token)
    if not payload:
        return None
    
    username = payload.get("sub")
    if not username:
        return None
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        return user
    finally:
        db.close()

@router.websocket("/")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """Asosiy WebSocket endpoint"""
    user = await get_user_from_token(token)
    user_id = user.id if user else None
    
    connection_id = await manager.connect(websocket, user_id)
    
    try:
        while True:
            # Xabarni qabul qilish
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                message_type = message.get("type")
                
                # Ping
                if message_type == "ping":
                    await manager.send_personal_message({"type": "pong"}, connection_id)
                
                # Xonaga qo'shilish
                elif message_type == "join_room":
                    room = message.get("room")
                    if room:
                        manager.join_room(connection_id, room)
                        await manager.send_personal_message({
                            "type": "room_joined",
                            "room": room
                        }, connection_id)
                
                # Xonadan chiqish
                elif message_type == "leave_room":
                    room = message.get("room")
                    if room:
                        manager.leave_room(connection_id, room)
                        await manager.send_personal_message({
                            "type": "room_left",
                            "room": room
                        }, connection_id)
                
                # Xonaga xabar yuborish
                elif message_type == "room_message":
                    room = message.get("room")
                    msg_data = message.get("data")
                    if room and msg_data:
                        await manager.broadcast_to_room(
                            room,
                            {
                                "type": "room_broadcast",
                                "room": room,
                                "sender": user_id,
                                "data": msg_data
                            },
                            exclude=connection_id
                        )
                
                # Foydalanuvchiga shaxsiy xabar
                elif message_type == "user_message":
                    target_user_id = message.get("user_id")
                    msg_data = message.get("data")
                    if target_user_id and msg_data:
                        await manager.send_to_user(target_user_id, {
                            "type": "personal_message",
                            "sender": user_id,
                            "data": msg_data
                        })
                
                # Holatni olish
                elif message_type == "get_status":
                    await manager.send_personal_message({
                        "type": "status",
                        "online_users": list(manager.get_online_users()),
                        "rooms": {
                            room: len(members)
                            for room, members in manager.rooms.items()
                        }
                    }, connection_id)
                
            except json.JSONDecodeError:
                print(f"[WS] Noto'g'ri JSON: {data}")
                
    except WebSocketDisconnect:
        manager.disconnect(connection_id, user_id)
        print(f"[WS] Uzildi: {connection_id}")

@router.websocket("/pos")
async def pos_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """POS terminal uchun WebSocket"""
    user = await get_user_from_token(token)
    user_id = user.id if user else None
    
    connection_id = await manager.connect(websocket, user_id)
    manager.join_room(connection_id, "pos")
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                
                if message.get("type") == "order_update":
                    # Buyurtma yangilanishini oshxonaga yuborish
                    await manager.broadcast_to_kitchen({
                        "type": "order_updated",
                        "data": message.get("data")
                    })
                    
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        manager.disconnect(connection_id, user_id)

@router.websocket("/kitchen")
async def kitchen_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """Oshxona displey uchun WebSocket"""
    user = await get_user_from_token(token)
    user_id = user.id if user else None
    
    connection_id = await manager.connect(websocket, user_id)
    manager.join_room(connection_id, "kitchen")
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                
                if message.get("type") == "item_status_update":
                    # Mahsulot holati yangilanishini POS ga yuborish
                    await manager.broadcast_to_pos({
                        "type": "item_status_changed",
                        "data": message.get("data")
                    })
                    
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        manager.disconnect(connection_id, user_id)