from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.encoders import ENCODERS_BY_TYPE
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.avatar_store import UPLOAD_ROOT, ensure_dirs
from app.config import get_settings
from app.database import SessionLocal
from app.migrate import migrate_schema
from app.routers import admin, auth, chat, chat_requests, invites, posts, projects, site, social, users
from app.seed import seed_database
from app.timeutil import utc_iso

# Persist as UTC; always emit Z-suffixed ISO so clients can convert to Asia/Shanghai.
ENCODERS_BY_TYPE[datetime] = lambda value: utc_iso(value)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Apply schema updates and seed required rows before serving requests."""
    migrate_schema()
    ensure_dirs()
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="Zeej Blog API",
    version="1.1.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ensure_dirs()
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_ROOT)), name="uploads")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(posts.router)
app.include_router(projects.router)
app.include_router(chat.router)
app.include_router(chat_requests.router)
app.include_router(invites.router)
app.include_router(social.router)
app.include_router(admin.router)
app.include_router(site.router)

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "site": "zeej"}
