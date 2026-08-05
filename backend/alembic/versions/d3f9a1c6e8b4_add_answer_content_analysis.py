"""add answer content analysis and question nlp_reference_id

Revision ID: d3f9a1c6e8b4
Revises: c7e1a4f8b2d5
Create Date: 2026-08-06 00:00:00.000000

Phase 3C: real Answer Content Score (claim decomposition -> BGE-M3
retrieval -> NLI -> Precision/Coverage/Score), wired per persisted
answer segment.

Adds:
  - `questions.nlp_reference_id` (nullable) -- the NLP module's
    reference-document ID (e.g. "SE-028") for questions that have one.
    NULL for every other question; no fuzzy/guessed mapping.
  - `answer_content_analyses` -- new table, 1:1 with `answer_segments`
    (unique FK, ON DELETE CASCADE), mirroring the existing
    `audio_analyses` table's shape.

Data backfill: sets `nlp_reference_id = 'SE-028'` on the one existing
seeded question whose text was manually copied from that exact
reference-doc entry (see backend/app/utils/seed.py's own comment) --
every other row is left untouched.

Does not alter any other table, and does not touch any other existing
row.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd3f9a1c6e8b4'
down_revision: Union[str, None] = 'c7e1a4f8b2d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SE_028_QUESTION_TEXT = "ما هو TDD وما دورته؟"


def upgrade() -> None:
    op.add_column('questions', sa.Column('nlp_reference_id', sa.String(length=20), nullable=True))

    op.create_table(
        'answer_content_analyses',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column(
            'answer_segment_id', sa.Integer(),
            sa.ForeignKey('answer_segments.id', ondelete='CASCADE'),
            nullable=False, unique=True, index=True,
        ),
        sa.Column('status', sa.String(length=30), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('question_reference_id', sa.String(length=20), nullable=True),
        sa.Column('precision', sa.Float(), nullable=True),
        sa.Column('coverage', sa.Float(), nullable=True),
        sa.Column('harmonic_f', sa.Float(), nullable=True),
        sa.Column('answer_content_score', sa.Float(), nullable=True),
        sa.Column('claims', sa.JSON(), nullable=True),
        sa.Column('claim_scores', sa.JSON(), nullable=True),
        sa.Column('model_identifiers', sa.JSON(), nullable=True),
        sa.Column('raw_diagnostic', sa.JSON(), nullable=True),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    questions = sa.table(
        'questions',
        sa.column('question', sa.String),
        sa.column('nlp_reference_id', sa.String),
    )
    op.execute(
        questions.update()
        .where(questions.c.question == _SE_028_QUESTION_TEXT)
        .values(nlp_reference_id='SE-028')
    )


def downgrade() -> None:
    op.drop_table('answer_content_analyses')
    op.drop_column('questions', 'nlp_reference_id')
