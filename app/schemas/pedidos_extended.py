from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# ==================== SCHEMAS PARA IMÁGENES ====================

class ImagenPedidoCreate(BaseModel):
    url: str
    filename: str
    size_bytes: Optional[int] = None
    mime_type: Optional[str] = None

class ImagenPedidoResponse(BaseModel):
    id: int
    pedido_id: int
    url: str
    filename: str
    size_bytes: Optional[int]
    mime_type: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== SCHEMAS PARA COMENTARIOS ====================

class ComentarioPedidoCreate(BaseModel):
    comentario: str

class ComentarioPedidoResponse(BaseModel):
    id: int
    pedido_id: int
    user_id: int
    comentario: str
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== SCHEMAS PARA FILTROS GUARDADOS ====================

class FiltroGuardadoCreate(BaseModel):
    nombre: str
    filtros_json: str  # JSON string con los filtros
    is_default: bool = False

class FiltroGuardadoUpdate(BaseModel):
    nombre: Optional[str] = None
    filtros_json: Optional[str] = None
    is_default: Optional[bool] = None

class FiltroGuardadoResponse(BaseModel):
    id: int
    usuario_id: int
    nombre: str
    filtros_json: str
    is_default: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== SCHEMAS PARA ESTADÍSTICAS AVANZADAS ====================

class EstadisticasAvanzadas(BaseModel):
    total_mensajes: int
    total_pedidos: int

    # Por estado
    pedidos_por_estado: dict

    # Por prioridad
    pedidos_por_prioridad: dict

    # Tiempos promedio por estado (en minutos)
    tiempo_promedio_confirmacion: Optional[float] = None
    tiempo_promedio_preparacion: Optional[float] = None
    tiempo_promedio_completado: Optional[float] = None

    # Tasa de cancelación
    tasa_cancelacion: float

    # Pedidos por hora del día
    pedidos_por_hora: dict

    # Rendimiento por staff (si aplica)
    pedidos_por_staff: Optional[dict] = None


# ==================== SCHEMAS PARA BÚSQUEDA AVANZADA ====================

class BusquedaAvanzadaRequest(BaseModel):
    query: Optional[str] = None  # Búsqueda en resumen_items y notas
    telegram_username: Optional[str] = None
    estado: Optional[str] = None
    prioridad: Optional[str] = None
    fecha_desde: Optional[datetime] = None
    fecha_hasta: Optional[datetime] = None
    asignado_a: Optional[str] = None
    limit: int = 50
    offset: int = 0


# ==================== SCHEMAS PARA HISTORIAL ====================

class HistorialEstadoResponse(BaseModel):
    id: int
    pedido_id: int
    estado_anterior: Optional[str]
    estado_nuevo: str
    modificado_por: Optional[str]
    notas: Optional[str]
    fecha_cambio: datetime

    class Config:
        from_attributes = True
