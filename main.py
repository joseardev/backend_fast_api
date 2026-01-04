import os
import asyncio
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database.database import engine, Base, get_db
from pydantic import BaseModel

# Importar routers básicos
from app.routers import auth, users

# NO importar router de telegram aquí - se hará en startup
telegram_router_available = False

app = FastAPI(
    title="FastAPI Backend con Autenticación",
    version="2.0.4",
    description="API con sistema de autenticación JWT"
)

# Incluir routers básicos SIEMPRE
app.include_router(auth.router)
app.include_router(users.router)
print("✅ Routers básicos incluidos")

# Configurar CORS para permitir peticiones desde Firebase
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://pruebas-19cc6.web.app",
        "https://pruebas-19cc6.firebaseapp.com",
        "http://localhost:3000",  # Para desarrollo local
        "*"  # Permitir todos los orígenes temporalmente
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Schema para recibir datos en POST
class DataInput(BaseModel):
    nombre: str
    mensaje: str

@app.get("/")
def read_root():
    return {"message": "Hello World"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        # Try a simple query to verify DB connection
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": "disconnected", "detail": str(e)}

# Endpoints para el frontend React
@app.get("/api/ejemplo")
def get_ejemplo():
    """Endpoint GET para obtener datos de ejemplo"""
    return {
        "mensaje": "Datos desde el backend FastAPI",
        "data": [
            {"id": 1, "nombre": "Item 1"},
            {"id": 2, "nombre": "Item 2"},
            {"id": 3, "nombre": "Item 3"}
        ],
        "timestamp": "2024-12-31"
    }

@app.post("/api/ejemplo")
def post_ejemplo(data: DataInput):
    """Endpoint POST para recibir datos desde el frontend"""
    return {
        "status": "success",
        "mensaje": f"Datos recibidos correctamente de {data.nombre}",
        "recibido": {
            "nombre": data.nombre,
            "mensaje": data.mensaje
        },
        "respuesta_backend": "Los datos fueron procesados exitosamente"
    }

@app.on_event("startup")
async def startup_event():
    """Evento de inicio de la aplicación"""
    print("🚀 Iniciando aplicación FastAPI...")

    # Paso 1: Crear tablas básicas de autenticación
    try:
        print("🗄️ Creando tablas básicas de autenticación...")
        # Solo crear tablas de User primero
        from app.models.models import User
        User.__table__.create(bind=engine, checkfirst=True)
        print("✅ Tabla de usuarios verificada/creada")
    except Exception as e:
        print(f"⚠️ Info al crear tabla User (puede ya existir): {e}")

    # Paso 2: Intentar cargar módulos de Telegram y crear sus tablas
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    chat_id_resumenes = os.getenv("TELEGRAM_CHAT_ID_RESUMENES")

    if telegram_token and gemini_api_key:
        print("📱 Configurando funcionalidad de Telegram...")
        try:
            # Importar router de telegram
            from app.routers import telegram as telegram_router
            app.include_router(telegram_router.router)
            print("✅ Router de Telegram incluido dinámicamente")

            # Crear tablas de Telegram
            from app.models.models import LogMensaje, Pedido, HistorialEstado, NotificacionEnviada
            try:
                print("🗄️ Creando tablas de Telegram...")
                LogMensaje.__table__.create(bind=engine, checkfirst=True)
                Pedido.__table__.create(bind=engine, checkfirst=True)
                HistorialEstado.__table__.create(bind=engine, checkfirst=True)
                NotificacionEnviada.__table__.create(bind=engine, checkfirst=True)
                print("✅ Tablas de Telegram verificadas/creadas")
            except Exception as table_error:
                print(f"⚠️ Error al crear tablas de Telegram (pueden ya existir): {table_error}")

            # Importar módulos del bot
            from app.telegram.bot import start_bot
            from app.telegram.scheduler import start_scheduler

            # Iniciar bot en background
            try:
                asyncio.create_task(start_bot(telegram_token, gemini_api_key))
                print("✅ Bot de Telegram iniciado en background")
            except Exception as bot_error:
                print(f"⚠️ Error al iniciar bot: {bot_error}")

            # Iniciar scheduler
            try:
                start_scheduler(telegram_token, chat_id_resumenes)
                print("✅ Scheduler iniciado correctamente")
            except Exception as scheduler_error:
                print(f"⚠️ Error al iniciar scheduler: {scheduler_error}")

        except Exception as e:
            print(f"⚠️ Funcionalidad de Telegram no disponible: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("⚠️ Bot de Telegram no configurado (variables TELEGRAM_TOKEN/GEMINI_API_KEY no definidas)")

    print("✅ Aplicación FastAPI iniciada correctamente")


@app.on_event("shutdown")
async def shutdown_event():
    """Evento de cierre de la aplicación"""
    print("🛑 Deteniendo aplicación FastAPI...")

    # Detener bot de Telegram si está en ejecución
    try:
        from app.telegram.bot import get_bot, stop_bot
        from app.telegram.scheduler import stop_scheduler

        bot = get_bot()
        if bot:
            print("📱 Deteniendo bot de Telegram...")
            await stop_bot()

        # Detener scheduler
        stop_scheduler()

        print("✅ Bot de Telegram y scheduler detenidos")
    except Exception as e:
        print(f"⚠️ Error al detener bot de Telegram: {e}")

    print("✅ Aplicación FastAPI detenida correctamente")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
