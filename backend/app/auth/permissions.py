"""Reusable, minimal, backend-enforced authorization primitives.

Deliberately small: a handful of explicit dependency functions and plain
helpers — not a generic permissions framework. No permission tables, no
JSON permissions, no middleware-based tenant context, no decorators that
hide what database query is being run.

The database (via `get_current_user`) is always the source of truth. A
user's global role and their organization membership role are read fresh
from PostgreSQL on every request; values from the request payload, JWT
claims, or frontend state are never trusted for authorization decisions.
"""
from typing import Optional

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationStatus
from app.models.organization_membership import OrganizationMembership, MembershipRole
from app.auth.jwt_handler import get_current_user


def is_system_admin(user: User) -> bool:
    return user.role == UserRole.SYSTEM_ADMIN.value


# --- A. Global-role check --------------------------------------------------


def require_global_roles(*allowed_roles: UserRole):
    """FastAPI dependency factory.

    Only allows the given global `UserRole` values through. The role is
    always read from the database-backed current user. Returns the current
    user for downstream use; raises 403 otherwise.
    """
    allowed_values = {r.value for r in allowed_roles}

    def _dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_values:
            raise HTTPException(
                status_code=403,
                detail=f"Requires one of the following global roles: {', '.join(sorted(allowed_values))}",
            )
        return current_user

    return _dependency


# --- B. Organization membership lookup -------------------------------------


def get_active_membership(
    db: Session, organization_id: int, user_id: int
) -> Optional[OrganizationMembership]:
    """Plain helper (not a dependency): the caller's active membership row
    for an organization, or None if they have none (or it's inactive).
    system_admin bypass is intentionally NOT applied here — callers combine
    this with `is_system_admin()` explicitly, so the bypass is always
    visible at the call site rather than hidden inside this helper.
    """
    return (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.is_active.is_(True),
        )
        .first()
    )


def get_organization_or_404(db: Session, organization_id: int) -> Organization:
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


# --- D. Organization status check -------------------------------------------


def ensure_organization_status_accessible(org: Organization, *, admin_bypass: bool) -> None:
    """Rejects a `suspended` organization for anyone other than
    system_admin. `pending` and `active` organizations are both treated as
    accessible to active members in this phase — this deliberately does
    NOT distinguish pending from active for read access; see
    README_LOCAL_SETUP.md for the documented policy. This is intentionally
    a single narrow check, not a broader status policy matrix.
    """
    if org.status == OrganizationStatus.SUSPENDED.value and not admin_bypass:
        raise HTTPException(status_code=403, detail="Organization is suspended")


def require_organization_access(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Organization:
    """FastAPI dependency.

    Requires the caller to be system_admin OR to have an *active*
    membership in `organization_id` (any membership role), and enforces
    the suspended-organization policy. Returns the `Organization` row. Use
    this for read endpoints that only need "any active member" access, not
    a specific membership role — see `require_organization_roles` below
    for that.
    """
    admin_bypass = is_system_admin(current_user)
    org = get_organization_or_404(db, organization_id)

    if not admin_bypass:
        membership = get_active_membership(db, organization_id, current_user.id)
        if not membership:
            # Same 404 as a nonexistent organization — does not confirm or
            # deny the existence of an organization the caller cannot
            # access.
            raise HTTPException(status_code=404, detail="Organization not found")

    ensure_organization_status_accessible(org, admin_bypass=admin_bypass)
    return org


# --- C. Organization-role check ---------------------------------------------


def require_organization_roles(*allowed_membership_roles):
    """FastAPI dependency factory.

    Requires active membership in `organization_id` (a path parameter)
    with one of the given `MembershipRole` values — OR system_admin, which
    always passes. Also enforces the suspended-organization policy.
    Returns the current user for downstream use.

    First wired to a route in Phase 2C (organization membership
    management). Fixed in Phase 2C: a caller with no membership at all in
    an existing organization now gets the same 404 as a nonexistent
    organization (matching `require_organization_access`'s
    privacy-preserving behavior), instead of a 403 that would have
    confirmed the organization's existence to a non-member. A genuine
    member whose membership role is simply insufficient still gets 403 —
    they already know the organization exists. This had zero behavioral
    impact on any endpoint prior to Phase 2C, since nothing called this
    function before.
    """
    allowed_values = {r.value for r in allowed_membership_roles}

    def _dependency(
        organization_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> User:
        admin_bypass = is_system_admin(current_user)
        org = get_organization_or_404(db, organization_id)

        if not admin_bypass:
            membership = get_active_membership(db, organization_id, current_user.id)
            if not membership:
                raise HTTPException(status_code=404, detail="Organization not found")
            if membership.membership_role not in allowed_values:
                raise HTTPException(
                    status_code=403,
                    detail=f"Requires organization role: {', '.join(sorted(allowed_values))}",
                )

        ensure_organization_status_accessible(org, admin_bypass=admin_bypass)
        return current_user

    return _dependency


# --- E. Organization-membership management check ---------------------------


def require_membership_manager(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """FastAPI dependency (Phase 2C).

    Requires system_admin OR an active `owner`/`admin` membership in
    `organization_id`. Enforces the suspended-organization policy
    (system_admin may still manage a suspended organization; owner/admin
    may not). Returns `(current_user, caller_membership)` —
    `caller_membership` is `None` for a system_admin who is not themselves
    a member of this organization, otherwise the caller's own
    `OrganizationMembership` row (always `owner` or `admin`), which
    endpoints use for self-management checks.

    Global roles (other than system_admin) are never consulted here — a
    `company_admin` with no active organization membership gets the same
    404 as any other non-member.
    """
    admin_bypass = is_system_admin(current_user)
    org = get_organization_or_404(db, organization_id)

    caller_membership = None
    if not admin_bypass:
        caller_membership = get_active_membership(db, organization_id, current_user.id)
        if not caller_membership:
            raise HTTPException(status_code=404, detail="Organization not found")
        if caller_membership.membership_role not in {MembershipRole.OWNER.value, MembershipRole.ADMIN.value}:
            raise HTTPException(status_code=403, detail="Requires organization role: admin, owner")

    ensure_organization_status_accessible(org, admin_bypass=admin_bypass)
    return current_user, caller_membership
