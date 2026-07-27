from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationStatus
from app.models.organization_membership import OrganizationMembership, MembershipRole
from app.models.organization_invitation import OrganizationInvitation, InvitationStatus
from app.schemas.invitation import (
    InvitationCreate,
    InvitationSummary,
    InvitationCreatedResponse,
    InvitationListResponse,
    InvitationUserSummary,
    InvitationInspectResponse,
    InvitationAcceptRequest,
    InvitationAcceptResponse,
    InvitationRegisterAcceptRequest,
)
from app.schemas.user import Token
from app.auth.jwt_handler import get_current_user, create_access_token
from app.auth.password import hash_password
from app.auth.invitation_tokens import generate_invitation_token, hash_invitation_token
from app.auth.permissions import require_membership_manager
from app.config import settings

# Org-scoped management endpoints: create/list/revoke/rotate. Mirrors the
# membership-management router's shape (Phase 2C's organizations.py).
router = APIRouter(prefix="/organizations/{organization_id}/invitations", tags=["invitations"])

# Public endpoints: token inspection and acceptance. Not organization-scoped
# in the URL — the token itself resolves to exactly one organization.
public_router = APIRouter(prefix="/invitations", tags=["invitations"])

_ALLOWED_INVITATION_ROLES = {MembershipRole.ADMIN.value, MembershipRole.INTERVIEWER.value, MembershipRole.CANDIDATE.value}
_ALLOWED_INVITATION_STATUSES = {s.value for s in InvitationStatus}

# Preferred global-role mapping for a brand-new account created through
# invite-registration (Phase 2D task spec, section 15). company_admin has
# had no creation path until now — an invited `admin` membership is the
# first and only way a company_admin account gets created in this app.
_INVITE_ROLE_TO_GLOBAL_ROLE = {
    MembershipRole.ADMIN.value: UserRole.COMPANY_ADMIN.value,
    MembershipRole.INTERVIEWER.value: UserRole.INTERVIEWER.value,
    MembershipRole.CANDIDATE.value: UserRole.CANDIDATE.value,
}


def _lazy_expire_scope(db: Session, *, organization_id: Optional[int] = None, email: Optional[str] = None) -> None:
    """Deterministically transitions any PENDING invitation whose
    `expires_at` has already passed to EXPIRED, within the given scope.
    Called at the top of every list/create endpoint so expiry never
    depends on a background scheduler (none exists in this phase) — see
    README_LOCAL_SETUP.md for the documented policy.
    """
    query = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.status == InvitationStatus.PENDING.value,
        OrganizationInvitation.expires_at < datetime.now(timezone.utc),
    )
    if organization_id is not None:
        query = query.filter(OrganizationInvitation.organization_id == organization_id)
    if email is not None:
        query = query.filter(func.lower(OrganizationInvitation.email) == email)
    query.update({"status": InvitationStatus.EXPIRED.value}, synchronize_session=False)
    db.commit()


def _lazy_expire_one(db: Session, invitation: OrganizationInvitation) -> None:
    """Same lazy-expiry policy as `_lazy_expire_scope`, applied to a single
    already-loaded invitation row (revoke/rotate/inspect/accept paths),
    updating the in-memory object so the rest of the request sees the
    correct status without a second query.
    """
    if invitation.status == InvitationStatus.PENDING.value and invitation.expires_at < datetime.now(timezone.utc):
        invitation.status = InvitationStatus.EXPIRED.value
        db.commit()
        db.refresh(invitation)


def _user_summary(user: Optional[User]) -> Optional[InvitationUserSummary]:
    if not user:
        return None
    return InvitationUserSummary(id=user.id, name=user.name, email=user.email)


def _to_summary(invitation: OrganizationInvitation) -> InvitationSummary:
    return InvitationSummary(
        id=invitation.id,
        organization_id=invitation.organization_id,
        email=invitation.email,
        membership_role=invitation.membership_role,
        status=invitation.status,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        accepted_at=invitation.accepted_at,
        created_by=_user_summary(invitation.created_by),
        accepted_by=_user_summary(invitation.accepted_by),
    )


def _get_invitation_or_404(db: Session, organization_id: int, invitation_id: int) -> OrganizationInvitation:
    invitation = (
        db.query(OrganizationInvitation)
        .filter(
            OrganizationInvitation.id == invitation_id,
            OrganizationInvitation.organization_id == organization_id,
        )
        .first()
    )
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found in this organization")
    return invitation


# --- A. Create -------------------------------------------------------------


@router.post("", response_model=InvitationCreatedResponse, status_code=201)
def create_invitation(
    organization_id: int,
    data: InvitationCreate,
    db: Session = Depends(get_db),
    caller=Depends(require_membership_manager),
):
    current_user, _caller_membership = caller
    # require_membership_manager already validated: organization exists,
    # caller is system_admin or an active owner/admin member, and the
    # suspended-organization policy (blocked for owner/admin, allowed for
    # system_admin).

    existing_user = db.query(User).filter(func.lower(User.email) == data.email).first()
    if existing_user:
        if not existing_user.is_active:
            raise HTTPException(status_code=400, detail="This email belongs to an inactive existing user")
        existing_membership = (
            db.query(OrganizationMembership)
            .filter(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.user_id == existing_user.id,
            )
            .first()
        )
        if existing_membership:
            raise HTTPException(
                status_code=400,
                detail="This user already has a membership (active or inactive) in this organization",
            )

    # Lazily expire any stale pending invitation for this exact
    # organization+email before checking for a conflicting pending one —
    # keeps the "one pending invitation per org/email" rule from blocking
    # a legitimate re-invite just because a scheduler doesn't exist to
    # sweep expired rows proactively.
    _lazy_expire_scope(db, organization_id=organization_id, email=data.email)

    conflicting = (
        db.query(OrganizationInvitation)
        .filter(
            OrganizationInvitation.organization_id == organization_id,
            OrganizationInvitation.email == data.email,
            OrganizationInvitation.status == InvitationStatus.PENDING.value,
        )
        .first()
    )
    if conflicting:
        raise HTTPException(
            status_code=400,
            detail="An unexpired pending invitation already exists for this organization and email",
        )

    raw_token = generate_invitation_token()
    token_hash = hash_invitation_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.INVITATION_EXPIRE_HOURS)

    try:
        invitation = OrganizationInvitation(
            organization_id=organization_id,
            email=data.email,
            membership_role=data.membership_role,
            token_hash=token_hash,
            status=InvitationStatus.PENDING.value,
            expires_at=expires_at,
            created_by_user_id=current_user.id,
        )
        db.add(invitation)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="An unexpired pending invitation already exists for this organization and email",
        )
    db.refresh(invitation)

    accept_url = f"{settings.FRONTEND_PUBLIC_URL}/invitations/accept?token={raw_token}"
    return InvitationCreatedResponse(
        **_to_summary(invitation).model_dump(),
        token=raw_token,
        accept_url=accept_url,
    )


# --- B. List -----------------------------------------------------------


@router.get("", response_model=InvitationListResponse)
def list_invitations(
    organization_id: int,
    q: Optional[str] = None,
    status: Optional[str] = None,
    membership_role: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    caller=Depends(require_membership_manager),
):
    if status is not None and status not in _ALLOWED_INVITATION_STATUSES:
        raise HTTPException(
            status_code=400, detail=f"status must be one of: {', '.join(sorted(_ALLOWED_INVITATION_STATUSES))}"
        )
    if membership_role is not None and membership_role not in _ALLOWED_INVITATION_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"membership_role must be one of: {', '.join(sorted(_ALLOWED_INVITATION_ROLES))}",
        )

    _lazy_expire_scope(db, organization_id=organization_id)

    page = max(page, 1)
    page_size = max(1, min(page_size, 100))

    query = db.query(OrganizationInvitation).filter(OrganizationInvitation.organization_id == organization_id)
    if q:
        query = query.filter(OrganizationInvitation.email.ilike(f"%{q.strip().lower()}%"))
    if status is not None:
        query = query.filter(OrganizationInvitation.status == status)
    if membership_role is not None:
        query = query.filter(OrganizationInvitation.membership_role == membership_role)

    total = query.count()
    rows = (
        query.order_by(OrganizationInvitation.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [_to_summary(inv) for inv in rows]
    return InvitationListResponse(items=items, total=total, page=page, page_size=page_size)


# --- C. Revoke ---------------------------------------------------------


@router.patch("/{invitation_id}/revoke", response_model=InvitationSummary)
def revoke_invitation(
    organization_id: int,
    invitation_id: int,
    db: Session = Depends(get_db),
    caller=Depends(require_membership_manager),
):
    invitation = _get_invitation_or_404(db, organization_id, invitation_id)
    _lazy_expire_one(db, invitation)

    if invitation.status == InvitationStatus.REVOKED.value:
        # Idempotent: revoking an already-revoked invitation is a safe
        # no-op success rather than an error.
        return _to_summary(invitation)
    if invitation.status == InvitationStatus.ACCEPTED.value:
        raise HTTPException(status_code=400, detail="An accepted invitation cannot be revoked")
    if invitation.status == InvitationStatus.EXPIRED.value:
        raise HTTPException(status_code=400, detail="An expired invitation cannot be revoked")

    invitation.status = InvitationStatus.REVOKED.value
    db.commit()
    db.refresh(invitation)
    return _to_summary(invitation)


# --- D. Rotate (optional) -----------------------------------------------


@router.post("/{invitation_id}/rotate", response_model=InvitationCreatedResponse)
def rotate_invitation(
    organization_id: int,
    invitation_id: int,
    db: Session = Depends(get_db),
    caller=Depends(require_membership_manager),
):
    invitation = _get_invitation_or_404(db, organization_id, invitation_id)
    _lazy_expire_one(db, invitation)

    if invitation.status != InvitationStatus.PENDING.value:
        raise HTTPException(
            status_code=400,
            detail=f"Only a pending invitation can be rotated (current status: {invitation.status})",
        )

    raw_token = generate_invitation_token()
    invitation.token_hash = hash_invitation_token(raw_token)
    # The old token stops working immediately: any lookup by its hash no
    # longer matches a row, since token_hash has been overwritten here.
    invitation.expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.INVITATION_EXPIRE_HOURS)
    db.commit()
    db.refresh(invitation)

    accept_url = f"{settings.FRONTEND_PUBLIC_URL}/invitations/accept?token={raw_token}"
    return InvitationCreatedResponse(
        **_to_summary(invitation).model_dump(),
        token=raw_token,
        accept_url=accept_url,
    )


# --- E. Public inspect ---------------------------------------------------


@public_router.get("/inspect", response_model=InvitationInspectResponse)
def inspect_invitation(token: str, db: Session = Depends(get_db)):
    token_hash = hash_invitation_token(token)
    invitation = db.query(OrganizationInvitation).filter(OrganizationInvitation.token_hash == token_hash).first()
    if not invitation:
        return InvitationInspectResponse(valid=False, reason="not_found")

    _lazy_expire_one(db, invitation)

    if invitation.status != InvitationStatus.PENDING.value:
        return InvitationInspectResponse(valid=False, reason=invitation.status)

    org = db.query(Organization).filter(Organization.id == invitation.organization_id).first()
    if not org or org.status == OrganizationStatus.SUSPENDED.value:
        return InvitationInspectResponse(valid=False, reason="organization_suspended")

    existing_account = (
        db.query(User).filter(func.lower(User.email) == invitation.email, User.is_active.is_(True)).first()
        is not None
    )
    return InvitationInspectResponse(
        valid=True,
        organization_name=org.name,
        email=invitation.email,
        membership_role=invitation.membership_role,
        expires_at=invitation.expires_at,
        existing_account=existing_account,
    )


# --- F. Accept with existing account -------------------------------------


@public_router.post("/accept", response_model=InvitationAcceptResponse)
def accept_invitation(
    data: InvitationAcceptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # get_current_user already rejects an inactive account with 403 before
    # this body runs, so "user must be active" is structurally guaranteed.
    token_hash = hash_invitation_token(data.token)
    invitation = db.query(OrganizationInvitation).filter(OrganizationInvitation.token_hash == token_hash).first()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invalid invitation token")

    _lazy_expire_one(db, invitation)

    if invitation.status != InvitationStatus.PENDING.value:
        raise HTTPException(status_code=400, detail=f"This invitation is no longer valid ({invitation.status})")

    # Case-insensitive match against the invitation's normalized (already
    # lowercase) email. No system_admin bypass here, deliberately — this
    # is the invited person accepting for themselves, not a management
    # action, and the task requires this rule to hold for every caller.
    if current_user.email.lower() != invitation.email:
        raise HTTPException(status_code=403, detail="This invitation was issued to a different email address")

    org = db.query(Organization).filter(Organization.id == invitation.organization_id).first()
    if not org or org.status == OrganizationStatus.SUSPENDED.value:
        raise HTTPException(status_code=403, detail="This organization is currently suspended")

    existing_membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == invitation.organization_id,
            OrganizationMembership.user_id == current_user.id,
        )
        .first()
    )
    if existing_membership:
        raise HTTPException(status_code=400, detail="You already have a membership in this organization")

    try:
        membership = OrganizationMembership(
            organization_id=invitation.organization_id,
            user_id=current_user.id,
            membership_role=invitation.membership_role,
            is_active=True,
        )
        db.add(membership)
        invitation.status = InvitationStatus.ACCEPTED.value
        invitation.accepted_at = datetime.now(timezone.utc)
        invitation.accepted_by_user_id = current_user.id
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Could not accept this invitation — please try again")

    return InvitationAcceptResponse(
        message="Invitation accepted",
        organization_id=invitation.organization_id,
        membership_role=invitation.membership_role,
    )


# --- G. Register and accept (new account) --------------------------------


@public_router.post("/register-and-accept", response_model=Token, status_code=201)
def register_and_accept_invitation(data: InvitationRegisterAcceptRequest, db: Session = Depends(get_db)):
    token_hash = hash_invitation_token(data.token)
    invitation = db.query(OrganizationInvitation).filter(OrganizationInvitation.token_hash == token_hash).first()
    if not invitation:
        raise HTTPException(status_code=404, detail="Invalid invitation token")

    _lazy_expire_one(db, invitation)

    if invitation.status != InvitationStatus.PENDING.value:
        raise HTTPException(status_code=400, detail=f"This invitation is no longer valid ({invitation.status})")

    org = db.query(Organization).filter(Organization.id == invitation.organization_id).first()
    if not org or org.status == OrganizationStatus.SUSPENDED.value:
        raise HTTPException(status_code=403, detail="This organization is currently suspended")

    if db.query(User).filter(func.lower(User.email) == invitation.email).first():
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists — please log in and accept the invitation from your account",
        )

    global_role = _INVITE_ROLE_TO_GLOBAL_ROLE.get(invitation.membership_role)
    if not global_role:
        # Structurally unreachable: InvitationCreate only ever allows
        # admin/interviewer/candidate, all three of which are mapped
        # above. Defensive guard only.
        raise HTTPException(status_code=400, detail="This invitation's role cannot be used for registration")

    try:
        user = User(
            name=data.name,
            email=invitation.email,  # from the invitation only — never client-supplied
            password_hash=hash_password(data.password),
            role=global_role,
        )
        db.add(user)
        db.flush()  # assigns user.id within this transaction

        membership = OrganizationMembership(
            organization_id=invitation.organization_id,
            user_id=user.id,
            membership_role=invitation.membership_role,
            is_active=True,
        )
        db.add(membership)

        invitation.status = InvitationStatus.ACCEPTED.value
        invitation.accepted_at = datetime.now(timezone.utc)
        invitation.accepted_by_user_id = user.id
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists — please log in and accept the invitation from your account",
        )
    db.refresh(user)

    # Auto-login on success, matching the existing public /auth/register
    # behavior exactly (same Token shape, same create_access_token call) —
    # not a new, inconsistent auth pattern introduced just for this flow.
    token = create_access_token(
        {"sub": str(user.id)}, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": token, "token_type": "bearer", "user": user}
