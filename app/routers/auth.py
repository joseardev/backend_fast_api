from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.models.models import User
from app.schemas.user import UserCreate, UserLogin, Token, UserResponse, RefreshTokenRequest
from app.auth.password import hash_password, verify_password
from app.auth.jwt import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    revoke_refresh_token,
    revoke_all_user_tokens,
    get_current_active_user
)
from datetime import timedelta
import secrets

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Registrar un nuevo usuario"""
    # Verificar si el email ya existe
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )

    # Crear nuevo usuario
    hashed_password = hash_password(user_data.password)

    # Generar token de verificación de email
    email_verification_token = secrets.token_urlsafe(32)

    new_user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        email_verification_token=email_verification_token
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Crear tokens
    access_token = create_access_token(data={"sub": new_user.email})
    refresh_token = create_refresh_token(new_user.id, db)

    # TODO: Enviar email de verificación con el token
    # send_verification_email(new_user.email, email_verification_token)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": new_user
    }

@router.post("/login", response_model=Token)
def login(user_credentials: UserLogin, db: Session = Depends(get_db)):
    """Iniciar sesión"""
    # Buscar usuario por email
    user = db.query(User).filter(User.email == user_credentials.email).first()

    # Verificar si el usuario existe
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )

    # Verificar la contraseña
    if not verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )

    # Verificar si el usuario está activo
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo"
        )

    # Crear tokens
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(user.id, db)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user
    }

# Endpoint compatible con OAuth2PasswordRequestForm (para Swagger UI)
@router.post("/token", response_model=Token)
def login_oauth2(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login usando OAuth2PasswordRequestForm (para Swagger UI)"""
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo"
        )

    # Crear tokens
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(user.id, db)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user
    }


@router.post("/refresh", response_model=Token)
def refresh_access_token(
    refresh_request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """Obtener un nuevo access token usando un refresh token"""
    # Verificar el refresh token
    user = verify_refresh_token(refresh_request.refresh_token, db)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido o expirado"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo"
        )

    # Crear nuevo access token
    access_token = create_access_token(data={"sub": user.email})

    # Opcionalmente rotar el refresh token (más seguro)
    # Revocar el anterior
    revoke_refresh_token(refresh_request.refresh_token, db)

    # Crear uno nuevo
    new_refresh_token = create_refresh_token(user.id, db)

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "user": user
    }


@router.post("/logout")
def logout(
    refresh_request: RefreshTokenRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Cerrar sesión (revocar refresh token)"""
    success = revoke_refresh_token(refresh_request.refresh_token, db)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token no encontrado"
        )

    return {"message": "Sesión cerrada exitosamente"}


@router.post("/logout-all")
def logout_all(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Cerrar todas las sesiones del usuario (revocar todos los refresh tokens)"""
    count = revoke_all_user_tokens(current_user.id, db)

    return {
        "message": f"Se cerraron {count} sesiones exitosamente"
    }


@router.post("/verify-email/{token}")
def verify_email(token: str, db: Session = Depends(get_db)):
    """Verificar email usando el token enviado por correo"""
    user = db.query(User).filter(User.email_verification_token == token).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token de verificación inválido"
        )

    # Marcar email como verificado
    user.is_email_verified = True
    user.email_verification_token = None
    db.commit()

    return {"message": "Email verificado exitosamente"}


@router.post("/resend-verification")
def resend_verification_email(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Reenviar email de verificación"""
    if current_user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está verificado"
        )

    # Generar nuevo token
    email_verification_token = secrets.token_urlsafe(32)
    current_user.email_verification_token = email_verification_token
    db.commit()

    # TODO: Enviar email de verificación
    # send_verification_email(current_user.email, email_verification_token)

    return {"message": "Email de verificación enviado"}
