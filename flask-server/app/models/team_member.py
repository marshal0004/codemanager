from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship
import uuid
from app.models.custom_types import UUIDType, JSONType
import enum

from app.models import db


class MemberRole(enum.Enum):
    """Enumeration for team member roles with flexible case handling"""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"
    GUEST = "guest"

    @classmethod
    def _missing_(cls, value):
        """Handle case-insensitive enum lookup"""
        if isinstance(value, str):
            # Try lowercase first
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
            # Try uppercase
            for member in cls:
                if member.value.upper() == value.upper():
                    return member
        return None


class InvitationStatus(enum.Enum):
    """Enumeration for invitation statuses with flexible case handling"""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    REVOKED = "revoked"

    @classmethod
    def _missing_(cls, value):
        """Handle case-insensitive enum lookup"""
        if isinstance(value, str):
            # Try lowercase first
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
            # Try uppercase
            for member in cls:
                if member.value.upper() == value.upper():
                    return member
        return None


# Force SQLAlchemy to use flexible enum processing
from sqlalchemy.types import TypeDecorator, Enum as SQLEnum


class FlexibleEnum(TypeDecorator):
    """Custom enum type that handles case-insensitive values"""

    impl = SQLEnum
    cache_ok = True

    def __init__(self, enum_class, **kwargs):
        self.enum_class = enum_class
        super().__init__(enum_class, **kwargs)

    def process_bind_param(self, value, dialect):
        """Convert Python enum to database value"""
        if value is None:
            return None
        if isinstance(value, self.enum_class):
            return value.value
        return str(value).lower()

    def process_result_value(self, value, dialect):
        """Convert database value to Python enum"""
        if value is None:
            return None
        try:
            # Try direct lookup first
            return self.enum_class(value)
        except ValueError:
            # Use the _missing_ method for flexible lookup
            result = self.enum_class._missing_(value)
            if result is None:
                # Fallback: try lowercase
                try:
                    return self.enum_class(value.lower())
                except (ValueError, AttributeError):
                    # Last resort: return first enum value
                    return list(self.enum_class)[0]
            return result


class TeamMember(db.Model):
    """Team membership model with comprehensive permission management"""

    __tablename__ = "team_members"

    # Primary identifiers
    id = db.Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()))
    team_id = db.Column(UUIDType, db.ForeignKey("teams.id"), nullable=False, index=True)
    user_id = db.Column(UUIDType, db.ForeignKey("users.id"), nullable=False, index=True)

    team = relationship("Team", back_populates="members")

    # Role and permissions
    # Role and permissions
    role = Column(FlexibleEnum(MemberRole), default=MemberRole.MEMBER, nullable=False)
    custom_permissions = Column(
        JSONType,
        default=lambda: {
            "snippets": {
                "create": None,  # None means inherit from role
                "edit_own": None,
                "edit_all": None,
                "delete_own": None,
                "delete_all": None,
                "share_external": None,
            },
            "collections": {
                "create": None,
                "edit_own": None,
                "edit_all": None,
                "delete_own": None,
                "delete_all": None,
                "reorganize": None,
            },
            "team": {
                "invite_members": None,
                "remove_members": None,
                "change_member_roles": None,
                "modify_settings": None,
                "manage_integrations": None,
            },
        },
    )

    # Membership status and timeline
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    invitation_status = Column(
        FlexibleEnum(InvitationStatus),
        default=InvitationStatus.ACCEPTED,
        nullable=False,
    )
    invited_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    joined_at = Column(DateTime, nullable=True)
    left_at = Column(DateTime, nullable=True)
    last_active_at = Column(DateTime, default=datetime.utcnow)

    # Invitation and management
    invited_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    invitation_token = Column(String(100), unique=True, nullable=True, index=True)
    invitation_expires_at = Column(DateTime, nullable=True)

    # Member preferences and settings
    preferences = Column(
        JSONType,
        default=lambda: {
            "notifications": {
                "new_snippets": True,
                "snippet_comments": True,
                "collection_updates": True,
                "team_announcements": True,
                "member_activity": False,
                "weekly_digest": True,
            },
            "ui_preferences": {
                "default_view": "grid",  # grid, list, timeline
                "theme": "auto",  # light, dark, auto
                "sidebar_collapsed": False,
                "show_activity_feed": True,
            },
            "collaboration": {
                "auto_watch_created": True,
                "auto_watch_edited": False,
                "share_activity_status": True,
                "allow_mentions": True,
            },
        },
    )

    # Activity and contribution tracking
    activity_summary = Column(
        JSONType,
        default=lambda: {
            "snippets_created": 0,
            "snippets_edited": 0,
            "collections_created": 0,
            "comments_posted": 0,
            "last_7_days_activity": 0,
            "favorite_languages": {},
            "collaboration_score": 0,
        },
    )

    # Access control and limitations
    access_level = Column(String(20), default="full")  # full, limited, read_only
    access_restrictions = Column(
        JSONType,
        default=lambda: {
            "allowed_languages": [],  # Empty means all allowed
            "blocked_languages": [],
            "max_snippets_per_day": None,
            "max_collections": None,
            "can_export": True,
            "can_share_external": True,
            "ip_restrictions": [],
        },
    )

    # Relationships
    # Change these relationships

    user = relationship("User", foreign_keys=[user_id])
    invited_by = relationship(
        "User", foreign_keys=[invited_by_id], backref="sent_invitations"
    )

    # Composite unique constraint
    __table_args__ = (
        db.UniqueConstraint("team_id", "user_id", name="unique_team_user"),
    )

    def __init__(self, **kwargs):
        """Initialize team member with flexible parameters"""
        # Handle required fields
        self.team_id = kwargs.get("team_id")
        self.user_id = kwargs.get("user_id")

        # Handle role - can be string or enum
        role_value = kwargs.get("role", "member")
        if isinstance(role_value, str):
            try:
                self.role = MemberRole(role_value)
            except ValueError:
                self.role = MemberRole.MEMBER
        else:
            self.role = role_value or MemberRole.MEMBER

        # Handle invitation
        self.invited_by_id = kwargs.get("invited_by_id", kwargs.get("invited_by"))

        # Set invitation status based on whether this is a direct add or invitation
        if self.invited_by_id:
            self.invitation_status = InvitationStatus.PENDING
            self.invitation_token = self._generate_invitation_token()
            self.invitation_expires_at = datetime.utcnow() + timedelta(days=7)
        else:
            self.invitation_status = InvitationStatus.ACCEPTED
            self.joined_at = datetime.utcnow()

        # Set other fields from kwargs
        for key, value in kwargs.items():
            if hasattr(self, key) and key not in [
                "team_id",
                "user_id",
                "role",
                "invited_by_id",
            ]:
                setattr(self, key, value)

    def _generate_invitation_token(self):
        """Generate unique invitation token"""
        import secrets

        return secrets.token_urlsafe(32)

    @property
    def is_owner(self):
        """Check if member is team owner"""
        return self.role == MemberRole.OWNER

    @property
    def is_admin(self):
        """Check if member has admin privileges"""
        return self.role in [MemberRole.OWNER, MemberRole.ADMIN]

    @property
    def can_manage_team(self):
        """Check if member can manage team settings"""
        return self.role in [MemberRole.OWNER, MemberRole.ADMIN]

    @property
    def days_since_joined(self):
        """Calculate days since member joined"""
        if not self.joined_at:
            return 0
        return (datetime.utcnow() - self.joined_at).days

    @property
    def is_invitation_expired(self):
        """Check if invitation has expired"""
        if self.invitation_status != InvitationStatus.PENDING:
            return False
        return (
            datetime.utcnow() > self.invitation_expires_at
            if self.invitation_expires_at
            else True
        )

    @property
    def status(self):
        """Get member status for API compatibility"""
        if self.is_active and self.invitation_status == InvitationStatus.ACCEPTED:
            return "active"
        elif self.invitation_status == InvitationStatus.PENDING:
            return "invited"
        else:
            return "inactive"

    def get_effective_permissions(self):
        """Get effective permissions combining role-based and custom permissions"""
        # Default role-based permissions
        role_permissions = {
            MemberRole.OWNER: {
                "snippets": {
                    "create": True,
                    "edit_own": True,
                    "edit_all": True,
                    "delete_own": True,
                    "delete_all": True,
                    "share_external": True,
                },
                "collections": {
                    "create": True,
                    "edit_own": True,
                    "edit_all": True,
                    "delete_own": True,
                    "delete_all": True,
                    "reorganize": True,
                },
                "team": {
                    "invite_members": True,
                    "remove_members": True,
                    "change_member_roles": True,
                    "modify_settings": True,
                    "manage_integrations": True,
                },
            },
            MemberRole.ADMIN: {
                "snippets": {
                    "create": True,
                    "edit_own": True,
                    "edit_all": True,
                    "delete_own": True,
                    "delete_all": False,
                    "share_external": True,
                },
                "collections": {
                    "create": True,
                    "edit_own": True,
                    "edit_all": True,
                    "delete_own": True,
                    "delete_all": False,
                    "reorganize": True,
                },
                "team": {
                    "invite_members": True,
                    "remove_members": True,
                    "change_member_roles": True,  # ✅ FIXED: Admin can change roles (except Owner)
                    "modify_settings": True,  # ✅ FIXED: Admin can modify settings
                    "manage_integrations": True,
                },
            },
            MemberRole.MEMBER: {
                "snippets": {
                    "create": True,
                    "edit_own": True,
                    "edit_all": False,  # ✅ CORRECT: Can only edit own snippets
                    "delete_own": True,
                    "delete_all": False,
                    "share_external": True,
                },
                "collections": {
                    "create": True,
                    "edit_own": True,
                    "edit_all": False,  # ✅ CORRECT: Can only edit own collections
                    "delete_own": True,
                    "delete_all": False,
                    "reorganize": False,
                },
                "team": {
                    "invite_members": False,  # ✅ CORRECT: Cannot invite
                    "remove_members": False,
                    "change_member_roles": False,
                    "modify_settings": False,
                    "manage_integrations": False,
                },
            },
            MemberRole.VIEWER: {
                "snippets": {
                    "create": False,
                    "edit_own": False,
                    "edit_all": False,
                    "delete_own": False,
                    "delete_all": False,
                    "share_external": False,
                },
                "collections": {
                    "create": False,
                    "edit_own": False,
                    "edit_all": False,
                    "delete_own": False,
                    "delete_all": False,
                    "reorganize": False,
                },
                "team": {
                    "invite_members": False,
                    "remove_members": False,
                    "change_member_roles": False,
                    "modify_settings": False,
                    "manage_integrations": False,
                },
            },
            MemberRole.GUEST: {
                "snippets": {
                    "create": False,
                    "edit_own": False,
                    "edit_all": False,
                    "delete_own": False,
                    "delete_all": False,
                    "share_external": False,
                },
                "collections": {
                    "create": False,
                    "edit_own": False,
                    "edit_all": False,
                    "delete_own": False,
                    "delete_all": False,
                    "reorganize": False,
                },
                "team": {
                    "invite_members": False,
                    "remove_members": False,
                    "change_member_roles": False,
                    "modify_settings": False,
                    "manage_integrations": False,
                },
            },
        }

        # Get base permissions for role
        effective = role_permissions.get(
            self.role, role_permissions[MemberRole.MEMBER]
        ).copy()

        # Apply custom permission overrides
        if self.custom_permissions:
            for category, permissions in self.custom_permissions.items():
                if category in effective:
                    for permission, value in permissions.items():
                        if value is not None and permission in effective[category]:
                            effective[category][permission] = value

        return effective

    def can(self, action, resource_type="snippets", resource_owner_id=None):
        """Check if member can perform specific action with enhanced logging"""
        # ✅ ENHANCED LOGGING
        print(f"🔍 PERMISSION_CHECK: User {self.user_id}, Action: {action}, Resource: {resource_type}")
        print(f"  - Role: {self.role}")
        print(f"  - Is Active: {self.is_active}")
        print(f"  - Invitation Status: {self.invitation_status}")
        print(f"  - Resource Owner: {resource_owner_id}")
        print(f"  - Current User: {self.user_id}")
        
        if not self.is_active or self.invitation_status != InvitationStatus.ACCEPTED:
            print(f"  - ❌ DENIED: User not active or invitation not accepted")
            return False

        permissions = self.get_effective_permissions()
        print(f"  - Effective Permissions: {permissions.get(resource_type, {})}")

        if resource_type not in permissions:
            print(f"  - ❌ DENIED: Resource type {resource_type} not in permissions")
            return False

        # ✅ ENHANCED: Check ownership-based permissions first
        if resource_owner_id and str(resource_owner_id) == str(self.user_id):
            own_action = f"{action}_own"
            if own_action in permissions[resource_type]:
                result = permissions[resource_type][own_action]
                print(f"  - 🔑 OWN RESOURCE: {own_action} = {result}")
                return result

        # Check general permissions
        all_action = f"{action}_all" if f"{action}_all" in permissions[resource_type] else action
        result = permissions[resource_type].get(all_action, False)
        print(f"  - 🌐 GENERAL: {all_action} = {result}")
        
        return result

    def accept_invitation(self):
        """Accept team invitation"""
        if self.invitation_status != InvitationStatus.PENDING:
            return False

        if self.is_invitation_expired:
            self.invitation_status = InvitationStatus.EXPIRED
            return False

        self.invitation_status = InvitationStatus.ACCEPTED
        self.joined_at = datetime.utcnow()
        self.is_active = True
        db.session.commit()
        return True

    def decline_invitation(self):
        """Decline team invitation"""
        if self.invitation_status != InvitationStatus.PENDING:
            return False

        self.invitation_status = InvitationStatus.DECLINED
        db.session.commit()
        return True

    def log_activity(self, activity_type: str, details: dict = None):
        """Log member activity with enhanced tracking"""
        try:
            from datetime import datetime

            # Update last active timestamp
            self.last_active_at = datetime.utcnow()

            # Initialize activity summary if needed
            if not self.activity_summary:
                self.activity_summary = {
                    "snippets_created": 0,
                    "snippets_edited": 0,
                    "collections_created": 0,
                    "comments_posted": 0,
                    "last_7_days_activity": 0,
                    "favorite_languages": {},
                    "collaboration_score": 0,
                    "recent_activities": [],
                }

            # Update activity counters
            if activity_type in self.activity_summary:
                self.activity_summary[activity_type] += 1

            # Add to recent activities
            activity_entry = {
                "type": activity_type,
                "timestamp": datetime.utcnow().isoformat(),
                "details": details or {},
            }

            if "recent_activities" not in self.activity_summary:
                self.activity_summary["recent_activities"] = []

            self.activity_summary["recent_activities"].insert(0, activity_entry)

            # Keep only last 10 activities
            if len(self.activity_summary["recent_activities"]) > 10:
                self.activity_summary["recent_activities"] = self.activity_summary[
                    "recent_activities"
                ][:10]

            # Update weekly activity
            self.activity_summary["last_7_days_activity"] += 1

            # Update language preferences if provided
            if details and "language" in details:
                lang = details["language"]
                if "favorite_languages" not in self.activity_summary:
                    self.activity_summary["favorite_languages"] = {}
                self.activity_summary["favorite_languages"][lang] = (
                    self.activity_summary["favorite_languages"].get(lang, 0) + 1
                )

            # Recalculate collaboration score
            self._update_collaboration_score()

            # Mark as modified for SQLAlchemy
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(self, "activity_summary")

            db.session.commit()

            print(f"✅ ACTIVITY_LOG: Logged {activity_type} for member {self.id}")

        except Exception as e:
            print(f"❌ ACTIVITY_LOG ERROR: {str(e)}")
            db.session.rollback()

    def _update_collaboration_score(self):
        """Update member's collaboration score based on activities"""
        try:
            if not self.activity_summary:
                return

            score = 0
            score += self.activity_summary.get("snippets_created", 0) * 5
            score += self.activity_summary.get("snippets_edited", 0) * 3
            score += self.activity_summary.get("collections_created", 0) * 8
            score += self.activity_summary.get("comments_posted", 0) * 2
            score += min(self.activity_summary.get("last_7_days_activity", 0), 50)

            self.activity_summary["collaboration_score"] = score

        except Exception as e:
            print(f"❌ COLLABORATION_SCORE ERROR: {str(e)}")

    def get_role_permissions(self):
        """Get detailed permissions based on role"""
        try:
            role_permissions = {
                "OWNER": {
                    "can_manage_members": True,
                    "can_edit_team": True,
                    "can_delete_team": True,
                    "can_change_roles": True,
                    "can_invite_members": True,
                    "can_remove_members": True,
                    "can_create_snippets": True,
                    "can_edit_all_snippets": True,
                    "can_delete_all_snippets": True,
                    "can_manage_collections": True,
                    "access_level": "full",
                },
                "ADMIN": {
                    "can_manage_members": True,
                    "can_edit_team": True,
                    "can_delete_team": False,
                    "can_change_roles": True,
                    "can_invite_members": True,
                    "can_remove_members": True,
                    "can_create_snippets": True,
                    "can_edit_all_snippets": True,
                    "can_delete_all_snippets": False,
                    "can_manage_collections": True,
                    "access_level": "admin",
                },
                "EDITOR": {
                    "can_manage_members": False,
                    "can_edit_team": False,
                    "can_delete_team": False,
                    "can_change_roles": False,
                    "can_invite_members": False,
                    "can_remove_members": False,
                    "can_create_snippets": True,
                    "can_edit_all_snippets": False,
                    "can_delete_all_snippets": False,
                    "can_manage_collections": True,
                    "access_level": "editor",
                },
                "VIEWER": {
                    "can_manage_members": False,
                    "can_edit_team": False,
                    "can_delete_team": False,
                    "can_change_roles": False,
                    "can_invite_members": False,
                    "can_remove_members": False,
                    "can_create_snippets": False,
                    "can_edit_all_snippets": False,
                    "can_delete_all_snippets": False,
                    "can_manage_collections": False,
                    "access_level": "read_only",
                },
            }

            role_str = str(self.role).upper()
            if "MEMBERROLE." in role_str:
                role_str = role_str.replace("MEMBERROLE.", "")

            return role_permissions.get(role_str, role_permissions["VIEWER"])

        except Exception as e:
            print(f"❌ GET_ROLE_PERMISSIONS ERROR: {str(e)}")
            return role_permissions["VIEWER"]

    def can_perform_action(self, action: str) -> bool:
        """Check if member can perform specific action"""
        try:
            permissions = self.get_role_permissions()
            return permissions.get(action, False)
        except Exception as e:
            print(f"❌ CAN_PERFORM_ACTION ERROR: {str(e)}")
            return False

    def update_activity(self, activity_type, metadata=None):
        """Update member activity tracking"""
        self.last_active_at = datetime.utcnow()

        if not self.activity_summary:
            self.activity_summary = {
                "snippets_created": 0,
                "snippets_edited": 0,
                "collections_created": 0,
                "comments_posted": 0,
                "last_7_days_activity": 0,
                "favorite_languages": {},
                "collaboration_score": 0,
            }

        # Update specific activity counters
        activity_key = f"{activity_type}"
        if activity_key in self.activity_summary:
            self.activity_summary[activity_key] += 1

        # Update weekly activity
        self.activity_summary["last_7_days_activity"] += 1

        # Update language preferences if metadata includes language
        if metadata and "language" in metadata:
            lang = metadata["language"]
            if lang in self.activity_summary["favorite_languages"]:
                self.activity_summary["favorite_languages"][lang] += 1
            else:
                self.activity_summary["favorite_languages"][lang] = 1

        # Calculate collaboration score
        self._calculate_collaboration_score()

        db.session.commit()

    def _calculate_collaboration_score(self):
        """Calculate member's collaboration score"""
        score = 0
        score += self.activity_summary.get("snippets_created", 0) * 5
        score += self.activity_summary.get("snippets_edited", 0) * 3
        score += self.activity_summary.get("collections_created", 0) * 8
        score += self.activity_summary.get("comments_posted", 0) * 2
        score += min(self.activity_summary.get("last_7_days_activity", 0), 50)

        self.activity_summary["collaboration_score"] = score

    def get_activity_stats(self):
        """Get comprehensive activity statistics"""
        return {
            "summary": self.activity_summary,
            "membership": {
                "role": self.role.value,
                "joined_days_ago": self.days_since_joined,
                "last_active": (
                    self.last_active_at.isoformat() if self.last_active_at else None
                ),
                "is_active": self.is_active,
            },
            "permissions": {
                "can_create_snippets": self.can("create", "snippets"),
                "can_manage_team": self.can_manage_team,
                "is_admin": self.is_admin,
                "access_level": self.access_level,
            },
        }

    def log_member_error(self, context, error, additional_data=None):
        """Enhanced error logging for team member operations"""
        import traceback

        error_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "member_id": str(self.id),
            "team_id": str(self.team_id),
            "user_id": str(self.user_id),
            "role": self.role.value,
            "context": context,
            "error": str(error),
            "traceback": traceback.format_exc(),
            "additional_data": additional_data or {},
        }

        print(f"🔥 TEAM_MEMBER_ERROR [{context}] Member: {self.user_id}: {error_data}")

        # Store error in member's activity summary for debugging
        try:
            if not hasattr(self, "activity_summary") or not self.activity_summary:
                self.activity_summary = {}

            if "errors" not in self.activity_summary:
                self.activity_summary["errors"] = []

            self.activity_summary["errors"].append(error_data)

            # Keep only last 5 errors per member
            if len(self.activity_summary["errors"]) > 5:
                self.activity_summary["errors"] = self.activity_summary["errors"][-5:]

        except Exception as log_error:
            print(
                f"🔥 TEAM_MEMBER: Failed to log error to activity_summary: {str(log_error)}"
            )

        return error_data

    def get_permissions(self):
        """Get permissions list for API compatibility"""
        try:
            effective_perms = self.get_effective_permissions()
            permissions = []

            # Convert nested permissions to flat list
            for category, perms in effective_perms.items():
                for action, allowed in perms.items():
                    if allowed:
                        permissions.append(f"{category}:{action}")

            return permissions
        except Exception as e:
            print(f"❌ TEAM_MEMBER: Error getting permissions: {str(e)}")
            return ["member:basic"]

    def can_invite(self):
        """Check if member can invite others"""
        try:
            return self.can("invite_members", "team")
        except Exception as e:
            print(f"❌ TEAM_MEMBER: Error checking invite permission: {str(e)}")
            return False

    def get_contribution_score(self):
        """Get member contribution score for API"""
        try:
            if not self.activity_summary:
                return 0
            return self.activity_summary.get("collaboration_score", 0)
        except Exception as e:
            print(f"❌ TEAM_MEMBER: Error getting contribution score: {str(e)}")
            return 0

    def to_dict(self, include_sensitive=False):
        """Convert team member to dictionary"""
        data = {
            "id": str(self.id),
            "team_id": str(self.team_id),
            "user_id": str(self.user_id),
            "role": self.role.value,
            "is_active": self.is_active,
            "invitation_status": self.invitation_status.value,
            "invited_at": self.invited_at.isoformat(),
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
            "last_active_at": (
                self.last_active_at.isoformat() if self.last_active_at else None
            ),
            "days_since_joined": self.days_since_joined,
            "activity_stats": self.get_activity_stats(),
        }

        if include_sensitive:
            data.update(
                {
                    "custom_permissions": self.custom_permissions,
                    "preferences": self.preferences,
                    "access_restrictions": self.access_restrictions,
                    "invitation_token": self.invitation_token,
                    "effective_permissions": self.get_effective_permissions(),
                }
            )

        return data

    def __repr__(self):
        return f"<TeamMember user_id={self.user_id} team_id={self.team_id} role={self.role.value}>"


from app.models.team import Team
