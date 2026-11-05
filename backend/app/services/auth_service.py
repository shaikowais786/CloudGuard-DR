from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User, Workspace
from app.schemas.auth import AuthData, LoginRequest, RegisterRequest, UserPublic, WorkspacePublic


def _auth_data(db: Session, user: User) -> AuthData:
    workspace = db.scalar(select(Workspace).where(Workspace.owner_user_id == user.id)
                          .order_by(Workspace.created_at).limit(1))
    return AuthData(
        access_token=create_access_token(str(user.id)),
        expires_in=settings.jwt_access_token_minutes * 60,
        user=UserPublic(id=user.id, email=user.email, name=user.name),
        workspace=WorkspacePublic(id=workspace.id, name=workspace.name) if workspace else None,
    )


def register_user(payload: RegisterRequest, db: Session) -> AuthData:
    email = payload.email.lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(email=email, name=payload.name.strip(), password_hash=hash_password(payload.password))
    user.workspaces.append(Workspace(name=payload.workspace_name.strip()))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists") from exc
    db.refresh(user)
    return _auth_data(db, user)


def authenticate_user(payload: LoginRequest, db: Session) -> AuthData:
    user = db.scalar(select(User).where(func.lower(User.email) == payload.email.lower()))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect", headers={"WWW-Authenticate": "Bearer"})
    return _auth_data(db, user)

