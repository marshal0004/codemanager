from datetime import datetime, timezone
from app.models import db
from app.models.custom_types import UUIDType
import uuid


class SnippetChat(db.Model):
    __tablename__ = "snippet_chats"

    id = db.Column(UUIDType, primary_key=True, default=uuid.uuid4)
    snippet_id = db.Column(
        UUIDType, db.ForeignKey("snippets.id"), nullable=False, index=True
    )
    user_id = db.Column(UUIDType, db.ForeignKey("users.id"), nullable=False, index=True)
    team_id = db.Column(UUIDType, db.ForeignKey("teams.id"), nullable=False, index=True)

    message = db.Column(db.Text, nullable=False)
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
    snippet = db.relationship("Snippet", backref="chat_messages")
    user = db.relationship("User", backref="snippet_chats")
    team = db.relationship("Team", backref="snippet_chats")

    def to_dict(self):
        return {
            "id": str(self.id),
            "snippet_id": str(self.snippet_id),
            "user_id": str(self.user_id),
            "team_id": str(self.team_id),
            "message": self.message,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_deleted": self.is_deleted,
            "username": self.user.username if self.user else "Unknown",
            "user_avatar": (
                getattr(self.user, "avatar_url", None) if self.user else None
            ),
        }

    @classmethod
    def get_snippet_chats(cls, snippet_id, include_deleted=False, limit=100):
        """Get chat messages for a snippet"""
        query = cls.query.filter_by(snippet_id=snippet_id)
        if not include_deleted:
            query = query.filter_by(is_deleted=False)
        return query.order_by(cls.created_at.asc()).limit(limit).all()

    @classmethod
    def clear_snippet_chats(cls, snippet_id, cleared_by_user_id):
        """Clear all chat messages for a snippet (soft delete)"""
        chats = cls.query.filter_by(snippet_id=snippet_id, is_deleted=False).all()
        for chat in chats:
            chat.is_deleted = True
            chat.deleted_at = datetime.now(timezone.utc)
        db.session.commit()
        return len(chats)
