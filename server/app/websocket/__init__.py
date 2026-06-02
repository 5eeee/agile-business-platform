# WebSocket-менеджер для чата и онлайн-статуса
import uuid
import json
from datetime import datetime
from fastapi import WebSocket
from typing import Dict, Set


class ConnectionManager:
    """Управление WebSocket-подключениями"""

    def __init__(self):
        # iteration_id -> set of WebSocket connections
        self.iteration_connections: Dict[str, Set[WebSocket]] = {}
        # user_id -> WebSocket connection (для онлайн-статуса)
        self.user_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, iteration_id: str, user_id: str):
        await websocket.accept()
        if iteration_id not in self.iteration_connections:
            self.iteration_connections[iteration_id] = set()
        self.iteration_connections[iteration_id].add(websocket)
        self.user_connections[user_id] = websocket

    def disconnect(self, websocket: WebSocket, iteration_id: str, user_id: str):
        if iteration_id in self.iteration_connections:
            self.iteration_connections[iteration_id].discard(websocket)
        self.user_connections.pop(user_id, None)

    async def broadcast_to_iteration(self, iteration_id: str, message: dict, exclude_ws: WebSocket = None):
        """Отправка сообщения всем в итерации"""
        if iteration_id in self.iteration_connections:
            dead = set()
            for ws in self.iteration_connections[iteration_id]:
                if ws is exclude_ws:
                    continue
                try:
                    await ws.send_text(json.dumps(message, default=str))
                except Exception:
                    dead.add(ws)
            self.iteration_connections[iteration_id] -= dead

    async def send_to_user(self, user_id: str, message: dict):
        """Отправка пользователю"""
        ws = self.user_connections.get(user_id)
        if ws:
            try:
                await ws.send_text(json.dumps(message, default=str))
            except Exception:
                self.user_connections.pop(user_id, None)

    async def broadcast_all(self, message: dict, exclude_user: str = None):
        """Отправка всем подключённым пользователям"""
        dead = []
        for uid, ws in self.user_connections.items():
            if uid == exclude_user:
                continue
            try:
                await ws.send_text(json.dumps(message, default=str))
            except Exception:
                dead.append(uid)
        for uid in dead:
            self.user_connections.pop(uid, None)

    def get_online_users(self) -> list[str]:
        return list(self.user_connections.keys())


manager = ConnectionManager()
