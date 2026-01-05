from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.models.models import User
from app.schemas.user import UserResponse, UserUpdate, PasswordChange, PushTokenRegister
from app.auth.jwt import get_current_active_user
from app.auth.password import hash_password, verify_password

router = APIRouter(prefix="/api/users", tags=["Users"])

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """Obtener el perfil del usuario actual"""
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Actualizar el perfil del usuario actual"""
    # Actualizar campos si se proporcionan
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name

    if user_update.email is not None:
        # Verificar si el nuevo email ya existe
        existing_user = db.query(User).filter(
            User.email == user_update.email,
            User.id != current_user.id
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está en uso"
            )
        current_user.email = user_update.email

    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/me/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Cambiar la contraseña del usuario actual"""
    # Verificar la contraseña actual
    if not verify_password(password_data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contraseña actual incorrecta"
        )

    # Actualizar la contraseña
    current_user.hashed_password = hash_password(password_data.new_password)
    db.commit()

    return {"message": "Contraseña actualizada exitosamente"}

@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Obtener usuario por ID"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    return user


@router.post("/me/register-push-token")
async def register_push_token(
    token_data: PushTokenRegister,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Registrar token de notificaciones push (FCM para Android/iOS o APNS para iOS)
    """
    if token_data.fcm_token:
        current_user.fcm_token = token_data.fcm_token

    if token_data.apns_token:
        current_user.apns_token = token_data.apns_token

    db.commit()

    return {
        "message": "Token de notificaciones push registrado exitosamente",
        "fcm_registered": token_data.fcm_token is not None,
        "apns_registered": token_data.apns_token is not None
    }


@router.delete("/me/push-token")
async def unregister_push_token(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Eliminar tokens de notificaciones push (al cerrar sesión)
    """
    current_user.fcm_token = None
    current_user.apns_token = None
    db.commit()

    return {"message": "Tokens de notificaciones eliminados exitosamente"}
