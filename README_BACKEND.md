# Backend FastAPI - Configuración Actualizada

## Cambios Realizados

Se han agregado los siguientes componentes al backend para que funcione con el frontend React:

### 1. CORS Middleware

Se configuró CORS para permitir peticiones desde:
- Firebase Hosting: `https://pruebas-19cc6.web.app`
- Firebase Hosting alternativa: `https://pruebas-19cc6.firebaseapp.com`
- Desarrollo local: `http://localhost:3000`

### 2. Nuevos Endpoints

#### GET /api/ejemplo
Devuelve datos de ejemplo para el frontend.

**Respuesta:**
```json
{
  "mensaje": "Datos desde el backend FastAPI",
  "data": [
    {"id": 1, "nombre": "Item 1"},
    {"id": 2, "nombre": "Item 2"},
    {"id": 3, "nombre": "Item 3"}
  ],
  "timestamp": "2024-12-31"
}
```

#### POST /api/ejemplo
Recibe datos desde el frontend.

**Request Body:**
```json
{
  "nombre": "Usuario",
  "mensaje": "Hola desde React"
}
```

**Respuesta:**
```json
{
  "status": "success",
  "mensaje": "Datos recibidos correctamente de Usuario",
  "recibido": {
    "nombre": "Usuario",
    "mensaje": "Hola desde React"
  },
  "respuesta_backend": "Los datos fueron procesados exitosamente"
}
```

## Cómo Ejecutar

### Localmente

```bash
# Activar entorno virtual
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Mac/Linux

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar servidor
python main.py
```

El servidor estará disponible en: `http://localhost:8000`

### En Google Cloud

```bash
# Conectarse al servidor
gcloud compute ssh fastapi-server --zone=us-central1-a

# Activar entorno virtual
source venv/bin/activate

# Ejecutar con uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000

# O ejecutar en background con nohup
nohup uvicorn main:app --host 0.0.0.0 --port 8000 &
```

## Endpoints Disponibles

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/` | Mensaje de bienvenida |
| GET | `/health` | Health check + verificación de DB |
| GET | `/api/ejemplo` | Obtener datos de ejemplo |
| POST | `/api/ejemplo` | Enviar datos al backend |

## Documentación Interactiva

Una vez que el servidor esté corriendo, puedes acceder a:

- **Swagger UI**: http://34.57.113.255:8000/docs
- **ReDoc**: http://34.57.113.255:8000/redoc

## Probar los Endpoints

### Con curl

```bash
# GET - Obtener datos
curl http://34.57.113.255:8000/api/ejemplo

# POST - Enviar datos
curl -X POST http://34.57.113.255:8000/api/ejemplo \
  -H "Content-Type: application/json" \
  -d '{"nombre": "Test", "mensaje": "Hola desde curl"}'

# Health check
curl http://34.57.113.255:8000/health
```

### Con el Frontend React

El frontend en Firebase (`https://pruebas-19cc6.web.app`) ya está configurado para llamar a estos endpoints automáticamente.

## Seguridad - CORS en Producción

Actualmente CORS está configurado con `"*"` (permitir todos los orígenes).

**Para producción**, se recomienda cambiar esto en `main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://pruebas-19cc6.web.app",
        "https://pruebas-19cc6.firebaseapp.com",
    ],  # Remover el "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Troubleshooting

### El frontend no puede conectarse

1. Verifica que el servidor esté corriendo:
   ```bash
   curl http://34.57.113.255:8000/health
   ```

2. Verifica que el firewall permita el puerto 8000:
   ```bash
   gcloud compute firewall-rules list
   ```

3. Revisa los logs del servidor:
   ```bash
   journalctl -u fastapi -f
   ```

### Error de CORS

Si ves errores de CORS en la consola del navegador:

1. Verifica que el middleware CORS esté configurado en `main.py`
2. Reinicia el servidor después de hacer cambios
3. Limpia la caché del navegador

## Próximos Pasos

- [ ] Agregar autenticación (JWT)
- [ ] Conectar endpoints con la base de datos
- [ ] Agregar validación de datos más robusta
- [ ] Implementar rate limiting
- [ ] Configurar HTTPS con certificado SSL
- [ ] Agregar logging estructurado
- [ ] Configurar variables de entorno (.env)

## Información del Servidor

- **IP Pública**: 34.57.113.255
- **Puerto**: 8000
- **Zona**: us-central1-a
- **Nombre**: fastapi-server
