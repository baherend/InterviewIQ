from typing import List, Optional
from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator

# Deliberately duplicated (not imported) from
# app.schemas.organization._ASSIGNABLE_MEMBERSHIP_ROLES: same values today
# (admin/interviewer/candidate — owner and system_admin are never
# assignable), but invitations and direct membership-management are
# independent features and importing a private, underscore-prefixed name
# across modules would create unnecessary coupling between them.
_ALLOWED_INVITATION_ROLES = {"admin", "interviewer", "candidate"}


class InvitationUserSummary(BaseModel):
    # Safe fields only — no password_hash, no global role, no is_active.
    id: int
    name: str
    email: str


class InvitationCreate(BaseModel):
    email: EmailStr
    membership_role: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("membership_role")
    @classmethod
    def validate_membership_role(cls, value: str) -> str:
        if value not in _ALLOWED_INVITATION_ROLES:
            raise ValueError(
                f"membership_role must be one of: {', '.join(sorted(_ALLOWED_INVITATION_ROLES))} "
                "(owner and system_admin cannot be invited)"
            )
        return value


class InvitationSummary(BaseModel):
    id: int
    organization_id: int
    email: str
    membership_role: str
    status: str
    expires_at: datetime
    created_at: datetime
    accepted_at: Optional[datetime] = None
    created_by: Optional[InvitationUserSummary] = None
    accepted_by: Optional[InvitationUserSummary] = None


class InvitationCreatedResponse(InvitationSummary):
    # Raw token + acceptance URL — returned ONLY from the create/rotate
    # endpoints, exactly once. Never included in InvitationSummary, the
    # list endpoint, or any other response; never persisted anywhere
    # (only its hash is stored — see backend/app/auth/invitation_tokens.py).
    token: str
    accept_url: str


class InvitationListResponse(BaseModel):
    items: List[InvitationSummary]
    total: int
    page: int
    page_size: int


class InvitationInspectResponse(BaseModel):
    valid: bool
    # "not_found" | "expired" | "revoked" | "accepted" | "organization_suspended" — only
    # present when valid is False.
    reason: Optional[str] = None
    organization_name: Optional[str] = None
    email: Optional[str] = None
    membership_role: Optional[str] = None
    expires_at: Optional[datetime] = None
    # True if an active account with the invited email already exists
    # (the recipient should log in and accept, not register); False if a
    # new account may be created via the register-and-accept flow.
    existing_account: Optional[bool] = None


class InvitationAcceptRequest(BaseModel):
    token: str


class InvitationAcceptResponse(BaseModel):
    message: str
    organization_id: int
    membership_role: str


class InvitationRegisterAcceptRequest(BaseModel):
    # No `email` or `membership_role` field, by design — both come
    # exclusively from the server-side invitation row the token resolves
    # to. A client cannot influence either through this request body.
    token: str
    name: str
    password: str
