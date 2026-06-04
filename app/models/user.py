import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Numeric, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    """Zoho-sourced employee/user data."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zoho_user_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    role = Column(String(100))  # developer, designer, QA, PM, etc.
    capacity_hours_per_week = Column(Numeric(5, 2), default=40.0)
    is_active = Column(Boolean, default=True)
    synced_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    assigned_tasks = relationship("Task", back_populates="assignee", foreign_keys="Task.assigned_to")
    timesheet_entries = relationship("TimesheetEntry", back_populates="user")
    utilization_snapshots = relationship("UtilizationSnapshot", back_populates="user")
    source_recommendations = relationship("Recommendation", back_populates="source_user",
                                          foreign_keys="Recommendation.source_user_id")
    target_recommendations = relationship("Recommendation", back_populates="target_user",
                                          foreign_keys="Recommendation.target_user_id")
    reviewed_recommendations = relationship("Recommendation", back_populates="reviewer",
                                            foreign_keys="Recommendation.reviewed_by")

    __table_args__ = (
        Index("ix_users_active", "is_active"),
    )

    def __repr__(self):
        return f"<User id={self.id} name={self.name} email={self.email}>"


class PlatformUser(Base):
    """Internal platform users (managers, admins, viewers) — separate from Zoho users."""
    __tablename__ = "platform_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="viewer")  # admin, manager, viewer
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime(timezone=True))
    zoho_user_id = Column(String(100))  # optional link to a Zoho user record
    managed_team_ids = Column(Text)  # JSON list of Zoho user IDs this manager oversees
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<PlatformUser id={self.id} email={self.email} role={self.role}>"
