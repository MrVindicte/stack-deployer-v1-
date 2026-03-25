"""Stack Deployer — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.routes import auth_router, deploy_router, infra_router, stacks_router
from app.core.config import get_settings
from app.core.database import init_db
from app.core.security import hash_password
from app.models.models import User

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events."""
    logger.info(f"Starting {settings.app_name} ({settings.app_env})")

    # Init database tables
    await init_db()

    # Create default admin user if not exists
    from app.core.database import async_session

    async with async_session() as db:
        from sqlalchemy import select

        result = await db.execute(
            select(User).where(User.username == settings.first_admin_user)
        )
        if not result.scalar_one_or_none():
            admin = User(
                username=settings.first_admin_user,
                hashed_password=hash_password(settings.first_admin_password),
                role="admin",
            )
            db.add(admin)
            await db.commit()
            logger.info(f"Admin user '{settings.first_admin_user}' created")

    # Sync stack definitions
    from app.services.stack_loader import load_all_stacks

    stacks = load_all_stacks()
    logger.info(f"Loaded {len(stacks)} stack definition(s)")

    yield
    logger.info("Shutting down")


app = FastAPI(
    title=settings.app_name,
    description="Portail self-service de déploiement de stacks VM sur Proxmox VE",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(stacks_router, prefix="/api")
app.include_router(deploy_router, prefix="/api")
app.include_router(infra_router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}
