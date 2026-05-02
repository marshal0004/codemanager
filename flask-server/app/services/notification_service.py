import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
from flask_socketio import emit
from sqlalchemy import and_, or_, desc
from app.models.user import User
from app.models.snippet import Snippet
from app.models.collection import Collection
from app.models.team import Team
from app.models.team_member import TeamMember
import redis
import uuid
from threading import Thread
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class NotificationType(Enum):
    SNIPPET_SHARED = "snippet_shared"
    SNIPPET_UPDATED = "snippet_updated"
    SNIPPET_COMMENTED = "snippet_commented"
    COLLECTION_SHARED = "collection_shared"
    TEAM_INVITATION = "team_invitation"
    TEAM_MEMBER_JOINED = "team_member_joined"
    COLLABORATION_STARTED = "collaboration_started"
    COLLABORATION_ENDED = "collaboration_ended"
    SYSTEM_UPDATE = "system_update"
    ACHIEVEMENT_UNLOCKED = "achievement_unlocked"
    WEEKLY_DIGEST = "weekly_digest"
    SECURITY_ALERT = "security_alert"


class NotificationPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


class NotificationChannel(Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    PUSH = "push"
    WEBHOOK = "webhook"


@dataclass
class Notification:
    id: str
    user_id: int
    type: NotificationType
    title: str
    message: str
    data: Dict = None
    priority: NotificationPriority = NotificationPriority.MEDIUM
    channels: List[NotificationChannel] = None
    created_at: datetime = None
    read_at: Optional[datetime] = None
    clicked_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    action_url: Optional[str] = None
    action_text: Optional[str] = None
    avatar_url: Optional[str] = None
    group_key: Optional[str] = None  # For grouping similar notifications


@dataclass
class ActivityItem:
    id: str
    user_id: int
    actor_id: int
    action: str
    target_type: str  # 'snippet', 'collection', 'team'
    target_id: int
    target_name: Optional[str]
    description: str
    metadata: Dict = None
    created_at: datetime = None
    is_public: bool = True


class NotificationService:
    def __init__(self, redis_client=None):
        self.redis_client = redis_client or redis.Redis(decode_responses=True)
        self.notification_templates = self._load_notification_templates()
        self.user_preferences = {}

    def _load_notification_templates(self) -> Dict:
        """Load notification templates for different types"""
        return {
            NotificationType.SNIPPET_SHARED: {
                "title": "{actor} shared a snippet with you",
                "message": "{actor} shared '{snippet_name}' - {snippet_language}",
                "emoji": "🔗",
                "color": "#4ECDC4",
            },
            NotificationType.SNIPPET_UPDATED: {
                "title": "Snippet updated",
                "message": "'{snippet_name}' was updated by {actor}",
                "emoji": "✏️",
                "color": "#45B7D1",
            },
            NotificationType.SNIPPET_COMMENTED: {
                "title": "New comment on your snippet",
                "message": "{actor} commented on '{snippet_name}': {comment_preview}",
                "emoji": "💬",
                "color": "#96CEB4",
            },
            NotificationType.COLLECTION_SHARED: {
                "title": "{actor} shared a collection",
                "message": "Collection '{collection_name}' with {snippet_count} snippets",
                "emoji": "📁",
                "color": "#FFEAA7",
            },
            NotificationType.TEAM_INVITATION: {
                "title": "Team invitation",
                "message": "You've been invited to join '{team_name}' by {actor}",
                "emoji": "👥",
                "color": "#DDA0DD",
            },
            NotificationType.TEAM_MEMBER_JOINED: {
                "title": "New team member",
                "message": "{actor} joined your team '{team_name}'",
                "emoji": "🎉",
                "color": "#98D8C8",
            },
            NotificationType.COLLABORATION_STARTED: {
                "title": "Collaboration session started",
                "message": "{actor} started editing '{snippet_name}' with you",
                "emoji": "🤝",
                "color": "#F7DC6F",
            },
            NotificationType.ACHIEVEMENT_UNLOCKED: {
                "title": "Achievement unlocked! 🏆",
                "message": "You've unlocked '{achievement_name}'",
                "emoji": "🏆",
                "color": "#FFD700",
            },
            NotificationType.SECURITY_ALERT: {
                "title": "Security Alert",
                "message": "{message}",
                "emoji": "🔒",
                "color": "#FF6B6B",
            },
        }

    def create_notification(
        self,
        user_id: int,
        notification_type: NotificationType,
        data: Dict,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        channels: List[NotificationChannel] = None,
        expires_in_hours: int = 168,  # 7 days default
    ) -> str:
        """Create a new notification"""

        notification_id = str(uuid.uuid4())
        template = self.notification_templates.get(notification_type, {})

        # Build notification content
        title = template.get("title", "New notification").format(**data)
        message = template.get("message", "You have a new notification").format(**data)

        # Set default channels if not provided
        if channels is None:
            channels = [NotificationChannel.IN_APP]
            if priority.value >= NotificationPriority.HIGH.value:
                channels.append(NotificationChannel.EMAIL)

        notification = Notification(
            id=notification_id,
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            data=data,
            priority=priority,
            channels=channels,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=expires_in_hours),
            action_url=data.get("action_url"),
            action_text=data.get("action_text"),
            avatar_url=data.get("avatar_url"),
            group_key=data.get("group_key"),
        )

        # Store notification
        self._store_notification(notification)

        # Send through appropriate channels
        self._send_notification(notification)

        return notification_id

    def _store_notification(self, notification: Notification):
        """Store notification in Redis and update user's notification list"""
        # Store individual notification
        self.redis_client.setex(
            f"notification:{notification.id}",
            int((notification.expires_at - datetime.utcnow()).total_seconds()),
            json.dumps(asdict(notification), default=str),
        )

        # Add to user's notification list (sorted by creation time)
        self.redis_client.zadd(
            f"user_notifications:{notification.user_id}",
            {notification.id: notification.created_at.timestamp()},
        )

        # Increment unread count
        self.redis_client.incr(f"unread_count:{notification.user_id}")

        # Group similar notifications if group_key provided
        if notification.group_key:
            self.redis_client.sadd(
                f"notification_group:{notification.group_key}", notification.id
            )

    def _send_notification(self, notification: Notification):
        """Send notification through specified channels"""
        for channel in notification.channels:
            if channel == NotificationChannel.IN_APP:
                self._send_in_app_notification(notification)
            elif channel == NotificationChannel.EMAIL:
                self._send_email_notification(notification)
            elif channel == NotificationChannel.PUSH:
                self._send_push_notification(notification)
            elif channel == NotificationChannel.WEBHOOK:
                self._send_webhook_notification(notification)

    def _send_in_app_notification(self, notification: Notification):
        """Send real-time in-app notification"""
        user = User.query.get(notification.user_id)
        if user and user.is_online:
            emit(
                "new_notification",
                {
                    "id": notification.id,
                    "type": notification.type.value,
                    "title": notification.title,
                    "message": notification.message,
                    "priority": notification.priority.value,
                    "created_at": notification.created_at.isoformat(),
                    "action_url": notification.action_url,
                    "action_text": notification.action_text,
                    "avatar_url": notification.avatar_url,
                    "data": notification.data,
                },
                room=f"user_{notification.user_id}",
            )

    def _send_email_notification(self, notification: Notification):
        """Send email notification (background thread)"""

        def send_email():
            try:
                user = User.query.get(notification.user_id)
                if not user or not user.email_notifications_enabled:
                    return

                # Create email content
                msg = MIMEMultipart("alternative")
                msg["Subject"] = f"[CodeSnippets] {notification.title}"
                msg["From"] = "notifications@codesnippets.com"
                msg["To"] = user.email

                # HTML email template
                html_body = self._generate_email_template(notification, user)
                msg.attach(MIMEText(html_body, "html"))

                # Send email (implement your SMTP configuration)
                # This is a placeholder - implement actual SMTP sending
                print(f"Sending email to {user.email}: {notification.title}")

            except Exception as e:
                print(f"Error sending email notification: {e}")

        Thread(target=send_email).start()

    def _send_push_notification(self, notification: Notification):
        """Send push notification (placeholder for web push)"""
        # Implement web push notifications here
        pass

    def _send_webhook_notification(self, notification: Notification):
        """Send webhook notification"""
        # Implement webhook sending here
        pass

    def _generate_email_template(self, notification: Notification, user: User) -> str:
        """Generate beautiful HTML email template"""
        template = self.notification_templates.get(notification.type, {})
        color = template.get("color", "#4ECDC4")
        emoji = template.get("emoji", "📝")

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{notification.title}</title>
        </head>
        <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f5f5f5;">
            <div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
                <div style="background: linear-gradient(135deg, {color}, {color}99); padding: 30px; text-align: center;">
                    <div style="font-size: 48px; margin-bottom: 16px;">{emoji}</div>
                    <h1 style="color: white; margin: 0; font-size: 24px; font-weight: 600;">{notification.title}</h1>
                </div>
                <div style="padding: 30px;">
                    <p style="font-size: 16px; line-height: 1.6; color: #333; margin-bottom: 24px;">
                        Hi {user.username},
                    </p>
                    <p style="font-size: 16px; line-height: 1.6; color: #333; margin-bottom: 24px;">
                        {notification.message}
                    </p>
                    {f'<a href="{notification.action_url}" style="display: inline-block; background-color: {color}; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 600; margin: 16px 0;">{notification.action_text}</a>' if notification.action_url else ''}
                </div>
                <div style="background-color: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #e9ecef;">
                    <p style="margin: 0; color: #6c757d; font-size: 14px;">
                        Sent by CodeSnippets • <a href="#" style="color: {color};">Unsubscribe</a>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

    def get_user_notifications(
        self, user_id: int, limit: int = 50, offset: int = 0, unread_only: bool = False
    ) -> List[Dict]:
        """Get user's notifications"""
        # Get notification IDs from sorted set
        notification_ids = self.redis_client.zrevrange(
            f"user_notifications:{user_id}", offset, offset + limit - 1
        )

        notifications = []
        for notification_id in notification_ids:
            notification_data = self.redis_client.get(f"notification:{notification_id}")
            if notification_data:
                notification = json.loads(notification_data)

                # Filter unread if requested
                if unread_only and notification.get("read_at"):
                    continue

                notifications.append(notification)

        return notifications

    def mark_as_read(self, user_id: int, notification_ids: List[str]) -> bool:
        """Mark notifications as read"""
        for notification_id in notification_ids:
            notification_data = self.redis_client.get(f"notification:{notification_id}")
            if notification_data:
                notification = json.loads(notification_data)
                if notification["user_id"] == user_id and not notification.get(
                    "read_at"
                ):
                    notification["read_at"] = datetime.utcnow().isoformat()

                    # Update stored notification
                    self.redis_client.setex(
                        f"notification:{notification_id}",
                        int(
                            (
                                datetime.fromisoformat(
                                    notification["expires_at"].replace("Z", "+00:00")
                                )
                                - datetime.utcnow()
                            ).total_seconds()
                        ),
                        json.dumps(notification),
                    )

                    # Decrement unread count
                    current_count = int(
                        self.redis_client.get(f"unread_count:{user_id}") or 0
                    )
                    if current_count > 0:
                        self.redis_client.decr(f"unread_count:{user_id}")

        return True

    def mark_as_clicked(self, user_id: int, notification_id: str) -> bool:
        """Mark notification as clicked"""
        notification_data = self.redis_client.get(f"notification:{notification_id}")
        if notification_data:
            notification = json.loads(notification_data)
            if notification["user_id"] == user_id:
                notification["clicked_at"] = datetime.utcnow().isoformat()

                # Also mark as read if not already
                if not notification.get("read_at"):
                    notification["read_at"] = datetime.utcnow().isoformat()
                    current_count = int(
                        self.redis_client.get(f"unread_count:{user_id}") or 0
                    )
                    if current_count > 0:
                        self.redis_client.decr(f"unread_count:{user_id}")

                self.redis_client.setex(
                    f"notification:{notification_id}",
                    int(
                        (
                            datetime.fromisoformat(
                                notification["expires_at"].replace("Z", "+00:00")
                            )
                            - datetime.utcnow()
                        ).total_seconds()
                    ),
                    json.dumps(notification),
                )
                return True
        return False

    def dismiss_notification(self, user_id: int, notification_id: str) -> bool:
        """Dismiss/delete notification"""
        notification_data = self.redis_client.get(f"notification:{notification_id}")
        if notification_data:
            notification = json.loads(notification_data)
            if notification["user_id"] == user_id:
                # Remove from user's notification list
                self.redis_client.zrem(f"user_notifications:{user_id}", notification_id)

                # Delete the notification
                self.redis_client.delete(f"notification:{notification_id}")

                # Decrement unread count if it wasn't read
                if not notification.get("read_at"):
                    current_count = int(
                        self.redis_client.get(f"unread_count:{user_id}") or 0
                    )
                    if current_count > 0:
                        self.redis_client.decr(f"unread_count:{user_id}")

                return True
        return False

    def get_unread_count(self, user_id: int) -> int:
        """Get user's unread notification count"""
        return int(self.redis_client.get(f"unread_count:{user_id}") or 0)

    def create_activity_item(
        self,
        user_id: int,
        actor_id: int,
        action: str,
        target_type: str,
        target_id: int,
        target_name: str = None,
        description: str = None,
        metadata: Dict = None,
        is_public: bool = True,
    ) -> str:
        """Create activity feed item"""
        activity_id = str(uuid.uuid4())

        activity = ActivityItem(
            id=activity_id,
            user_id=user_id,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            description=description
            or self._generate_activity_description(action, target_type, target_name),
            metadata=metadata or {},
            created_at=datetime.utcnow(),
            is_public=is_public,
        )

        # Store activity item
        self.redis_client.setex(
            f"activity:{activity_id}",
            86400 * 30,  # Keep for 30 days
            json.dumps(asdict(activity), default=str),
        )

        # Add to user's activity feed
        self.redis_client.zadd(
            f"user_activity:{user_id}", {activity_id: activity.created_at.timestamp()}
        )

        # Add to global activity feed if public
        if is_public:
            self.redis_client.zadd(
                "global_activity", {activity_id: activity.created_at.timestamp()}
            )

        # Add to team activity feed if user is in teams
        user_teams = TeamMember.query.filter_by(user_id=user_id).all()
        for team_member in user_teams:
            self.redis_client.zadd(
                f"team_activity:{team_member.team_id}",
                {activity_id: activity.created_at.timestamp()},
            )

        return activity_id

    def _generate_activity_description(
        self, action: str, target_type: str, target_name: str
    ) -> str:
        """Generate human-readable activity description"""
        action_templates = {
            "created": f"created {target_type} '{target_name}'",
            "updated": f"updated {target_type} '{target_name}'",
            "deleted": f"deleted {target_type} '{target_name}'",
            "shared": f"shared {target_type} '{target_name}'",
            "favorited": f"favorited {target_type} '{target_name}'",
            "commented": f"commented on {target_type} '{target_name}'",
            "forked": f"forked {target_type} '{target_name}'",
            "joined": f"joined {target_type} '{target_name}'",
            "left": f"left {target_type} '{target_name}'",
        }

        return action_templates.get(action, f"{action} {target_type} '{target_name}'")

    def get_activity_feed(
        self,
        user_id: int = None,
        team_id: int = None,
        limit: int = 50,
        offset: int = 0,
        include_global: bool = False,
    ) -> List[Dict]:
        """Get activity feed"""
        if team_id:
            feed_key = f"team_activity:{team_id}"
        elif user_id:
            feed_key = f"user_activity:{user_id}"
        elif include_global:
            feed_key = "global_activity"
        else:
            return []

        # Get activity IDs from sorted set (newest first)
        activity_ids = self.redis_client.zrevrange(feed_key, offset, offset + limit - 1)

        activities = []
        for activity_id in activity_ids:
            activity_data = self.redis_client.get(f"activity:{activity_id}")
            if activity_data:
                activity = json.loads(activity_data)

                # Enrich with user data
                actor = User.query.get(activity["actor_id"])
                if actor:
                    activity["actor"] = {
                        "id": actor.id,
                        "username": actor.username,
                        "avatar": actor.profile_picture,
                        "display_name": actor.display_name or actor.username,
                    }

                activities.append(activity)

        return activities

    def create_batch_notifications(self, notifications_data: List[Dict]) -> List[str]:
        """Create multiple notifications efficiently"""
        notification_ids = []

        for notification_data in notifications_data:
            notification_id = self.create_notification(**notification_data)
            notification_ids.append(notification_id)

        return notification_ids

    def send_digest_notification(
        self, user_id: int, digest_type: str = "weekly"
    ) -> str:
        """Send digest notification with user's activity summary"""
        # Calculate time range
        if digest_type == "daily":
            since = datetime.utcnow() - timedelta(days=1)
            title = "Your daily snippet digest"
        elif digest_type == "weekly":
            since = datetime.utcnow() - timedelta(days=7)
            title = "Your weekly snippet digest"
        else:
            since = datetime.utcnow() - timedelta(days=30)
            title = "Your monthly snippet digest"

        # Get user's activity and stats
        user_activities = self.get_activity_feed(user_id=user_id, limit=20)
        recent_activities = [
            activity
            for activity in user_activities
            if datetime.fromisoformat(activity["created_at"].replace("Z", "+00:00"))
            > since
        ]

        # Get snippet stats
        snippet_count = Snippet.query.filter(
            Snippet.user_id == user_id, Snippet.created_at > since
        ).count()

        # Create digest notification
        digest_data = {
            "user_id": user_id,
            "activities_count": len(recent_activities),
            "snippets_created": snippet_count,
            "digest_type": digest_type,
            "action_url": "/dashboard",
            "action_text": "View Dashboard",
        }

        return self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.WEEKLY_DIGEST,
            data=digest_data,
            priority=NotificationPriority.LOW,
            channels=[NotificationChannel.EMAIL],
        )

    def cleanup_old_notifications(self, days_old: int = 30):
        """Clean up old notifications and activities"""
        cutoff_time = datetime.utcnow() - timedelta(days=days_old)
        cutoff_timestamp = cutoff_time.timestamp()

        # Find all user notification lists
        user_keys = self.redis_client.keys("user_notifications:*")

        for user_key in user_keys:
            # Remove old notifications from user lists
            self.redis_client.zremrangebyscore(user_key, 0, cutoff_timestamp)

        # Clean up activity feeds
        activity_keys = self.redis_client.keys("*_activity*")
        for activity_key in activity_keys:
            self.redis_client.zremrangebyscore(activity_key, 0, cutoff_timestamp)

        print(f"Cleaned up notifications and activities older than {days_old} days")

    def get_notification_preferences(self, user_id: int) -> Dict:
        """Get user's notification preferences"""
        prefs_data = self.redis_client.get(f"notification_prefs:{user_id}")
        if prefs_data:
            return json.loads(prefs_data)

        # Default preferences
        return {
            "email_notifications": True,
            "push_notifications": True,
            "digest_frequency": "weekly",
            "notification_types": {
                "snippet_shared": True,
                "snippet_updated": True,
                "team_invitation": True,
                "collaboration_started": True,
                "security_alert": True,
            },
        }

    def update_notification_preferences(self, user_id: int, preferences: Dict) -> bool:
        """Update user's notification preferences"""
        self.redis_client.setex(
            f"notification_prefs:{user_id}",
            86400 * 365,  # Keep for 1 year
            json.dumps(preferences),
        )
        return True

    def get_notification_analytics(self, user_id: int = None, days: int = 30) -> Dict:
        """Get notification analytics"""
        since = datetime.utcnow() - timedelta(days=days)

        if user_id:
            # User-specific analytics
            notifications = self.get_user_notifications(user_id, limit=1000)
            total_sent = len(notifications)
            total_read = len([n for n in notifications if n.get("read_at")])
            total_clicked = len([n for n in notifications if n.get("clicked_at")])
        else:
            # Global analytics (would need database queries in real implementation)
            total_sent = 0
            total_read = 0
            total_clicked = 0

        return {
            "total_sent": total_sent,
            "total_read": total_read,
            "total_clicked": total_clicked,
            "read_rate": (total_read / total_sent * 100) if total_sent > 0 else 0,
            "click_rate": (total_clicked / total_sent * 100) if total_sent > 0 else 0,
            "period_days": days,
        }


# Global instance
notification_service = NotificationService()
