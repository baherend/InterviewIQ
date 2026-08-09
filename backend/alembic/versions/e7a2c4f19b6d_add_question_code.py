"""add question.code stable provisioning key

Revision ID: e7a2c4f19b6d
Revises: d3f9a1c6e8b4
Create Date: 2026-08-08 00:00:00.000000

Phase 3D: introduces `questions.code` -- a nullable, unique, hand-assigned,
backend-only stable key for provisioning (never exposed via any API,
never derived from text or row order). Replaces the exact-question-text
matching used by the c7e1a4f8b2d5-era SE-028 backfill going forward.

Data backfill (the one and only time exact question text is used to
locate a row -- retired after this):
  - `se-028-tdd`  -> the existing SE-028-mapped question (code only;
    nlp_reference_id was already set by c7e1a4f8b2d5).
  - `da-017-sql-join-inner-left` -> "Explain the difference between INNER
    JOIN and LEFT JOIN in SQL." (Data Analysis), newly mapped to DA-017
    (DA017-C01/C02 are that document's own key_points and state exactly
    INNER JOIN's and LEFT JOIN's definitions).
  - `da-005-missing-values` -> "How do you handle missing values in a
    dataset?" (Data Analysis), newly mapped to DA-005 (a near-exact
    translation match).

Deliberately NOT mapped: "What is the difference between descriptive and
inferential statistics?" -- no matching reference document exists in the
corpus (checked all 50 Data-Analysis-track documents); Phase 3D's
acceptance test uses this question to verify the NO_REFERENCE_DOCUMENT
gate, not an oversight.

Does not alter any other table, and does not touch any other existing
row.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e7a2c4f19b6d'
down_revision: Union[str, None] = 'd3f9a1c6e8b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SE_028_TEXT = "ما هو TDD وما دورته؟"
_DA_017_TEXT = "Explain the difference between INNER JOIN and LEFT JOIN in SQL."
_DA_005_TEXT = "How do you handle missing values in a dataset?"


def upgrade() -> None:
    op.add_column('questions', sa.Column('code', sa.String(length=50), nullable=True))
    with op.batch_alter_table('questions') as batch_op:
        batch_op.create_unique_constraint('uq_questions_code', ['code'])

    questions = sa.table(
        'questions',
        sa.column('question', sa.String),
        sa.column('code', sa.String),
        sa.column('nlp_reference_id', sa.String),
    )
    op.execute(
        questions.update()
        .where(questions.c.question == _SE_028_TEXT)
        .values(code='se-028-tdd')
    )
    op.execute(
        questions.update()
        .where(questions.c.question == _DA_017_TEXT)
        .values(code='da-017-sql-join-inner-left', nlp_reference_id='DA-017')
    )
    op.execute(
        questions.update()
        .where(questions.c.question == _DA_005_TEXT)
        .values(code='da-005-missing-values', nlp_reference_id='DA-005')
    )


def downgrade() -> None:
    questions = sa.table(
        'questions',
        sa.column('code', sa.String),
        sa.column('nlp_reference_id', sa.String),
    )
    op.execute(
        questions.update()
        .where(questions.c.code.in_(['da-017-sql-join-inner-left', 'da-005-missing-values']))
        .values(nlp_reference_id=None)
    )
    with op.batch_alter_table('questions') as batch_op:
        batch_op.drop_constraint('uq_questions_code', type_='unique')
        batch_op.drop_column('code')
