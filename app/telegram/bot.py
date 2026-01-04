"""
Configuración e inicialización del bot de Telegram
"""

import asyncio
from typing import Optional
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

from .gemini_service import GeminiService
from .handlers import TelegramHandlers


# Variable global para mantener referencia al bot
_bot_instance: Optional[Application] = None


class TelegramBot:
    """Clase para configurar y ejecutar el bot de Telegram"""

    def __init__(self, telegram_token: str, gemini_api_key: str):
        """
        Inicializa el bot de Telegram

        Args:
            telegram_token: Token del bot de Telegram
            gemini_api_key: API key de Google Gemini
        """
        self.telegram_token = telegram_token
        self.gemini_api_key = gemini_api_key
        self.application: Optional[Application] = None
        self.gemini_service: Optional[GeminiService] = None
        self.handlers: Optional[TelegramHandlers] = None

    def setup_handlers(self):
        """Configura todos los handlers del bot"""
        # Crear servicio de Gemini
        self.gemini_service = GeminiService(self.gemini_api_key)

        # Crear handlers
        self.handlers = TelegramHandlers(self.gemini_service)

        # Crear aplicación
        self.application = Application.builder().token(self.telegram_token).build()

        # Registrar handlers de comandos
        self.application.add_handler(CommandHandler("start", self.handlers.start_command))
        self.application.add_handler(CommandHandler("stats", self.handlers.stats_command))
        self.application.add_handler(CommandHandler("pendientes", self.handlers.pendientes_command))

        # IMPORTANTE: Handlers de voz DEBEN registrarse ANTES que handlers de texto
        # para que procesen correctamente los mensajes de voz
        self.application.add_handler(
            MessageHandler(filters.VOICE, self.handlers.procesar_mensaje_voz)
        )

        # Handler de mensajes de texto
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handlers.procesar_mensaje)
        )

        # Handler de botones inline
        self.application.add_handler(CallbackQueryHandler(self.handlers.manejar_confirmacion))

        print("✅ Handlers del bot configurados correctamente")

    async def start(self):
        """Inicia el bot en modo polling"""
        print("🤖 Iniciando bot de Telegram...")

        # Configurar handlers si no están configurados
        if self.application is None:
            self.setup_handlers()

        # Inicializar la aplicación
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"]
        )

        print("✅ Bot de Telegram iniciado correctamente")
        print(f"🔗 El bot está escuchando mensajes...")

    async def stop(self):
        """Detiene el bot limpiamente"""
        if self.application:
            print("🛑 Deteniendo bot de Telegram...")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            print("✅ Bot de Telegram detenido")


# Funciones auxiliares para integración con FastAPI

async def start_bot(telegram_token: str, gemini_api_key: str):
    """
    Inicia el bot de Telegram en background

    Args:
        telegram_token: Token del bot de Telegram
        gemini_api_key: API key de Google Gemini
    """
    global _bot_instance

    bot = TelegramBot(telegram_token, gemini_api_key)
    await bot.start()

    # Guardar referencia global
    _bot_instance = bot.application


def get_bot() -> Optional[Application]:
    """
    Obtiene la instancia del bot

    Returns:
        Instancia de Application o None si no está iniciado
    """
    return _bot_instance


async def stop_bot():
    """Detiene el bot si está en ejecución"""
    global _bot_instance

    if _bot_instance:
        bot = TelegramBot("", "")  # Token y API key no importan para detener
        bot.application = _bot_instance
        await bot.stop()
        _bot_instance = None
