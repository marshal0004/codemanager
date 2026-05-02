from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
import uuid
from app.models.custom_types import UUIDType, JSONType
from app.models import db


class SnippetEdit(db.Model):
    """Model for tracking independent snippet edits by team members"""

    __tablename__ = "snippet_edits"

    # Primary identifiers
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    original_snippet_id = Column(
        UUIDType, ForeignKey("snippets.id"), nullable=False, index=True
    )
    team_id = Column(UUIDType, ForeignKey("teams.id"), nullable=False, index=True)
    editor_user_id = Column(
        UUIDType, ForeignKey("users.id"), nullable=False, index=True
    )

    # Snapshot of edited content (independent copy)
    title = Column(String(200), nullable=False)
    code = Column(Text, nullable=False)
    language = Column(String(50), nullable=False)
    tags = Column(String(500), nullable=True)  # Comma-separated tags

    # Edit metadata (MANDATORY)
    edit_description = Column(Text, nullable=False)  # REQUIRED field
    edit_type = Column(String(50), default="content_update", nullable=False)

    # Timestamps
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Soft delete for independence
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(UUIDType, ForeignKey("users.id"), nullable=True)

    # Relationships
    original_snippet = relationship(
        "Snippet", foreign_keys=[original_snippet_id], lazy=True
    )
    team = relationship("Team", foreign_keys=[team_id], lazy=True)
    editor = relationship("User", foreign_keys=[editor_user_id], lazy=True)
    deleted_by_user = relationship("User", foreign_keys=[deleted_by], lazy=True)

    # Database constraints
    __table_args__ = (
        db.CheckConstraint(
            "LENGTH(TRIM(edit_description)) > 0",
            name="check_edit_description_not_empty",
        ),
        db.Index("idx_snippet_edits_original_team", "original_snippet_id", "team_id"),
        db.Index(
            "idx_snippet_edits_created_desc",
            "created_at",
            postgresql_using="btree",
            postgresql_ops={"created_at": "DESC"},
        ),
    )

    def __init__(self, **kwargs):
        """Initialize snippet edit with validation"""
        # Required fields
        self.original_snippet_id = kwargs.get("original_snippet_id")
        self.team_id = kwargs.get("team_id")
        self.editor_user_id = kwargs.get("editor_user_id")

        # Content fields (snapshot from original)
        self.title = kwargs.get("title", "")
        self.code = kwargs.get("code", "")
        self.language = kwargs.get("language", "text")
        self.tags = kwargs.get("tags", "")

        # MANDATORY edit description
        edit_description = kwargs.get("edit_description", "").strip()
        if not edit_description:
            raise ValueError("Edit description is required and cannot be empty")
        self.edit_description = edit_description

        # Optional fields
        self.edit_type = kwargs.get("edit_type", "content_update")
        self.is_deleted = kwargs.get("is_deleted", False)

        # Auto-generate ID if not provided
        if "id" not in kwargs:
            self.id = uuid.uuid4()

    def soft_delete(self, deleted_by_user_id):
        """Soft delete this edit (maintains independence)"""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = deleted_by_user_id
        self.updated_at = datetime.now(timezone.utc)

    def can_user_delete(self, user_id):
        """Check if user can delete this edit"""
        # Only the editor can delete their own edit
        return str(self.editor_user_id) == str(user_id)

    def get_tags_list(self):
        """Get tags as a list"""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]

    def get_code_preview(self, max_lines=5):
        """Get a preview of the edited code"""
        lines = self.code.split("\n")
        preview_lines = lines[:max_lines]
        preview = "\n".join(preview_lines)
        if len(lines) > max_lines:
            preview += "\n..."
        return preview

    def get_line_count(self):
        """Get number of lines in the edited code"""
        return len(self.code.split("\n"))

    def get_character_count(self):
        """Get number of characters in the edited code"""
        return len(self.code)

    def to_dict(self, include_code=True):
        """Convert snippet edit to dictionary"""
        data = {
            "id": str(self.id),
            "original_snippet_id": str(self.original_snippet_id),
            "team_id": str(self.team_id),
            "editor_user_id": str(self.editor_user_id),
            "title": self.title,
            "language": self.language,
            "tags": self.get_tags_list(),
            "edit_description": self.edit_description,
            "edit_type": self.edit_type,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_deleted": self.is_deleted,
            "line_count": self.get_line_count(),
            "character_count": self.get_character_count(),
            # Editor info
            "editor_name": (
                self.editor.username or self.editor.email if self.editor else "Unknown"
            ),
            "editor_email": self.editor.email if self.editor else "Unknown",
        }

        if include_code:
            data["code"] = self.code
        else:
            data["code_preview"] = self.get_code_preview()

        # Add deletion info if deleted
        if self.is_deleted:
            data.update(
                {
                    "deleted_at": (
                        self.deleted_at.isoformat() if self.deleted_at else None
                    ),
                    "deleted_by": str(self.deleted_by) if self.deleted_by else None,
                }
            )

        return data

    @classmethod
    def get_edits_by_original_snippet(
        cls, original_snippet_id, team_id, include_deleted=False
    ):
        """Get all edits for an original snippet in a team"""
        query = cls.query.filter_by(
            original_snippet_id=original_snippet_id, team_id=team_id
        )

        if not include_deleted:
            query = query.filter_by(is_deleted=False)

        return query.order_by(cls.created_at.desc()).all()

    @classmethod
    def get_team_edits_grouped(cls, team_id, include_deleted=False):
        """Get all team edits grouped by original snippet"""
        from sqlalchemy import func

        query = cls.query.filter_by(team_id=team_id)

        if not include_deleted:
            query = query.filter_by(is_deleted=False)

        # Get all edits ordered by original snippet and creation time
        edits = query.order_by(cls.original_snippet_id, cls.created_at.desc()).all()

        # Group by original snippet
        grouped_edits = {}
        for edit in edits:
            snippet_id = str(edit.original_snippet_id)
            if snippet_id not in grouped_edits:
                grouped_edits[snippet_id] = {
                    "original_snippet_id": snippet_id,
                    "original_title": (
                        edit.original_snippet.title
                        if edit.original_snippet
                        else edit.title
                    ),
                    "edits": [],
                }
            grouped_edits[snippet_id]["edits"].append(edit)

        return grouped_edits

    @classmethod
    def create_from_snippet(
        cls, original_snippet, team_id, editor_user_id, edit_description
    ):
        """Create edit from existing snippet"""
        if not edit_description or not edit_description.strip():
            raise ValueError("Edit description is required")

        return cls(
            original_snippet_id=original_snippet.id,
            team_id=team_id,
            editor_user_id=editor_user_id,
            title=original_snippet.title,
            code=original_snippet.code,
            language=original_snippet.language,
            tags=original_snippet.tags,
            edit_description=edit_description.strip(),
        )

    def __repr__(self):
        return f"<SnippetEdit {self.title} by {self.editor_user_id}>"
