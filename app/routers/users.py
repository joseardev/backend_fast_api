from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database.database import get_db
from app.models.models import User
from app.schemas.user import UserResponse, UserUpdate, PasswordChange, PushTokenRegister, UserAdminUpdate, AdminPasswordChange
from app.auth.jwt import get_current_active_user
from app.auth.password import hash_password, verify_password

router = APIRouter(prefix="/api/users", tags=["Users"])

# Dependency para verificar si el usuario es admin
def require_admin(current_user: User = Depends(get_current_active_user)):
    """Verificar que el usuario actual sea administrador"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para realizar esta acción"
        )
    return current_user

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


# ===== ENDPOINTS DE ADMINISTRACIÓN =====

@router.get("/", response_model=List[UserResponse])
async def get_all_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Obtener lista de todos los usuarios (solo admins)"""
    users = db.query(User).all()
    return users


@router.put("/{user_id}", response_model=UserResponse)
async def update_user_by_admin(
    user_id: int,
    user_update: UserAdminUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Actualizar usuario por ID (solo admins)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    # Actualizar campos si se proporcionan
    if user_update.email is not None:
        # Verificar si el nuevo email ya existe
        existing_user = db.query(User).filter(
            User.email == user_update.email,
            User.id != user_id
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está en uso"
            )
        user.email = user_update.email

    if user_update.full_name is not None:
        user.full_name = user_update.full_name

    if user_update.role is not None:
        user.role = user_update.role

    if user_update.is_active is not None:
        user.is_active = user_update.is_active

    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def partial_update_user(
    user_id: int,
    user_update: UserAdminUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Actualización parcial de usuario (solo admins)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    # Solo actualizar campos proporcionados
    update_data = user_update.dict(exclude_unset=True)

    if "email" in update_data:
        existing_user = db.query(User).filter(
            User.email == update_data["email"],
            User.id != user_id
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El email ya está en uso"
            )

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}/password")
async def change_user_password_by_admin(
    user_id: int,
    password_data: AdminPasswordChange,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Cambiar contraseña de cualquier usuario (solo admins)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    # Actualizar la contraseña
    user.hashed_password = hash_password(password_data.new_password)
    db.commit()

    return {"message": "Contraseña actualizada exitosamente"}


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Eliminar usuario por ID (solo admins)"""
    # No permitir que el admin se elimine a sí mismo
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes eliminar tu propia cuenta"
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    db.delete(user)
    db.commit()

    return {"message": "Usuario eliminado exitosamente"}
