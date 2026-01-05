from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime

# Schema para crear usuario (registro)
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) > 72:
            raise ValueError('La contraseña no puede tener más de 72 caracteres')
        if len(v) < 6:
            raise ValueError('La contraseña debe tener al menos 6 caracteres')
        return v

# Schema para login
class UserLogin(BaseModel):
    email: EmailStr
    password: str

# Schema para respuesta de usuario (sin password)
class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    role: str  # Cambiado de UserRole a str para coincidir con el modelo
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Schema para el token JWT
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: UserResponse

# Schema para refresh token request
class RefreshTokenRequest(BaseModel):
    refresh_token: str

# Schema para actualizar perfil
class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None

# Schema para cambiar contraseña
class PasswordChange(BaseModel):
    old_password: str
    new_password: str

# Schema para registrar token de notificaciones push
class PushTokenRegister(BaseModel):
    fcm_token: Optional[str] = None
    apns_token: Optional[str] = None


# ===== SCHEMAS PARA ADMINISTRACIÓN =====

# Schema para actualización de usuario por admin
class UserAdminUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[str] = None  # user, staff, admin
    is_active: Optional[bool] = None

    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        if v is not None and v not in ['user', 'staff', 'admin']:
            raise ValueError('El rol debe ser: user, staff o admin')
        return v


# Schema para cambio de contraseña por admin
class AdminPasswordChange(BaseModel):
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v):
        if len(v) > 72:
            raise ValueError('La contraseña no puede tener más de 72 caracteres')
        if len(v) < 6:
            raise ValueError('La contraseña debe tener al menos 6 caracteres')
        return v