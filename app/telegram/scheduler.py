"""
Tareas programadas para el bot de Telegram
"""

import os
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from telegram import Bot

from app.database.database import SessionLocal
from app.models.models import Pedido, EstadoPedidoEnum, PrioridadEnum


class TelegramScheduler:
    """Manejador de tareas programadas para Telegram"""

    def __init__(self, bot_token: str, chat_id_resumenes: Optional[str] = None):
        """
        Inicializa el scheduler

        Args:
            bot_token: Token del bot de Telegram
            chat_id_resumenes: ID del chat donde enviar resúmenes (opcional)
        """
        self.bot = Bot(token=bot_token)
        self.chat_id_resumenes = chat_id_resumenes
        self.scheduler = AsyncIOScheduler(timezone=pytz.UTC)

    async def enviar_resumen_pedidos(self):
        """
        Función que se ejecuta cada hora
        Envía un resumen de todos los pedidos activos
        """
        print(f"\n⏰ Ejecutando tarea programada: {datetime.now()}")

        if not self.chat_id_resumenes:
            print("⚠️ No hay chat configurado para resúmenes (TELEGRAM_CHAT_ID_RESUMENES no configurado)")
            return

        db = SessionLocal()
        try:
            # Obtener pedidos activos (no completados ni cancelados)
            pedidos = db.query(Pedido).filter(
                Pedido.estado.in_([
                    EstadoPedidoEnum.PENDIENTE_CONFIRMACION,
                    EstadoPedidoEnum.CONFIRMADO,
                    EstadoPedidoEnum.EN_PREPARACION,
                    EstadoPedidoEnum.LISTO_PARA_RECOGER
                ])
            ).order_by(Pedido.prioridad, Pedido.fecha_creacion).all()

            if not pedidos:
                print("No hay pedidos activos para enviar")
                return

            # Agrupar por prioridad
            pedidos_alta = [p for p in pedidos if p.prioridad == PrioridadEnum.ALTA]
            pedidos_media = [p for p in pedidos if p.prioridad == PrioridadEnum.MEDIA]
            pedidos_baja = [p for p in pedidos if p.prioridad == PrioridadEnum.BAJA]

            # Crear mensaje
            mensaje = f"📊 **RESUMEN DE PEDIDOS ACTIVOS**\n"
            mensaje += f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
            mensaje += f"📦 Total: {len(pedidos)} pedidos activos\n\n"

            # Pedidos de alta prioridad
            if pedidos_alta:
                mensaje += f"🔴 **PRIORIDAD ALTA** ({len(pedidos_alta)}):\n"
                for p in pedidos_alta:
                    mensaje += self._formatear_pedido_resumen(p)
                mensaje += "\n"

            # Pedidos de media prioridad
            if pedidos_media:
                mensaje += f"🟡 **PRIORIDAD MEDIA** ({len(pedidos_media)}):\n"
                for p in pedidos_media:
                    mensaje += self._formatear_pedido_resumen(p)
                mensaje += "\n"

            # Pedidos de baja prioridad
            if pedidos_baja:
                mensaje += f"🟢 **PRIORIDAD BAJA** ({len(pedidos_baja)}):\n"
                for p in pedidos_baja:
                    mensaje += self._formatear_pedido_resumen(p)
                mensaje += "\n"

            # Desglose por estado
            mensaje += "**ESTADOS:**\n"
            por_confirmar = len([p for p in pedidos if p.estado == EstadoPedidoEnum.PENDIENTE_CONFIRMACION])
            confirmados = len([p for p in pedidos if p.estado == EstadoPedidoEnum.CONFIRMADO])
            en_prep = len([p for p in pedidos if p.estado == EstadoPedidoEnum.EN_PREPARACION])
            listos = len([p for p in pedidos if p.estado == EstadoPedidoEnum.LISTO_PARA_RECOGER])

            if por_confirmar > 0:
                mensaje += f"⏳ Por confirmar: {por_confirmar}\n"
            if confirmados > 0:
                mensaje += f"✅ Confirmados: {confirmados}\n"
            if en_prep > 0:
                mensaje += f"🔄 En preparación: {en_prep}\n"
            if listos > 0:
                mensaje += f"🎉 Listos: {listos}\n"

            # Enviar mensaje
            await self.bot.send_message(
                chat_id=self.chat_id_resumenes,
                text=mensaje
            )

            print(f"✅ Resumen enviado: {len(pedidos)} pedidos activos")

        except Exception as e:
            print(f"❌ Error al enviar resumen de pedidos: {e}")
        finally:
            db.close()

    def _formatear_pedido_resumen(self, pedido: Pedido) -> str:
        """Formatea un pedido para el resumen"""
        texto = f"\n🔢 #{pedido.id} - {pedido.resumen_items[:50]}"
        if len(pedido.resumen_items) > 50:
            texto += "..."
        texto += f"\n   📍 Estado: {self._emoji_estado(pedido.estado)}{pedido.estado.value.replace('_', ' ').title()}\n"

        if pedido.fecha_solicitada:
            from .gemini_service import GeminiService
            fecha_legible = GeminiService.formatear_fecha_legible(
                pedido.fecha_solicitada.strftime("%Y-%m-%d")
            )
            if pedido.hora_solicitada:
                texto += f"   📅 Para: {fecha_legible} a las {pedido.hora_solicitada}\n"
            else:
                texto += f"   📅 Para: {fecha_legible}\n"

        return texto

    def _emoji_estado(self, estado: EstadoPedidoEnum) -> str:
        """Retorna emoji según estado"""
        emojis = {
            EstadoPedidoEnum.PENDIENTE_CONFIRMACION: "⏳ ",
            EstadoPedidoEnum.CONFIRMADO: "✅ ",
            EstadoPedidoEnum.EN_PREPARACION: "🔄 ",
            EstadoPedidoEnum.LISTO_PARA_RECOGER: "🎉 ",
            EstadoPedidoEnum.COMPLETADO: "✔️ ",
            EstadoPedidoEnum.CANCELADO: "❌ "
        }
        return emojis.get(estado, "")

    def start(self):
        """Inicia el scheduler con tarea cada hora"""
        # Programar envío de resúmenes cada hora
        self.scheduler.add_job(
            self.enviar_resumen_pedidos,
            trigger=CronTrigger(minute=0, timezone=pytz.UTC),  # Cada hora en punto
            id="resumen_pedidos",
            name="Resumen de pedidos activos",
            replace_existing=True
        )

        self.scheduler.start()
        print("✅ Scheduler iniciado - Resúmenes cada hora")

    def stop(self):
        """Detiene el scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("✅ Scheduler detenido")


# Función auxiliar para iniciar scheduler desde FastAPI
_scheduler_instance: Optional[TelegramScheduler] = None


def start_scheduler(bot_token: str, chat_id_resumenes: Optional[str] = None):
    """
    Inicia el scheduler de tareas programadas

    Args:
        bot_token: Token del bot de Telegram
        chat_id_resumenes: ID del chat para enviar resúmenes
    """
    global _scheduler_instance

    if _scheduler_instance is not None:
        print("⚠️ Scheduler ya está en ejecución")
        return

    _scheduler_instance = TelegramScheduler(bot_token, chat_id_resumenes)
    _scheduler_instance.start()


def stop_scheduler():
    """Detiene el scheduler si está en ejecución"""
    global _scheduler_instance

    if _scheduler_instance is not None:
        _scheduler_instance.stop()
        _scheduler_instance = None


def get_scheduler() -> Optional[TelegramScheduler]:
    """Retorna la instancia del scheduler"""
    return _scheduler_instance
