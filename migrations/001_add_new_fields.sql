-- Migración 001: Agregar nuevos campos a tablas existentes
-- Fecha: 2026-01-05
-- Versión: 3.0.0

-- ===== TABLA USERS =====
-- Agregar campos de verificación de email
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_email_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verification_token VARCHAR;

-- Agregar campos de notificaciones push
ALTER TABLE users ADD COLUMN IF NOT EXISTS fcm_token VARCHAR;
ALTER TABLE users ADD COLUMN IF NOT EXISTS apns_token VARCHAR;

-- ===== CREAR TABLAS NUEVAS =====

-- Tabla de refresh tokens
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token ON refresh_tokens(token);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id);

-- Tabla de imágenes de pedidos
CREATE TABLE IF NOT EXISTS imagenes_pedidos (
    id SERIAL PRIMARY KEY,
    pedido_id INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
    url VARCHAR NOT NULL,
    filename VARCHAR NOT NULL,
    size_bytes INTEGER,
    mime_type VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_imagenes_pedidos_pedido_id ON imagenes_pedidos(pedido_id);

-- Tabla de comentarios en pedidos
CREATE TABLE IF NOT EXISTS comentarios_pedidos (
    id SERIAL PRIMARY KEY,
    pedido_id INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    comentario TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_comentarios_pedidos_pedido_id ON comentarios_pedidos(pedido_id);
CREATE INDEX IF NOT EXISTS idx_comentarios_pedidos_user_id ON comentarios_pedidos(user_id);

-- Tabla de filtros guardados
CREATE TABLE IF NOT EXISTS filtros_guardados (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    nombre VARCHAR NOT NULL,
    filtros_json TEXT NOT NULL,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_filtros_guardados_usuario_id ON filtros_guardados(usuario_id);

-- Verificar que todo se creó correctamente
DO $$
BEGIN
    RAISE NOTICE '✅ Migración 001 completada exitosamente';
    RAISE NOTICE '   - Campos agregados a users: is_email_verified, email_verification_token, fcm_token, apns_token';
    RAISE NOTICE '   - Tablas creadas: refresh_tokens, imagenes_pedidos, comentarios_pedidos, filtros_guardados';
END $$;
