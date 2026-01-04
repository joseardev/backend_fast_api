"""
Schemas Pydantic para endpoints de Telegram
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# Schemas para Pedidos

class PedidoBase(BaseModel):
    """Base schema para pedido"""
    resumen_items: str = Field(..., description="Descripción de los items del pedido")
    prioridad: str = Field(default="media", pattern="^(alta|media|baja)$")
    fecha_solicitada: Optional[datetime] = None
    hora_solicitada: Optional[str] = None
    notas_adicionales: Optional[str] = None


class PedidoCreate(PedidoBase):
    """Schema para crear un pedido manualmente"""
    telegram_user_id: int
    telegram_username: Optional[str] = None


class PedidoUpdate(BaseModel):
    """Schema para actualizar un pedido"""
    notas_adicionales: Optional[str] = None
    asignado_a: Optional[str] = None


class CambiarEstadoPedido(BaseModel):
    """Schema para cambiar el estado de un pedido"""
    nuevo_estado: str = Field(
        ...,
        pattern="^(pendiente_confirmacion|confirmado|en_preparacion|listo_para_recoger|completado|cancelado)$"
    )
    notas: Optional[str] = None


class HistorialEstadoResponse(BaseModel):
    """Schema para respuesta de historial de estado"""
    id: int
    estado_anterior: Optional[str]
    estado_nuevo: str
    modificado_por: Optional[str]
    notas: Optional[str]
    fecha_cambio: datetime

    class Config:
        from_attributes = True


class PedidoResponse(PedidoBase):
    """Schema para respuesta de pedido"""
    id: int
    usuario_id: Optional[int]
    telegram_user_id: int
    telegram_username: Optional[str]
    mensaje_id: int
    estado: str
    asignado_a: Optional[str]
    fecha_creacion: datetime
    fecha_confirmacion: Optional[datetime]
    fecha_preparacion: Optional[datetime]
    fecha_listo: Optional[datetime]
    fecha_completado: Optional[datetime]
    fecha_cancelado: Optional[datetime]
    historial: Optional[List[HistorialEstadoResponse]] = []

    class Config:
        from_attributes = True


class PedidoListResponse(BaseModel):
    """Schema para lista de pedidos con paginación"""
    total: int
    pedidos: List[PedidoResponse]
    offset: int
    limit: int


# Schemas para Estadísticas

class EstadisticasResponse(BaseModel):
    """Schema para estadísticas generales"""
    total_mensajes: int
    total_pedidos: int
    pedidos_por_estado: dict
    pedidos_por_prioridad: dict


# Schemas para filtros

class PedidosFiltros(BaseModel):
    """Schema para filtros de pedidos"""
    estado: Optional[str] = Field(
        None,
        pattern="^(pendiente_confirmacion|confirmado|en_preparacion|listo_para_recoger|completado|cancelado)$"
    )
    prioridad: Optional[str] = Field(None, pattern="^(alta|media|baja)$")
    telegram_user_id: Optional[int] = None
    fecha_desde: Optional[datetime] = None
    fecha_hasta: Optional[datetime] = None
    asignado_a: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
