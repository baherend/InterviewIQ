from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.organization_membership import OrganizationMembership
from app.schemas.admin_user import (
    AdminUserListItem,
    AdminUserListResponse,
    AdminUserDetail,
    AdminUserMembershipSummary,
    AdminUserStatusUpdate,
    AdminUserRoleUpdate,
)
from app.auth.permissions import require_global_roles

router = APIRouter(prefix="/admin/users", tags=["admin-users"])

_ALLOWED_ROLES = {r.value for r in UserRole}


def _active_system_admin_count(db: Session, exclude_user_id: Optional[int] = None) -> int:
    query = db.query(User).filter(
        User.role == UserRole.SYSTEM_ADMIN.value, User.is_active.is_(True)
    )
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return query.count()


def _to_detail(db: Session, user: User) -> AdminUserDetail:
    memberships = (
        db.query(OrganizationMembership).filter(OrganizationMembership.user_id == user.id).all()
    )
    return AdminUserDetail(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        memberships=[
            AdminUserMembershipSummary(
                organization_id=m.organization_id,
                membership_role=m.membership_role,
                is_active=m.is_active,
            )
            for m in memberships
        ],
    )


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("", response_model=AdminUserListResponse)
def list_users(
    q: Optional[str] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(require_global_roles(UserRole.SYSTEM_ADMIN)),
):
    if role is not None and role not in _ALLOWED_ROLES:
        raise HTTPException(
            status_code=400, detail=f"role must be one of: {', '.join(sorted(_ALLOWED_ROLES))}"
        )

    page = max(page, 1)
    page_size = max(1, min(page_size, 100))

    query = db.query(User)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.name.ilike(like), User.email.ilike(like)))
    if role is not None:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active.is_(is_active))

    total = query.count()
    # Stable ordering: id ascending is deterministic across pages even as
    # rows are added/updated between requests.
    items = query.order_by(User.id).offset((page - 1) * page_size).limit(page_size).all()

    return AdminUserListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{user_id}", response_model=AdminUserDetail)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_global_roles(UserRole.SYSTEM_ADMIN)),
):
    user = _get_user_or_404(db, user_id)
    return _to_detail(db, user)


@router.patch("/{user_id}/status", response_model=AdminUserDetail)
def update_user_status(
    user_id: int,
    data: AdminUserStatusUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_global_roles(UserRole.SYSTEM_ADMIN)),
):
    target = _get_user_or_404(db, user_id)

    # Last-active-system_admin protection: applies equally whether the
    # caller is suspending themselves or someone else — the invariant
    # being protected is "at least one active system_admin must always
    # exist", not "who is performing the action".
    if (
        data.is_active is False
        and target.role == UserRole.SYSTEM_ADMIN.value
        and target.is_active
    ):
        remaining = _active_system_admin_count(db, exclude_user_id=target.id)
        if remaining == 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot suspend the last active system_admin.",
            )

    target.is_active = data.is_active
    db.commit()
    db.refresh(target)
    return _to_detail(db, target)


@router.patch("/{user_id}/role", response_model=AdminUserDetail)
def update_user_role(
    user_id: int,
    data: AdminUserRoleUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_global_roles(UserRole.SYSTEM_ADMIN)),
):
    target = _get_user_or_404(db, user_id)

    if (
        target.role == UserRole.SYSTEM_ADMIN.value
        and target.is_active
        and data.role != UserRole.SYSTEM_ADMIN.value
    ):
        remaining = _active_system_admin_count(db, exclude_user_id=target.id)
        if remaining == 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot change role: this is the last active system_admin.",
            )

    # Organization memberships are never touched here — changing a user's
    # global role has no side effect on their organization_memberships
    # rows; no membership is created, deleted, or altered as a result.
    target.role = data.role
    db.commit()
    db.refresh(target)
    return _to_detail(db, target)
