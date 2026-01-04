"""
Servicio de integración con Google Gemini AI para análisis de mensajes
y transcripción de audio
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional

from google import genai
from google.genai import types


class GeminiService:
    """Servicio para interactuar con Gemini AI"""

    def __init__(self, api_key: str):
        """
        Inicializa el cliente de Gemini

        Args:
            api_key: API key de Google AI Studio
        """
        self.client = genai.Client(api_key=api_key)
        self.model = 'gemini-2.5-flash'

    def _crear_prompt_sistema(self) -> str:
        """
        Crea el prompt del sistema para instruir a Gemini
        sobre cómo analizar los mensajes
        """
        hoy = datetime.now()
        manana = hoy + timedelta(days=1)
        pasado_manana = hoy + timedelta(days=2)
        fecha_hoy = hoy.strftime("%Y-%m-%d")
        fecha_manana = manana.strftime("%Y-%m-%d")
        fecha_pasado_manana = pasado_manana.strftime("%Y-%m-%d")

        return f"""Eres un asistente especializado en analizar mensajes para identificar pedidos y detectar intenciones del usuario.

FECHA Y HORA ACTUAL: {hoy.strftime("%Y-%m-%d %H:%M")}
- HOY es: {fecha_hoy}
- MAÑANA es: {fecha_manana}
- PASADO MAÑANA es: {fecha_pasado_manana}

Tu tarea es determinar si un mensaje:
1. Contiene UNO O MÚLTIPLES PEDIDOS
2. Es CONVERSACIÓN CASUAL

Un PEDIDO incluye:
- Solicitud explícita de productos o servicios
- Cantidades específicas
- Posiblemente fechas u horarios
- Indicación de necesidad de algo

Una CONVERSACIÓN CASUAL incluye:
- Saludos
- Preguntas generales
- Comentarios sin solicitud específica
- Agradecimientos

IMPORTANTE: Un mensaje puede contener MÚLTIPLES PEDIDOS si menciona diferentes fechas/horas o conjuntos de items.
Ejemplo: "Quiero una pizza para mañana y dos hamburguesas para hoy a la noche" = 2 pedidos distintos

Debes responder ÚNICAMENTE con un JSON válido con la siguiente estructura:
{{
    "es_pedido": true/false,
    "pedidos": [
        {{
            "prioridad": "alta/media/baja",
            "fecha_solicitada": "YYYY-MM-DD o null",
            "hora_solicitada": "HH:MM o null",
            "resumen_items": "breve descripción de los items solicitados"
        }}
    ]
}}

Si es_pedido es false, el array "pedidos" debe estar vacío []
Si hay múltiples pedidos, incluye cada uno en el array "pedidos"

REGLAS IMPORTANTES PARA FECHAS Y HORAS:

1. FECHAS:
   - "hoy" o sin fecha especificada → usar {fecha_hoy}
   - "mañana" → usar {fecha_manana}
   - "pasado mañana" → usar {fecha_pasado_manana}
   - Fechas específicas convertirlas al formato YYYY-MM-DD
   - Si NO se menciona fecha → usar {fecha_hoy} (asumir que es para hoy)

2. HORAS:
   - Usar formato 24 horas (HH:MM)
   - "12 AM" o "12 de la mañana" = 00:00 (medianoche)
   - "12 PM" o "12 del mediodía" o "12 del día" = 12:00 (mediodía)
   - "12" sin especificar AM/PM → asumir 12:00 (mediodía)
   - "8" sin especificar AM/PM → si es < 7, asumir PM (20:00), si es >= 7, usar contexto
   - Si NO se menciona hora → usar null

3. CONTEXTO ESPAÑOL:
   - "a las 12" generalmente significa mediodía (12:00)
   - "al mediodía" = 12:00
   - "en la mañana" = entre 06:00-11:59
   - "en la tarde" = entre 12:00-19:59
   - "en la noche" = entre 20:00-23:59

Criterios de prioridad:
- ALTA: Menciona urgencia, "lo antes posible", "hoy", "urgente", "ya"
- MEDIA: Menciona fecha específica cercana (mañana, esta semana)
- BAJA: Sin urgencia aparente o fecha lejana

Si NO es un pedido, igual responde el JSON con es_pedido: false y los demás campos en null o vacíos.

IMPORTANTE: Responde SOLO con el JSON, sin texto adicional."""

    async def analizar_mensaje(self, texto: str) -> Optional[dict]:
        """
        Envía el mensaje a Gemini y obtiene el análisis

        Args:
            texto: Texto del mensaje a analizar

        Returns:
            Diccionario con el análisis o None si hay error
            {
                "es_pedido": bool,
                "pedidos": [
                    {
                        "prioridad": "alta/media/baja",
                        "fecha_solicitada": "YYYY-MM-DD",
                        "hora_solicitada": "HH:MM",
                        "resumen_items": str
                    }
                ]
            }
        """
        try:
            # Crear el prompt completo
            prompt_completo = f"{self._crear_prompt_sistema()}\n\nMensaje a analizar:\n{texto}"

            # Generar respuesta con Gemini
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt_completo
            )

            # Extraer el texto de la respuesta
            respuesta_texto = response.text.strip()

            # Limpiar markdown si existe
            if respuesta_texto.startswith("```json"):
                respuesta_texto = respuesta_texto.replace("```json", "").replace("```", "").strip()
            elif respuesta_texto.startswith("```"):
                respuesta_texto = respuesta_texto.replace("```", "").strip()

            resultado = json.loads(respuesta_texto)

            print(f"🤖 Gemini analizó: es_pedido={resultado.get('es_pedido')}")
            return resultado

        except json.JSONDecodeError as e:
            print(f"❌ Error al parsear JSON de Gemini: {e}")
            print(f"Respuesta recibida: {respuesta_texto}")
            return None
        except Exception as e:
            print(f"❌ Error al llamar a Gemini: {e}")
            return None

    async def transcribir_audio(self, audio_bytes: bytes, duracion: int = 0) -> Optional[str]:
        """
        Transcribe audio bytes a texto usando Gemini

        Args:
            audio_bytes: Datos de audio en formato OGG
            duracion: Duración en segundos (para logging)

        Returns:
            Texto transcrito o None si hay error
        """
        try:
            print(f"🎤 Transcribiendo audio ({duracion}s, {len(audio_bytes)} bytes)...")

            # Crear parte de audio para Gemini
            audio_part = types.Part.from_bytes(
                data=audio_bytes,
                mime_type='audio/ogg'
            )

            # Crear prompt de transcripción
            prompt = """Transcribe este mensaje de voz a texto en español.
Responde ÚNICAMENTE con el texto transcrito, sin agregar comentarios ni formato adicional."""

            # Generar transcripción
            response = self.client.models.generate_content(
                model=self.model,
                contents=[prompt, audio_part]
            )

            transcripcion = response.text.strip()
            print(f"✅ Audio transcrito: {transcripcion[:100]}...")

            return transcripcion

        except Exception as e:
            print(f"❌ Error al transcribir audio: {e}")
            return None

    @staticmethod
    def formatear_fecha_legible(fecha_str: str) -> str:
        """
        Convierte una fecha YYYY-MM-DD a formato legible en español

        Args:
            fecha_str: Fecha en formato YYYY-MM-DD

        Returns:
            Fecha en formato legible (ej: "hoy", "mañana", "26/12/2025")
        """
        if not fecha_str:
            return ""

        try:
            fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            hoy = datetime.now().date()
            manana = hoy + timedelta(days=1)
            pasado_manana = hoy + timedelta(days=2)

            if fecha == hoy:
                return "hoy"
            elif fecha == manana:
                return "mañana"
            elif fecha == pasado_manana:
                return "pasado mañana"
            else:
                # Formato: día/mes/año
                return fecha.strftime("%d/%m/%Y")
        except:
            return fecha_str
