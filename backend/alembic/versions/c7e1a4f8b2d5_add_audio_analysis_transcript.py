"""add transcript and transcript_status to audio_analyses

Revision ID: c7e1a4f8b2d5
Revises: b4d8f2a917c3
Create Date: 2026-08-06 00:00:00.000000

Phase 3B: per-question ASR and completed vocal delivery metrics.

Adds two nullable columns to the existing `audio_analyses` table only —
`transcript` (the real per-question transcript produced by the existing
ASR implementation) and `transcript_status` (the ASR engine's own
ok/no_speech/too_short status). Does not alter any other table, and does
not touch any existing row (both columns default to NULL for every
pre-Phase-3B row, which the API/frontend already treat as "not
available", not an error).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c7e1a4f8b2d5'
down_revision: Union[str, None] = 'b4d8f2a917c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('audio_analyses', sa.Column('transcript', sa.Text(), nullable=True))
    op.add_column('audio_analyses', sa.Column('transcript_status', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('audio_analyses', 'transcript_status')
    op.drop_column('audio_analyses', 'transcript')
