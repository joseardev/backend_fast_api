"""
WebSocket para actualizaciones en tiempo real de pedidos
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.models.models import User
from app.auth.jwt import verify_token
from typing import List, Dict
import json
import asyncio

router = APIRouter()

# Gestión de conexiones activas
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        """Conectar un nuevo cliente"""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        print(f"✅ WebSocket conectado para usuario {user_id}")

    def disconnect(self, websocket: WebSocket, user_id: str):
        """Desconectar un cliente"""
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        print(f"❌ WebSocket desconectado para usuario {user_id}")

    async def send_personal_message(self, message: dict, user_id: str):
        """Enviar mensaje a un usuario específico"""
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"Error enviando mensaje a {user_id}: {e}")

    async def broadcast(self, message: dict):
        """Enviar mensaje a todos los usuarios conectados"""
        disconnected = []
        for user_id, connections in self.active_connections.items():
            for connection in connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    print(f"Error broadcasting a {user_id}: {e}")
                    disconnected.append((user_id, connection))

        # Limpiar conexiones muertas
        for user_id, connection in disconnected:
            self.disconnect(connection, user_id)

    async def broadcast_to_admins(self, message: dict, db: Session):
        """Enviar mensaje solo a usuarios admin/staff"""
        for user_id in list(self.active_connections.keys()):
            # Verificar si el usuario es admin/staff
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user and user.role in ["admin", "staff"]:
                await self.send_personal_message(message, user_id)


manager = ConnectionManager()


@router.websocket("/ws/pedidos")
async def websocket_pedidos(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    WebSocket para recibir actualizaciones en tiempo real de pedidos

    Uso:
    ws://backend-url/ws/pedidos?token=YOUR_JWT_TOKEN

    Mensajes que se envían:
    - pedido_nuevo: Cuando se crea un pedido nuevo
    - pedido_actualizado: Cuando se actualiza un pedido
    - estado_cambiado: Cuando cambia el estado de un pedido
    - pedido_eliminado: Cuando se elimina un pedido
    - comentario_nuevo: Cuando se agrega un comentario
    """

    # Verificar token JWT
    email = verify_token(token)
    if not email:
        await websocket.close(code=1008, reason="Token inválido")
        return

    # Obtener usuario
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        await websocket.close(code=1008, reason="Usuario inválido o inactivo")
        return

    # Verificar permisos (solo admin/staff pueden usar WebSockets de pedidos)
    if user.role not in ["admin", "staff"]:
        await websocket.close(code=1008, reason="Permisos insuficientes")
        return

    user_id = str(user.id)

    try:
        # Conectar usuario
        await manager.connect(websocket, user_id)

        # Enviar mensaje de bienvenida
        await websocket.send_json({
            "type": "connection_established",
            "message": "Conectado a WebSocket de pedidos",
            "user_id": user.id,
            "user_name": user.full_name or user.email
        })

        # Mantener conexión abierta y recibir mensajes
        while True:
            try:
                # Recibir mensajes del cliente (heartbeat, etc.)
                data = await websocket.receive_text()

                # Procesar comandos del cliente
                try:
                    command = json.loads(data)

                    if command.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})

                    elif command.get("type") == "subscribe":
                        # Cliente se suscribe a eventos específicos
                        await websocket.send_json({
                            "type": "subscribed",
                            "events": ["pedido_nuevo", "pedido_actualizado", "estado_cambiado"]
                        })

                except json.JSONDecodeError:
                    pass

            except WebSocketDisconnect:
                break

    except Exception as e:
        print(f"Error en WebSocket para usuario {user_id}: {e}")

    finally:
        manager.disconnect(websocket, user_id)


# Funciones helper para enviar notificaciones desde otros módulos

async def notify_pedido_nuevo(pedido_data: dict, db: Session):
    """Notificar a todos los admins sobre un nuevo pedido"""
    message = {
        "type": "pedido_nuevo",
        "pedido": pedido_data
    }
    await manager.broadcast_to_admins(message, db)


async def notify_pedido_actualizado(pedido_data: dict, db: Session):
    """Notificar sobre actualización de pedido"""
    message = {
        "type": "pedido_actualizado",
        "pedido": pedido_data
    }
    await manager.broadcast_to_admins(message, db)


async def notify_estado_cambiado(pedido_id: int, estado_anterior: str, estado_nuevo: str, db: Session):
    """Notificar cambio de estado"""
    message = {
        "type": "estado_cambiado",
        "pedido_id": pedido_id,
        "estado_anterior": estado_anterior,
        "estado_nuevo": estado_nuevo
    }
    await manager.broadcast_to_admins(message, db)


async def notify_comentario_nuevo(pedido_id: int, comentario_data: dict, db: Session):
    """Notificar nuevo comentario"""
    message = {
        "type": "comentario_nuevo",
        "pedido_id": pedido_id,
        "comentario": comentario_data
    }
    await manager.broadcast_to_admins(message, db)


# Exportar el manager para que otros módulos puedan usarlo
__all__ = [
    "router",
    "manager",
    "notify_pedido_nuevo",
    "notify_pedido_actualizado",
    "notify_estado_cambiado",
    "notify_comentario_nuevo"
]
