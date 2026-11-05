from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database.session import get_db
from app.models import User
from app.schemas.auth import AuthData, LoginRequest, RegisterRequest, UserPublic
from app.schemas.common import APIResponse
from app.services.auth_service import authenticate_user, register_user

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=APIResponse[AuthData], status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    data = register_user(payload, db)
    return {"success": True, "message": "Account created", "data": data}


@router.post("/login", response_model=APIResponse[AuthData])
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    data = authenticate_user(payload, db)
    return {"success": True, "message": "Signed in", "data": data}


@router.get("/me", response_model=APIResponse[UserPublic])
def me(user: User = Depends(get_current_user)):
    return {"success": True, "message": "Current user", "data": UserPublic(id=user.id, email=user.email, name=user.name)}

