# flask-server/app/models/team_chat.py
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Integer
from sqlalchemy.orm import relationship
import uuid
from app.models.custom_types import UUIDType
from app.models import db


class TeamChat(db.Model):
    """Team-level chat messages for team communication"""

    __tablename__ = "team_chats"

    # Primary identifiers
    id = Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()))
    team_id = Column(UUIDType, ForeignKey("teams.id"), nullable=False, index=True)
    user_id = Column(UUIDType, ForeignKey("users.id"), nullable=False, index=True)

    # Message content
    message = Column(Text, nullable=False)
    message_type = Column(
        String(20), default="text", nullable=False
    )  # text, system, announcement

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    edited_at = Column(DateTime, nullable=True)

    # Message status
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by_id = Column(UUIDType, ForeignKey("users.id"), nullable=True)

    # Message metadata
    reply_to_id = Column(
        UUIDType, ForeignKey("team_chats.id"), nullable=True
    )  # For threaded replies
    mention_user_ids = Column(Text, nullable=True)  # JSON string of mentioned user IDs
    is_pinned = Column(Boolean, default=False, nullable=False)
    pinned_by_id = Column(UUIDType, ForeignKey("users.id"), nullable=True)
    pinned_at = Column(DateTime, nullable=True)

    # Relationships
    team = relationship("Team", backref="chat_messages")
    user = relationship("User", foreign_keys=[user_id], backref="team_chat_messages")
    deleted_by = relationship("User", foreign_keys=[deleted_by_id])
    pinned_by = relationship("User", foreign_keys=[pinned_by_id])

    # Self-referential relationship for replies
    reply_to = relationship("TeamChat", remote_side=[id], backref="replies")

    def __init__(self, **kwargs):
        """Initialize team chat message"""
        self.team_id = kwargs.get("team_id")
        self.user_id = kwargs.get("user_id")
        self.message = kwargs.get("message", "")
        self.message_type = kwargs.get("message_type", "text")
        self.reply_to_id = kwargs.get("reply_to_id")
        self.mention_user_ids = kwargs.get("mention_user_ids")

    @classmethod
    def get_team_chats(cls, team_id, limit=50, offset=0):
        """Get chat messages for a team"""
        try:
            chats = (
                cls.query.filter_by(team_id=team_id, is_deleted=False)
                .order_by(cls.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )

            # Return in chronological order (oldest first)
            return list(reversed(chats))
        except Exception as e:
            print(f"❌ GET_TEAM_CHATS ERROR: {str(e)}")
            return []

    @classmethod
    def get_recent_team_chats(cls, team_id, hours=24):
        """Get recent chat messages for a team"""
        try:
            from datetime import timedelta

            cutoff_time = datetime.utcnow() - timedelta(hours=hours)

            chats = (
                cls.query.filter_by(team_id=team_id, is_deleted=False)
                .filter(cls.created_at >= cutoff_time)
                .order_by(cls.created_at.asc())
                .all()
            )

            return chats
        except Exception as e:
            print(f"❌ GET_RECENT_TEAM_CHATS ERROR: {str(e)}")
            return []

    @classmethod
    def clear_team_chats(cls, team_id, cleared_by_user_id):
        """Clear all chat messages for a team (Admin/Owner only)"""
        try:
            # Soft delete all messages
            chats = cls.query.filter_by(team_id=team_id, is_deleted=False).all()

            cleared_count = 0
            for chat in chats:
                chat.is_deleted = True
                chat.deleted_at = datetime.utcnow()
                chat.deleted_by_id = cleared_by_user_id
                cleared_count += 1

            db.session.commit()
            print(
                f"✅ CLEAR_TEAM_CHATS: Cleared {cleared_count} messages for team {team_id}"
            )
            return cleared_count

        except Exception as e:
            db.session.rollback()
            print(f"❌ CLEAR_TEAM_CHATS ERROR: {str(e)}")
            return 0

    @classmethod
    def get_chat_statistics(cls, team_id):
        """Get chat statistics for a team"""
        try:
            from sqlalchemy import func

            stats = (
                db.session.query(
                    func.count(cls.id).label("total_messages"),
                    func.count(func.distinct(cls.user_id)).label("active_users"),
                    func.max(cls.created_at).label("last_message_at"),
                )
                .filter_by(team_id=team_id, is_deleted=False)
                .first()
            )

            return {
                "total_messages": stats.total_messages or 0,
                "active_users": stats.active_users or 0,
                "last_message_at": (
                    stats.last_message_at.isoformat() if stats.last_message_at else None
                ),
            }

        except Exception as e:
            print(f"❌ GET_CHAT_STATISTICS ERROR: {str(e)}")
            return {"total_messages": 0, "active_users": 0, "last_message_at": None}

    def soft_delete(self, deleted_by_user_id):
        """Soft delete this chat message"""
        try:
            self.is_deleted = True
            self.deleted_at = datetime.utcnow()
            self.deleted_by_id = deleted_by_user_id
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"❌ SOFT_DELETE ERROR: {str(e)}")
            return False

    def edit_message(self, new_message, edited_by_user_id):
        """Edit this chat message"""
        try:
            # Only allow editing by the original author
            if str(self.user_id) != str(edited_by_user_id):
                return False

            self.message = new_message
            self.edited_at = datetime.utcnow()
            self.updated_at = datetime.utcnow()
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"❌ EDIT_MESSAGE ERROR: {str(e)}")
            return False

    def pin_message(self, pinned_by_user_id):
        """Pin this chat message"""
        try:
            self.is_pinned = True
            self.pinned_by_id = pinned_by_user_id
            self.pinned_at = datetime.utcnow()
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"❌ PIN_MESSAGE ERROR: {str(e)}")
            return False

    def unpin_message(self):
        """Unpin this chat message"""
        try:
            self.is_pinned = False
            self.pinned_by_id = None
            self.pinned_at = None
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"❌ UNPIN_MESSAGE ERROR: {str(e)}")
            return False

    def get_user_info(self):
        """Get user information for this chat message"""
        try:
            if self.user:
                return {
                    "id": str(self.user.id),
                    "username": (
                        self.user.username or self.user.email.split("@")[0]
                        if self.user.email
                        else "Unknown"
                    ),
                    "email": self.user.email,
                    "avatar_url": getattr(self.user, "avatar_url", None),
                }
            return {
                "id": str(self.user_id),
                "username": "Unknown User",
                "email": None,
                "avatar_url": None,
            }
        except Exception as e:
            print(f"❌ GET_USER_INFO ERROR: {str(e)}")
            return {
                "id": str(self.user_id),
                "username": "Unknown User",
                "email": None,
                "avatar_url": None,
            }

    def to_dict(self, include_user_info=True):
        """Convert team chat message to dictionary with proper timezone handling"""
        try:
            # ✅ FIX: Add 'Z' suffix to indicate UTC time
            data = {
                "id": str(self.id),
                "team_id": str(self.team_id),
                "user_id": str(self.user_id),
                "message": self.message,
                "message_type": self.message_type,
                "created_at": self.created_at.isoformat() + 'Z',  # ✅ FIX: Add UTC indicator
                "updated_at": (self.updated_at.isoformat() + 'Z') if self.updated_at else None,
                "edited_at": (self.edited_at.isoformat() + 'Z') if self.edited_at else None,
                "is_deleted": self.is_deleted,
                "reply_to_id": str(self.reply_to_id) if self.reply_to_id else None,
                "is_pinned": self.is_pinned,
                "pinned_at": self.pinned_at.isoformat() if self.pinned_at else None,
                "mention_user_ids": self.mention_user_ids,
            }

            if include_user_info:
                data["user"] = self.get_user_info()

            if self.deleted_at:
                data["deleted_at"] = self.deleted_at.isoformat()
                data["deleted_by_id"] = (
                    str(self.deleted_by_id) if self.deleted_by_id else None
                )

            if self.pinned_by_id:
                data["pinned_by_id"] = str(self.pinned_by_id)

            return data

        except Exception as e:
            print(f"❌ TO_DICT ERROR: {str(e)}")
            return {
                "id": str(self.id),
                "team_id": str(self.team_id),
                "user_id": str(self.user_id),
                "message": self.message or "",
                "message_type": self.message_type or "text",
                "created_at": (
                    self.created_at.isoformat()
                    if self.created_at
                    else datetime.utcnow().isoformat()
                ),
                "error": "Failed to serialize message",
            }




    def __repr__(self):
        return f"<TeamChat team_id={self.team_id} user_id={self.user_id} message='{self.message[:50]}...'>"


# Add this to ensure the model is properly imported
def _ensure_team_chat_import():
    """Ensure TeamChat model is properly imported"""
    try:
        from app.models.team import Team
        from app.models.user import User

        return True
    except ImportError as e:
        print(f"❌ TEAM_CHAT: Could not import related models: {str(e)}")
        return False


# Call it once to establish imports
_ensure_team_chat_import()
