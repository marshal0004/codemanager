from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import re
from datetime import datetime, timezone, timedelta
from sqlalchemy import event
import json
from enum import Enum
from ..models.user import User
from ..models.team_member import TeamMember
from sqlalchemy.dialects.postgresql import UUID
from app.models import db
import uuid
from app.models.custom_types import UUIDType, JSONType

# Association table for many-to-many relationship between snippets and collections
snippet_collections = db.Table(
    "snippet_collections",
    db.Column("snippet_id", UUIDType, db.ForeignKey("snippets.id"), primary_key=True),
    db.Column(
        "collection_id", UUIDType, db.ForeignKey("collections.id"), primary_key=True
    ),
)


# ADD these new classes before the Snippet model:
class SharePermission(Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


class SnippetStatus(Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


from app.models import db


class Snippet(db.Model):
    __tablename__ = "snippets"
    # Versioning fields
    # Relationships
    user = db.relationship(
        "User", back_populates="snippets", foreign_keys="[Snippet.user_id]"
    )
    collections = db.relationship(
        "Collection", secondary=snippet_collections, back_populates="snippets"
    )
    # Replace these relationship definitions in snippet.py
    version = db.Column(db.Integer, default=1, nullable=False)
    parent_version_id = db.Column(
        db.Integer, db.ForeignKey("snippets.id"), nullable=True
    )
    version_notes = db.Column(db.Text, nullable=True)
    # Team sharing and collaboration fields
    team_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("teams.id"), nullable=True, index=True
    )
    team = db.relationship("Team", back_populates="snippets", foreign_keys=[team_id])

    is_team_snippet = db.Column(db.Boolean, default=False, nullable=False)
    share_permission = db.Column(db.Enum(SharePermission), default=SharePermission.READ)
    is_public = db.Column(db.Boolean, default=False, nullable=False)
    public_url = db.Column(db.String(255), unique=True, nullable=True)
    # Team sharing fields (ADD THESE AFTER line ~85)
    shared_team_ids = db.Column(db.JSON, nullable=True)  # Store team IDs snippet is shared with
    team_permissions = db.Column(db.JSON, nullable=True)  # Store team-specific permissions

    # Collaborative editing
    is_collaborative = db.Column(db.Boolean, default=False, nullable=False)
    current_editors = db.Column(db.Text, nullable=True)  # JSON array of user IDs
    last_editor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    edit_session_id = db.Column(db.String(100), nullable=True)

    # Versioning and history
    version_number = db.Column(db.Integer, default=1, nullable=False)

    is_version = db.Column(db.Boolean, default=False, nullable=False)
    version_note = db.Column(db.Text, nullable=True)

    # Advanced metadata
    status = db.Column(
        db.Enum(SnippetStatus), default=SnippetStatus.ACTIVE, nullable=False
    )
    execution_count = db.Column(db.Integer, default=0, nullable=False)
    last_executed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    execution_time_ms = db.Column(db.Integer, nullable=True)

    # Analytics and usage tracking
    view_count = db.Column(db.Integer, default=0, nullable=False)
    copy_count = db.Column(db.Integer, default=0, nullable=False)
    share_count = db.Column(db.Integer, default=0, nullable=False)
    last_viewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    unique_viewers = db.Column(db.Text, nullable=True)  # JSON array of user IDs

    # External integrations
    github_gist_id = db.Column(db.String(100), nullable=True)
    github_repo_path = db.Column(db.String(500), nullable=True)
    slack_shared_channels = db.Column(db.Text, nullable=True)  # JSON array

    # AI and smart features
    ai_generated_summary = db.Column(db.Text, nullable=True)
    complexity_score = db.Column(db.Float, nullable=True)
    suggested_improvements = db.Column(db.Text, nullable=True)  # JSON array
    similar_snippets = db.Column(db.Text, nullable=True)  # JSON array of snippet IDs

    # ADD these new relationships:

    last_editor = db.relationship("User", foreign_keys=[last_editor_id], lazy=True)
    versions = db.relationship(
        "Snippet",
        backref=db.backref("parent_version", remote_side="Snippet.id"),
        lazy="dynamic",
    )

    # Sharing fields

    share_token = db.Column(db.String(64), unique=True, nullable=True)
    share_expires_at = db.Column(db.DateTime, nullable=True)

    # Analytics fields

    last_accessed = db.Column(db.DateTime, nullable=True)

    # Enhanced metadata
    file_extension = db.Column(db.String(10), nullable=True)
    original_url = db.Column(
        db.String(500), nullable=True
    )  # URL where snippet was captured
    source_type = db.Column(
        db.String(50), default="manual", nullable=False
    )  # manual, extension, import

    # Performance tracking
    execution_time = db.Column(db.Float, nullable=True)  # For code that can be executed
    memory_usage = db.Column(db.Integer, nullable=True)

    # Collaboration
    collaborators = db.relationship(
        "User",
        secondary="snippet_collaborators",
        backref=db.backref("collaborated_snippets", lazy="dynamic"),
        lazy="dynamic",
    )

    id = db.Column(UUIDType, primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUIDType, db.ForeignKey("users.id"), nullable=False, index=True)
    order = db.Column(db.Integer, default=0)
    execution_count = db.Column(db.Integer, default=0)
    last_executed = db.Column(db.DateTime)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)  # ADD THIS LINE
    code = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(50), nullable=False, index=True)
    source_url = db.Column(db.String(500), nullable=True)
    tags = db.Column(db.String(500), nullable=True)  # Comma-separated tags
    created_at = db.Column(
        db.DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)  # ADD THIS LINE
    is_favorite = db.Column(db.Boolean, default=False, nullable=False)  # ADD THIS LINE
    # ADD THESE LINES:
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(UUIDType, db.ForeignKey("users.id"), nullable=True)

    def increment_view_count(self):
        """Increment view count and update last accessed time"""
        self.view_count += 1
        self.last_accessed = datetime.utcnow()
        db.session.commit()

    def increment_copy_count(self):
        """Increment copy count"""
        self.copy_count += 1
        db.session.commit()

    def create_version(self, changed_by_id, change_summary=None):
        """Create a new version of the snippet"""
        # Save current state to history
        history_entry = SnippetHistory(
            snippet_id=self.id,
            version=self.version,
            content=self.content,
            title=self.title,
            description=self.description,
            changed_by=changed_by_id,
            change_type="edit",
            change_summary=change_summary,
        )
        db.session.add(history_entry)

        # Increment version
        self.version += 1
        self.updated_at = datetime.utcnow()
        db.session.commit()

    def get_current_editors(self):
        """Get list of users currently editing this snippet"""
        if not self.current_editors:
            return []
        try:
            editor_ids = json.loads(self.current_editors)
            return User.query.filter(User.id.in_(editor_ids)).all()
        except (json.JSONDecodeError, TypeError):
            return []

    def set_current_editors(self, user_ids):
        """Set current editors list"""
        self.current_editors = json.dumps(user_ids) if user_ids else None

    def add_editor(self, user_id):
        """Add user to current editors"""
        current = self.get_current_editor_ids()
        if user_id not in current:
            current.append(user_id)
            self.set_current_editors(current)

    def remove_editor(self, user_id):
        """Remove user from current editors"""
        current = self.get_current_editor_ids()
        if user_id in current:
            current.remove(user_id)
            self.set_current_editors(current if current else None)

    def get_current_editor_ids(self):
        """Get list of current editor IDs"""
        if not self.current_editors:
            return []
        try:
            return json.loads(self.current_editors)
        except (json.JSONDecodeError, TypeError):
            return []

    def can_user_edit(self, user):
        """Check if user can edit this snippet"""
        if self.user_id == user.id:
            return True

        if self.is_team_snippet and self.team:
            member = TeamMember.query.filter_by(
                team_id=self.team_id, user_id=user.id
            ).first()

            if member:
                if self.share_permission == SharePermission.ADMIN:
                    return member.role in ["admin", "user"]
                elif self.share_permission == SharePermission.WRITE:
                    return member.role in ["admin", "user", "editor"]
                else:
                    return False

        return False

    def can_user_view(self, user):
        """Check if user can view this snippet"""
        if self.is_public:
            return True

        if self.user_id == user.id:
            return True

        if self.is_team_snippet and self.team:
            member = TeamMember.query.filter_by(
                team_id=self.team_id, user_id=user.id
            ).first()
            return member is not None

        return False

    def track_view(self, user_id=None):
        """Track when snippet is viewed"""
        try:
            print(f"🔍 TRACKING VIEW - Snippet ID: {self.id}, User ID: {user_id}")

            self.view_count += 1

            # Update last_viewed_at (use existing field or create new one)
            if hasattr(self, "last_viewed_at"):
                self.last_viewed_at = datetime.now(timezone.utc)
            else:
                # Fallback to last_accessed if last_viewed_at doesn't exist
                if hasattr(self, "last_accessed"):
                    self.last_accessed = datetime.now(timezone.utc)

            if user_id:
                # Track unique viewers
                viewers = self.get_unique_viewers()
                if str(user_id) not in viewers:
                    viewers.append(str(user_id))
                    self.unique_viewers = json.dumps(viewers)
                    print(f"✅ Added new viewer: {user_id}")

            db.session.commit()
            print(f"✅ VIEW TRACKED - New count: {self.view_count}")

        except Exception as e:
            print(f"❌ ERROR tracking snippet view: {str(e)}")
            import traceback

            traceback.print_exc()
            db.session.rollback()

    def create_version(self, user_id, note=None):
        """Create a new version of this snippet"""
        version = Snippet(
            title=f"{self.title} (v{self.version_number + 1})",
            content=self.content,
            language=self.language,
            tags=self.tags,
            description=self.description,
            user_id=self.user_id,
            parent_version_id=self.id,
            is_version=True,
            version_number=self.version_number + 1,
            version_note=note,
            team_id=self.team_id,
            is_team_snippet=self.is_team_snippet,
        )

        db.session.add(version)

        # Update current snippet version
        self.version_number += 1
        self.last_editor_id = user_id
        self.updated_at = datetime.now(timezone.utc)

        return version

    def get_version_history(self):
        """Get all versions of this snippet"""
        if self.is_version:
            # If this is a version, get parent's versions
            parent = self.parent_version
            if parent:
                return parent.versions.order_by(Snippet.version_number.desc()).all()
        else:
            # Get all versions of this snippet
            return self.versions.order_by(Snippet.version_number.desc()).all()
        return []

    def increment_view_count(self, user_id=None):
        """Increment view count and track unique viewers"""
        self.view_count += 1
        self.last_viewed_at = datetime.now(timezone.utc)

        if user_id:
            viewers = self.get_unique_viewers()
            if user_id not in viewers:
                viewers.append(user_id)
                self.unique_viewers = json.dumps(viewers)

    def increment_copy_count(self):
        """Increment copy count"""
        self.copy_count += 1

    def increment_share_count(self):
        """Increment share count"""
        self.share_count += 1

    def get_unique_viewers(self):
        """Get list of unique viewer IDs"""
        if not self.unique_viewers:
            return []
        try:
            return json.loads(self.unique_viewers)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_slack_shared_channels(self):
        """Get list of Slack channels this snippet was shared to"""
        if not self.slack_shared_channels:
            return []
        try:
            return json.loads(self.slack_shared_channels)
        except (json.JSONDecodeError, TypeError):
            return []

    def add_slack_channel(self, channel_id, channel_name):
        """Add Slack channel to shared channels list"""
        channels = self.get_slack_shared_channels()
        channel_info = {"id": channel_id, "name": channel_name}

        # Check if already exists
        if not any(ch["id"] == channel_id for ch in channels):
            channels.append(channel_info)
            self.slack_shared_channels = json.dumps(channels)

    def get_suggested_improvements(self):
        """Get AI suggested improvements"""
        if not self.suggested_improvements:
            return []
        try:
            return json.loads(self.suggested_improvements)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_suggested_improvements(self, improvements):
        """Set AI suggested improvements"""
        self.suggested_improvements = json.dumps(improvements) if improvements else None

    def get_similar_snippets(self):
        """Get similar snippets list"""
        if not self.similar_snippets:
            return []
        try:
            snippet_ids = json.loads(self.similar_snippets)
            return Snippet.query.filter(Snippet.id.in_(snippet_ids)).all()
        except (json.JSONDecodeError, TypeError):
            return []

    def set_similar_snippets(self, snippet_ids):
        """Set similar snippets list"""
        self.similar_snippets = json.dumps(snippet_ids) if snippet_ids else None

    def record_execution(self, execution_time_ms=None):
        """Record snippet execution"""
        self.execution_count += 1
        self.last_executed_at = datetime.now(timezone.utc)
        if execution_time_ms:
            self.execution_time_ms = execution_time_ms

    def get_analytics_summary(self):
        """Get analytics summary for this snippet"""
        return {
            "view_count": self.view_count,
            "copy_count": self.copy_count,
            "share_count": self.share_count,
            "execution_count": self.execution_count,
            "unique_viewers_count": len(self.get_unique_viewers()),
            "version_count": len(self.get_version_history()),
            "last_viewed_at": (
                self.last_viewed_at.isoformat() if self.last_viewed_at else None
            ),
            "last_executed_at": (
                self.last_executed_at.isoformat() if self.last_executed_at else None
            ),
            "avg_execution_time": self.execution_time_ms,
            "complexity_score": self.complexity_score,
        }

    def to_dict_extended(self):
        """Extended dictionary representation with team and collaboration info"""
        base_dict = self.to_dict()  # Your existing to_dict method

        # Add extended fields
        extended_dict = {
            **base_dict,
            "team_id": self.team_id,
            "is_team_snippet": self.is_team_snippet,
            "share_permission": (
                self.share_permission.value if self.share_permission else None
            ),
            "is_public": self.is_public,
            "public_url": self.public_url,
            "is_collaborative": self.is_collaborative,
            "current_editors": self.get_current_editor_ids(),
            "last_editor_id": self.last_editor_id,
            "version_number": self.version_number,
            "is_version": self.is_version,
            "version_note": self.version_note,
            "status": self.status.value if self.status else None,
            "analytics": self.get_analytics_summary(),
            "github_gist_id": self.github_gist_id,
            "github_repo_path": self.github_repo_path,
            "slack_shared_channels": self.get_slack_shared_channels(),
            "ai_generated_summary": self.ai_generated_summary,
            "complexity_score": self.complexity_score,
            "suggested_improvements": self.get_suggested_improvements(),
            "team_name": self.team.name if self.team else None,
            "last_editor_name": self.last_editor.username if self.last_editor else None,
            "version_count": len(self.get_version_history()),
            "has_versions": len(self.get_version_history()) > 0,
        }

        return extended_dict

    def to_collaborative_dict(self):
        """Dictionary representation for collaborative editing"""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "language": self.language,
            "current_editors": self.get_current_editor_ids(),
            "last_editor_id": self.last_editor_id,
            "edit_session_id": self.edit_session_id,
            "version_number": self.version_number,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_collaborative": self.is_collaborative,
        }

    @classmethod
    def get_team_snippets(cls, team_id, user_id):
        """Get all snippets accessible to user in a team"""
        return cls.query.filter(
            cls.team_id == team_id, cls.status == SnippetStatus.ACTIVE
        ).all()

    @classmethod
    def get_public_snippets(cls, limit=50):
        """Get public snippets"""
        return (
            cls.query.filter(cls.is_public == True, cls.status == SnippetStatus.ACTIVE)
            .limit(limit)
            .all()
        )

    @classmethod
    def search_team_snippets(cls, team_id, query, user_id):
        """Search snippets within a team"""
        return cls.query.filter(
            cls.team_id == team_id,
            cls.status == SnippetStatus.ACTIVE,
            db.or_(
                cls.title.contains(query),
                cls.content.contains(query),
                cls.tags.contains(query),
                cls.description.contains(query),
            ),
        ).all()

    @classmethod
    def get_collaborative_snippets(cls, user_id):
        """Get snippets currently being edited collaboratively by user"""
        return cls.query.filter(
            cls.is_collaborative == True,
            cls.current_editors.contains(str(user_id)),
            cls.status == SnippetStatus.ACTIVE,
        ).all()

    @classmethod
    def get_trending_snippets(cls, team_id=None, limit=10):
        """Get trending snippets based on recent activity"""
        query = cls.query.filter(cls.status == SnippetStatus.ACTIVE)

        if team_id:
            query = query.filter(cls.team_id == team_id)

        # Order by recent views, copies, and shares
        return (
            query.order_by(
                (cls.view_count + cls.copy_count * 2 + cls.share_count * 3).desc(),
                cls.updated_at.desc(),
            )
            .limit(limit)
            .all()
        )

    def get_version_history(self):
        """Get all versions of this snippet"""
        return self.history.all()

    def restore_version(self, version_number, restored_by_id):
        """Restore snippet to a specific version"""
        history_entry = self.history.filter_by(version=version_number).first()
        if not history_entry:
            return False

        # Create current state backup
        self.create_version(restored_by_id, f"Restored to version {version_number}")

        # Restore content
        self.content = history_entry.content
        self.title = history_entry.title
        self.description = history_entry.description

        # Create restore history entry
        restore_entry = SnippetHistory(
            snippet_id=self.id,
            version=self.version,
            content=self.content,
            title=self.title,
            description=self.description,
            changed_by=restored_by_id,
            change_type="restore",
            change_summary=f"Restored from version {version_number}",
        )
        db.session.add(restore_entry)
        db.session.commit()
        return True

    def generate_share_token(self, expires_hours=24):
        """Generate a shareable token for this snippet"""
        import secrets

        self.share_token = secrets.token_urlsafe(32)
        if expires_hours:
            self.share_expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
        db.session.commit()
        return self.share_token

    def is_share_valid(self):
        """Check if share token is still valid"""
        if not self.share_token:
            return False
        if self.share_expires_at and datetime.utcnow() > self.share_expires_at:
            return False
        return True

    def get_analytics_data(self):
        """Get analytics data for this snippet"""
        return {
            "view_count": self.view_count,
            "copy_count": self.copy_count,
            "last_accessed": (
                self.last_accessed.isoformat() if self.last_accessed else None
            ),
            "version": self.version,
            "total_versions": self.history.count(),
            "collaborators_count": self.collaborators.count(),
            "is_public": self.is_public,
            "has_active_share": self.is_share_valid(),
        }


    def share_with_teams(self, team_ids, permissions=None):
        """Share snippet with multiple teams"""
        if not team_ids:
            self.shared_team_ids = None
            self.team_permissions = None
            return
        
        self.shared_team_ids = team_ids
        self.team_permissions = permissions or {}
        
    def get_shared_teams(self):
        """Get list of team IDs snippet is shared with"""
        return self.shared_team_ids or []
        
    def is_shared_with_team(self, team_id):
        """Check if snippet is shared with specific team"""
        shared_teams = self.get_shared_teams()
        return str(team_id) in [str(tid) for tid in shared_teams]
        
    def can_team_member_edit(self, user_id, team_id):
        """Check if team member can edit this snippet"""
        if not self.is_shared_with_team(team_id):
            return False
            
        permissions = self.team_permissions or {}
        team_perms = permissions.get(str(team_id), {})
        
        return team_perms.get('allow_editing', False)        

    def __init__(
        self,
        user_id,
        title,
        code,
        language,
        source_url=None,
        tags=None,
        description=None,
        **kwargs,
    ):
        self.id = kwargs.get("id", str(uuid.uuid4()))
        self.user_id = user_id
        self.title = title.strip()
        self.description = description  # ADD THIS LINE

        self.code = code
        self.language = language.lower()
        self.source_url = source_url
        self.created_at = kwargs.get("created_at", datetime.utcnow())
        self.updated_at = kwargs.get("updated_at", datetime.utcnow())

        # Set all the required fields with defaults
        self.is_deleted = kwargs.get("is_deleted", False)
        self.version = kwargs.get("version", 1)
        self.is_team_snippet = kwargs.get("is_team_snippet", False)
        self.is_public = kwargs.get("is_public", False)
        self.is_collaborative = kwargs.get("is_collaborative", False)
        self.version_number = kwargs.get("version_number", 1)
        self.is_version = kwargs.get("is_version", False)
        self.execution_count = kwargs.get("execution_count", 0)
        self.view_count = kwargs.get("view_count", 0)
        self.copy_count = kwargs.get("copy_count", 0)
        self.share_count = kwargs.get("share_count", 0)
        self.order = kwargs.get("order", 0)
        self.source_type = kwargs.get("source_type", "manual")

        # Set enum fields with defaults
        from .snippet import SharePermission, SnippetStatus  # Import at top of file

        self.share_permission = kwargs.get("share_permission", SharePermission.READ)
        self.status = kwargs.get("status", SnippetStatus.ACTIVE)

        self.set_tags(tags)

    def set_tags(self, tags):
        """Process and set tags (comma-separated string)"""
        if tags:
            if isinstance(tags, list):
                # Convert list to comma-separated string
                tag_list = [tag.strip().lower() for tag in tags if tag.strip()]
            else:
                # Process comma-separated string
                tag_list = [
                    tag.strip().lower() for tag in tags.split(",") if tag.strip()
                ]

            # Remove duplicates and join
            unique_tags = list(set(tag_list))
            self.tags = ",".join(unique_tags)
        else:
            self.tags = ""

    def get_tags_list(self):
        """Get tags as a list"""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]

    def add_tag(self, tag):
        """Add a single tag"""
        current_tags = self.get_tags_list()
        tag = tag.strip().lower()
        if tag and tag not in current_tags:
            current_tags.append(tag)
            self.set_tags(current_tags)

    def remove_tag(self, tag):
        """Remove a single tag"""
        current_tags = self.get_tags_list()
        tag = tag.strip().lower()
        if tag in current_tags:
            current_tags.remove(tag)
            self.set_tags(current_tags)

    def get_code_preview(self, max_lines=5):
        """Get a preview of the code (first few lines)"""
        lines = self.code.split("\n")
        preview_lines = lines[:max_lines]
        preview = "\n".join(preview_lines)
        if len(lines) > max_lines:
            preview += "\n..."
        return preview

    def get_line_count(self):
        """Get number of lines in the code"""
        return len(self.code.split("\n"))

    def get_character_count(self):
        """Get number of characters in the code"""
        return len(self.code)

    def increment_view_count(self):
        """Increment view count"""
        self.view_count += 1
        db.session.commit()

    def get_domain_from_url(self):
        """Extract domain from source URL"""
        if not self.source_url:
            return None

        # Simple regex to extract domain
        match = re.search(r"https?://([^/]+)", self.source_url)
        return match.group(1) if match else None

    def is_user(self, user_id):
        """Check if user is the user of this snippet"""
        return self.user_id == user_id

    def add_collaborator(self, user_id, permission="view"):
        """Add a collaborator to this snippet"""
        from sqlalchemy import text

        if permission not in ["view", "edit", "admin"]:
            return False

        # Check if already a collaborator
        existing = db.session.execute(
            text(
                "SELECT * FROM snippet_collaborators WHERE snippet_id = :snippet_id AND user_id = :user_id"
            ),
            {"snippet_id": self.id, "user_id": user_id},
        ).fetchone()

        if existing:
            # Update permission
            db.session.execute(
                text(
                    "UPDATE snippet_collaborators SET permission = :permission WHERE snippet_id = :snippet_id AND user_id = :user_id"
                ),
                {"permission": permission, "snippet_id": self.id, "user_id": user_id},
            )
        else:
            # Add new collaborator
            db.session.execute(
                text(
                    "INSERT INTO snippet_collaborators (snippet_id, user_id, permission) VALUES (:snippet_id, :user_id, :permission)"
                ),
                {"snippet_id": self.id, "user_id": user_id, "permission": permission},
            )

        db.session.commit()
        return True

    def can_user_access(self, user_id, required_permission="view"):
        """Check if user can access this snippet with required permission"""
        # user has all permissions
        if self.user_id == user_id:
            return True

        # Public snippets can be viewed
        if self.is_public and required_permission == "view":
            return True

        # Check collaborator permissions
        from sqlalchemy import text

        collab = db.session.execute(
            text(
                "SELECT permission FROM snippet_collaborators WHERE snippet_id = :snippet_id AND user_id = :user_id"
            ),
            {"snippet_id": self.id, "user_id": user_id},
        ).fetchone()

        if not collab:
            return False

        permission_hierarchy = {"view": 1, "edit": 2, "admin": 3}
        user_level = permission_hierarchy.get(collab.permission, 0)
        required_level = permission_hierarchy.get(required_permission, 0)

        return user_level >= required_level

    def to_dict(self, include_code=True):
        """Convert snippet to dictionary"""
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": getattr(self, "description", ""),  # ADD THIS LINE
            "language": self.language,
            "source_url": self.source_url,
            "tags": self.get_tags_list(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_public": self.is_public,
            "view_count": self.view_count,
            "line_count": self.get_line_count(),
            "character_count": self.get_character_count(),
            "domain": self.get_domain_from_url(),
        }

        if include_code:
            data["code"] = self.code
        else:
            data["code_preview"] = self.get_code_preview()

        return data

    @staticmethod
    def search_by_content(query, user_id=None, language=None):
        """Search snippets by content, title, or tags"""
        search_query = Snippet.query

        # Filter by user if specified
        if user_id:
            search_query = search_query.filter_by(user_id=user_id)

        # Filter by language if specified
        if language:
            search_query = search_query.filter_by(language=language)

        # Search in title, code, and tags
        search_term = f"%{query}%"
        search_query = search_query.filter(
            db.or_(
                Snippet.title.ilike(search_term),
                Snippet.code.ilike(search_term),
                Snippet.tags.ilike(search_term),
            )
        )

        return search_query.order_by(Snippet.created_at.desc())

    def __repr__(self):
        return f"<Snippet {self.title} ({self.language})>"


# Snippet collaborators association table (add after your model class)
# Snippet collaborators association table (add after your model class)
snippet_collaborators = db.Table(
    "snippet_collaborators",
    db.Column(
        "snippet_id", UUIDType, db.ForeignKey("snippets.id"), primary_key=True
    ),  # CHANGED: Integer to UUIDType
    db.Column(
        "user_id", UUIDType, db.ForeignKey("users.id"), primary_key=True
    ),  # CHANGED: Integer to UUIDType
    db.Column("permission", db.String(20), default="view"),
    db.Column("added_at", db.DateTime, default=datetime.utcnow),
)
# Snippet history/versions table (add as separate model)


class SnippetHistory(db.Model):
    __tablename__ = "snippet_history"

    id = db.Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()))
    snippet_id = db.Column(
        UUIDType, db.ForeignKey("snippets.id"), nullable=False
    )  # CHANGED: Integer to UUIDType
    version = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    changed_by = db.Column(
        UUIDType, db.ForeignKey("users.id"), nullable=False
    )  # CHANGED: Integer to UUIDType
    changed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    change_type = db.Column(db.String(20), default="edit")  # create, edit, restore
    change_summary = db.Column(db.String(500), nullable=True)

    # Relationships stay the same
    snippet = db.relationship(
        "Snippet",
        backref=db.backref(
            "history", lazy="dynamic", order_by="SnippetHistory.version.desc()"
        ),
    )
    user = db.relationship(
        "User", backref=db.backref("snippet_changes", lazy="dynamic")
    )

    # ADD this new model for snippet sharing permissions


class SnippetShare(db.Model):
    """Model for snippet sharing with specific users"""

    __tablename__ = "snippet_shares"

    id = db.Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()))
    snippet_id = db.Column(
        UUIDType, db.ForeignKey("snippets.id"), nullable=False
    )  # CHANGED: Integer to UUIDType
    shared_by_id = db.Column(
        UUIDType, db.ForeignKey("users.id"), nullable=False
    )  # CHANGED: Integer to UUIDType
    shared_with_id = db.Column(
        UUIDType, db.ForeignKey("users.id"), nullable=False
    )  # CHANGED: Integer to UUIDType
    permission = db.Column(
        db.Enum(SharePermission), default=SharePermission.READ, nullable=False
    )
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationships stay the same
    snippet = db.relationship("Snippet", backref="direct_shares")
    shared_by = db.relationship("User", foreign_keys=[shared_by_id])
    shared_with = db.relationship("User", foreign_keys=[shared_with_id])

    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint(
            "snippet_id", "shared_with_id", name="unique_snippet_share"
        ),
    )

    def is_expired(self):
        """Check if share has expired"""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "snippet_id": self.snippet_id,
            "shared_by_id": self.shared_by_id,
            "shared_with_id": self.shared_with_id,
            "permission": self.permission.value,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active,
            "is_expired": self.is_expired(),
            "shared_by_username": self.shared_by.username,
            "shared_with_username": self.shared_with.username,
        }
