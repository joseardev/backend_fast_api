import os
import asyncio
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database.database import engine, Base, get_db
from pydantic import BaseModel
from app.routers import auth, users, telegram

# Create the database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FastAPI Backend con Autenticación",
    version="2.0.2",
    description="API con sistema de autenticación JWT"
)

# Incluir routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(telegram.router)

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

    # Configurar e iniciar bot de Telegram si las variables están configuradas
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    chat_id_resumenes = os.getenv("TELEGRAM_CHAT_ID_RESUMENES")

    if telegram_token and gemini_api_key:
        print("📱 Configurando bot de Telegram...")
        try:
            # Importar módulos del bot
            from app.telegram.bot import start_bot
            from app.telegram.scheduler import start_scheduler

            # Iniciar bot en background
            asyncio.create_task(start_bot(telegram_token, gemini_api_key))

            # Iniciar scheduler de tareas programadas
            start_scheduler(telegram_token, chat_id_resumenes)

            print("✅ Bot de Telegram y scheduler iniciados correctamente")
        except Exception as e:
            print(f"❌ Error al iniciar bot de Telegram: {e}")
    else:
        print("⚠️ Bot de Telegram no configurado (faltan variables TELEGRAM_TOKEN o GEMINI_API_KEY)")

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
