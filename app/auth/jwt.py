from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.models.models import User, RefreshToken
import os
import secrets

# Configuración JWT
SECRET_KEY = os.getenv("SECRET_KEY", "tu-clave-secreta-super-segura-cambiala-en-produccion")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # 15 minutos (más seguro)
REFRESH_TOKEN_EXPIRE_DAYS = 7  # 7 días

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Crea un token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[str]:
    """Verifica y decodifica un token JWT"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        return email
    except JWTError:
        return None

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Obtiene el usuario actual desde el token JWT"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudo validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )

    email = verify_token(token)
    if email is None:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception

    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Verifica que el usuario esté activo"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Usuario inactivo")
    return current_user


def create_refresh_token(user_id: int, db: Session) -> str:
    """Crea un refresh token y lo guarda en la base de datos"""
    # Generar token aleatorio seguro
    token = secrets.token_urlsafe(32)

    # Calcular fecha de expiración
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    # Crear registro en base de datos
    refresh_token = RefreshToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at
    )

    db.add(refresh_token)
    db.commit()

    return token


def verify_refresh_token(token: str, db: Session) -> Optional[User]:
    """Verifica un refresh token y retorna el usuario asociado"""
    # Buscar el token en la base de datos
    refresh_token = db.query(RefreshToken).filter(
        RefreshToken.token == token,
        RefreshToken.is_revoked == False
    ).first()

    if not refresh_token:
        return None

    # Verificar si el token ha expirado
    if refresh_token.expires_at < datetime.utcnow():
        return None

    # Obtener el usuario
    user = db.query(User).filter(User.id == refresh_token.user_id).first()
    return user


def revoke_refresh_token(token: str, db: Session) -> bool:
    """Revoca un refresh token"""
    refresh_token = db.query(RefreshToken).filter(RefreshToken.token == token).first()

    if not refresh_token:
        return False

    refresh_token.is_revoked = True
    db.commit()
    return True


def revoke_all_user_tokens(user_id: int, db: Session) -> int:
    """Revoca todos los refresh tokens de un usuario"""
    updated_count = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.is_revoked == False
    ).update({"is_revoked": True})

    db.commit()
    return updated_count


def cleanup_expired_tokens(db: Session) -> int:
    """Elimina tokens expirados de la base de datos"""
    deleted_count = db.query(RefreshToken).filter(
        RefreshToken.expires_at < datetime.utcnow()
    ).delete()

    db.commit()
    return deleted_count
