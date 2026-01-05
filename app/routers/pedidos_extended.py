"""
Router extendido para pedidos con funcionalidades avanzadas:
- Búsqueda avanzada
- Upload de imágenes
- Comentarios
- Historial de cambios
- Estadísticas avanzadas
- Export de datos
- Filtros guardados
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, extract, desc
from app.database.database import get_db
from app.models.models import (
    User, Pedido, ImagenPedido, ComentarioPedido,
    FiltroGuardado, HistorialEstado, LogMensaje,
    EstadoPedidoEnum
)
from app.schemas.pedidos_extended import (
    ImagenPedidoCreate, ImagenPedidoResponse,
    ComentarioPedidoCreate, ComentarioPedidoResponse,
    FiltroGuardadoCreate, FiltroGuardadoUpdate, FiltroGuardadoResponse,
    EstadisticasAvanzadas, BusquedaAvanzadaRequest,
    HistorialEstadoResponse
)
from app.auth.jwt import get_current_active_user
from typing import List, Optional
from datetime import datetime, timedelta
import json
import csv
import io

router = APIRouter(prefix="/api/pedidos-extended", tags=["Pedidos Extended"])


def require_admin_or_staff(current_user: User = Depends(get_current_active_user)):
    """Dependency para verificar que el usuario sea admin o staff"""
    if current_user.role not in ["admin", "staff"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para acceder a este recurso"
        )
    return current_user


# ==================== BÚSQUEDA AVANZADA ====================

@router.post("/buscar")
def buscar_pedidos_avanzado(
    busqueda: BusquedaAvanzadaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_staff)
):
    """
    Búsqueda avanzada de pedidos con múltiples filtros
    """
    query = db.query(Pedido)

    # Filtro de texto (buscar en resumen_items y notas)
    if busqueda.query:
        search_term = f"%{busqueda.query}%"
        query = query.filter(
            or_(
                Pedido.resumen_items.ilike(search_term),
                Pedido.notas_adicionales.ilike(search_term),
                Pedido.telegram_username.ilike(search_term)
            )
        )

    # Filtro por username de Telegram
    if busqueda.telegram_username:
        query = query.filter(Pedido.telegram_username.ilike(f"%{busqueda.telegram_username}%"))

    # Filtro por estado
    if busqueda.estado:
        query = query.filter(Pedido.estado == busqueda.estado)

    # Filtro por prioridad
    if busqueda.prioridad:
        query = query.filter(Pedido.prioridad == busqueda.prioridad)

    # Filtro por rango de fechas
    if busqueda.fecha_desde:
        query = query.filter(Pedido.fecha_creacion >= busqueda.fecha_desde)

    if busqueda.fecha_hasta:
        query = query.filter(Pedido.fecha_creacion <= busqueda.fecha_hasta)

    # Filtro por asignación
    if busqueda.asignado_a:
        query = query.filter(Pedido.asignado_a == busqueda.asignado_a)

    # Contar total de resultados
    total = query.count()

    # Aplicar paginación y ordenar por fecha más reciente
    pedidos = query.order_by(desc(Pedido.fecha_creacion)) \
        .limit(busqueda.limit) \
        .offset(busqueda.offset) \
        .all()

    return {
        "total": total,
        "pedidos": pedidos,
        "limit": busqueda.limit,
        "offset": busqueda.offset
    }


# ==================== IMÁGENES DE PEDIDOS ====================

@router.post("/pedidos/{pedido_id}/imagenes", response_model=ImagenPedidoResponse)
def agregar_imagen_pedido(
    pedido_id: int,
    imagen_data: ImagenPedidoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_staff)
):
    """
    Agregar una imagen a un pedido
    """
    # Verificar que el pedido existe
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if not pedido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido no encontrado"
        )

    # Crear imagen
    imagen = ImagenPedido(
        pedido_id=pedido_id,
        url=imagen_data.url,
        filename=imagen_data.filename,
        size_bytes=imagen_data.size_bytes,
        mime_type=imagen_data.mime_type
    )

    db.add(imagen)
    db.commit()
    db.refresh(imagen)

    return imagen


@router.get("/pedidos/{pedido_id}/imagenes", response_model=List[ImagenPedidoResponse])
def obtener_imagenes_pedido(
    pedido_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_staff)
):
    """
    Obtener todas las imágenes de un pedido
    """
    imagenes = db.query(ImagenPedido) \
        .filter(ImagenPedido.pedido_id == pedido_id) \
        .all()

    return imagenes


@router.delete("/imagenes/{imagen_id}")
def eliminar_imagen(
    imagen_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_staff)
):
    """
    Eliminar una imagen
    """
    imagen = db.query(ImagenPedido).filter(ImagenPedido.id == imagen_id).first()

    if not imagen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Imagen no encontrada"
        )

    db.delete(imagen)
    db.commit()

    return {"message": "Imagen eliminada exitosamente"}


# ==================== COMENTARIOS EN PEDIDOS ====================

@router.post("/pedidos/{pedido_id}/comentarios", response_model=ComentarioPedidoResponse)
def agregar_comentario(
    pedido_id: int,
    comentario_data: ComentarioPedidoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_staff)
):
    """
    Agregar un comentario a un pedido
    """
    # Verificar que el pedido existe
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if not pedido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido no encontrado"
        )

    # Crear comentario
    comentario = ComentarioPedido(
        pedido_id=pedido_id,
        user_id=current_user.id,
        comentario=comentario_data.comentario
    )

    db.add(comentario)
    db.commit()
    db.refresh(comentario)

    return comentario


@router.get("/pedidos/{pedido_id}/comentarios", response_model=List[ComentarioPedidoResponse])
def obtener_comentarios(
    pedido_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_staff)
):
    """
    Obtener todos los comentarios de un pedido
    """
    comentarios = db.query(ComentarioPedido) \
        .filter(ComentarioPedido.pedido_id == pedido_id) \
        .order_by(ComentarioPedido.created_at) \
        .all()

    return comentarios


# ==================== HISTORIAL DE CAMBIOS ====================

@router.get("/pedidos/{pedido_id}/historial", response_model=List[HistorialEstadoResponse])
def obtener_historial(
    pedido_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_staff)
):
    """
    Obtener historial de cambios de estado de un pedido
    """
    historial = db.query(HistorialEstado) \
        .filter(HistorialEstado.pedido_id == pedido_id) \
        .order_by(HistorialEstado.fecha_cambio) \
        .all()

    return historial


# ==================== FILTROS GUARDADOS ====================

@router.post("/filtros", response_model=FiltroGuardadoResponse)
def guardar_filtro(
    filtro_data: FiltroGuardadoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Guardar una configuración de filtros
    """
    # Si se marca como predeterminado, desmarcar los otros
    if filtro_data.is_default:
        db.query(FiltroGuardado) \
            .filter(FiltroGuardado.usuario_id == current_user.id) \
            .update({"is_default": False})

    filtro = FiltroGuardado(
        usuario_id=current_user.id,
        nombre=filtro_data.nombre,
        filtros_json=filtro_data.filtros_json,
        is_default=filtro_data.is_default
    )

    db.add(filtro)
    db.commit()
    db.refresh(filtro)

    return filtro


@router.get("/filtros", response_model=List[FiltroGuardadoResponse])
def obtener_filtros(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Obtener todos los filtros guardados del usuario
    """
    filtros = db.query(FiltroGuardado) \
        .filter(FiltroGuardado.usuario_id == current_user.id) \
        .order_by(desc(FiltroGuardado.is_default), FiltroGuardado.created_at) \
        .all()

    return filtros


@router.put("/filtros/{filtro_id}", response_model=FiltroGuardadoResponse)
def actualizar_filtro(
    filtro_id: int,
    filtro_data: FiltroGuardadoUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Actualizar un filtro guardado
    """
    filtro = db.query(FiltroGuardado).filter(
        FiltroGuardado.id == filtro_id,
        FiltroGuardado.usuario_id == current_user.id
    ).first()

    if not filtro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Filtro no encontrado"
        )

    # Si se marca como predeterminado, desmarcar los otros
    if filtro_data.is_default and filtro_data.is_default != filtro.is_default:
        db.query(FiltroGuardado) \
            .filter(
                FiltroGuardado.usuario_id == current_user.id,
                FiltroGuardado.id != filtro_id
            ) \
            .update({"is_default": False})

    # Actualizar campos
    if filtro_data.nombre is not None:
        filtro.nombre = filtro_data.nombre
    if filtro_data.filtros_json is not None:
        filtro.filtros_json = filtro_data.filtros_json
    if filtro_data.is_default is not None:
        filtro.is_default = filtro_data.is_default

    db.commit()
    db.refresh(filtro)

    return filtro


@router.delete("/filtros/{filtro_id}")
def eliminar_filtro(
    filtro_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Eliminar un filtro guardado
    """
    filtro = db.query(FiltroGuardado).filter(
        FiltroGuardado.id == filtro_id,
        FiltroGuardado.usuario_id == current_user.id
    ).first()

    if not filtro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Filtro no encontrado"
        )

    db.delete(filtro)
    db.commit()

    return {"message": "Filtro eliminado exitosamente"}


# ==================== ESTADÍSTICAS AVANZADAS ====================

@router.get("/estadisticas-avanzadas", response_model=EstadisticasAvanzadas)
def obtener_estadisticas_avanzadas(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_staff)
):
    """
    Obtener estadísticas avanzadas con tiempos y rendimiento
    """
    # Totales básicos
    total_mensajes = db.query(func.count(LogMensaje.id)).scalar()
    total_pedidos = db.query(func.count(Pedido.id)).scalar()

    # Pedidos por estado
    pedidos_por_estado = {}
    for estado in EstadoPedidoEnum:
        count = db.query(func.count(Pedido.id)) \
            .filter(Pedido.estado == estado.value) \
            .scalar()
        pedidos_por_estado[estado.value] = count

    # Pedidos por prioridad
    pedidos_por_prioridad = db.query(
        Pedido.prioridad,
        func.count(Pedido.id)
    ).group_by(Pedido.prioridad).all()

    pedidos_por_prioridad_dict = {str(p[0]): p[1] for p in pedidos_por_prioridad}

    # Tiempos promedio por estado (en minutos)
    pedidos_confirmados = db.query(Pedido).filter(
        Pedido.fecha_confirmacion.isnot(None)
    ).all()

    if pedidos_confirmados:
        tiempos_confirmacion = [
            (p.fecha_confirmacion - p.fecha_creacion).total_seconds() / 60
            for p in pedidos_confirmados
        ]
        tiempo_promedio_confirmacion = sum(tiempos_confirmacion) / len(tiempos_confirmacion)
    else:
        tiempo_promedio_confirmacion = None

    pedidos_preparados = db.query(Pedido).filter(
        Pedido.fecha_preparacion.isnot(None),
        Pedido.fecha_confirmacion.isnot(None)
    ).all()

    if pedidos_preparados:
        tiempos_preparacion = [
            (p.fecha_preparacion - p.fecha_confirmacion).total_seconds() / 60
            for p in pedidos_preparados
        ]
        tiempo_promedio_preparacion = sum(tiempos_preparacion) / len(tiempos_preparacion)
    else:
        tiempo_promedio_preparacion = None

    pedidos_completados = db.query(Pedido).filter(
        Pedido.fecha_completado.isnot(None)
    ).all()

    if pedidos_completados:
        tiempos_completado = [
            (p.fecha_completado - p.fecha_creacion).total_seconds() / 60
            for p in pedidos_completados
        ]
        tiempo_promedio_completado = sum(tiempos_completado) / len(tiempos_completado)
    else:
        tiempo_promedio_completado = None

    # Tasa de cancelación
    pedidos_cancelados = pedidos_por_estado.get('cancelado', 0)
    tasa_cancelacion = (pedidos_cancelados / total_pedidos * 100) if total_pedidos > 0 else 0

    # Pedidos por hora del día
    pedidos_por_hora = {}
    for hora in range(24):
        count = db.query(func.count(Pedido.id)) \
            .filter(extract('hour', Pedido.fecha_creacion) == hora) \
            .scalar()
        pedidos_por_hora[str(hora)] = count

    # Pedidos por staff (quién tiene asignados)
    pedidos_por_staff = db.query(
        Pedido.asignado_a,
        func.count(Pedido.id)
    ).filter(
        Pedido.asignado_a.isnot(None)
    ).group_by(Pedido.asignado_a).all()

    pedidos_por_staff_dict = {p[0]: p[1] for p in pedidos_por_staff} if pedidos_por_staff else None

    return EstadisticasAvanzadas(
        total_mensajes=total_mensajes,
        total_pedidos=total_pedidos,
        pedidos_por_estado=pedidos_por_estado,
        pedidos_por_prioridad=pedidos_por_prioridad_dict,
        tiempo_promedio_confirmacion=tiempo_promedio_confirmacion,
        tiempo_promedio_preparacion=tiempo_promedio_preparacion,
        tiempo_promedio_completado=tiempo_promedio_completado,
        tasa_cancelacion=round(tasa_cancelacion, 2),
        pedidos_por_hora=pedidos_por_hora,
        pedidos_por_staff=pedidos_por_staff_dict
    )


# ==================== EXPORT DE DATOS ====================

@router.get("/export/csv")
def exportar_pedidos_csv(
    estado: Optional[str] = None,
    fecha_desde: Optional[datetime] = None,
    fecha_hasta: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_staff)
):
    """
    Exportar pedidos a CSV
    """
    query = db.query(Pedido)

    # Aplicar filtros
    if estado:
        query = query.filter(Pedido.estado == estado)
    if fecha_desde:
        query = query.filter(Pedido.fecha_creacion >= fecha_desde)
    if fecha_hasta:
        query = query.filter(Pedido.fecha_creacion <= fecha_hasta)

    pedidos = query.all()

    # Crear CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Encabezados
    writer.writerow([
        'ID', 'Telegram User ID', 'Username', 'Prioridad', 'Estado',
        'Fecha Solicitada', 'Hora Solicitada', 'Resumen Items',
        'Notas', 'Asignado A', 'Fecha Creación', 'Fecha Confirmación',
        'Fecha Preparación', 'Fecha Listo', 'Fecha Completado'
    ])

    # Datos
    for p in pedidos:
        writer.writerow([
            p.id,
            p.telegram_user_id,
            p.telegram_username,
            p.prioridad,
            p.estado,
            p.fecha_solicitada,
            p.hora_solicitada,
            p.resumen_items,
            p.notas_adicionales,
            p.asignado_a,
            p.fecha_creacion,
            p.fecha_confirmacion,
            p.fecha_preparacion,
            p.fecha_listo,
            p.fecha_completado
        ])

    # Retornar CSV
    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=pedidos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )
