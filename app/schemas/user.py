from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from app.models.models import UserRole

# Schema para crear usuario (registro)
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

# Schema para login
class UserLogin(BaseModel):
    email: EmailStr
    password: str

# Schema para respuesta de usuario (sin password)
class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    role: UserRole
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Schema para el token JWT
class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

# Schema para actualizar perfil
class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None

# Schema para cambiar contraseña
class PasswordChange(BaseModel):
    old_password: str
    new_password: str