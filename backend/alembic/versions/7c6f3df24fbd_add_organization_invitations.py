"""add organization invitations

Revision ID: 7c6f3df24fbd
Revises: 5112e9dff333
Create Date: 2026-07-26 00:49:01.844873

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '7c6f3df24fbd'
down_revision: Union[str, None] = '5112e9dff333'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Phase 2D: adds a single new table only. Does not alter users,
    # organizations, organization_memberships, questions, interviews, or
    # results in any way — reviewed against the raw `alembic revision
    # --autogenerate` output, which proposed exactly these operations and
    # nothing else (no unrelated drift was detected).
    op.create_table(
        'organization_invitations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        # Always normalized lowercase by the Pydantic schema before a row
        # is inserted (see app/schemas/invitation.py).
        sa.Column('email', sa.String(length=255), nullable=False),
        # Validated at the application layer against {admin, interviewer,
        # candidate} only — owner and system_admin can never be invited.
        sa.Column('membership_role', sa.String(length=20), nullable=False),
        # SHA-256 hex digest of the raw token. The raw token itself is
        # never persisted anywhere — see app/auth/invitation_tokens.py.
        sa.Column('token_hash', sa.String(length=128), nullable=False),
        # pending | accepted | revoked | expired — plain string, validated
        # at the application layer, same pattern as organizations.status.
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('accepted_by_user_id', sa.Integer(), nullable=True),
        # SET NULL (not CASCADE) on the two user references: this app has
        # no user-deletion endpoint today, but if a user row were ever
        # removed, the invitation history should survive with a null
        # creator/acceptor rather than disappearing.
        sa.ForeignKeyConstraint(['accepted_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_organization_invitations_email'), 'organization_invitations', ['email'], unique=False)
    op.create_index(op.f('ix_organization_invitations_expires_at'), 'organization_invitations', ['expires_at'], unique=False)
    op.create_index(op.f('ix_organization_invitations_id'), 'organization_invitations', ['id'], unique=False)
    op.create_index(op.f('ix_organization_invitations_organization_id'), 'organization_invitations', ['organization_id'], unique=False)
    op.create_index(op.f('ix_organization_invitations_status'), 'organization_invitations', ['status'], unique=False)
    # Unique, not just indexed: token lookup must resolve to at most one
    # row, and a duplicate hash would indicate a collision or a bug.
    op.create_index(op.f('ix_organization_invitations_token_hash'), 'organization_invitations', ['token_hash'], unique=True)
    # Partial unique index (not a plain unique constraint): enforces "at
    # most one PENDING invitation per organization+email" at the database
    # level as a race-condition backstop, while still allowing a brand
    # new invitation to be created for the same organization+email once an
    # old one has been accepted, revoked, or (lazily) marked expired —
    # see README_LOCAL_SETUP.md.
    pending_predicate = sa.text("status = 'pending'")
    op.create_index(
        'uq_org_invitations_pending_org_email',
        'organization_invitations',
        ['organization_id', 'email'],
        unique=True,
        postgresql_where=pending_predicate,
        sqlite_where=pending_predicate,
    )


def downgrade() -> None:
    # Drops only what this migration added: the organization_invitations
    # table and its indexes. Does not touch users, organizations,
    # organization_memberships, questions, interviews, or results — no
    # existing data is deleted by this downgrade.
    op.drop_index('uq_org_invitations_pending_org_email', table_name='organization_invitations')
    op.drop_index(op.f('ix_organization_invitations_token_hash'), table_name='organization_invitations')
    op.drop_index(op.f('ix_organization_invitations_status'), table_name='organization_invitations')
    op.drop_index(op.f('ix_organization_invitations_organization_id'), table_name='organization_invitations')
    op.drop_index(op.f('ix_organization_invitations_id'), table_name='organization_invitations')
    op.drop_index(op.f('ix_organization_invitations_expires_at'), table_name='organization_invitations')
    op.drop_index(op.f('ix_organization_invitations_email'), table_name='organization_invitations')
    op.drop_table('organization_invitations')
