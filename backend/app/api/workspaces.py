from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database.session import get_db
from app.models import User
from app.schemas.common import APIResponse
from app.services.workspace_service import create_user_workspace, list_user_workspaces

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)


@router.get("", response_model=APIResponse[list[dict]])
def list_workspaces(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = list_user_workspaces(user, db)
    return {"success": True, "message": "Workspaces", "data": data}


@router.post("", response_model=APIResponse[dict], status_code=201)
def create_workspace(payload: WorkspaceCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = create_user_workspace(payload.name, user, db)
    return {"success": True, "message": "Workspace created", "data": data}

