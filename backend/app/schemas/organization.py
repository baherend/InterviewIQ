from typing import List, Optional
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.models.organization import OrganizationStatus
from app.models.organization_membership import MembershipRole

_ALLOWED_MEMBERSHIP_ROLES = {r.value for r in MembershipRole}
_ALLOWED_STATUSES = {s.value for s in OrganizationStatus}


class OrganizationCreate(BaseModel):
    # No `id` or `status` field: id is server-assigned, and a newly created
    # organization always starts as `pending` — clients cannot choose the
    # initial status. `owner_user_id` is required; the caller must be
    # system_admin and the referenced user must already exist and be
    # active (enforced in the router, not here).
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    owner_user_id: int


class OrganizationUpdate(BaseModel):
    # Deliberately excludes `status` — status only ever changes through the
    # dedicated PATCH .../status endpoint. If a client includes a "status"
    # key in this request body, Pydantic silently drops it (not a declared
    # field on this schema), so it can never leak through here. Also
    # excludes owner/membership fields — this endpoint never touches
    # organization_memberships.
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None


class OrganizationStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in _ALLOWED_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(_ALLOWED_STATUSES))}")
        return value


class OrganizationResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OrganizationOwnerSummary(BaseModel):
    # Safe fields only — no password_hash. Shown only to system_admin
    # (list/detail responses branch on caller role in the router).
    user_id: int
    name: str
    email: str
    is_active: bool


class AdminOrganizationListItem(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    owner: Optional[OrganizationOwnerSummary] = None
    member_count: int


class AdminOrganizationListResponse(BaseModel):
    items: List[AdminOrganizationListItem]
    total: int
    page: int
    page_size: int


class OrganizationDetail(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    owner: Optional[OrganizationOwnerSummary] = None
    member_count: int


class OrganizationMembershipCreate(BaseModel):
    # Not currently wired to a public endpoint — owner membership is created
    # server-side as part of organization creation. Kept as an explicit,
    # validated schema for the internal creation path and for a later phase.
    organization_id: int
    user_id: int
    membership_role: str

    @field_validator("membership_role")
    @classmethod
    def validate_membership_role(cls, value: str) -> str:
        if value not in _ALLOWED_MEMBERSHIP_ROLES:
            raise ValueError(
                f"membership_role must be one of: {', '.join(sorted(_ALLOWED_MEMBERSHIP_ROLES))}"
            )
        return value


class OrganizationMembershipResponse(BaseModel):
    id: int
    organization_id: int
    user_id: int
    membership_role: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# --- Phase 2C: membership management -----------------------------------

# Owner is deliberately excluded here: it can never be assigned through the
# membership-management endpoints (add / change role). There is always
# exactly one owner membership, created only as a side effect of
# organization creation (see POST /organizations) and never mutated
# afterward — owner replacement is out of scope for this phase.
_ASSIGNABLE_MEMBERSHIP_ROLES = {
    MembershipRole.ADMIN.value,
    MembershipRole.INTERVIEWER.value,
    MembershipRole.CANDIDATE.value,
}


class MembershipUserSummary(BaseModel):
    # Safe fields only — no password_hash. This is the global user role,
    # shown for context; it is never editable through this schema.
    id: int
    name: str
    email: str
    role: str
    is_active: bool


class MembershipListItem(BaseModel):
    id: int
    organization_id: int
    membership_role: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    user: MembershipUserSummary


class MembershipListResponse(BaseModel):
    items: List[MembershipListItem]
    total: int
    page: int
    page_size: int


class MembershipCreate(BaseModel):
    # No `organization_id` field — the target organization always comes
    # from the URL path, never the request body. No `id`, `is_active`, or
    # timestamp fields — those are server-assigned/managed.
    user_id: int
    membership_role: str

    @field_validator("membership_role")
    @classmethod
    def validate_membership_role(cls, value: str) -> str:
        if value not in _ASSIGNABLE_MEMBERSHIP_ROLES:
            raise ValueError(
                f"membership_role must be one of: {', '.join(sorted(_ASSIGNABLE_MEMBERSHIP_ROLES))} "
                "(owner cannot be assigned through this endpoint)"
            )
        return value


class MembershipRoleUpdate(BaseModel):
    membership_role: str

    @field_validator("membership_role")
    @classmethod
    def validate_membership_role(cls, value: str) -> str:
        if value not in _ASSIGNABLE_MEMBERSHIP_ROLES:
            raise ValueError(
                f"membership_role must be one of: {', '.join(sorted(_ASSIGNABLE_MEMBERSHIP_ROLES))} "
                "(owner cannot be assigned through this endpoint)"
            )
        return value


class MembershipStatusUpdate(BaseModel):
    is_active: bool
