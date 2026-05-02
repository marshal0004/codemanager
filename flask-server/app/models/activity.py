# flask-server/app/models/activity.py
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Boolean, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
import json


class Activity:
    """
    Activity tracking model for team collaboration and user actions
    Fixed to avoid circular imports and SQLAlchemy reserved words
    """

    def __init__(self, db):
        """Initialize with db instance to avoid circular imports"""
        self.db = db
        self._setup_model()

    def _setup_model(self):
        """Setup the SQLAlchemy model dynamically"""

        class ActivityModel(self.db.Model):
            __tablename__ = "activities"

            # Primary fields
            id = self.db.Column(
                String(36), primary_key=True, default=lambda: str(uuid.uuid4())
            )

            # Core activity data
            action_type = self.db.Column(String(50), nullable=False, index=True)
            action_category = self.db.Column(String(20), nullable=False, index=True)

            # User who performed the action
            user_id = self.db.Column(
                String(36), ForeignKey("users.id"), nullable=False, index=True
            )

            # Team context (nullable for personal activities)
            team_id = self.db.Column(
                String(36), ForeignKey("teams.id"), nullable=True, index=True
            )

            # Target resource (what was acted upon)
            target_type = self.db.Column(String(20), nullable=True)
            target_id = self.db.Column(String(36), nullable=True, index=True)
            target_name = self.db.Column(String(255), nullable=True)

            # Activity details - FIXED: renamed from 'metadata' to avoid SQLAlchemy conflict
            description = self.db.Column(Text, nullable=False)
            activity_data = self.db.Column(
                Text, nullable=True
            )  # JSON string for additional data

            # Timestamps
            created_at = self.db.Column(
                DateTime, default=datetime.utcnow, nullable=False, index=True
            )

            # Visibility and status
            is_public = self.db.Column(Boolean, default=True, nullable=False)
            is_deleted = self.db.Column(Boolean, default=False, nullable=False)

            # Analytics fields
            importance_score = self.db.Column(Integer, default=1, nullable=False)

            # Relationships
            user = relationship("User", backref="activities")
            team = relationship("Team", backref="activities")

            def __init__(self, **kwargs):
                """Initialize activity with proper defaults"""
                super(ActivityModel, self).__init__(**kwargs)
                if not self.id:
                    self.id = str(uuid.uuid4())
                if not self.created_at:
                    self.created_at = datetime.utcnow()

            def to_dict(self):
                """Convert activity to dictionary for API responses"""
                return {
                    "id": self.id,
                    "action_type": self.action_type,
                    "action_category": self.action_category,
                    "user_id": self.user_id,
                    "team_id": self.team_id,
                    "target_type": self.target_type,
                    "target_id": self.target_id,
                    "target_name": self.target_name,
                    "description": self.description,
                    "metadata": (
                        json.loads(self.activity_data) if self.activity_data else {}
                    ),
                    "created_at": self.created_at.isoformat(),
                    "is_public": self.is_public,
                    "importance_score": self.importance_score,
                    "user": (
                        {
                            "id": self.user.id,
                            "username": self.user.username
                            or self.user.email.split("@")[0],
                            "avatar": getattr(self.user, "avatar_url", None),
                        }
                        if self.user
                        else None
                    ),
                    "team": (
                        {"id": self.team.id, "name": self.team.name}
                        if self.team
                        else None
                    ),
                }

            def set_metadata(self, data):
                """Set metadata as JSON string"""
                self.activity_data = json.dumps(data) if data else None

            def get_metadata(self):
                """Get metadata as Python object"""
                return json.loads(self.activity_data) if self.activity_data else {}

            def __repr__(self):
                return f"<Activity {self.action_type} by {self.user_id} at {self.created_at}>"

        self.Model = ActivityModel
        return ActivityModel

    @classmethod
    def get_instance(cls):
        """Get Activity instance with db - avoids circular import"""
        if not hasattr(cls, "_instance"):
            # Import db here to avoid circular import
            from app.models import db

            cls._instance = cls(db)
        return cls._instance

    @classmethod
    def log_activity(
        cls,
        action_type,
        user_id,
        description,
        team_id=None,
        target_type=None,
        target_id=None,
        target_name=None,
        metadata=None,
        importance_score=1,
        is_public=True,
    ):
        """
        Create and save a new activity log entry
        """
        try:
            # Get instance with db
            instance = cls.get_instance()

            # Determine category from action_type
            category_map = {
                "team_created": "team",
                "team_deleted": "team",
                "team_updated": "team",
                "member_invited": "member",
                "member_joined": "member",
                "member_left": "member",
                "member_removed": "member",
                "role_changed": "member",
                "snippet_created": "snippet",
                "snippet_shared": "snippet",
                "snippet_edited": "snippet",
                "snippet_deleted": "snippet",
                "collection_created": "collection",
                "collection_shared": "collection",
                "collection_updated": "collection",
                "collection_deleted": "collection",
                "chat_message_sent": "communication",
                "chat_cleared": "communication",
                "comment_added": "communication",
            }

            action_category = category_map.get(action_type, "other")

            activity = instance.Model(
                action_type=action_type,
                action_category=action_category,
                user_id=str(user_id),
                team_id=str(team_id) if team_id else None,
                target_type=target_type,
                target_id=str(target_id) if target_id else None,
                target_name=target_name,
                description=description,
                importance_score=importance_score,
                is_public=is_public,
            )

            if metadata:
                activity.set_metadata(metadata)

            instance.db.session.add(activity)
            instance.db.session.commit()

            print(f"✅ ACTIVITY LOGGED: {action_type} by user {user_id}")
            return activity

        except Exception as e:
            try:
                instance.db.session.rollback()
            except:
                pass
            print(f"❌ ACTIVITY LOG ERROR: {str(e)}")
            return None

    @classmethod
    def get_team_activities(cls, team_id, limit=50, offset=0, category=None):
        """Get activities for a specific team"""
        try:
            instance = cls.get_instance()
            query = instance.Model.query.filter_by(
                team_id=team_id, is_deleted=False, is_public=True
            )

            if category:
                query = query.filter_by(action_category=category)

            return (
                query.order_by(instance.Model.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
        except Exception as e:
            print(f"❌ GET_TEAM_ACTIVITIES ERROR: {str(e)}")
            return []

    @classmethod
    def get_user_activities(cls, user_id, limit=50, offset=0):
        """Get activities for a specific user"""
        try:
            instance = cls.get_instance()
            return (
                instance.Model.query.filter_by(user_id=user_id, is_deleted=False)
                .order_by(instance.Model.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
        except Exception as e:
            print(f"❌ GET_USER_ACTIVITIES ERROR: {str(e)}")
            return []

    @classmethod
    def get_recent_activities(cls, team_ids=None, limit=20):
        """Get recent activities across teams or globally"""
        try:
            instance = cls.get_instance()
            query = instance.Model.query.filter_by(is_deleted=False, is_public=True)

            if team_ids:
                query = query.filter(instance.Model.team_id.in_(team_ids))

            return query.order_by(instance.Model.created_at.desc()).limit(limit).all()
        except Exception as e:
            print(f"❌ GET_RECENT_ACTIVITIES ERROR: {str(e)}")
            return []

    @classmethod
    def get_activity_stats(cls, team_id=None, days=30):
        """Get activity statistics"""
        try:
            from datetime import timedelta

            instance = cls.get_instance()
            start_date = datetime.utcnow() - timedelta(days=days)
            query = instance.Model.query.filter(
                instance.Model.created_at >= start_date,
                instance.Model.is_deleted == False,
            )

            if team_id:
                query = query.filter_by(team_id=team_id)

            activities = query.all()

            stats = {
                "total_activities": len(activities),
                "by_category": {},
                "by_type": {},
                "by_day": {},
                "most_active_users": {},
            }

            for activity in activities:
                # Category stats
                category = activity.action_category
                stats["by_category"][category] = (
                    stats["by_category"].get(category, 0) + 1
                )

                # Type stats
                action_type = activity.action_type
                stats["by_type"][action_type] = stats["by_type"].get(action_type, 0) + 1

                # Daily stats
                day = activity.created_at.date().isoformat()
                stats["by_day"][day] = stats["by_day"].get(day, 0) + 1

                # User stats
                user_id = activity.user_id
                stats["most_active_users"][user_id] = (
                    stats["most_active_users"].get(user_id, 0) + 1
                )

            return stats
        except Exception as e:
            print(f"❌ GET_ACTIVITY_STATS ERROR: {str(e)}")
            return {
                "total_activities": 0,
                "by_category": {},
                "by_type": {},
                "by_day": {},
                "most_active_users": {},
            }

    @classmethod
    def cleanup_old_activities(cls, days=90):
        """Clean up old activities (optional maintenance)"""
        try:
            from datetime import timedelta

            instance = cls.get_instance()
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            old_activities = instance.Model.query.filter(
                instance.Model.created_at < cutoff_date
            ).all()

            for activity in old_activities:
                activity.is_deleted = True

            instance.db.session.commit()
            return len(old_activities)
        except Exception as e:
            print(f"❌ CLEANUP_ACTIVITIES ERROR: {str(e)}")
            return 0


# Create a convenience function for easy importing
def get_activity_model():
    """Get the Activity model class"""
    return Activity.get_instance().Model


# For backward compatibility
Activity = Activity
