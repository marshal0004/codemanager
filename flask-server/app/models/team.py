from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
import uuid
import typing
from app.models.custom_types import UUIDType, JSONType  # Import the custom types

# Add this line after line 8:


from app.models import db


class Team(db.Model):
    """Team model for workspace management and collaboration"""

    __tablename__ = "teams"
    if typing.TYPE_CHECKING:
        from app.models.team_member import TeamMember

    owner_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)

    owner = relationship("User", backref="owned_teams", foreign_keys=[owner_id])

    members = relationship(
        "TeamMember", back_populates="team", cascade="all, delete-orphan"
    )
    # Primary identifiers
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, index=True)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    # Add this line after description field (around line 25):
    created_by = Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=True)

    # Ownership and creation

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Team settings and configuration
    settings = db.Column(
        JSONType,
        default=lambda: {
            "visibility": "private",  # private, internal, public
            "snippet_permissions": {
                "create": ["member", "admin", "owner"],
                "edit": ["admin", "owner"],
                "delete": ["admin", "owner"],
                "share_external": ["admin", "owner"],
            },
            "collection_permissions": {
                "create": ["member", "admin", "owner"],
                "edit": ["admin", "owner"],
                "delete": ["owner"],
                "reorganize": ["admin", "owner"],
            },
            "member_permissions": {
                "invite": ["admin", "owner"],
                "remove": ["admin", "owner"],
                "change_roles": ["owner"],
            },
            "integrations": {
                "github_enabled": False,
                "slack_enabled": False,
                "webhook_enabled": False,
            },
            "limits": {"max_members": 10, "max_snippets": 1000, "max_collections": 50},
        },
    )

    # Team status and metrics
    is_active = Column(Boolean, default=True, nullable=False)
    member_count = Column(
        Integer, default=1, nullable=False
    )  # Denormalized for performance
    snippet_count = Column(Integer, default=0, nullable=False)
    collection_count = Column(Integer, default=0, nullable=False)

    # Collaboration features
    last_activity_at = Column(DateTime, default=datetime.utcnow)
    activity_summary = db.Column(
        JSONType,
        default=lambda: {
            "recent_snippets": [],
            "active_members": [],
            "popular_languages": {},
            "weekly_activity": 0,
        },
    )

    # Branding and customization
    avatar_url = Column(String(500), nullable=True)
    brand_colors = db.Column(
        JSONType,
        default=lambda: {
            "primary": "#3B82F6",
            "secondary": "#10B981",
            "accent": "#F59E0B",
        },
    )

    # Integration configurations
    integrations = db.Column(
        JSONType,
        default=lambda: {
            "github": {
                "enabled": False,
                "org_name": None,
                "default_repo": None,
                "auto_sync": False,
            },
            "slack": {
                "enabled": False,
                "webhook_url": None,
                "channel": None,
                "notifications": {
                    "new_snippets": True,
                    "member_joins": True,
                    "collection_updates": False,
                },
            },
            "webhooks": {"enabled": False, "endpoints": [], "events": []},
        },
    )

    # Relationships

    snippets = relationship(
        "Snippet", back_populates="team", cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs):
        """Initialize team with flexible parameters"""
        # Handle ID
        if "id" in kwargs:
            if isinstance(kwargs["id"], str):
                self.id = uuid.UUID(kwargs["id"])
            else:
                self.id = kwargs["id"]

        # Required fields
        self.name = kwargs.get("name", "")
        self.description = kwargs.get("description", "")

        # Handle owner_id and created_by (they're the same)
        if "created_by" in kwargs:
            if isinstance(kwargs["created_by"], str):
                self.created_by = (
                    uuid.UUID(kwargs["created_by"])
                    if kwargs["created_by"] != "test_user_id"
                    else None
                )
            else:
                self.created_by = kwargs["created_by"]
            self.owner_id = self.created_by
        elif "owner_id" in kwargs:
            self.owner_id = kwargs["owner_id"]
            self.created_by = kwargs["owner_id"]

        # Handle avatar_url
        self.avatar_url = kwargs.get("avatar_url", kwargs.get("avatar", ""))

        # Generate slug
        if self.name:
            self.slug = self._generate_slug(self.name)

        # Override default settings if provided
        if "settings" in kwargs:
            default_settings = self.settings or {}
            default_settings.update(kwargs["settings"])
            self.settings = default_settings

    def _generate_slug(self, name):
        """Generate URL-friendly slug from team name"""
        import re

        slug = re.sub(r"[^a-zA-Z0-9\s-]", "", name.lower())
        slug = re.sub(r"[\s-]+", "-", slug).strip("-")

        # Ensure uniqueness
        base_slug = slug
        counter = 1
        while Team.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    @property
    def is_owner(self, user_id):
        """Check if user is team owner"""
        return str(self.owner_id) == str(user_id)

    def get_member_role(self, user_id):
        """Get user's role in the team"""
        if self.is_owner(user_id):
            return "owner"

        # Use late import to avoid circular dependency
        from app.models.team_member import TeamMember

        member = TeamMember.query.filter_by(
            team_id=self.id, user_id=user_id, is_active=True
        ).first()

        return member.role if member else None

    def get_analytics(self, days=30):
        """Get team analytics using analytics service"""
        try:
            from app.services.analytics_service import AnalyticsService
            from app.models import db

            analytics_service = AnalyticsService(db.session)
            return analytics_service.get_team_dashboard_analytics(self.id, days)
        except Exception as e:
            print(f"❌ TEAM ANALYTICS: Error getting analytics: {str(e)}")
            return {"error": "Failed to load analytics", "team_id": self.id}

    def can_user_perform_action(self, user_id, action_type, resource_type):
        """Check if user has permission to perform specific action"""
        user_role = self.get_member_role(user_id)
        if not user_role:
            return False

        permissions_key = f"{resource_type}_permissions"
        if permissions_key not in self.settings:
            return False

        allowed_roles = self.settings[permissions_key].get(action_type, [])
        return user_role in allowed_roles

    def add_member(self, user_id, role="member", invited_by=None):
        """Add new member to team"""
        # Use late import to avoid circular dependency
        from app.models.team_member import TeamMember

        # Check if already a member
        existing = TeamMember.query.filter_by(team_id=self.id, user_id=user_id).first()

        if existing:
            if existing.is_active:
                return existing, False  # Already active member
            else:
                # Reactivate existing member
                existing.is_active = True
                existing.role = role
                existing.joined_at = datetime.utcnow()
                existing.invited_by_id = invited_by
                db.session.commit()
                return existing, True

        # Create new member
        member = TeamMember(
            team_id=self.id, user_id=user_id, role=role, invited_by_id=invited_by
        )

        db.session.add(member)
        self.member_count += 1
        self.last_activity_at = datetime.utcnow()
        db.session.commit()

        return member, True
    @staticmethod
    def generate_slug(name):
        """Generate unique slug from team name"""
        import re
        
        slug = re.sub(r"[^a-zA-Z0-9\s-]", "", name.lower())
        slug = re.sub(r"[\s-]+", "-", slug).strip("-")
        
        # Ensure uniqueness
        base_slug = slug
        counter = 1
        while Team.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
            
        return slug

    def remove_member(self, user_id, removed_by=None):
        """Remove member from team"""
        # Use late import to avoid circular dependency
        from app.models.team_member import TeamMember

        member = TeamMember.query.filter_by(
            team_id=self.id, user_id=user_id, is_active=True
        ).first()

        if not member:
            return False

        member.is_active = False
        member.left_at = datetime.utcnow()
        self.member_count = max(0, self.member_count - 1)
        self.last_activity_at = datetime.utcnow()
        db.session.commit()

        return True

    def update_activity(self, activity_type, user_id, metadata=None):
        """Update team activity summary"""
        now = datetime.utcnow()
        self.last_activity_at = now

        # Update activity summary
        if not self.activity_summary:
            self.activity_summary = {
                "recent_snippets": [],
                "active_members": [],
                "popular_languages": {},
                "weekly_activity": 0,
            }

        # Track active members
        if user_id not in self.activity_summary["active_members"]:
            self.activity_summary["active_members"].append(str(user_id))

        # Update weekly activity counter
        self.activity_summary["weekly_activity"] += 1

        db.session.commit()

    def get_statistics(self):
        """Get comprehensive team statistics"""
        return {
            "overview": {
                "member_count": self.member_count,
                "snippet_count": self.snippet_count,
                "collection_count": self.collection_count,
                "created_days_ago": (datetime.utcnow() - self.created_at).days,
            },
            "activity": {
                "last_activity": (
                    self.last_activity_at.isoformat() if self.last_activity_at else None
                ),
                "weekly_activity": self.activity_summary.get("weekly_activity", 0),
                "active_members_count": len(
                    self.activity_summary.get("active_members", [])
                ),
            },
            "popular_languages": self.activity_summary.get("popular_languages", {}),
            "integrations_enabled": sum(
                [config.get("enabled", False) for config in self.integrations.values()]
            ),
        }

    def get_activity_score(self):
        """Get team activity score for frontend"""
        try:
            if not self.activity_summary:
                return 0

            weekly_activity = self.activity_summary.get("weekly_activity", 0)
            active_members = len(self.activity_summary.get("active_members", []))

            # Simple scoring algorithm
            score = (weekly_activity * 0.7) + (active_members * 0.3)
            return min(100, max(0, score))  # Cap between 0-100
        except Exception as e:
            print(f"❌ TEAM: Error calculating activity score: {str(e)}")
            return 0

    def get_recent_activity(self, limit=3):
        """Get recent team activity for frontend"""
        try:
            if not self.activity_summary:
                return []

            recent_snippets = self.activity_summary.get("recent_snippets", [])
            return recent_snippets[:limit]
        except Exception as e:
            print(f"❌ TEAM: Error getting recent activity: {str(e)}")
            return []

    def get_recent_members(self, limit=10):
        """Get recently joined members"""
        try:
            from app.models.team_member import TeamMember
            from app.models.user import User

            members = (
                TeamMember.query.filter_by(team_id=self.id, is_active=True)
                .join(User)
                .order_by(TeamMember.joined_at.desc())
                .limit(limit)
                .all()
            )

            return [
                {
                    "id": str(member.user_id),
                    "name": member.user.name if hasattr(member, "user") else "Unknown",
                    "role": member.role,
                    "joined_at": (
                        member.joined_at.isoformat() if member.joined_at else None
                    ),
                }
                for member in members
            ]
        except Exception as e:
            print(f"❌ TEAM: Error getting recent members: {str(e)}")
            return []

    def get_top_contributors(self, limit=5):
        """Get top contributing members"""
        try:
            from app.models.team_member import TeamMember
            from app.models.user import User

            members = (
                TeamMember.query.filter_by(team_id=self.id, is_active=True)
                .join(User)
                .order_by(TeamMember.joined_at.asc())  # Oldest members first for now
                .limit(limit)
                .all()
            )

            return [
                {
                    "id": str(member.user_id),
                    "name": member.user.name if hasattr(member, "user") else "Unknown",
                    "role": member.role,
                    "contribution_score": 85,  # Mock score for Step 1
                }
                for member in members
            ]
        except Exception as e:
            print(f"❌ TEAM: Error getting top contributors: {str(e)}")
            return []

    def generate_invite_code(self):
        """Generate team invite code"""
        try:
            import hashlib
            import time

            # Create a simple invite code
            data = f"{self.id}{self.name}{time.time()}"
            return hashlib.md5(data.encode()).hexdigest()[:8].upper()
        except Exception as e:
            print(f"❌ TEAM: Error generating invite code: {str(e)}")
            return "INVITE123"

    def to_dict(self, include_sensitive=False):
        """Convert team to dictionary"""
        data = {
            "id": str(self.id),
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "owner_id": str(self.owner_id),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_active": self.is_active,
            "member_count": self.member_count,
            "snippet_count": self.snippet_count,
            "collection_count": self.collection_count,
            "avatar_url": self.avatar_url,
            "brand_colors": self.brand_colors,
            "statistics": self.get_statistics(),
        }

        if include_sensitive:
            data.update(
                {
                    "settings": self.settings,
                    "integrations": self.integrations,
                    "activity_summary": self.activity_summary,
                }
            )

        return data

    def __repr__(self):
        return f"<Team {self.name} ({self.slug})>"


# Remove the existing import handling and replace with:
def _ensure_team_member_import():
    """Ensure TeamMember is imported to avoid circular import issues"""
    try:
        from app.models.team_member import TeamMember

        return TeamMember
    except ImportError as e:
        print(f"❌ TEAM: Could not import TeamMember: {str(e)}")
        return None


# Call it once to establish the import
_ensure_team_member_import()
