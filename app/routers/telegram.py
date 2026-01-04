"""
Router de API REST para gestión de pedidos de Telegram
"""

import os
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.database import get_db
from app.models.models import (
    User, Pedido, LogMensaje, HistorialEstado,
    EstadoPedidoEnum, PrioridadEnum
)
from app.schemas.telegram import (
    PedidoResponse, PedidoListResponse, PedidoUpdate,
    CambiarEstadoPedido, EstadisticasResponse
)
from app.auth.jwt import get_current_active_user

router = APIRouter(prefix="/api/telegram", tags=["Telegram"])


def verificar_admin(current_user: User):
    """Verifica que el usuario tenga rol admin o staff"""
    if current_user.role not in ["admin", "staff"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para acceder a este recurso"
        )


@router.get("/pedidos", response_model=PedidoListResponse)
async def listar_pedidos(
    estado: Optional[str] = Query(None, regex="^(pendiente_confirmacion|confirmado|en_preparacion|listo_para_recoger|completado|cancelado)$"),
    prioridad: Optional[str] = Query(None, regex="^(alta|media|baja)$"),
    telegram_user_id: Optional[int] = None,
    fecha_desde: Optional[datetime] = None,
    fecha_hasta: Optional[datetime] = None,
    asignado_a: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Lista pedidos con filtros opcionales
    Requiere rol admin o staff
    """
    verificar_admin(current_user)

    # Construir query base
    query = db.query(Pedido)

    # Aplicar filtros
    if estado:
        query = query.filter(Pedido.estado == estado)

    if prioridad:
        query = query.filter(Pedido.prioridad == prioridad)

    if telegram_user_id:
        query = query.filter(Pedido.telegram_user_id == telegram_user_id)

    if fecha_desde:
        query = query.filter(Pedido.fecha_creacion >= fecha_desde)

    if fecha_hasta:
        query = query.filter(Pedido.fecha_creacion <= fecha_hasta)

    if asignado_a:
        query = query.filter(Pedido.asignado_a == asignado_a)

    # Contar total
    total = query.count()

    # Aplicar paginación y ordenar
    pedidos = query.order_by(
        Pedido.fecha_creacion.desc()
    ).offset(offset).limit(limit).all()

    return PedidoListResponse(
        total=total,
        pedidos=pedidos,
        offset=offset,
        limit=limit
    )


@router.get("/pedidos/{pedido_id}", response_model=PedidoResponse)
async def obtener_pedido(
    pedido_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene detalle de un pedido específico
    Requiere rol admin o staff
    """
    verificar_admin(current_user)

    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()

    if not pedido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido #{pedido_id} no encontrado"
        )

    return pedido


@router.put("/pedidos/{pedido_id}", response_model=PedidoResponse)
async def actualizar_pedido(
    pedido_id: int,
    pedido_update: PedidoUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Actualiza información de un pedido
    Requiere rol admin o staff
    """
    verificar_admin(current_user)

    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()

    if not pedido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido #{pedido_id} no encontrado"
        )

    # Actualizar campos permitidos
    if pedido_update.notas_adicionales is not None:
        pedido.notas_adicionales = pedido_update.notas_adicionales

    if pedido_update.asignado_a is not None:
        pedido.asignado_a = pedido_update.asignado_a

    db.commit()
    db.refresh(pedido)

    return pedido


@router.post("/pedidos/{pedido_id}/cambiar-estado", response_model=PedidoResponse)
async def cambiar_estado_pedido(
    pedido_id: int,
    cambio_estado: CambiarEstadoPedido,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Cambia el estado de un pedido
    Envía notificación automática al cliente
    Requiere rol admin o staff
    """
    verificar_admin(current_user)

    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()

    if not pedido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido #{pedido_id} no encontrado"
        )

    # Validar nuevo estado
    try:
        nuevo_estado = EstadoPedidoEnum(cambio_estado.nuevo_estado)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Estado '{cambio_estado.nuevo_estado}' no válido"
        )

    estado_anterior = pedido.estado

    # Actualizar estado
    pedido.estado = nuevo_estado

    # Actualizar timestamps según el nuevo estado
    if nuevo_estado == EstadoPedidoEnum.CONFIRMADO:
        pedido.fecha_confirmacion = datetime.utcnow()
    elif nuevo_estado == EstadoPedidoEnum.EN_PREPARACION:
        pedido.fecha_preparacion = datetime.utcnow()
    elif nuevo_estado == EstadoPedidoEnum.LISTO_PARA_RECOGER:
        pedido.fecha_listo = datetime.utcnow()
    elif nuevo_estado == EstadoPedidoEnum.COMPLETADO:
        pedido.fecha_completado = datetime.utcnow()
    elif nuevo_estado == EstadoPedidoEnum.CANCELADO:
        pedido.fecha_cancelado = datetime.utcnow()

    # Registrar en historial
    historial = HistorialEstado(
        pedido_id=pedido_id,
        estado_anterior=estado_anterior,
        estado_nuevo=nuevo_estado,
        modificado_por=current_user.email,
        notas=cambio_estado.notas
    )
    db.add(historial)
    db.commit()
    db.refresh(pedido)

    # Enviar notificación al cliente (asíncrono)
    # Nota: Esto se ejecutará en background
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    if telegram_token:
        import asyncio
        from app.telegram.notifications import NotificationService

        async def enviar_notif():
            notif_service = NotificationService(telegram_token)
            from app.database.database import SessionLocal
            db_notif = SessionLocal()
            try:
                await notif_service.enviar_notificacion_cambio_estado(
                    db=db_notif,
                    pedido=pedido,
                    nuevo_estado=nuevo_estado
                )
            finally:
                db_notif.close()

        asyncio.create_task(enviar_notif())

    return pedido


@router.get("/estadisticas", response_model=EstadisticasResponse)
async def obtener_estadisticas(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene estadísticas generales del sistema
    Requiere rol admin o staff
    """
    verificar_admin(current_user)

    # Total de mensajes
    total_mensajes = db.query(LogMensaje).count()

    # Total de pedidos
    total_pedidos = db.query(Pedido).count()

    # Pedidos por estado
    pedidos_por_estado = {}
    for estado in EstadoPedidoEnum:
        count = db.query(Pedido).filter(Pedido.estado == estado).count()
        pedidos_por_estado[estado.value] = count

    # Pedidos por prioridad
    pedidos_por_prioridad = {}
    for prioridad in PrioridadEnum:
        count = db.query(Pedido).filter(Pedido.prioridad == prioridad).count()
        pedidos_por_prioridad[prioridad.value] = count

    return EstadisticasResponse(
        total_mensajes=total_mensajes,
        total_pedidos=total_pedidos,
        pedidos_por_estado=pedidos_por_estado,
        pedidos_por_prioridad=pedidos_por_prioridad
    )
