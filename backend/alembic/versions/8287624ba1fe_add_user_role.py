"""add user role

Revision ID: 8287624ba1fe
Revises: 48e6b0ce95ae
Create Date: 2026-07-22 20:15:10.689444

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '8287624ba1fe'
down_revision: Union[str, None] = '48e6b0ce95ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Manually rewritten from the raw autogenerate output, which proposed a
    # single `ADD COLUMN role VARCHAR(20) NOT NULL` with no default — this
    # would fail immediately against any existing row (Postgres rejects a
    # NOT NULL column add with no default/backfill on a non-empty table).
    # Safe sequence: add nullable -> backfill existing rows -> enforce
    # NOT NULL -> index. No application-side default is relied on here;
    # the backfill is an explicit UPDATE executed by this migration.

    # 1. Add the column as nullable so existing rows are unaffected.
    op.add_column('users', sa.Column('role', sa.String(length=20), nullable=True))

    # 2. Backfill every existing user to 'student'. Public registration
    #    already only ever creates 'student' accounts, so this correctly
    #    represents what every pre-existing account already was in
    #    practice; it does not change ids, emails, names, or password
    #    hashes.
    users_table = sa.table('users', sa.column('role', sa.String(length=20)))
    op.execute(users_table.update().values(role='student'))

    # 3. Now that every row has a value, enforce NOT NULL at the DB level.
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column(
            'role', existing_type=sa.String(length=20), nullable=False
        )

    # 4. Index, matching the model's `index=True` on this column.
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)


def downgrade() -> None:
    # Removes only what this migration added: the role column and its
    # index. Does not touch any other column, table, or row — no user data
    # is deleted by this downgrade.
    op.drop_index(op.f('ix_users_role'), table_name='users')
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('role')
