"""quota scopes: add scope to usage/anon_usage and update unique constraints

Revision ID: 148707ac5f25
Revises: 7c8c6e158ca7
Create Date: 2025-11-10 00:18:10.550352
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '148707ac5f25'
down_revision = '7c8c6e158ca7'
branch_labels = None
depends_on = None


def upgrade():
    # --- ANON (일간) ---
    with op.batch_alter_table('anon_usage', schema=None) as batch_op:
        # 1) scope 추가 (임시 기본값 'rewrite'로 데이터 채우기)
        batch_op.add_column(
            sa.Column('scope', sa.String(length=32), server_default='rewrite', nullable=True)
        )
    # 2) 기존 행들 scope 업데이트(혹시 null인 행 대비)
    op.execute("UPDATE anon_usage SET scope = 'rewrite' WHERE scope IS NULL")

    with op.batch_alter_table('anon_usage', schema=None) as batch_op:
        # 3) NOT NULL 로 전환 + 기본값 제거
        batch_op.alter_column('scope', existing_type=sa.String(length=32),
                              nullable=False, server_default=None)
        # 4) 기존 unique 제거 → 신규 unique 생성
        batch_op.drop_constraint('uq_anon_key_window', type_='unique')
        batch_op.create_index('ix_anon_scope_window', ['scope', 'window_start'], unique=False)
        batch_op.create_index(batch_op.f('ix_anon_usage_scope'), ['scope'], unique=False)
        batch_op.create_unique_constraint(
            'uq_anon_key_scope_window', ['anon_key', 'scope', 'window_start']
        )

    # --- USAGE (월간) ---
    with op.batch_alter_table('usage', schema=None) as batch_op:
        # 1) scope 추가 (임시 기본값 'rewrite')
        batch_op.add_column(
            sa.Column('scope', sa.String(length=32), server_default='rewrite', nullable=True)
        )
    # 2) 기존 행들 scope 업데이트
    op.execute("UPDATE usage SET scope = 'rewrite' WHERE scope IS NULL")

    with op.batch_alter_table('usage', schema=None) as batch_op:
        # 3) NOT NULL + 기본값 제거
        batch_op.alter_column('scope', existing_type=sa.String(length=32),
                              nullable=False, server_default=None)
        # 4) 기존 unique 제거 → 신규 unique 생성
        batch_op.drop_constraint('uq_usage_user_tier_window', type_='unique')
        batch_op.create_index(batch_op.f('ix_usage_scope'), ['scope'], unique=False)
        batch_op.create_index('ix_usage_scope_window', ['scope', 'window_start'], unique=False)
        batch_op.create_unique_constraint(
            'uq_usage_user_tier_scope_window',
            ['user_id', 'tier', 'scope', 'window_start']
        )


def downgrade():
    # --- USAGE (월간) 되돌리기 ---
    with op.batch_alter_table('usage', schema=None) as batch_op:
        batch_op.drop_constraint('uq_usage_user_tier_scope_window', type_='unique')
        batch_op.drop_index('ix_usage_scope_window')
        batch_op.drop_index(batch_op.f('ix_usage_scope'))
        # 원래 unique 복구 (아래 매개변수는 PG가 있으면 그대로 두어도 무해)
        batch_op.create_unique_constraint(
            'uq_usage_user_tier_window', ['user_id', 'tier', 'window_start']
        )
        batch_op.drop_column('scope')

    # --- ANON (일간) 되돌리기 ---
    with op.batch_alter_table('anon_usage', schema=None) as batch_op:
        batch_op.drop_constraint('uq_anon_key_scope_window', type_='unique')
        batch_op.drop_index(batch_op.f('ix_anon_usage_scope'))
        batch_op.drop_index('ix_anon_scope_window')
        batch_op.create_unique_constraint(
            'uq_anon_key_window', ['anon_key', 'window_start']
        )
        batch_op.drop_column('scope')
