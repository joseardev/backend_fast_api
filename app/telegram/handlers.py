"""
Handlers del bot de Telegram para procesamiento de mensajes y comandos
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.models import LogMensaje, Pedido, HistorialEstado, User, EstadoPedidoEnum
from .gemini_service import GeminiService


class TelegramHandlers:
    """Clase para manejar los handlers del bot"""

    def __init__(self, gemini_service: GeminiService):
        """
        Inicializa los handlers

        Args:
            gemini_service: Instancia del servicio de Gemini
        """
        self.gemini = gemini_service

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para el comando /start"""
        await update.message.reply_text(
            "¡Hola! 👋\n\n"
            "Soy un bot de gestión de pedidos.\n"
            "Puedes escribirme tus pedidos y los procesaré automáticamente.\n\n"
            "Comandos disponibles:\n"
            "/start - Mostrar este mensaje\n"
            "/stats - Ver estadísticas\n"
            "/pendientes - Ver pedidos pendientes"
        )

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para el comando /stats"""
        db: Session = SessionLocal()
        try:
            user = update.effective_user

            # Obtener estadísticas
            total_mensajes = db.query(LogMensaje).filter(
                LogMensaje.telegram_user_id == user.id
            ).count()

            total_pedidos = db.query(Pedido).filter(
                Pedido.telegram_user_id == user.id
            ).count()

            pedidos_por_confirmar = db.query(Pedido).filter(
                Pedido.telegram_user_id == user.id,
                Pedido.estado == EstadoPedidoEnum.PENDIENTE_CONFIRMACION
            ).count()

            pedidos_confirmados = db.query(Pedido).filter(
                Pedido.telegram_user_id == user.id,
                Pedido.estado == EstadoPedidoEnum.CONFIRMADO
            ).count()

            pedidos_cancelados = db.query(Pedido).filter(
                Pedido.telegram_user_id == user.id,
                Pedido.estado == EstadoPedidoEnum.CANCELADO
            ).count()

            mensaje = (
                "📊 Estadísticas del Bot\n\n"
                f"📝 Total mensajes: {total_mensajes}\n"
                f"🛒 Total pedidos: {total_pedidos}\n\n"
                f"⏳ Por confirmar: {pedidos_por_confirmar}\n"
                f"✅ Confirmados: {pedidos_confirmados}\n"
                f"❌ Cancelados: {pedidos_cancelados}"
            )

            await update.message.reply_text(mensaje)

        finally:
            db.close()

    async def pendientes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler para el comando /pendientes - muestra pedidos activos"""
        db: Session = SessionLocal()
        try:
            user = update.effective_user

            # Obtener pedidos pendientes (no completados ni cancelados)
            pedidos = db.query(Pedido).filter(
                Pedido.telegram_user_id == user.id,
                Pedido.estado.in_([
                    EstadoPedidoEnum.PENDIENTE_CONFIRMACION,
                    EstadoPedidoEnum.CONFIRMADO,
                    EstadoPedidoEnum.EN_PREPARACION,
                    EstadoPedidoEnum.LISTO_PARA_RECOGER
                ])
            ).order_by(Pedido.fecha_creacion.desc()).all()

            if not pedidos:
                await update.message.reply_text(
                    "✅ No hay pedidos pendientes en este momento.\n"
                    "Puedes crear uno enviándome un mensaje con tu pedido."
                )
                return

            # Separar por estado
            por_confirmar = [p for p in pedidos if p.estado == EstadoPedidoEnum.PENDIENTE_CONFIRMACION]
            confirmados = [p for p in pedidos if p.estado == EstadoPedidoEnum.CONFIRMADO]
            en_preparacion = [p for p in pedidos if p.estado == EstadoPedidoEnum.EN_PREPARACION]
            listos = [p for p in pedidos if p.estado == EstadoPedidoEnum.LISTO_PARA_RECOGER]

            mensaje = "📋 **TUS PEDIDOS**\n\n"

            # Mostrar pedidos por confirmar
            if por_confirmar:
                mensaje += "⏳ **POR CONFIRMAR:**\n"
                for pedido in por_confirmar:
                    mensaje += self._formatear_pedido(pedido)
                mensaje += "\n"

            # Mostrar pedidos confirmados
            if confirmados:
                mensaje += "✅ **CONFIRMADOS:**\n"
                for pedido in confirmados:
                    mensaje += self._formatear_pedido(pedido)
                mensaje += "\n"

            # Mostrar pedidos en preparación
            if en_preparacion:
                mensaje += "🔄 **EN PREPARACIÓN:**\n"
                for pedido in en_preparacion:
                    mensaje += self._formatear_pedido(pedido)
                mensaje += "\n"

            # Mostrar pedidos listos
            if listos:
                mensaje += "🎉 **LISTOS PARA RECOGER:**\n"
                for pedido in listos:
                    mensaje += self._formatear_pedido(pedido)
                mensaje += "\n"

            mensaje += f"📊 Total: {len(pedidos)} pedidos"

            await update.message.reply_text(mensaje)

        finally:
            db.close()

    def _formatear_pedido(self, pedido: Pedido) -> str:
        """Formatea un pedido para mostrar"""
        texto = f"\n🔢 Pedido #{pedido.id}\n"
        texto += f"📦 {pedido.resumen_items}\n"
        texto += f"⚡ Prioridad: {pedido.prioridad.value.upper()}\n"

        if pedido.fecha_solicitada:
            fecha_legible = self.gemini.formatear_fecha_legible(
                pedido.fecha_solicitada.strftime("%Y-%m-%d")
            )
            if pedido.hora_solicitada:
                texto += f"📅 Para: {fecha_legible} a las {pedido.hora_solicitada}\n"
            else:
                texto += f"📅 Para: {fecha_legible}\n"
        elif pedido.hora_solicitada:
            texto += f"🕐 Hora: {pedido.hora_solicitada}\n"

        return texto

    async def procesar_mensaje(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handler principal para todos los mensajes de texto
        1. Guarda el mensaje en la BD
        2. Analiza con Gemini
        3. Si es pedido, lo guarda y confirma
        """
        user = update.effective_user
        texto = update.message.text

        print(f"\n📨 Mensaje recibido de {user.username} ({user.id}): {texto[:50]}...")

        db: Session = SessionLocal()
        try:
            # 1. Guardar mensaje en la base de datos
            log_mensaje = LogMensaje(
                telegram_user_id=user.id,
                telegram_username=user.username,
                mensaje_id=update.message.message_id,
                tipo_mensaje='text',
                contenido=texto
            )
            db.add(log_mensaje)
            db.commit()
            db.refresh(log_mensaje)

            # 2. Analizar con Gemini
            await update.message.reply_text("Analizando tu mensaje... 🤔")

            analisis = await self.gemini.analizar_mensaje(texto)

            if analisis is None:
                await update.message.reply_text(
                    "❌ Hubo un error al analizar tu mensaje. Por favor, intenta de nuevo."
                )
                return

            # 3. Verificar si es un pedido
            if analisis.get("es_pedido", False):
                # Actualizar log de mensaje
                log_mensaje.es_pedido = True
                db.commit()

                # Obtener lista de pedidos (puede haber múltiples)
                pedidos_list = analisis.get("pedidos", [])

                if not pedidos_list:
                    await update.message.reply_text(
                        "❌ No pude extraer los detalles del pedido. Por favor, intenta de nuevo."
                    )
                    return

                # Guardar cada pedido
                pedidos_ids = []
                for pedido_data in pedidos_list:
                    fecha_solicitada = None
                    if pedido_data.get("fecha_solicitada"):
                        from datetime import datetime
                        fecha_solicitada = datetime.strptime(
                            pedido_data["fecha_solicitada"],
                            "%Y-%m-%d"
                        )

                    pedido = Pedido(
                        telegram_user_id=user.id,
                        telegram_username=user.username,
                        mensaje_id=update.message.message_id,
                        prioridad=pedido_data.get("prioridad", "media"),
                        fecha_solicitada=fecha_solicitada,
                        hora_solicitada=pedido_data.get("hora_solicitada"),
                        resumen_items=pedido_data.get("resumen_items", "")
                    )
                    db.add(pedido)
                    db.commit()
                    db.refresh(pedido)
                    pedidos_ids.append((pedido.id, pedido_data))

                # Confirmar al usuario
                respuesta = await self._crear_respuesta_pedidos(pedidos_ids, False)
                keyboard = self._crear_teclado_confirmacion(pedidos_ids)
                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(respuesta, reply_markup=reply_markup)

            else:
                # No es un pedido, responder de forma casual
                await update.message.reply_text(
                    "Entendido. Si necesitas hacer un pedido, déjame saber qué necesitas. 😊"
                )

        finally:
            db.close()

    async def procesar_mensaje_voz(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handler para mensajes de voz
        1. Descarga el audio
        2. Transcribe con Gemini
        3. Analiza el texto transcrito
        4. Guarda como pedido si corresponde
        """
        user = update.effective_user
        voice = update.message.voice

        print(f"\n🎤 Mensaje de voz recibido de {user.username or user.first_name} ({user.id})")
        print(f"   Duración: {voice.duration}s, Tamaño: {voice.file_size} bytes")

        # 1. Descargar audio a memoria
        try:
            file = await voice.get_file()
            audio_bytes = await file.download_as_bytearray()
            print(f"📥 Audio descargado exitosamente")
        except Exception as e:
            print(f"❌ Error descargando audio: {e}")
            await update.message.reply_text(
                "❌ Error al descargar el mensaje de voz. Por favor, intenta nuevamente."
            )
            return

        # 2. Transcribir audio con Gemini
        await update.message.reply_text("🎤 Transcribiendo tu mensaje de voz...")

        transcripcion = await self.gemini.transcribir_audio(bytes(audio_bytes), voice.duration)

        if not transcripcion:
            await update.message.reply_text(
                "❌ No pude transcribir el mensaje de voz. Por favor, intenta enviar un mensaje de texto."
            )
            return

        db: Session = SessionLocal()
        try:
            # 3. Guardar mensaje en la base de datos con transcripción
            texto_completo = f"[Mensaje de voz - {voice.duration}s]: {transcripcion}"
            log_mensaje = LogMensaje(
                telegram_user_id=user.id,
                telegram_username=user.username or user.first_name,
                mensaje_id=update.message.message_id,
                tipo_mensaje='voice',
                contenido=texto_completo,
                transcripcion=transcripcion
            )
            db.add(log_mensaje)
            db.commit()
            db.refresh(log_mensaje)

            # 4. Analizar texto transcrito con Gemini
            print(f"🤖 Analizando transcripción con Gemini...")
            analisis = await self.gemini.analizar_mensaje(transcripcion)

            if not analisis:
                await update.message.reply_text(
                    f"🎤 Mensaje de voz transcrito:\n\n\"{transcripcion}\"\n\n"
                    "⚠️ No pude analizar el contenido. Se guardó como mensaje normal."
                )
                return

            # 5. Procesar resultado del análisis - verificar si es un pedido
            if analisis.get("es_pedido", False):
                # Actualizar log de mensaje
                log_mensaje.es_pedido = True
                db.commit()

                # Obtener lista de pedidos
                pedidos_list = analisis.get("pedidos", [])

                if not pedidos_list:
                    await update.message.reply_text(
                        f"🎤 Transcripción: \"{transcripcion}\"\n\n"
                        "❌ No pude extraer los detalles del pedido."
                    )
                    return

                # Guardar cada pedido
                pedidos_ids = []
                for pedido_data in pedidos_list:
                    fecha_solicitada = None
                    if pedido_data.get("fecha_solicitada"):
                        from datetime import datetime
                        fecha_solicitada = datetime.strptime(
                            pedido_data["fecha_solicitada"],
                            "%Y-%m-%d"
                        )

                    pedido = Pedido(
                        telegram_user_id=user.id,
                        telegram_username=user.username or user.first_name,
                        mensaje_id=update.message.message_id,
                        prioridad=pedido_data.get("prioridad", "media"),
                        fecha_solicitada=fecha_solicitada,
                        hora_solicitada=pedido_data.get("hora_solicitada"),
                        resumen_items=pedido_data.get("resumen_items", "")
                    )
                    db.add(pedido)
                    db.commit()
                    db.refresh(pedido)
                    pedidos_ids.append((pedido.id, pedido_data))

                # Confirmar al usuario
                respuesta = await self._crear_respuesta_pedidos(pedidos_ids, True, transcripcion)
                keyboard = self._crear_teclado_confirmacion(pedidos_ids)
                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(respuesta, reply_markup=reply_markup)
                print(f"✅ {len(pedidos_ids)} pedido(s) de voz guardado(s)")

            else:
                # No es un pedido, mensaje casual
                await update.message.reply_text(
                    f"🎤 Mensaje de voz recibido:\n\n\"{transcripcion}\"\n\n"
                    "💬 Entendido. Si necesitas hacer un pedido, déjame saber. 😊"
                )
                print(f"💬 Mensaje de voz casual procesado")

        finally:
            db.close()

    async def manejar_confirmacion(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handler para los botones de confirmación/cancelación de pedidos
        Soporta tanto pedidos individuales como confirmar/cancelar múltiples pedidos
        """
        query = update.callback_query

        try:
            await query.answer()  # Responder al callback para quitar el "loading"
        except Exception as e:
            # Si el callback expiró, continuar de todos modos
            print(f"⚠️ No se pudo responder al callback (probablemente expiró): {e}")
            return

        db: Session = SessionLocal()
        try:
            # Extraer acción y pedido_id(s) del callback_data
            callback_data = query.data
            parts = callback_data.split('_')

            # Verificar si es acción múltiple
            if parts[0] == "confirmar" and parts[1] == "todos":
                # Formato: confirmar_todos_1,2,3
                pedidos_ids_str = parts[2]
                pedidos_ids = [int(pid) for pid in pedidos_ids_str.split(',')]

                print(f"\n🔘 Botón presionado: confirmar todos ({len(pedidos_ids)} pedidos)")

                # Confirmar todos los pedidos
                for pedido_id in pedidos_ids:
                    self._cambiar_estado_pedido(db, pedido_id, EstadoPedidoEnum.CONFIRMADO)

                # Actualizar el mensaje eliminando los botones
                await query.edit_message_text(
                    text=query.message.text.replace(
                        "\n\n⚠️ Por favor, confirma o cancela todos los pedidos:",
                        f"\n\n✅ **TODOS LOS PEDIDOS CONFIRMADOS ({len(pedidos_ids)})**"
                    )
                )

                # Enviar mensaje de confirmación
                await query.message.reply_text(
                    f"✅ {len(pedidos_ids)} pedidos confirmados correctamente.\n"
                    f"IDs confirmados: {', '.join(f'#{pid}' for pid in pedidos_ids)}\n\n"
                    "Los pedidos están listos para ser procesados."
                )

            elif parts[0] == "cancelar" and parts[1] == "todos":
                # Formato: cancelar_todos_1,2,3
                pedidos_ids_str = parts[2]
                pedidos_ids = [int(pid) for pid in pedidos_ids_str.split(',')]

                print(f"\n🔘 Botón presionado: cancelar todos ({len(pedidos_ids)} pedidos)")

                # Cancelar todos los pedidos
                for pedido_id in pedidos_ids:
                    self._cambiar_estado_pedido(db, pedido_id, EstadoPedidoEnum.CANCELADO)

                # Actualizar el mensaje eliminando los botones
                await query.edit_message_text(
                    text=query.message.text.replace(
                        "\n\n⚠️ Por favor, confirma o cancela todos los pedidos:",
                        f"\n\n❌ **TODOS LOS PEDIDOS CANCELADOS ({len(pedidos_ids)})**"
                    )
                )

                # Enviar mensaje de cancelación
                await query.message.reply_text(
                    f"❌ {len(pedidos_ids)} pedidos cancelados.\n"
                    f"IDs cancelados: {', '.join(f'#{pid}' for pid in pedidos_ids)}\n\n"
                    "Los pedidos no serán procesados."
                )

            elif parts[0] == "confirmar":
                # Formato individual: confirmar_123
                pedido_id = int(parts[1])
                print(f"\n🔘 Botón presionado: confirmar para pedido {pedido_id}")

                # Cambiar estado a confirmado
                self._cambiar_estado_pedido(db, pedido_id, EstadoPedidoEnum.CONFIRMADO)

                # Actualizar el mensaje eliminando los botones
                await query.edit_message_text(
                    text=query.message.text.replace(
                        "\n\n⚠️ Por favor, confirma o cancela este pedido:",
                        "\n\n✅ **PEDIDO CONFIRMADO**"
                    )
                )

                # Enviar mensaje de confirmación
                await query.message.reply_text(
                    f"✅ Pedido #{pedido_id} confirmado correctamente.\n"
                    "El pedido está listo para ser procesado."
                )

            elif parts[0] == "cancelar":
                # Formato individual: cancelar_123
                pedido_id = int(parts[1])
                print(f"\n🔘 Botón presionado: cancelar para pedido {pedido_id}")

                # Cambiar estado a cancelado
                self._cambiar_estado_pedido(db, pedido_id, EstadoPedidoEnum.CANCELADO)

                # Actualizar el mensaje eliminando los botones
                await query.edit_message_text(
                    text=query.message.text.replace(
                        "\n\n⚠️ Por favor, confirma o cancela este pedido:",
                        "\n\n❌ **PEDIDO CANCELADO**"
                    )
                )

                # Enviar mensaje de cancelación
                await query.message.reply_text(
                    f"❌ Pedido #{pedido_id} cancelado.\n"
                    "El pedido no será procesado."
                )

        finally:
            db.close()

    def _cambiar_estado_pedido(self, db: Session, pedido_id: int, nuevo_estado: EstadoPedidoEnum):
        """Cambia el estado de un pedido y registra en historial"""
        from datetime import datetime

        pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
        if not pedido:
            return

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
            modificado_por="telegram_bot"
        )
        db.add(historial)
        db.commit()

    async def _crear_respuesta_pedidos(self, pedidos_ids: list, es_voz: bool, transcripcion: str = None) -> str:
        """Crea el texto de respuesta para pedidos guardados"""
        if len(pedidos_ids) > 1:
            respuesta = f"✅ ¡{len(pedidos_ids)} pedidos registrados"
            if es_voz:
                respuesta += " desde mensaje de voz"
            respuesta += " correctamente!\n\n"
        else:
            respuesta = "✅ ¡Pedido registrado"
            if es_voz:
                respuesta += " desde mensaje de voz"
            respuesta += " correctamente!\n\n"

        if es_voz and transcripcion:
            respuesta += f"📝 Transcripción: \"{transcripcion}\"\n\n"

        # Mostrar cada pedido
        for idx, (pedido_id, pedido_data) in enumerate(pedidos_ids, 1):
            if len(pedidos_ids) > 1:
                respuesta += f"**PEDIDO #{idx}:**\n"

            respuesta += f"📦 Resumen: {pedido_data.get('resumen_items')}\n"
            respuesta += f"⚡ Prioridad: {pedido_data.get('prioridad', 'media').upper()}\n"

            # Formatear fecha y hora
            fecha_solicitada = pedido_data.get('fecha_solicitada')
            hora_solicitada = pedido_data.get('hora_solicitada')

            if fecha_solicitada:
                fecha_legible = self.gemini.formatear_fecha_legible(fecha_solicitada)
                if hora_solicitada:
                    respuesta += f"📅 Para: {fecha_legible} a las {hora_solicitada}\n"
                else:
                    respuesta += f"📅 Para: {fecha_legible}\n"
            elif hora_solicitada:
                respuesta += f"🕐 Hora: {hora_solicitada}\n"

            respuesta += f"🔢 ID del pedido: {pedido_id}\n"

            if len(pedidos_ids) > 1 and idx < len(pedidos_ids):
                respuesta += "\n"

        # Agregar texto de confirmación
        if len(pedidos_ids) > 1:
            respuesta += "\n⚠️ Por favor, confirma o cancela todos los pedidos:"
        else:
            respuesta += "\n⚠️ Por favor, confirma o cancela este pedido:"

        return respuesta

    def _crear_teclado_confirmacion(self, pedidos_ids: list) -> list:
        """Crea el teclado inline para confirmación"""
        if len(pedidos_ids) > 1:
            # Múltiples pedidos: botón único para confirmar/cancelar todos
            pedidos_ids_str = ','.join(str(pid) for pid, _ in pedidos_ids)
            keyboard = [[
                InlineKeyboardButton(
                    f"✅ Confirmar Todos ({len(pedidos_ids)})",
                    callback_data=f"confirmar_todos_{pedidos_ids_str}"
                ),
                InlineKeyboardButton(
                    f"❌ Cancelar Todos ({len(pedidos_ids)})",
                    callback_data=f"cancelar_todos_{pedidos_ids_str}"
                )
            ]]
        else:
            # Un solo pedido: botón individual
            pedido_id = pedidos_ids[0][0]
            keyboard = [[
                InlineKeyboardButton(
                    "✅ Confirmar Pedido",
                    callback_data=f"confirmar_{pedido_id}"
                ),
                InlineKeyboardButton(
                    "❌ Cancelar Pedido",
                    callback_data=f"cancelar_{pedido_id}"
                )
            ]]

        return keyboard
