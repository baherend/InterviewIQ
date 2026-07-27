import enum

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class UserRole(str, enum.Enum):
    """Allowed user roles. Persisted as plain lowercase strings in
    PostgreSQL (not a native Postgres ENUM), validated at the application
    layer via this Enum. Do not add values here without a corresponding
    reviewed Alembic migration.
    """

    SYSTEM_ADMIN = "system_admin"
    STUDENT = "student"
    COMPANY_ADMIN = "company_admin"
    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default=UserRole.STUDENT.value, index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    interviews = relationship("Interview", back_populates="user", cascade="all, delete-orphan")
    organization_memberships = relationship(
        "OrganizationMembership", back_populates="user", cascade="all, delete-orphan"
    )
