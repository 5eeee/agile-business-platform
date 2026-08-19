# WebSocket-менеджер для чата и онлайн-статуса
import json
from collections import defaultdict
from fastapi import WebSocket
from typing import Dict, Set


class ConnectionManager:
    """Управление WebSocket-подключениями (несколько сокетов на пользователя: чат + статус)."""

    def __init__(self):
        self.iteration_connections: Dict[str, Set[WebSocket]] = {}
        self.user_sockets: Dict[str, Set[WebSocket]] = defaultdict(set)

    def add_user_socket(self, user_id: str, websocket: WebSocket) -> None:
        self.user_sockets[user_id].add(websocket)

    def remove_user_socket(self, user_id: str, websocket: WebSocket) -> None:
        s = self.user_sockets.get(user_id)
        if not s:
            return
        s.discard(websocket)
        if not s:
            del self.user_sockets[user_id]

    def user_has_connections(self, user_id: str) -> bool:
        return bool(self.user_sockets.get(user_id))

    def _purge_websocket(self, websocket: WebSocket) -> None:
        for it_id, conns in list(self.iteration_connections.items()):
            if websocket in conns:
                conns.discard(websocket)
                if not conns:
                    del self.iteration_connections[it_id]
        for uid, conns in list(self.user_sockets.items()):
            if websocket in conns:
                conns.discard(websocket)
                if not conns:
                    del self.user_sockets[uid]

    async def connect(self, websocket: WebSocket, iteration_id: str, user_id: str):
        await websocket.accept()
        if iteration_id not in self.iteration_connections:
            self.iteration_connections[iteration_id] = set()
        self.iteration_connections[iteration_id].add(websocket)
        self.add_user_socket(user_id, websocket)

    def disconnect(self, websocket: WebSocket, iteration_id: str, user_id: str):
        if iteration_id in self.iteration_connections:
            self.iteration_connections[iteration_id].discard(websocket)
        self.remove_user_socket(user_id, websocket)

    async def broadcast_to_iteration(self, iteration_id: str, message: dict, exclude_ws: WebSocket = None):
        """Отправка сообщения всем в итерации"""
        if iteration_id not in self.iteration_connections:
            return
        dead = set()
        for ws in self.iteration_connections[iteration_id]:
            if ws is exclude_ws:
                continue
            try:
                await ws.send_text(json.dumps(message, default=str))
            except Exception:
                dead.add(ws)
        self.iteration_connections[iteration_id] -= dead
        for ws in dead:
            self._purge_websocket(ws)

    async def send_to_user(self, user_id: str, message: dict):
        """Отправка пользователю (все активные сокеты)."""
        text = json.dumps(message, default=str)
        dead = []
        for ws in list(self.user_sockets.get(user_id, ())):
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._purge_websocket(ws)

    async def broadcast_all(self, message: dict, exclude_user: str = None):
        """Отправка всем подключённым пользователям (без дублей на одну вкладку)."""
        text = json.dumps(message, default=str)
        seen = set()
        dead = []
        for uid, socks in self.user_sockets.items():
            if uid == exclude_user:
                continue
            for ws in socks:
                if ws in seen:
                    continue
                seen.add(ws)
                try:
                    await ws.send_text(text)
                except Exception:
                    dead.append(ws)
        for ws in dead:
            self._purge_websocket(ws)

    def get_online_users(self) -> list[str]:
        return list(self.user_sockets.keys())


manager = ConnectionManager()
