import enum

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class InvitationStatus(str, enum.Enum):
    """Allowed invitation statuses. Persisted as plain lowercase strings
    (not a native Postgres ENUM), validated at the application layer —
    same pattern as OrganizationStatus and MembershipRole.
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class OrganizationInvitation(Base):
    __tablename__ = "organization_invitations"
    __table_args__ = (
        # At most one PENDING invitation per (organization, email) at a
        # time — a DB-level backstop against race conditions, mirroring
        # the application-layer check in the router. Deliberately a
        # partial index rather than a plain unique constraint, so a new
        # invitation can always be created after an old one for the same
        # organization/email is accepted, revoked, or (lazily) expired —
        # see README_LOCAL_SETUP.md.
        Index(
            "uq_org_invitations_pending_org_email",
            "organization_id",
            "email",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Always stored lowercase (normalized in the Pydantic schema before
    # this row is created) — comparisons against User.email elsewhere use
    # an explicit lower() to stay correct regardless.
    email = Column(String(255), nullable=False, index=True)
    membership_role = Column(String(20), nullable=False)
    # SHA-256 hex digest of the raw invitation token — the raw token itself
    # is never persisted anywhere. See backend/app/auth/invitation_tokens.py.
    token_hash = Column(String(128), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default=InvitationStatus.PENDING.value, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    accepted_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    organization = relationship("Organization", back_populates="invitations")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    accepted_by = relationship("User", foreign_keys=[accepted_by_user_id])
