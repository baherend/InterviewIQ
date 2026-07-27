import enum

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class OrganizationStatus(str, enum.Enum):
    """Allowed organization statuses. Persisted as plain lowercase strings
    (not a native Postgres ENUM), validated at the application layer via
    this Enum. Do not add values here without a corresponding reviewed
    Alembic migration.
    """

    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default=OrganizationStatus.PENDING.value, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    memberships = relationship(
        "OrganizationMembership", back_populates="organization", cascade="all, delete-orphan"
    )
    invitations = relationship(
        "OrganizationInvitation", back_populates="organization", cascade="all, delete-orphan"
    )
