from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AWSAccount, User, Workspace


def list_user_workspaces(user: User, db: Session) -> list[dict]:
    workspaces = list(db.scalars(select(Workspace).where(Workspace.owner_user_id == user.id)
                                 .order_by(Workspace.created_at)).all())
    return [{"id": str(workspace.id), "name": workspace.name,
             "aws_accounts": db.scalar(select(AWSAccount.id).where(AWSAccount.workspace_id == workspace.id).limit(1)) is not None}
            for workspace in workspaces]


def create_user_workspace(name: str, user: User, db: Session) -> dict:
    workspace = Workspace(owner_user_id=user.id, name=name.strip())
    db.add(workspace)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A workspace with that name already exists") from exc
    db.refresh(workspace)
    return {"id": str(workspace.id), "name": workspace.name}

