from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import install_error_handlers
from app.routers import auth_router, aws_router, workspaces_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.validate_secrets()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="AWS disaster recovery inventory, readiness, and recommendation API.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],
)
install_error_handlers(app)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(workspaces_router, prefix=settings.api_prefix)
app.include_router(aws_router, prefix=settings.api_prefix)


@app.get("/health", tags=["health"])
def health():
    return {"success": True, "message": "CloudGuard DR API is healthy", "data": {"status": "ok"}}

