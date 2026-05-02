from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import jwt
from flask import current_app

# ADD these imports to your existing user.py file:
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime, timezone
import uuid
from sqlalchemy.dialects.postgresql import UUID
import json
from app.models.custom_types import JSONType, UUIDType

from app.models import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    # Add this field to your User class (around line 15, after email field)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    plan_type = db.Column(db.String(20), default="free", nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    # 🔥 ADD THESE AVATAR FIELDS HERE (after is_active, before snippets relationship)
    avatar_url = db.Column(db.String(255), nullable=True)  # Direct avatar URL field
    avatar_filename = db.Column(db.String(255), nullable=True)  # Original filename
    avatar_uploaded_at = db.Column(db.DateTime, nullable=True)  # Upload timestamp
    snippets = db.relationship(
        "Snippet",
        back_populates="user",
        lazy="dynamic",
        foreign_keys="[Snippet.user_id]",
    )
    collections = db.relationship(
        "Collection",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan",
        foreign_keys="[Collection.user_id]",  # ✅ CORRECT
    )

    # Theme and Dashboard Preferences
    theme_preference = db.Column(
        db.String(20), default="dark"
    )  # 'dark', 'light', 'auto'
    dashboard_layout = db.Column(
        db.String(20), default="grid"
    )  # 'grid', 'list', 'compact'
    sidebar_collapsed = db.Column(db.Boolean, default=False)
    editor_theme = db.Column(db.String(30), default="vs-dark")  # Monaco editor themes
    font_size = db.Column(db.Integer, default=14)
    font_family = db.Column(db.String(50), default="Fira Code")

    # Add these fields to your User model if they don't exist
    github_token = db.Column(db.String(255), nullable=True)
    github_username = db.Column(db.String(255), nullable=True)
    github_avatar = db.Column(db.String(255), nullable=True)
    github_connected_at = db.Column(db.DateTime, nullable=True)
    github_last_sync = db.Column(db.DateTime, nullable=True)

    slack_token = db.Column(db.String(255), nullable=True)
    slack_team_id = db.Column(db.String(255), nullable=True)
    slack_team_name = db.Column(db.String(255), nullable=True)
    slack_user_id = db.Column(db.String(255), nullable=True)
    slack_connected_at = db.Column(db.DateTime, nullable=True)

    vscode_settings = db.Column(db.JSON, nullable=True)
    vscode_last_sync = db.Column(db.DateTime, nullable=True)

    # Add helper methods if they don't exist
    def get_webhooks_count(self):
        """Get count of user's webhooks"""
        # Implement based on your webhook model
        return 0  # Placeholder

    # Dashboard Settings
    show_analytics = db.Column(db.Boolean, default=True)
    show_recent_activity = db.Column(db.Boolean, default=True)
    default_snippet_privacy = db.Column(
        db.String(10), default="private"
    )  # 'private', 'public'
    auto_save_enabled = db.Column(db.Boolean, default=True)
    keyboard_shortcuts_enabled = db.Column(db.Boolean, default=True)

    # Usage Statistics
    total_snippets_created = db.Column(db.Integer, default=0)
    total_collections_created = db.Column(db.Integer, default=0)
    last_active_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_session_time = db.Column(db.Integer, default=0)  # in minutes
    favorite_languages = db.Column(JSONType, default=list)

    # Productivity Settings
    snippets_per_page = db.Column(db.Integer, default=20)
    enable_code_execution = db.Column(db.Boolean, default=False)
    enable_ai_suggestions = db.Column(db.Boolean, default=True)
    enable_live_collaboration = db.Column(db.Boolean, default=False)

    # Notification Preferences
    email_notifications = db.Column(db.Boolean, default=True)
    desktop_notifications = db.Column(db.Boolean, default=True)
    collaboration_notifications = db.Column(db.Boolean, default=True)

    # # NEW: Team memberships and collaboration
    # # Replace with this:
    # team_memberships = db.relationship(
    #     "TeamMember",
    #     back_populates="user",
    #     lazy="dynamic",
    #     cascade="all, delete-orphan",
    # )

    # current_team_id = db.Column(
    #     UUID(as_uuid=True), db.ForeignKey("teams.id"), nullable=True
    # )  # Active team context

    # NEW: Notification preferences
    notification_settings = db.Column(
        JSONType,
        default=lambda: {
            "email_notifications": {
                "enabled": True,
                "snippet_shared": True,
                "collection_shared": True,
                "team_invites": True,
                "collaboration_updates": True,
                "weekly_digest": True,
                "security_alerts": True,
            },
            "push_notifications": {
                "enabled": True,
                "real_time_edits": True,
                "mentions": True,
                "team_activity": False,
                "system_updates": True,
            },
            "in_app_notifications": {
                "enabled": True,
                "show_tooltips": True,
                "activity_feed": True,
                "desktop_notifications": False,
            },
            "notification_schedule": {
                "quiet_hours_enabled": False,
                "quiet_start": "22:00",
                "quiet_end": "08:00",
                "weekend_notifications": True,
            },
        },
    )

    # NEW: Activity and analytics tracking
    activity_stats = db.Column(
        JSONType,
        default=lambda: {
            "snippets_created": 0,
            "snippets_shared": 0,
            "collections_created": 0,
            "collaborations_count": 0,
            "total_views": 0,
            "streak_days": 0,
            "last_activity_date": None,
            "favorite_languages": [],
            "most_active_hours": [],
        },
    )

    # NEW: Integration preferences
    integration_settings = db.Column(
        JSONType,
        default=lambda: {
            "github": {
                "connected": False,
                "username": None,
                "auto_sync": False,
                "default_repo": None,
                "access_token": None,  # Encrypted
            },
            "vscode": {"connected": False, "sync_settings": True, "auto_import": False},
            "slack": {
                "connected": False,
                "workspace_id": None,
                "channel_preferences": [],
            },
        },
    )

    # NEW: Advanced security settings
    security_settings = db.Column(
        JSONType,
        default=lambda: {
            "two_factor_enabled": False,
            "two_factor_secret": None,  # Encrypted
            "backup_codes": [],  # Encrypted
            "trusted_devices": [],
            "login_notifications": True,
            "session_timeout": 24,  # hours
            "password_changed_at": None,
            "failed_login_attempts": 0,
            "locked_until": None,
        },
    )

    # NEW: Workspace and editor preferences
    editor_preferences = db.Column(
        JSONType,
        default=lambda: {
            "font_family": "JetBrains Mono",
            "font_size": 14,
            "line_height": 1.5,
            "theme": "vs-dark",
            "word_wrap": True,
            "show_line_numbers": True,
            "show_minimap": True,
            "auto_save": True,
            "vim_mode": False,
            "tab_size": 2,
            "insert_spaces": True,
            "highlight_active_line": True,
            "bracket_matching": True,
            "code_folding": True,
        },
    )

    # NEW: API and developer settings
    api_settings = db.Column(
        JSONType,
        default=lambda: {
            "api_key": None,  # Generated API key for external access
            "api_key_created_at": None,
            "api_rate_limit": 1000,  # requests per hour
            "webhook_endpoints": [],
            "cors_origins": [],
        },
    )

    # Relationships
    # Replace these relationship definitions in user.py
    # In user.py, update these relationship definitions

    # Remove any direct imports of Snippet at the top

    # Update these relationships

    # current_team = db.relationship("Team", foreign_keys=[current_team_id])

    # NEW: Advanced profile and preferences
    profile_settings = db.Column(
        JSONType,
        default=lambda: {
            "avatar_url": None,
            "bio": "",
            "location": "",
            "website": "",
            "twitter": "",
            "github": "",
            "linkedin": "",
            "timezone": "UTC",
            "language": "en",
            "profile_visibility": "public",  # public, team, private
        },
    )


    # ADD THESE LINES HERE (before __init__ method):
    team_memberships = db.relationship(
        "TeamMember", 
        back_populates="user", 
        lazy="dynamic",
        foreign_keys="[TeamMember.user_id]"
    )

    current_team_id = db.Column(
        UUIDType, 
        db.ForeignKey("teams.id"), 
        nullable=True
    )

    current_team = db.relationship("Team", foreign_keys=[current_team_id])

    # Relationships
    # Relationships - UPDATE this section

    def __init__(self, email, password, username=None, plan_type="free", role=None):
        print(f"🔍 USER INIT - Starting with email: {email}, username: {username}, role: {role}")

        self.email = email.lower().strip()

        # FIXED: Properly handle username
        if username and username.strip():
            self.username = username.lower().strip()
            print(f"✅ USER INIT - Using provided username: {self.username}")
        else:
            # Generate username from email if not provided
            self.username = email.split("@")[0].lower().replace('.', '').replace('_', '')
            print(f"🔍 USER INIT - Generated username from email: {self.username}")

        self.set_password(password)
        self.plan_type = plan_type

        # FIXED: Initialize profile_settings with role
        default_profile = {
            'avatar_url': None,
            'bio': '',
            'location': '',
            'website': '',
            'twitter': '',
            'github': '',
            'linkedin': '',
            'timezone': 'UTC',
            'language': 'en',
            'profile_visibility': 'public'
        }

        # Add role if provided
        if role and role.strip():
            default_profile['role'] = role.strip()
            print(f"✅ USER INIT - Added role to profile: {role}")
        else:
            default_profile['role'] = 'Developer'  # Default role
            print(f"🔍 USER INIT - Using default role: Developer")

        self.profile_settings = default_profile

        print(f"✅ USER INIT - User created successfully:")
        print(f"  📧 Email: {self.email}")
        print(f"  👤 Username: {self.username}")
        print(f"  🎭 Role: {default_profile['role']}")
        print(f"  📋 Plan: {self.plan_type}")

    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if provided password matches hash"""
        return check_password_hash(self.password_hash, password)

    def get_dashboard_preferences(self):

        return {
            "theme": self.theme_preference,
            "layout": self.dashboard_layout,
            "sidebar_collapsed": self.sidebar_collapsed,
            "editor_theme": self.editor_theme,
            "font_size": self.font_size,
            "font_family": self.font_family,
            "show_analytics": self.show_analytics,
            "show_recent_activity": self.show_recent_activity,
            "auto_save_enabled": self.auto_save_enabled,
            "keyboard_shortcuts_enabled": self.keyboard_shortcuts_enabled,
            "snippets_per_page": self.snippets_per_page,
            "enable_code_execution": self.enable_code_execution,
            "enable_ai_suggestions": self.enable_ai_suggestions,
        }

    def update_preferences(self, preferences_dict):
        """Update user preferences from dict"""
        for key, value in preferences_dict.items():
            if hasattr(self, key):
                setattr(self, key, value)
        db.session.commit()

    def update_usage_stats(self, action_type, language=None):
        """Update user usage statistics"""
        if action_type == "snippet_created":
            self.total_snippets_created += 1
        elif action_type == "collection_created":
            self.total_collections_created += 1

        self.last_active_date = datetime.utcnow()

        if language:
            # Update favorite languages stats
            if self.favorite_languages:
                lang_stats = json.loads(self.favorite_languages)
            else:
                lang_stats = {}

            lang_stats[language] = lang_stats.get(language, 0) + 1
            self.favorite_languages = json.dumps(lang_stats)

        db.session.commit()

    def get_usage_analytics(self):
        """Return user analytics data"""
        favorite_langs = (
            json.loads(self.favorite_languages) if self.favorite_languages else {}
        )

        return {
            "total_snippets": self.total_snippets_created,
            "total_collections": self.total_collections_created,
            "total_session_time": self.total_session_time,
            "favorite_languages": favorite_langs,
            "last_active": (
                self.last_active_date.isoformat() if self.last_active_date else None
            ),
            "account_age_days": (
                (datetime.utcnow() - self.created_at).days if self.created_at else 0
            ),
        }

    def generate_token(self, expires_in=3600):
        """Generate JWT token for API authentication"""
        payload = {
            "user_id": self.id,
            "exp": datetime.utcnow().timestamp() + expires_in,
        }
        return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")

    @staticmethod
    def verify_token(token):
        """Verify JWT token and return user"""
        try:
            payload = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            user_id = payload["user_id"]
            return User.query.get(user_id)
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def can_create_snippet(self):
        """Check if user can create more snippets based on plan"""
        if self.plan_type == "pro":
            return True
        # Free plan limit: 100 snippets
        return self.snippets.count() < 100

    def get_snippet_count(self):
        """Get total number of snippets for this user"""
        return self.snippets.count()

    def get_collection_count(self):
        """Get total number of collections for this user"""
        return self.collections.count()

    def to_dict(self):
        """Convert user to dictionary (excluding sensitive data)"""
        return {
            "id": self.id,
            "email": self.email,
            "created_at": self.created_at.isoformat(),
            "plan_type": self.plan_type,
            "snippet_count": self.get_snippet_count(),
            "collection_count": self.get_collection_count(),
            "is_active": self.is_active,
        }

    def __repr__(self):
        return f"<User {self.email}>"

    # NEW FIELDS TO ADD:

    # User Preferences
    preferences = db.Column(
        JSONType,
        default=lambda: {
            "theme": "light",  # light, dark, auto
            "editor_theme": "github",  # syntax highlighting theme
            "font_size": 14,
            "show_line_numbers": True,
            "auto_save": True,
            "default_language": "javascript",
            "snippets_per_page": 20,
            "default_view": "grid",  # grid, list
            "keyboard_shortcuts": True,
            "notifications": {
                "email": True,
                "browser": True,
                "snippet_shared": True,
                "collection_shared": True,
            },
            "privacy": {
                "profile_public": False,
                "snippets_discoverable": False,
                "show_activity": True,
            },
        },
    )

    # Usage Statistics
    total_snippets = db.Column(db.Integer, default=0)
    total_collections = db.Column(db.Integer, default=0)
    snippets_created_today = db.Column(db.Integer, default=0)
    last_snippet_date = db.Column(db.Date)

    # Activity tracking
    login_count = db.Column(db.Integer, default=0)
    last_login_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Feature usage statistics
    search_count = db.Column(db.Integer, default=0)
    export_count = db.Column(db.Integer, default=0)
    share_count = db.Column(db.Integer, default=0)

    # Language preferences (most used languages)
    favorite_languages = db.Column(
        JSON, default=list
    )  # ['javascript', 'python', 'java']

    # Subscription info (for monetization)
    subscription_tier = db.Column(
        db.String(20), default="free"
    )  # free, pro, enterprise
    subscription_expires_at = db.Column(db.DateTime)
    snippet_limit = db.Column(db.Integer, default=100)  # free tier limit

    # ADD these methods to your existing User model:

    def update_preference(self, key, value):
        """Update a specific user preference"""
        if self.preferences is None:
            self.preferences = {}

        # Handle nested preferences (e.g., 'notifications.email')
        if "." in key:
            keys = key.split(".")
            current = self.preferences
            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                current = current[k]
            current[keys[-1]] = value
        else:
            self.preferences[key] = value

        # Mark as modified for SQLAlchemy
        db.session.add(self)
        db.session.commit()

    def get_preference(self, key, default=None):
        """Get a specific user preference"""
        if self.preferences is None:
            return default

        if "." in key:
            keys = key.split(".")
            current = self.preferences
            for k in keys:
                if isinstance(current, dict) and k in current:
                    current = current[k]
                else:
                    return default
            return current
        else:
            return self.preferences.get(key, default)

    def increment_snippet_count(self):
        """Increment snippet count and update daily stats"""
        self.total_snippets += 1

        today = datetime.now().date()
        if self.last_snippet_date != today:
            self.snippets_created_today = 1
            self.last_snippet_date = today
        else:
            self.snippets_created_today += 1

        self.update_activity()

    def increment_collection_count(self):
        """Increment collection count"""
        self.total_collections += 1
        self.update_activity()

    def decrement_snippet_count(self):
        """Decrement snippet count"""
        if self.total_snippets > 0:
            self.total_snippets -= 1

    def decrement_collection_count(self):
        """Decrement collection count"""
        if self.total_collections > 0:
            self.total_collections -= 1

    def update_activity(self):
        """Update last activity timestamp"""
        self.last_active_at = datetime.utcnow()

    def record_login(self):
        """Record user login"""
        self.login_count += 1
        self.last_login_at = datetime.utcnow()
        self.update_activity()

    def increment_search_count(self):
        """Track search usage"""
        self.search_count += 1
        self.update_activity()

    def increment_export_count(self):
        """Track export usage"""
        self.export_count += 1
        self.update_activity()

    def increment_share_count(self):
        """Track sharing usage"""
        self.share_count += 1
        self.update_activity()

    def update_favorite_languages(self, language):
        """Update favorite languages based on usage"""
        if self.favorite_languages is None:
            self.favorite_languages = []

        # Add language if not in list
        if language not in self.favorite_languages:
            self.favorite_languages.append(language)

        # Keep only top 10 languages
        if len(self.favorite_languages) > 10:
            self.favorite_languages = self.favorite_languages[:10]

    def can_create_snippet(self):
        """Check if user can create more snippets based on their tier"""
        if self.subscription_tier == "free":
            return self.total_snippets < self.snippet_limit
        return True  # Pro/Enterprise users have unlimited snippets

    def get_usage_stats(self):
        """Get comprehensive usage statistics"""
        return {
            "total_snippets": self.total_snippets,
            "total_collections": self.total_collections,
            "snippets_today": self.snippets_created_today,
            "login_count": self.login_count,
            "search_count": self.search_count,
            "export_count": self.export_count,
            "share_count": self.share_count,
            "favorite_languages": self.favorite_languages or [],
            "last_active": (
                self.last_active_at.isoformat() if self.last_active_at else None
            ),
            "subscription_tier": self.subscription_tier,
            "snippet_limit": self.snippet_limit,
            "snippets_remaining": (
                max(0, self.snippet_limit - self.total_snippets)
                if self.subscription_tier == "free"
                else "unlimited"
            ),
        }

    def is_premium_user(self):
        """Check if user has premium subscription"""
        if self.subscription_tier in ["pro", "enterprise"]:
            if self.subscription_expires_at:
                return self.subscription_expires_at > datetime.utcnow()
            return True
        return False

    def days_since_signup(self):
        """Calculate days since user signed up"""
        if self.created_at:
            return (datetime.utcnow() - self.created_at).days
        return 0

    def to_dict_with_stats(self):
        """Convert user to dictionary including statistics"""
        base_dict = self.to_dict()  # Assuming you have a basic to_dict method
        base_dict.update(
            {
                "preferences": self.preferences,
                "usage_stats": self.get_usage_stats(),
                "is_premium": self.is_premium_user(),
                "days_since_signup": self.days_since_signup(),
            }
        )
        return base_dict

    # NEW: Team membership methods
    def get_teams(self, include_role=False):
        """Get all teams user belongs to"""
        if include_role:
            return [
                (tm.team, tm.role)
                for tm in self.team_memberships
                if tm.status == "active"
            ]
        return [tm.team for tm in self.team_memberships if tm.status == "active"]

    def is_team_member(self, team_id):
        """Check if user is member of specific team"""
        return any(
            tm.team_id == team_id and tm.status == "active"
            for tm in self.team_memberships
        )

    def get_team_role(self, team_id):
        """Get user's role in specific team"""
        for tm in self.team_memberships:
            if tm.team_id == team_id and tm.status == "active":
                return tm.role
        return None

    def can_access_team_resource(self, team_id, required_role="member"):
        """Check if user can access team resource with required role"""
        role_hierarchy = {"member": 0, "admin": 1, "owner": 2}
        user_role = self.get_team_role(team_id)

        if not user_role:
            return False

        return role_hierarchy.get(user_role, -1) >= role_hierarchy.get(required_role, 0)

    # NEW: Notification methods
    def should_send_notification(self, notification_type, channel="email"):
        """Check if user wants to receive specific notification"""
        settings = self.notification_settings

        if channel == "email":
            return settings.get("email_notifications", {}).get(
                "enabled", True
            ) and settings.get("email_notifications", {}).get(notification_type, True)
        elif channel == "push":
            return settings.get("push_notifications", {}).get(
                "enabled", True
            ) and settings.get("push_notifications", {}).get(notification_type, True)
        elif channel == "in_app":
            return settings.get("in_app_notifications", {}).get(
                "enabled", True
            ) and settings.get("in_app_notifications", {}).get(notification_type, True)

        return False

    def is_in_quiet_hours(self):
        """Check if current time is in user's quiet hours"""
        schedule = self.notification_settings.get("notification_schedule", {})
        if not schedule.get("quiet_hours_enabled", False):
            return False

        # Implementation would check current time against quiet_start/quiet_end
        # considering user's timezone
        return False  # Simplified for now

    # NEW: Activity tracking methods
    def track_activity(self, activity_type, details=None):
        """Track user activity for analytics"""
        stats = self.activity_stats.copy()

        # Update counters
        if activity_type == "snippet_created":
            stats["snippets_created"] = stats.get("snippets_created", 0) + 1
        elif activity_type == "snippet_shared":
            stats["snippets_shared"] = stats.get("snippets_shared", 0) + 1
        elif activity_type == "collection_created":
            stats["collections_created"] = stats.get("collections_created", 0) + 1

        # Update last activity
        stats["last_activity_date"] = datetime.utcnow().isoformat()

        # Update streak (simplified logic)
        self.update_activity_streak(stats)

        self.activity_stats = stats
        db.session.commit()

    def update_activity_streak(self, stats):
        """Update user's activity streak"""
        last_activity = stats.get("last_activity_date")
        if last_activity:
            # Simplified streak calculation
            # In real implementation, you'd check consecutive days
            stats["streak_days"] = stats.get("streak_days", 0) + 1

    # NEW: Integration methods
    def connect_integration(self, service, credentials):
        """Connect external service integration"""
        settings = self.integration_settings.copy()
        if service in settings:
            settings[service].update(credentials)
            settings[service]["connected"] = True
            self.integration_settings = settings
            db.session.commit()
            return True
        return False

    def disconnect_integration(self, service):
        """Disconnect external service integration"""
        settings = self.integration_settings.copy()
        if service in settings:
            settings[service] = {
                "connected": False,
                **{k: None for k in settings[service] if k != "connected"},
            }
            self.integration_settings = settings
            db.session.commit()
            return True
        return False

    # NEW: Security methods
    def enable_two_factor(self, secret, backup_codes):
        """Enable two-factor authentication"""
        security = self.security_settings.copy()
        security["two_factor_enabled"] = True
        security["two_factor_secret"] = secret  # Should be encrypted
        security["backup_codes"] = backup_codes  # Should be encrypted
        self.security_settings = security
        db.session.commit()

    def verify_two_factor(self, token):
        """Verify two-factor authentication token"""
        # Implementation would verify TOTP token
        return True  # Simplified for now

    def is_account_locked(self):
        """Check if account is locked due to security reasons"""
        security = self.security_settings
        locked_until = security.get("locked_until")
        if locked_until:\
            from datetime import datetime

        return datetime.utcnow() < datetime.fromisoformat(locked_until)
        return False

    def get_auth_token(self):
        """Generate auth token for WebSocket authentication"""
        try:
            from datetime import datetime, timedelta
            from flask import current_app
            import jwt
            
            payload = {
                'user_id': str(self.id),
                'email': self.email,
                'exp': datetime.utcnow() + timedelta(hours=24)
            }
            
            token = jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')
            print(f"✅ Generated auth token for user: {self.email}")
            return token
        except Exception as e:
            print(f"❌ Error generating auth token: {e}")
            return None

    def to_dict(self, include_sensitive=False, include_stats=False):
        """Convert user to dictionary"""
        data = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_active": self.is_active,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "theme_preference": self.theme_preference,
            "profile_settings": self.profile_settings,
            "current_team_id": self.current_team_id,
        }

        if include_sensitive:
            data.update(
                {
                    "notification_settings": self.notification_settings,
                    "integration_settings": self.integration_settings,
                    "editor_preferences": self.editor_preferences,
                    "dashboard_settings": self.dashboard_settings,
                }
            )

        if include_stats:
            data["activity_stats"] = self.activity_stats
            data["teams"] = [
                tm.team.to_dict()
                for tm in self.team_memberships
                if tm.status == "active"
            ]

        return data

    def __repr__(self):
        return f"<User {self.username}>"
