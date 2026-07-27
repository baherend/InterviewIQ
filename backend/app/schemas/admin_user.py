from typing import List, Optional
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.models.user import UserRole

_ALLOWED_ROLES = {r.value for r in UserRole}


class AdminUserListItem(BaseModel):
    # Deliberately safe fields only — no password_hash.
    id: int
    name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminUserListResponse(BaseModel):
    items: List[AdminUserListItem]
    total: int
    page: int
    page_size: int


class AdminUserMembershipSummary(BaseModel):
    organization_id: int
    membership_role: str
    is_active: bool

    model_config = {"from_attributes": True}


class AdminUserDetail(BaseModel):
    id: int
    name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    memberships: List[AdminUserMembershipSummary] = []

    model_config = {"from_attributes": True}


class AdminUserStatusUpdate(BaseModel):
    is_active: bool


class AdminUserRoleUpdate(BaseModel):
    # No `id`, no arbitrary text — role must be one of the five known
    # UserRole values. Rejects anything else at the request-validation
    # layer, before the router even runs.
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in _ALLOWED_ROLES:
            raise ValueError(f"role must be one of: {', '.join(sorted(_ALLOWED_ROLES))}")
        return value
