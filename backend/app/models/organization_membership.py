import enum

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class MembershipRole(str, enum.Enum):
    """Allowed organization-membership roles. This is deliberately a
    separate concept from the global `UserRole` (app.models.user) — a
    user's platform-wide role (student, system_admin, ...) and their role
    within a given organization (owner, admin, ...) are independent and
    must not be merged. Persisted as plain lowercase strings, not a native
    Postgres ENUM.
    """

    OWNER = "owner"
    ADMIN = "admin"
    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_organization_memberships_org_user"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    membership_role = Column(String(20), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", back_populates="memberships")
    user = relationship("User", back_populates="organization_memberships")
