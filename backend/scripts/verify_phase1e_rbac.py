"""Phase 1E RBAC verification script.

Exercises the authorization primitives in app.auth.permissions directly
against a real database session — in particular `require_organization_roles`
and the organization-status policy, which are not wired to any HTTP route in
this phase (no existing endpoint needs a specific membership role yet).

This is a repeatable local verification script, not an automated test suite
(the project has none). It creates a small amount of clearly-marked,
temporary test data (a scratch organization + memberships) and deletes it
again before exiting, regardless of pass/fail. It never touches the
pre-existing seeded questions or any data from earlier phases.

Run inside the backend container:
    docker compose exec backend python scripts/verify_phase1e_rbac.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException

from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.organization import Organization, OrganizationStatus
from app.models.organization_membership import OrganizationMembership, MembershipRole
from app.auth.password import hash_password
from app.auth.jwt_handler import create_access_token, verify_token
from app.auth.permissions import (
    require_global_roles,
    require_organization_roles,
    require_organization_access,
    ensure_organization_status_accessible,
    get_active_membership,
)

PASS = []
FAIL = []


def check(name: str, condition: bool, detail: str = ""):
    if condition:
        PASS.append(name)
        print(f"PASS: {name}")
    else:
        FAIL.append(name)
        print(f"FAIL: {name} {detail}")


def expect_http_exception(status_code: int, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return False, None
    except HTTPException as exc:
        return exc.status_code == status_code, exc.status_code


def main():
    db = SessionLocal()
    created_user_ids = []
    created_org_id = None
    try:
        # --- Set up scratch test data -------------------------------------
        def make_user(email_suffix: str, role: str) -> User:
            u = User(
                name=f"Phase1E RBAC Verify {email_suffix}",
                email=f"phase1e-rbacverify-{email_suffix}@interviewiq-smoketest.dev",
                password_hash=hash_password("not-a-real-login-password"),
                role=role,
            )
            db.add(u)
            db.flush()
            created_user_ids.append(u.id)
            return u

        student_user = make_user("student", UserRole.STUDENT.value)
        company_admin_user = make_user("companyadmin", UserRole.COMPANY_ADMIN.value)
        system_admin_user = make_user("sysadmin", UserRole.SYSTEM_ADMIN.value)
        owner_active_user = make_user("owner-active", UserRole.STUDENT.value)
        admin_active_user = make_user("admin-active", UserRole.STUDENT.value)
        interviewer_active_user = make_user("interviewer-active", UserRole.STUDENT.value)
        candidate_active_user = make_user("candidate-active", UserRole.STUDENT.value)
        owner_inactive_user = make_user("owner-inactive", UserRole.STUDENT.value)
        nonmember_user = make_user("nonmember", UserRole.STUDENT.value)

        org = Organization(
            name="Phase1E RBAC Verify Org",
            slug="phase1e-rbac-verify-org",
            status=OrganizationStatus.ACTIVE.value,
        )
        db.add(org)
        db.flush()
        created_org_id = org.id

        def make_membership(user: User, role: str, active: bool) -> OrganizationMembership:
            m = OrganizationMembership(
                organization_id=org.id, user_id=user.id, membership_role=role, is_active=active
            )
            db.add(m)
            db.flush()
            return m

        make_membership(owner_active_user, MembershipRole.OWNER.value, True)
        make_membership(admin_active_user, MembershipRole.ADMIN.value, True)
        make_membership(interviewer_active_user, MembershipRole.INTERVIEWER.value, True)
        make_membership(candidate_active_user, MembershipRole.CANDIDATE.value, True)
        make_membership(owner_inactive_user, MembershipRole.OWNER.value, False)

        db.commit()

        # --- Test A: DB is the source of truth ------------------------------
        token = create_access_token({"sub": str(student_user.id)})
        payload = verify_token(token)
        check(
            "A1: JWT payload carries no role claim",
            "role" not in payload,
            f"payload={payload}",
        )
        db.refresh(student_user)
        check(
            "A2: role for authorization is read from DB, not token",
            student_user.role == UserRole.STUDENT.value,
        )

        # --- Test B: global-role checks --------------------------------------
        sysadmin_only = require_global_roles(UserRole.SYSTEM_ADMIN)
        try:
            result = sysadmin_only(current_user=system_admin_user)
            check("B1: system_admin passes system-admin-only dependency", result is system_admin_user)
        except HTTPException:
            check("B1: system_admin passes system-admin-only dependency", False)

        ok, code = expect_http_exception(403, sysadmin_only, current_user=student_user)
        check("B2: student fails system-admin-only dependency with 403", ok, f"got {code}")

        ok, code = expect_http_exception(403, sysadmin_only, current_user=company_admin_user)
        check(
            "B3: company_admin (global role only, no membership) fails system-admin-only dependency with 403",
            ok,
            f"got {code}",
        )

        # --- Test C: membership checks ---------------------------------------
        mgmt_only = require_organization_roles(MembershipRole.OWNER, MembershipRole.ADMIN)

        try:
            mgmt_only(organization_id=org.id, db=db, current_user=owner_active_user)
            check("C1: active owner passes management-role helper", True)
        except HTTPException as exc:
            check("C1: active owner passes management-role helper", False, f"raised {exc.status_code}")

        try:
            mgmt_only(organization_id=org.id, db=db, current_user=admin_active_user)
            check("C2: active admin passes management-role helper", True)
        except HTTPException as exc:
            check("C2: active admin passes management-role helper", False, f"raised {exc.status_code}")

        ok, code = expect_http_exception(
            403, mgmt_only, organization_id=org.id, db=db, current_user=interviewer_active_user
        )
        check("C3: active interviewer fails management-role helper with 403", ok, f"got {code}")

        ok, code = expect_http_exception(
            403, mgmt_only, organization_id=org.id, db=db, current_user=candidate_active_user
        )
        check("C4: active candidate fails management-role helper with 403", ok, f"got {code}")

        ok, code = expect_http_exception(
            403, mgmt_only, organization_id=org.id, db=db, current_user=owner_inactive_user
        )
        check("C5: inactive owner fails management-role helper with 403", ok, f"got {code}")

        ok, code = expect_http_exception(
            403, mgmt_only, organization_id=org.id, db=db, current_user=nonmember_user
        )
        check("C6: non-member fails management-role helper with 403", ok, f"got {code}")

        membership = get_active_membership(db, org.id, owner_inactive_user.id)
        check("C7: inactive membership is not returned by get_active_membership", membership is None)

        # --- Test D: organization status policy ------------------------------
        org.status = OrganizationStatus.ACTIVE.value
        try:
            ensure_organization_status_accessible(org, admin_bypass=False)
            check("D1: active org accessible to normal member", True)
        except HTTPException:
            check("D1: active org accessible to normal member", False)

        org.status = OrganizationStatus.PENDING.value
        try:
            ensure_organization_status_accessible(org, admin_bypass=False)
            check("D2: pending org accessible to normal (active) member", True)
        except HTTPException:
            check("D2: pending org accessible to normal (active) member", False)

        org.status = OrganizationStatus.SUSPENDED.value
        ok, code = expect_http_exception(
            403, ensure_organization_status_accessible, org, admin_bypass=False
        )
        check("D3: suspended org blocks normal member with 403", ok, f"got {code}")

        try:
            ensure_organization_status_accessible(org, admin_bypass=True)
            check("D4: system_admin can still read suspended org", True)
        except HTTPException:
            check("D4: system_admin can still read suspended org", False)

        # require_organization_access end-to-end (suspended, real dependency)
        db.flush()
        ok, code = expect_http_exception(
            403, require_organization_access, organization_id=org.id, db=db, current_user=owner_active_user
        )
        check(
            "D5: require_organization_access blocks active member on suspended org with 403",
            ok,
            f"got {code}",
        )
        try:
            require_organization_access(organization_id=org.id, db=db, current_user=system_admin_user)
            check("D6: require_organization_access allows system_admin on suspended org", True)
        except HTTPException as exc:
            check(
                "D6: require_organization_access allows system_admin on suspended org",
                False,
                f"raised {exc.status_code}",
            )

        org.status = OrganizationStatus.ACTIVE.value
        db.flush()

    finally:
        # --- Clean up: delete only what this script created -------------------
        db.rollback()
        if created_org_id is not None:
            db.query(OrganizationMembership).filter(
                OrganizationMembership.organization_id == created_org_id
            ).delete()
            db.query(Organization).filter(Organization.id == created_org_id).delete()
        if created_user_ids:
            db.query(User).filter(User.id.in_(created_user_ids)).delete(synchronize_session=False)
        db.commit()
        db.close()
        print(f"\nCleaned up {len(created_user_ids)} test user(s) and org id={created_org_id}.")

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed.")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    main()
