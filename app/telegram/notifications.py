"""
Servicio de notificaciones por Telegram
"""

from datetime import datetime
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError
from sqlalchemy.orm import Session

from app.models.models import NotificacionEnviada, Pedido, TipoNotificacionEnum, EstadoPedidoEnum


class NotificationService:
    """Servicio para enviar notificaciones vía Telegram"""

    def __init__(self, bot_token: str):
        """
        Inicializa el servicio de notificaciones

        Args:
            bot_token: Token del bot de Telegram
        """
        self.bot = Bot(token=bot_token)

    async def enviar_notificacion(
        self,
        db: Session,
        telegram_user_id: int,
        mensaje: str,
        tipo_notificacion: TipoNotificacionEnum,
        pedido_id: Optional[int] = None
    ) -> bool:
        """
        Envía una notificación directa vía Telegram

        Args:
            db: Sesión de base de datos
            telegram_user_id: ID de Telegram del usuario
            mensaje: Texto del mensaje a enviar
            tipo_notificacion: Tipo de notificación
            pedido_id: ID del pedido relacionado (opcional)

        Returns:
            True si se envió correctamente, False si hubo error
        """
        try:
            # Enviar mensaje
            await self.bot.send_message(
                chat_id=telegram_user_id,
                text=mensaje
            )

            # Registrar notificación exitosa
            notificacion = NotificacionEnviada(
                pedido_id=pedido_id,
                telegram_user_id=telegram_user_id,
                tipo_notificacion=tipo_notificacion,
                mensaje=mensaje,
                exitoso=True
            )
            db.add(notificacion)
            db.commit()

            print(f"✅ Notificación enviada a {telegram_user_id}: {tipo_notificacion.value}")
            return True

        except TelegramError as e:
            error_msg = str(e)
            print(f"❌ Error al enviar notificación a {telegram_user_id}: {error_msg}")

            # Registrar notificación fallida
            notificacion = NotificacionEnviada(
                pedido_id=pedido_id,
                telegram_user_id=telegram_user_id,
                tipo_notificacion=tipo_notificacion,
                mensaje=mensaje,
                exitoso=False,
                error=error_msg
            )
            db.add(notificacion)
            db.commit()

            return False

        except Exception as e:
            print(f"❌ Error inesperado al enviar notificación: {e}")
            return False

    def notificar_cambio_estado(
        self,
        pedido: Pedido,
        nuevo_estado: EstadoPedidoEnum
    ) -> Optional[dict]:
        """
        Prepara mensaje de notificación para cambio de estado

        Args:
            pedido: Pedido que cambió de estado
            nuevo_estado: Nuevo estado del pedido

        Returns:
            Diccionario con datos para envío o None si no se debe notificar
        """
        # Mapeo de estados a mensajes
        mensajes_estado = {
            EstadoPedidoEnum.CONFIRMADO: (
                f"✅ **TU PEDIDO #{pedido.id} HA SIDO CONFIRMADO**\n\n"
                f"📦 {pedido.resumen_items}\n\n"
                f"Tu pedido ha sido confirmado y está en espera de preparación.\n"
                f"Te notificaremos cuando esté listo."
            ),
            EstadoPedidoEnum.EN_PREPARACION: (
                f"🔄 **TU PEDIDO #{pedido.id} ESTÁ EN PREPARACIÓN**\n\n"
                f"📦 {pedido.resumen_items}\n\n"
                f"Estamos preparando tu pedido.\n"
                f"Te avisaremos cuando esté listo para recoger."
            ),
            EstadoPedidoEnum.LISTO_PARA_RECOGER: (
                f"✅ **¡TU PEDIDO #{pedido.id} ESTÁ LISTO!**\n\n"
                f"📦 {pedido.resumen_items}\n\n"
                f"Tu pedido está listo para recoger.\n"
                f"¡Te esperamos!"
            ),
            EstadoPedidoEnum.COMPLETADO: (
                f"🎉 **¡GRACIAS POR TU PEDIDO #{pedido.id}!**\n\n"
                f"📦 {pedido.resumen_items}\n\n"
                f"Tu pedido ha sido completado.\n"
                f"¡Esperamos verte pronto!"
            ),
            EstadoPedidoEnum.CANCELADO: (
                f"❌ **TU PEDIDO #{pedido.id} HA SIDO CANCELADO**\n\n"
                f"📦 {pedido.resumen_items}\n\n"
                f"Tu pedido ha sido cancelado.\n"
                f"Si tienes alguna pregunta, contáctanos."
            )
        }

        # Obtener mensaje según el estado
        mensaje = mensajes_estado.get(nuevo_estado)

        if mensaje is None:
            # No notificar para PENDIENTE_CONFIRMACION (se notifica con los botones)
            return None

        return {
            "telegram_user_id": pedido.telegram_user_id,
            "mensaje": mensaje,
            "tipo_notificacion": TipoNotificacionEnum.CAMBIO_ESTADO,
            "pedido_id": pedido.id
        }

    async def enviar_notificacion_cambio_estado(
        self,
        db: Session,
        pedido: Pedido,
        nuevo_estado: EstadoPedidoEnum
    ) -> bool:
        """
        Envía notificación de cambio de estado de forma directa

        Args:
            db: Sesión de base de datos
            pedido: Pedido que cambió de estado
            nuevo_estado: Nuevo estado del pedido

        Returns:
            True si se envió correctamente, False si no se debe notificar o hay error
        """
        # Preparar datos de notificación
        notif_data = self.notificar_cambio_estado(pedido, nuevo_estado)

        if notif_data is None:
            return False

        # Enviar notificación
        return await self.enviar_notificacion(
            db=db,
            telegram_user_id=notif_data["telegram_user_id"],
            mensaje=notif_data["mensaje"],
            tipo_notificacion=notif_data["tipo_notificacion"],
            pedido_id=notif_data["pedido_id"]
        )

    async def enviar_recordatorio(
        self,
        db: Session,
        telegram_user_id: int,
        mensaje: str,
        pedido_id: Optional[int] = None
    ) -> bool:
        """
        Envía un recordatorio al usuario

        Args:
            db: Sesión de base de datos
            telegram_user_id: ID de Telegram del usuario
            mensaje: Texto del recordatorio
            pedido_id: ID del pedido relacionado (opcional)

        Returns:
            True si se envió correctamente
        """
        return await self.enviar_notificacion(
            db=db,
            telegram_user_id=telegram_user_id,
            mensaje=mensaje,
            tipo_notificacion=TipoNotificacionEnum.RECORDATORIO,
            pedido_id=pedido_id
        )

    async def enviar_resumen(
        self,
        db: Session,
        telegram_user_id: int,
        mensaje: str
    ) -> bool:
        """
        Envía un resumen al usuario o administrador

        Args:
            db: Sesión de base de datos
            telegram_user_id: ID de Telegram del usuario
            mensaje: Texto del resumen

        Returns:
            True si se envió correctamente
        """
        return await self.enviar_notificacion(
            db=db,
            telegram_user_id=telegram_user_id,
            mensaje=mensaje,
            tipo_notificacion=TipoNotificacionEnum.RESUMEN
        )
