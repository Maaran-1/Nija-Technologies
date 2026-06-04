"""initial schema - all tables

Revision ID: 0001_initial
Revises: 
Create Date: 2026-06-04

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('zoho_user_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('role', sa.String(100), nullable=True),
        sa.Column('capacity_hours_per_week', sa.Numeric(5, 2), nullable=True, default=40.0),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('zoho_user_id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_users_zoho_user_id', 'users', ['zoho_user_id'])
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_active', 'users', ['is_active'])

    # platform_users table
    op.create_table(
        'platform_users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, default='viewer'),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('zoho_user_id', sa.String(100), nullable=True),
        sa.Column('managed_team_ids', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_platform_users_email', 'platform_users', ['email'])

    # projects table
    op.create_table(
        'projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('zoho_project_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('status', sa.String(50), nullable=True, default='active'),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('budget_hours', sa.Numeric(8, 2), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('zoho_project_id'),
    )
    op.create_index('ix_projects_zoho_project_id', 'projects', ['zoho_project_id'])
    op.create_index('ix_projects_status', 'projects', ['status'])

    # tasks table
    op.create_table(
        'tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('zoho_task_id', sa.String(100), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assigned_to', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('status', sa.String(50), nullable=True, default='open'),
        sa.Column('priority', sa.SmallInteger(), nullable=True),
        sa.Column('estimated_hours', sa.Numeric(6, 2), nullable=True),
        sa.Column('actual_hours', sa.Numeric(6, 2), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.ForeignKeyConstraint(['assigned_to'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('zoho_task_id'),
    )
    op.create_index('ix_tasks_zoho_task_id', 'tasks', ['zoho_task_id'])
    op.create_index('ix_tasks_project_id', 'tasks', ['project_id'])
    op.create_index('ix_tasks_assigned_to', 'tasks', ['assigned_to'])
    op.create_index('ix_tasks_status', 'tasks', ['status'])
    op.create_index('ix_tasks_priority', 'tasks', ['priority'])
    op.create_index('ix_tasks_due_date', 'tasks', ['due_date'])
    op.create_index('ix_tasks_project_assignee', 'tasks', ['project_id', 'assigned_to'])

    # timesheet_entries table
    op.create_table(
        'timesheet_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('zoho_entry_id', sa.String(100), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('work_date', sa.Date(), nullable=False),
        sa.Column('hours_logged', sa.Numeric(5, 2), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('hours_logged > 0', name='check_hours_positive'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('zoho_entry_id'),
    )
    op.create_index('ix_timesheet_zoho_entry_id', 'timesheet_entries', ['zoho_entry_id'])
    op.create_index('ix_timesheet_user_date', 'timesheet_entries', ['user_id', 'work_date'])
    op.create_index('ix_timesheet_task_user', 'timesheet_entries', ['task_id', 'user_id'])
    op.create_index('ix_timesheet_work_date', 'timesheet_entries', ['work_date'])

    # milestones table
    op.create_table(
        'milestones',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('zoho_milestone_id', sa.String(100), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('is_completed', sa.Boolean(), nullable=True, default=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('zoho_milestone_id'),
    )
    op.create_index('ix_milestones_project_due', 'milestones', ['project_id', 'due_date'])

    # utilization_snapshots table
    op.create_table(
        'utilization_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('window_weeks', sa.SmallInteger(), nullable=True, default=2),
        sa.Column('capacity_hours', sa.Numeric(6, 2), nullable=True),
        sa.Column('allocated_hours', sa.Numeric(6, 2), nullable=True),
        sa.Column('logged_hours', sa.Numeric(6, 2), nullable=True),
        sa.Column('utilization_pct', sa.Numeric(5, 2), nullable=True),
        sa.Column('utilization_band', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'snapshot_date', 'window_weeks', name='uq_utilization_snapshot'),
    )
    op.create_index('ix_utilization_user_id', 'utilization_snapshots', ['user_id'])
    op.create_index('ix_utilization_snapshot_date', 'utilization_snapshots', ['snapshot_date'])
    op.create_index('ix_utilization_band', 'utilization_snapshots', ['utilization_band'])
    op.create_index('ix_utilization_user_date', 'utilization_snapshots', ['user_id', 'snapshot_date'])

    # project_health_scores table
    op.create_table(
        'project_health_scores',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scored_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('overall_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('schedule_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('resource_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('velocity_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=True),
        sa.Column('health_band', sa.String(20), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_health_scores_project_id', 'project_health_scores', ['project_id'])
    op.create_index('ix_health_scores_scored_at', 'project_health_scores', ['scored_at'])
    op.create_index('ix_health_scores_project_scored', 'project_health_scores', ['project_id', 'scored_at'])

    # sync_metadata table
    op.create_table(
        'sync_metadata',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sync_count', sa.SmallInteger(), nullable=True, default=0),
        sa.Column('last_sync_status', sa.String(20), nullable=True, default='pending'),
        sa.Column('last_error', sa.String(500), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_type'),
    )

    # recommendations table
    op.create_table(
        'recommendations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('source_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('target_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('projected_source_util', sa.Numeric(5, 2), nullable=True),
        sa.Column('projected_target_util', sa.Numeric(5, 2), nullable=True),
        sa.Column('impact_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('confidence_score', sa.Numeric(5, 2), nullable=True),
        sa.Column('status', sa.String(20), nullable=True, default='pending'),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['source_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['target_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id']),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_recommendations_source_user_id', 'recommendations', ['source_user_id'])
    op.create_index('ix_recommendations_target_user_id', 'recommendations', ['target_user_id'])
    op.create_index('ix_recommendations_task_id', 'recommendations', ['task_id'])
    op.create_index('ix_recommendations_status', 'recommendations', ['status'])
    op.create_index('ix_recommendations_status_created', 'recommendations', ['status', 'created_at'])
    op.create_index('ix_recommendations_type', 'recommendations', ['type'])

    # audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=True),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['actor_id'], ['platform_users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_created_at', 'audit_logs', ['created_at'])
    op.create_index('ix_audit_actor_created', 'audit_logs', ['actor_id', 'created_at'])
    op.create_index('ix_audit_entity', 'audit_logs', ['entity_type', 'entity_id'])


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('recommendations')
    op.drop_table('sync_metadata')
    op.drop_table('project_health_scores')
    op.drop_table('utilization_snapshots')
    op.drop_table('milestones')
    op.drop_table('timesheet_entries')
    op.drop_table('tasks')
    op.drop_table('projects')
    op.drop_table('platform_users')
    op.drop_table('users')
