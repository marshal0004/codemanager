from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import uuid
import json
from app.models import db
from app.models.custom_types import UUIDType, JSONType


class TeamSnippet(db.Model):
    """Independent team snippet model - separate from personal snippets"""

    __tablename__ = "team_snippets"

    # Primary fields
    id = db.Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()))
    team_id = db.Column(UUIDType, db.ForeignKey("teams.id"), nullable=False, index=True)
    original_snippet_id = db.Column(UUIDType, nullable=True)  # Reference to original
    shared_by_id = db.Column(UUIDType, db.ForeignKey("users.id"), nullable=False)

    # Content fields (copied from original)
    title = db.Column(db.String(200), nullable=False)
    code = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(50), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    tags = db.Column(db.String(500), nullable=True)

    # Team-specific fields
    team_permissions = db.Column(
        JSONType,
        default=lambda: {
            "can_edit": True,
            "can_delete": False,
            "can_comment": True,
            "visibility": "team_only",
        },
    )

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    shared_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Status fields
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    version = db.Column(db.Integer, default=1, nullable=False)

    # Analytics
    view_count = db.Column(db.Integer, default=0, nullable=False)
    edit_count = db.Column(db.Integer, default=0, nullable=False)
    last_accessed = db.Column(db.DateTime, nullable=True)

    # Relationships
    team = db.relationship("Team", backref="team_snippets")
    shared_by = db.relationship("User", foreign_keys=[shared_by_id])

    def __init__(self, **kwargs):
        """Initialize team snippet"""
        self.id = kwargs.get("id", str(uuid.uuid4()))
        self.team_id = kwargs["team_id"]
        self.shared_by_id = kwargs["shared_by_id"]
        self.title = kwargs["title"]
        self.code = kwargs["code"]
        self.language = kwargs["language"]
        self.description = kwargs.get("description", "")
        self.tags = kwargs.get("tags", "")
        self.original_snippet_id = kwargs.get("original_snippet_id")

    @classmethod
    def create_from_snippet(cls, snippet, team_id, shared_by_id):
        """Create team snippet copy from personal snippet"""
        return cls(
            team_id=team_id,
            shared_by_id=shared_by_id,
            original_snippet_id=snippet.id,
            title=snippet.title,
            code=snippet.code,
            language=snippet.language,
            description=getattr(snippet, "description", ""),
            tags=snippet.tags or "",
        )

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "team_id": self.team_id,
            "original_snippet_id": self.original_snippet_id,
            "title": self.title,
            "code": self.code,
            "language": self.language,
            "description": self.description,
            "tags": self.tags.split(",") if self.tags else [],
            "shared_by_id": self.shared_by_id,
            "shared_at": self.shared_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "view_count": self.view_count,
            "edit_count": self.edit_count,
            "team_permissions": self.team_permissions,
            "is_active": self.is_active,
            "version": self.version,
        }

    def can_user_edit(self, user_id, user_role):
        """Check if user can edit this team snippet"""
        # Shared by user can always edit
        if str(self.shared_by_id) == str(user_id):
            return True

        # Check team permissions
        if not self.team_permissions.get("can_edit", True):
            return False

        # Role-based permissions
        return user_role.upper() in ["OWNER", "ADMIN", "EDITOR", "MEMBER"]

    def increment_view_count(self):
        """Increment view count"""
        self.view_count += 1
        self.last_accessed = datetime.utcnow()

    def increment_edit_count(self):
        """Increment edit count"""
        self.edit_count += 1
        self.updated_at = datetime.utcnow()
        self.version += 1
