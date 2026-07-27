import re
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationStatus
from app.models.organization_membership import OrganizationMembership, MembershipRole
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationStatusUpdate,
    OrganizationResponse,
    OrganizationOwnerSummary,
    AdminOrganizationListItem,
    AdminOrganizationListResponse,
    OrganizationDetail,
    OrganizationMembershipResponse,
    MembershipUserSummary,
    MembershipListItem,
    MembershipListResponse,
    MembershipCreate,
    MembershipRoleUpdate,
    MembershipStatusUpdate,
)
from app.auth.jwt_handler import get_current_user
from app.auth.permissions import (
    is_system_admin,
    require_global_roles,
    require_organization_access,
    require_membership_manager,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])

_ALLOWED_STATUSES = {s.value for s in OrganizationStatus}
_ALLOWED_MEMBERSHIP_ROLES = {r.value for r in MembershipRole}

# Status transition policy (Phase 2B), enforced by PATCH .../status:
#   pending   -> pending, active, suspended
#   active    -> active, suspended                (NOT pending — no "un-approve")
#   suspended -> suspended, active                 (NOT pending — no "reset")
# Setting the current status again is an explicit no-op success (idempotent).
_ALLOWED_STATUS_TRANSITIONS = {
    OrganizationStatus.PENDING.value: {
        OrganizationStatus.PENDING.value,
        OrganizationStatus.ACTIVE.value,
        OrganizationStatus.SUSPENDED.value,
    },
    OrganizationStatus.ACTIVE.value: {
        OrganizationStatus.ACTIVE.value,
        OrganizationStatus.SUSPENDED.value,
    },
    OrganizationStatus.SUSPENDED.value: {
        OrganizationStatus.SUSPENDED.value,
        OrganizationStatus.ACTIVE.value,
    },
}


def _slugify(value: str) -> str:
    """Normalize a name/slug into a stable lowercase, hyphenated slug."""
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


def _get_owner_summary(db: Session, organization_id: int) -> Optional[OrganizationOwnerSummary]:
    row = (
        db.query(OrganizationMembership, User)
        .join(User, User.id == OrganizationMembership.user_id)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.membership_role == MembershipRole.OWNER.value,
        )
        .first()
    )
    if not row:
        return None
    _membership, user = row
    return OrganizationOwnerSummary(user_id=user.id, name=user.name, email=user.email, is_active=user.is_active)


def _get_member_count(db: Session, organization_id: int) -> int:
    return (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.organization_id == organization_id)
        .count()
    )


def _to_admin_list_item(db: Session, org: Organization) -> AdminOrganizationListItem:
    return AdminOrganizationListItem(
        id=org.id,
        name=org.name,
        slug=org.slug,
        description=org.description,
        status=org.status,
        created_at=org.created_at,
        updated_at=org.updated_at,
        owner=_get_owner_summary(db, org.id),
        member_count=_get_member_count(db, org.id),
    )


def _to_membership_item(membership: OrganizationMembership, user: User) -> MembershipListItem:
    return MembershipListItem(
        id=membership.id,
        organization_id=membership.organization_id,
        membership_role=membership.membership_role,
        is_active=membership.is_active,
        created_at=membership.created_at,
        updated_at=membership.updated_at,
        user=MembershipUserSummary(
            id=user.id, name=user.name, email=user.email, role=user.role, is_active=user.is_active
        ),
    )


def _to_org_detail(db: Session, org: Organization) -> OrganizationDetail:
    return OrganizationDetail(
        id=org.id,
        name=org.name,
        slug=org.slug,
        description=org.description,
        status=org.status,
        created_at=org.created_at,
        updated_at=org.updated_at,
        owner=_get_owner_summary(db, org.id),
        member_count=_get_member_count(db, org.id),
    )


@router.post("", response_model=OrganizationResponse, status_code=201)
def create_organization(
    data: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_global_roles(UserRole.SYSTEM_ADMIN)),
):
    # Only system_admin may create organizations in this phase (enforced by
    # require_global_roles above). This does not change the caller's or
    # the owner's global user role.
    owner = db.query(User).filter(User.id == data.owner_user_id).first()
    if not owner:
        raise HTTPException(
            status_code=404, detail="owner_user_id does not reference an existing user"
        )
    if not owner.is_active:
        raise HTTPException(status_code=400, detail="owner_user_id must reference an active user")

    slug = _slugify(data.slug or data.name)
    if not slug:
        raise HTTPException(
            status_code=400, detail="Could not derive a valid slug from the provided name/slug"
        )

    if db.query(Organization).filter(Organization.slug == slug).first():
        raise HTTPException(status_code=400, detail="An organization with this slug already exists")

    # Organization + owner membership are created in a single transaction:
    # if the membership insert fails for any reason, the organization
    # insert is rolled back with it — no orphaned organization is left
    # behind, and the owner's global role is never touched here. A
    # duplicate owner membership is structurally impossible here since
    # org.id is freshly assigned by this same transaction.
    try:
        org = Organization(
            name=data.name,
            slug=slug,
            description=data.description,
            status=OrganizationStatus.PENDING.value,
        )
        db.add(org)
        db.flush()  # assigns org.id within the same transaction

        membership = OrganizationMembership(
            organization_id=org.id,
            user_id=owner.id,
            membership_role=MembershipRole.OWNER.value,
            is_active=True,
        )
        db.add(membership)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="An organization with this slug already exists")

    db.refresh(org)
    return org


@router.get("")
def list_organizations(
    q: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # This endpoint intentionally has no fixed `response_model`: system_admin
    # gets a paginated, enriched `AdminOrganizationListResponse`; everyone
    # else gets the original plain `List[OrganizationResponse]` — the exact
    # response shape non-admin callers received before Phase 2B, unchanged.
    if is_system_admin(current_user):
        if status is not None and status not in _ALLOWED_STATUSES:
            raise HTTPException(
                status_code=400, detail=f"status must be one of: {', '.join(sorted(_ALLOWED_STATUSES))}"
            )
        page = max(page, 1)
        page_size = max(1, min(page_size, 100))

        query = db.query(Organization)
        if q:
            like = f"%{q}%"
            query = query.filter(or_(Organization.name.ilike(like), Organization.slug.ilike(like)))
        if status is not None:
            query = query.filter(Organization.status == status)

        total = query.count()
        orgs = query.order_by(Organization.id).offset((page - 1) * page_size).limit(page_size).all()
        items = [_to_admin_list_item(db, o) for o in orgs]
        return AdminOrganizationListResponse(items=items, total=total, page=page, page_size=page_size)

    # Non-admin: identical query and response shape to before Phase 2B —
    # only organizations where the caller has an active membership,
    # excluding suspended organizations (policy from Phase 1E/1D).
    member_org_ids = [
        m.organization_id
        for m in db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == current_user.id,
            OrganizationMembership.is_active.is_(True),
        )
        .all()
    ]
    if not member_org_ids:
        return []
    orgs = (
        db.query(Organization)
        .filter(
            Organization.id.in_(member_org_ids),
            Organization.status != OrganizationStatus.SUSPENDED.value,
        )
        .order_by(Organization.id)
        .all()
    )
    return [OrganizationResponse.model_validate(o) for o in orgs]


@router.get("/me/memberships", response_model=List[OrganizationMembershipResponse])
def get_my_memberships(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Policy (documented in README_LOCAL_SETUP.md): excludes memberships in
    # suspended organizations for everyone, including system_admin — this
    # endpoint reflects the caller's own active-membership standing, not
    # an admin view of the platform.
    return (
        db.query(OrganizationMembership)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .filter(
            OrganizationMembership.user_id == current_user.id,
            OrganizationMembership.is_active.is_(True),
            Organization.status != OrganizationStatus.SUSPENDED.value,
        )
        .order_by(OrganizationMembership.id)
        .all()
    )


@router.get("/{organization_id}")
def get_organization(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(require_organization_access),
):
    # require_organization_access already validated existence, active
    # membership (or system_admin), and the suspended-organization policy.
    # system_admin gets the enriched OrganizationDetail (owner + member
    # count); a regular active member gets the original plain
    # OrganizationResponse, unchanged from before Phase 2B.
    if is_system_admin(current_user):
        return _to_org_detail(db, org)
    return OrganizationResponse.model_validate(org)


@router.patch("/{organization_id}", response_model=OrganizationResponse)
def update_organization(
    organization_id: int,
    data: OrganizationUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_global_roles(UserRole.SYSTEM_ADMIN)),
):
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    update_data = data.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] is not None:
        org.name = update_data["name"]

    if "slug" in update_data and update_data["slug"] is not None:
        new_slug = _slugify(update_data["slug"])
        if not new_slug:
            raise HTTPException(
                status_code=400, detail="Could not derive a valid slug from the provided value"
            )
        if new_slug != org.slug:
            duplicate = (
                db.query(Organization)
                .filter(Organization.slug == new_slug, Organization.id != org.id)
                .first()
            )
            if duplicate:
                raise HTTPException(
                    status_code=400, detail="An organization with this slug already exists"
                )
            org.slug = new_slug

    if "description" in update_data:
        org.description = update_data["description"]

    # `status`, owner, and memberships are never touched by this endpoint —
    # OrganizationUpdate has no such fields, so nothing here can change them.
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="An organization with this slug already exists")

    db.refresh(org)
    return org


@router.patch("/{organization_id}/status", response_model=OrganizationResponse)
def update_organization_status(
    organization_id: int,
    data: OrganizationStatusUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_global_roles(UserRole.SYSTEM_ADMIN)),
):
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    allowed_next = _ALLOWED_STATUS_TRANSITIONS.get(org.status, set())
    if data.status not in allowed_next:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition organization from '{org.status}' to '{data.status}'.",
        )

    # Status changes touch only this one column — memberships and user
    # global roles are never modified here.
    org.status = data.status
    db.commit()
    db.refresh(org)
    return org


@router.get("/{organization_id}/members", response_model=MembershipListResponse)
def list_organization_members(
    organization_id: int,
    q: Optional[str] = None,
    membership_role: Optional[str] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    org: Organization = Depends(require_organization_access),
):
    # Phase 2C: this endpoint now always returns the enriched, paginated
    # MembershipListResponse shape (previously a plain list of bare
    # membership rows). Read access is unchanged — any active member of any
    # role, or system_admin (require_organization_access already enforced
    # this plus the suspended-organization policy); this is a read-only
    # listing endpoint, not a management one, so no membership-role
    # restriction is applied here. The one known frontend caller
    # (CompanyDashboard.jsx) has been updated to match this shape.
    if membership_role is not None and membership_role not in _ALLOWED_MEMBERSHIP_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"membership_role must be one of: {', '.join(sorted(_ALLOWED_MEMBERSHIP_ROLES))}",
        )
    page = max(page, 1)
    page_size = max(1, min(page_size, 100))

    query = (
        db.query(OrganizationMembership, User)
        .join(User, User.id == OrganizationMembership.user_id)
        .filter(OrganizationMembership.organization_id == org.id)
    )
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.name.ilike(like), User.email.ilike(like)))
    if membership_role is not None:
        query = query.filter(OrganizationMembership.membership_role == membership_role)
    if is_active is not None:
        query = query.filter(OrganizationMembership.is_active.is_(is_active))

    total = query.count()
    rows = (
        query.order_by(OrganizationMembership.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [_to_membership_item(m, u) for m, u in rows]
    return MembershipListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("/{organization_id}/members", response_model=MembershipListItem, status_code=201)
def add_organization_member(
    organization_id: int,
    data: MembershipCreate,
    db: Session = Depends(get_db),
    caller: Tuple[User, Optional[OrganizationMembership]] = Depends(require_membership_manager),
):
    # Authorization: system_admin, or an active owner/admin member of this
    # organization (require_membership_manager). `data.membership_role` is
    # already restricted to admin/interviewer/candidate by the schema
    # validator — owner can never be assigned here.
    target_user = db.query(User).filter(User.id == data.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="user_id does not reference an existing user")
    if not target_user.is_active:
        raise HTTPException(status_code=400, detail="user_id must reference an active user")

    existing = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == target_user.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="This user already has a membership (active or inactive) in this organization",
        )

    try:
        membership = OrganizationMembership(
            organization_id=organization_id,
            user_id=target_user.id,
            membership_role=data.membership_role,
            is_active=True,
        )
        db.add(membership)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="This user already has a membership in this organization",
        )
    db.refresh(membership)
    return _to_membership_item(membership, target_user)


def _get_membership_or_404(db: Session, organization_id: int, membership_id: int) -> OrganizationMembership:
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.id == membership_id,
            OrganizationMembership.organization_id == organization_id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found in this organization")
    return membership


@router.patch("/{organization_id}/members/{membership_id}/role", response_model=MembershipListItem)
def update_member_role(
    organization_id: int,
    membership_id: int,
    data: MembershipRoleUpdate,
    db: Session = Depends(get_db),
    caller: Tuple[User, Optional[OrganizationMembership]] = Depends(require_membership_manager),
):
    membership = _get_membership_or_404(db, organization_id, membership_id)

    # Owner invariant (universal — applies even to system_admin): the owner
    # membership's role can never be changed. `data.membership_role` is
    # already restricted to admin/interviewer/candidate by the schema
    # validator, so no membership can ever be promoted to owner here either.
    if membership.membership_role == MembershipRole.OWNER.value:
        raise HTTPException(status_code=400, detail="The owner membership's role cannot be changed")

    membership.membership_role = data.membership_role
    db.commit()
    db.refresh(membership)
    user = db.query(User).filter(User.id == membership.user_id).first()
    return _to_membership_item(membership, user)


@router.patch("/{organization_id}/members/{membership_id}/status", response_model=MembershipListItem)
def update_member_status(
    organization_id: int,
    membership_id: int,
    data: MembershipStatusUpdate,
    db: Session = Depends(get_db),
    caller: Tuple[User, Optional[OrganizationMembership]] = Depends(require_membership_manager),
):
    current_user, caller_membership = caller
    membership = _get_membership_or_404(db, organization_id, membership_id)

    # Owner invariant (universal): the owner membership can never be
    # deactivated (or reactivated via this route, since it can never leave
    # the active state in the first place).
    if membership.membership_role == MembershipRole.OWNER.value:
        raise HTTPException(status_code=400, detail="The owner membership cannot be deactivated")

    # Self-management (safer default): an organization admin cannot
    # deactivate their own admin membership — system_admin still can (the
    # is_system_admin check bypasses this entirely), and an owner acting on
    # someone else's admin membership is unaffected by this check.
    if (
        not is_system_admin(current_user)
        and caller_membership is not None
        and caller_membership.id == membership.id
        and caller_membership.membership_role == MembershipRole.ADMIN.value
        and data.is_active is False
    ):
        raise HTTPException(
            status_code=400,
            detail="Organization admins cannot deactivate their own membership — ask another owner/admin or a system admin",
        )

    # This only ever touches OrganizationMembership.is_active — the user's
    # global account status (users.is_active) is a different field and is
    # never modified here.
    membership.is_active = data.is_active
    db.commit()
    db.refresh(membership)
    user = db.query(User).filter(User.id == membership.user_id).first()
    return _to_membership_item(membership, user)


@router.delete("/{organization_id}/members/{membership_id}")
def remove_organization_member(
    organization_id: int,
    membership_id: int,
    db: Session = Depends(get_db),
    caller: Tuple[User, Optional[OrganizationMembership]] = Depends(require_membership_manager),
):
    current_user, caller_membership = caller
    membership = _get_membership_or_404(db, organization_id, membership_id)

    # Owner invariant (universal): the owner membership can never be removed.
    if membership.membership_role == MembershipRole.OWNER.value:
        raise HTTPException(status_code=400, detail="The owner membership cannot be removed")

    # Self-management (safer default), mirrors the status endpoint above.
    if (
        not is_system_admin(current_user)
        and caller_membership is not None
        and caller_membership.id == membership.id
        and caller_membership.membership_role == MembershipRole.ADMIN.value
    ):
        raise HTTPException(
            status_code=400,
            detail="Organization admins cannot remove their own membership — ask another owner/admin or a system admin",
        )

    # Deletes only the membership row — the User row is never touched.
    db.delete(membership)
    db.commit()
    return {"message": "Membership removed"}
