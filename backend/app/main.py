import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import ProgrammingError

from app.database import SessionLocal
from app.routers import auth, questions, interviews, dashboard, organizations, admin_users, invitations
from app.utils.seed import seed_questions
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Database schema is managed by Alembic, not by the application. A fresh
    # database must have `alembic upgrade head` run against it before the
    # backend is started — see README_LOCAL_SETUP.md.
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    settings.fusion_upload_path.mkdir(parents=True, exist_ok=True)
    settings.fusion_output_path.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        seed_questions(db)
    except ProgrammingError as exc:
        raise RuntimeError(
            "InterviewIQ backend failed to start: the 'questions' table was "
            "not found. This database has not been migrated yet. Run "
            "'alembic upgrade head' inside the backend container "
            "(see README_LOCAL_SETUP.md) before starting the application."
        ) from exc
    finally:
        db.close()
    yield


app = FastAPI(
    title="InterviewIQ API",
    description="AI-Powered Mock Interview Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(questions.router, prefix="/api")
app.include_router(interviews.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(organizations.router, prefix="/api")
app.include_router(admin_users.router, prefix="/api")
app.include_router(invitations.router, prefix="/api")
app.include_router(invitations.public_router, prefix="/api")


@app.get("/")
def root():
    return {"message": "InterviewIQ API", "version": "1.0.0", "status": "running"}


@app.get("/health")
def health():
    return {"status": "healthy"}
