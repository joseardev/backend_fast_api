from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, Text, Enum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from ..database.database import Base

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(String, default="user", nullable=False)
    is_active = Column(Boolean, default=True)
    is_email_verified = Column(Boolean, default=False)
    email_verification_token = Column(String, nullable=True)
    telegram_id = Column(BigInteger, nullable=True, unique=True, index=True)
    telegram_username = Column(String, nullable=True)

    # Push notifications
    fcm_token = Column(String, nullable=True)  # Firebase Cloud Messaging (Android/iOS)
    apns_token = Column(String, nullable=True)  # Apple Push Notification Service

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    pedidos = relationship("Pedido", back_populates="usuario")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    filtros_guardados = relationship("FiltroGuardado", back_populates="usuario", cascade="all, delete-orphan")


# Enums para Telegram
class PrioridadEnum(str, enum.Enum):
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


class EstadoPedidoEnum(str, enum.Enum):
    PENDIENTE_CONFIRMACION = "pendiente_confirmacion"
    CONFIRMADO = "confirmado"
    EN_PREPARACION = "en_preparacion"
    LISTO_PARA_RECOGER = "listo_para_recoger"
    COMPLETADO = "completado"
    CANCELADO = "cancelado"


class TipoNotificacionEnum(str, enum.Enum):
    CAMBIO_ESTADO = "cambio_estado"
    RECORDATORIO = "recordatorio"
    RESUMEN = "resumen"


# Modelo para registrar mensajes de Telegram
class LogMensaje(Base):
    __tablename__ = "logs_mensajes"

    id = Column(Integer, primary_key=True, index=True)
    telegram_user_id = Column(BigInteger, nullable=False, index=True)
    telegram_username = Column(String, nullable=True)
    mensaje_id = Column(BigInteger, nullable=False)
    tipo_mensaje = Column(String, nullable=False)  # 'text', 'voice', 'photo', etc.
    contenido = Column(Text, nullable=True)
    transcripcion = Column(Text, nullable=True)
    es_pedido = Column(Boolean, default=False)
    fecha_recepcion = Column(DateTime, default=datetime.utcnow, nullable=False)


# Modelo para pedidos procesados
class Pedido(Base):
    __tablename__ = "pedidos"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    telegram_user_id = Column(BigInteger, nullable=False, index=True)
    telegram_username = Column(String, nullable=True)
    mensaje_id = Column(BigInteger, nullable=False)

    # Clasificación del pedido
    prioridad = Column(Enum(PrioridadEnum, native_enum=True, name='prioridad_enum'),
                      default=PrioridadEnum.MEDIA, nullable=False)
    estado = Column(Enum(EstadoPedidoEnum, native_enum=True, name='estado_pedido_enum'),
                   default=EstadoPedidoEnum.PENDIENTE_CONFIRMACION, nullable=False)

    # Detalles del pedido
    fecha_solicitada = Column(DateTime, nullable=True)
    hora_solicitada = Column(String, nullable=True)
    resumen_items = Column(Text, nullable=False)
    notas_adicionales = Column(Text, nullable=True)

    # Asignación y seguimiento
    asignado_a = Column(String, nullable=True)

    # Timestamps
    fecha_creacion = Column(DateTime, default=datetime.utcnow, nullable=False)
    fecha_confirmacion = Column(DateTime, nullable=True)
    fecha_preparacion = Column(DateTime, nullable=True)
    fecha_listo = Column(DateTime, nullable=True)
    fecha_completado = Column(DateTime, nullable=True)
    fecha_cancelado = Column(DateTime, nullable=True)

    # Relaciones
    usuario = relationship("User", back_populates="pedidos")
    historial = relationship("HistorialEstado", back_populates="pedido", cascade="all, delete-orphan")
    imagenes = relationship("ImagenPedido", back_populates="pedido", cascade="all, delete-orphan")
    comentarios = relationship("ComentarioPedido", back_populates="pedido", cascade="all, delete-orphan")


# Modelo para auditoría de cambios de estado
class HistorialEstado(Base):
    __tablename__ = "historial_estados"

    id = Column(Integer, primary_key=True, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=False)
    estado_anterior = Column(Enum(EstadoPedidoEnum, native_enum=True, name='estado_pedido_enum'), nullable=True)
    estado_nuevo = Column(Enum(EstadoPedidoEnum, native_enum=True, name='estado_pedido_enum'), nullable=False)
    modificado_por = Column(String, nullable=True)
    notas = Column(Text, nullable=True)
    fecha_cambio = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relación
    pedido = relationship("Pedido", back_populates="historial")


# Modelo para tracking de notificaciones enviadas
class NotificacionEnviada(Base):
    __tablename__ = "notificaciones_enviadas"

    id = Column(Integer, primary_key=True, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=True)
    telegram_user_id = Column(BigInteger, nullable=False, index=True)
    tipo_notificacion = Column(Enum(TipoNotificacionEnum, native_enum=True, name='tipo_notificacion_enum'),
                               nullable=False)
    mensaje = Column(Text, nullable=False)
    exitoso = Column(Boolean, default=True)
    error = Column(Text, nullable=True)
    fecha_envio = Column(DateTime, default=datetime.utcnow, nullable=False)


# ==================== NUEVOS MODELOS ====================

# Modelo para Refresh Tokens
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relación
    user = relationship("User", back_populates="refresh_tokens")


# Modelo para Imágenes de Pedidos
class ImagenPedido(Base):
    __tablename__ = "imagenes_pedidos"

    id = Column(Integer, primary_key=True, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=False)
    url = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=True)
    mime_type = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relación
    pedido = relationship("Pedido", back_populates="imagenes")


# Modelo para Comentarios en Pedidos
class ComentarioPedido(Base):
    __tablename__ = "comentarios_pedidos"

    id = Column(Integer, primary_key=True, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    comentario = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relación
    pedido = relationship("Pedido", back_populates="comentarios")


# Modelo para Filtros Guardados
class FiltroGuardado(Base):
    __tablename__ = "filtros_guardados"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    nombre = Column(String, nullable=False)
    filtros_json = Column(Text, nullable=False)  # JSON con los filtros
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relación
    usuario = relationship("User", back_populates="filtros_guardados")
