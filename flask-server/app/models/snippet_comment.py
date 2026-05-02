from datetime import datetime, timezone
from app.models import db
from app.models.custom_types import UUIDType
import uuid


class SnippetComment(db.Model):
    __tablename__ = "snippet_comments"

    id = db.Column(UUIDType, primary_key=True, default=uuid.uuid4)
    snippet_id = db.Column(
        UUIDType, db.ForeignKey("snippets.id"), nullable=False, index=True
    )
    user_id = db.Column(UUIDType, db.ForeignKey("users.id"), nullable=False, index=True)
    team_id = db.Column(UUIDType, db.ForeignKey("teams.id"), nullable=False, index=True)

    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    snippet = db.relationship("Snippet", backref="comments")
    user = db.relationship("User", backref="snippet_comments")
    team = db.relationship("Team", backref="snippet_comments")

    def to_dict(self):
        return {
            "id": str(self.id),
            "snippet_id": str(self.snippet_id),
            "user_id": str(self.user_id),
            "team_id": str(self.team_id),
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_deleted": self.is_deleted,
            "username": self.user.username if self.user else "Unknown",
            "user_avatar": (
                getattr(self.user, "avatar_url", None) if self.user else None
            ),
        }

    @classmethod
    def get_snippet_comments(cls, snippet_id, include_deleted=False):
        """Get all comments for a snippet"""
        query = cls.query.filter_by(snippet_id=snippet_id)
        if not include_deleted:
            query = query.filter_by(is_deleted=False)
        return query.order_by(cls.created_at.asc()).all()

    @classmethod
    def clear_snippet_comments(cls, snippet_id, cleared_by_user_id):
        """Clear all comments for a snippet (soft delete)"""
        comments = cls.query.filter_by(snippet_id=snippet_id, is_deleted=False).all()
        for comment in comments:
            comment.is_deleted = True
            comment.deleted_at = datetime.now(timezone.utc)
        db.session.commit()
        return len(comments)
