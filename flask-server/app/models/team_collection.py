from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid
import json
from app.models import db
from app.models.custom_types import UUIDType, JSONType

# Association table for team collections and team snippets
team_snippet_collections = db.Table(
    "team_snippet_collections",
    db.Column(
        "team_snippet_id", UUIDType, db.ForeignKey("team_snippets.id"), primary_key=True
    ),
    db.Column(
        "team_collection_id",
        UUIDType,
        db.ForeignKey("team_collections.id"),
        primary_key=True,
    ),
)


class TeamCollection(db.Model):
    """Independent team collection model - separate from personal collections"""

    __tablename__ = "team_collections"

    # Primary fields
    id = db.Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()))
    team_id = db.Column(UUIDType, db.ForeignKey("teams.id"), nullable=False, index=True)
    original_collection_id = db.Column(UUIDType, nullable=True)  # Reference to original
    shared_by_id = db.Column(UUIDType, db.ForeignKey("users.id"), nullable=False)

    # Content fields (copied from original)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    color = db.Column(db.String(7), default="#3B82F6", nullable=False)
    icon = db.Column(db.String(50), default="📁", nullable=False)

    # Team-specific fields
    team_permissions = db.Column(
        JSONType,
        default=lambda: {
            "can_edit": True,
            "can_delete": False,
            "can_add_snippets": True,
            "visibility": "team_only",
        },
    )

    # Organization
    parent_id = db.Column(UUIDType, db.ForeignKey("team_collections.id"), nullable=True)
    sort_order = db.Column(db.Integer, default=0)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    shared_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Status fields
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Analytics
    view_count = db.Column(db.Integer, default=0, nullable=False)
    access_count = db.Column(db.Integer, default=0, nullable=False)
    last_accessed = db.Column(db.DateTime, nullable=True)

    # Relationships
    team = db.relationship("Team", backref="team_collections")
    shared_by = db.relationship("User", foreign_keys=[shared_by_id])
    team_snippets = db.relationship(
        "TeamSnippet", secondary=team_snippet_collections, backref="team_collections"
    )

    # Hierarchical relationships
    parent = db.relationship(
        "TeamCollection",
        remote_side=[id],
        backref=db.backref("children", lazy="dynamic"),
    )

    def __init__(self, **kwargs):
        """Initialize team collection"""
        self.id = kwargs.get("id", str(uuid.uuid4()))
        self.team_id = kwargs["team_id"]
        self.shared_by_id = kwargs["shared_by_id"]
        self.name = kwargs["name"]
        self.description = kwargs.get("description", "")
        self.color = kwargs.get("color", "#3B82F6")
        self.icon = kwargs.get("icon", "📁")
        self.original_collection_id = kwargs.get("original_collection_id")
        self.parent_id = kwargs.get("parent_id")

    @classmethod
    def create_from_collection(cls, collection, team_id, shared_by_id):
        """Create team collection copy from personal collection"""
        return cls(
            team_id=team_id,
            shared_by_id=shared_by_id,
            original_collection_id=collection.id,
            name=collection.name,
            description=collection.description or "",
            color=getattr(collection, "color", "#3B82F6"),
            icon=getattr(collection, "icon", "📁"),
        )

    def to_dict(self, include_snippets=False):
        """Convert to dictionary"""
        data = {
            "id": self.id,
            "team_id": self.team_id,
            "original_collection_id": self.original_collection_id,
            "name": self.name,
            "description": self.description,
            "color": self.color,
            "icon": self.icon,
            "shared_by_id": self.shared_by_id,
            "shared_at": self.shared_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "view_count": self.view_count,
            "access_count": self.access_count,
            "team_permissions": self.team_permissions,
            "is_active": self.is_active,
            "snippet_count": len(self.team_snippets),
            "parent_id": self.parent_id,
            "sort_order": self.sort_order,
        }

        if include_snippets:
            data["snippets"] = [snippet.to_dict() for snippet in self.team_snippets]

        return data

    def can_user_edit(self, user_id, user_role):
        """Check if user can edit this team collection"""
        # Shared by user can always edit
        if str(self.shared_by_id) == str(user_id):
            return True

        # Check team permissions
        if not self.team_permissions.get("can_edit", True):
            return False

        # Role-based permissions
        return user_role.upper() in ["OWNER", "ADMIN", "EDITOR", "MEMBER"]

    def add_team_snippet(self, team_snippet):
        """Add team snippet to this collection"""
        if team_snippet not in self.team_snippets:
            self.team_snippets.append(team_snippet)
            self.updated_at = datetime.utcnow()
            return True
        return False

    def remove_team_snippet(self, team_snippet):
        """Remove team snippet from this collection"""
        if team_snippet in self.team_snippets:
            self.team_snippets.remove(team_snippet)
            self.updated_at = datetime.utcnow()
            return True
        return False

    def increment_view_count(self):
        """Increment view count"""
        self.view_count += 1
        self.access_count += 1
        self.last_accessed = datetime.utcnow()
