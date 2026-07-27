"""add users is_active

Revision ID: 5112e9dff333
Revises: 4e460b268b46
Create Date: 2026-07-22 23:38:11.289454

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '5112e9dff333'
down_revision: Union[str, None] = '4e460b268b46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Manually rewritten from the raw autogenerate output, which proposed a
    # single `ADD COLUMN is_active BOOLEAN NOT NULL` with no default — this
    # would fail immediately against any existing row (Postgres rejects a
    # NOT NULL column add with no default/backfill on a non-empty table).
    # Safe sequence: add nullable -> backfill existing rows -> enforce
    # NOT NULL -> index. No application-side default is relied on here;
    # the backfill is an explicit UPDATE executed by this migration.

    # 1. Add the column as nullable so existing rows are unaffected.
    op.add_column('users', sa.Column('is_active', sa.Boolean(), nullable=True))

    # 2. Backfill every existing user to active (true). No account has
    #    been administratively suspended before this migration exists, so
    #    this correctly represents reality; it does not change ids,
    #    emails, names, roles, or password hashes.
    users_table = sa.table('users', sa.column('is_active', sa.Boolean()))
    op.execute(users_table.update().values(is_active=True))

    # 3. Now that every row has a value, enforce NOT NULL at the DB level.
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column(
            'is_active', existing_type=sa.Boolean(), nullable=False
        )

    # 4. Index, matching the model's `index=True` on this column (used as
    #    a primary filter in the admin user-list endpoint).
    op.create_index(op.f('ix_users_is_active'), 'users', ['is_active'], unique=False)


def downgrade() -> None:
    # Removes only what this migration added: the is_active column and its
    # index. Does not touch any other column, table, or row — no user data
    # is deleted by this downgrade, and roles/organizations/memberships/
    # questions/interviews/results are untouched.
    op.drop_index(op.f('ix_users_is_active'), table_name='users')
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('is_active')
