"""add interview_questions, answer_segments, audio_analyses

Revision ID: b4d8f2a917c3
Revises: 7c6f3df24fbd
Create Date: 2026-08-05 00:00:00.000000

Phase 3A: real per-question audio analysis with persistence.

Adds three new tables (`interview_questions`, `answer_segments`,
`audio_analyses`) and one nullable column on the existing `interviews`
table (`recording_completed_at`). Does not alter `users`, `questions`,
`results`, `organizations`, `organization_memberships`, or
`organization_invitations` in any way, and does not touch any existing
row in `interviews`. Existing historical interviews simply have no
`interview_questions`/`answer_segments` rows — the API and frontend treat
that as a legacy record ("Audio analysis not available for this
historical interview."), not an error.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'b4d8f2a917c3'
down_revision: Union[str, None] = '7c6f3df24fbd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'interviews',
        sa.Column('recording_completed_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        'interview_questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('interview_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=True),
        sa.Column('sequence_index', sa.Integer(), nullable=False),
        sa.Column('question_text', sa.String(length=1000), nullable=False),
        sa.Column('difficulty', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.CheckConstraint('sequence_index >= 0', name='ck_interview_questions_sequence_index_non_negative'),
        sa.ForeignKeyConstraint(['interview_id'], ['interviews.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('interview_id', 'sequence_index', name='uq_interview_questions_interview_sequence'),
        sa.UniqueConstraint('interview_id', 'question_id', name='uq_interview_questions_interview_question'),
    )
    op.create_index(op.f('ix_interview_questions_id'), 'interview_questions', ['id'], unique=False)
    op.create_index(op.f('ix_interview_questions_interview_id'), 'interview_questions', ['interview_id'], unique=False)
    op.create_index(op.f('ix_interview_questions_question_id'), 'interview_questions', ['question_id'], unique=False)

    op.create_table(
        'answer_segments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('interview_id', sa.Integer(), nullable=False),
        sa.Column('interview_question_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=True),
        sa.Column('sequence_index', sa.Integer(), nullable=False),
        sa.Column('media_path', sa.String(length=500), nullable=True),
        sa.Column('media_type', sa.String(length=100), nullable=True),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('upload_status', sa.String(length=20), nullable=False),
        sa.Column('processing_status', sa.String(length=30), nullable=False),
        sa.Column('failure_code', sa.String(length=50), nullable=True),
        sa.Column('failure_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.CheckConstraint('sequence_index >= 0', name='ck_answer_segments_sequence_index_non_negative'),
        sa.ForeignKeyConstraint(['interview_id'], ['interviews.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['interview_question_id'], ['interview_questions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('interview_id', 'interview_question_id', name='uq_answer_segments_interview_question'),
    )
    op.create_index(op.f('ix_answer_segments_id'), 'answer_segments', ['id'], unique=False)
    op.create_index(op.f('ix_answer_segments_interview_id'), 'answer_segments', ['interview_id'], unique=False)
    op.create_index(op.f('ix_answer_segments_interview_question_id'), 'answer_segments', ['interview_question_id'], unique=False)

    op.create_table(
        'audio_analyses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('answer_segment_id', sa.Integer(), nullable=False),
        sa.Column('emotion_label', sa.String(length=50), nullable=True),
        sa.Column('emotion_probabilities', sa.JSON(), nullable=True),
        sa.Column('model_confidence', sa.Float(), nullable=True),
        sa.Column('model_confidence_calibrated', sa.Boolean(), nullable=False),
        sa.Column('vocal_delivery_score', sa.Float(), nullable=True),
        sa.Column('speaking_rate_wpm', sa.Float(), nullable=True),
        sa.Column('speaking_rate_score', sa.Float(), nullable=True),
        sa.Column('pause_ratio', sa.Float(), nullable=True),
        sa.Column('pause_control_score', sa.Float(), nullable=True),
        sa.Column('volume_stability_score', sa.Float(), nullable=True),
        sa.Column('speech_continuity_score', sa.Float(), nullable=True),
        sa.Column('sufficient_evidence', sa.Boolean(), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('model_identifier', sa.String(length=200), nullable=True),
        sa.Column('model_version', sa.String(length=100), nullable=True),
        sa.Column('sample_rate_hz', sa.Integer(), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('raw_diagnostic', sa.JSON(), nullable=True),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['answer_segment_id'], ['answer_segments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('answer_segment_id'),
    )
    op.create_index(op.f('ix_audio_analyses_id'), 'audio_analyses', ['id'], unique=False)
    op.create_index(op.f('ix_audio_analyses_answer_segment_id'), 'audio_analyses', ['answer_segment_id'], unique=False)


def downgrade() -> None:
    # Drops only what this migration added. Does not touch users,
    # organizations, organization_memberships, organization_invitations,
    # questions, interviews (other than the added column), or results —
    # no pre-existing data is deleted by this downgrade.
    op.drop_index(op.f('ix_audio_analyses_answer_segment_id'), table_name='audio_analyses')
    op.drop_index(op.f('ix_audio_analyses_id'), table_name='audio_analyses')
    op.drop_table('audio_analyses')

    op.drop_index(op.f('ix_answer_segments_interview_question_id'), table_name='answer_segments')
    op.drop_index(op.f('ix_answer_segments_interview_id'), table_name='answer_segments')
    op.drop_index(op.f('ix_answer_segments_id'), table_name='answer_segments')
    op.drop_table('answer_segments')

    op.drop_index(op.f('ix_interview_questions_question_id'), table_name='interview_questions')
    op.drop_index(op.f('ix_interview_questions_interview_id'), table_name='interview_questions')
    op.drop_index(op.f('ix_interview_questions_id'), table_name='interview_questions')
    op.drop_table('interview_questions')

    op.drop_column('interviews', 'recording_completed_at')
