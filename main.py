from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database.database import engine, Base, get_db
from pydantic import BaseModel
from app.routers import auth, users

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
