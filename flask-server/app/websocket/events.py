# flask-server/app/websocket/events.py
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import json
from datetime import datetime

class WebSocketEvents:
    """
    Centralized WebSocket event definitions for consistent communication
    between Chrome extension and Flask server
    """

    # Connection Events
    CONNECT = 'connect'
    DISCONNECT = 'disconnect'
    CONNECTION_STATUS = 'connection_status'
    HEARTBEAT = 'heartbeat'
    HEARTBEAT_RESPONSE = 'heartbeat_response'

    # Snippet Events
    SNIPPET_SAVE = 'snippet_save'
    SNIPPET_SAVED = 'snippet_saved'
    SNIPPET_UPDATE = 'snippet_update'
    SNIPPET_UPDATED = 'snippet_updated'
    SNIPPET_DELETE = 'snippet_delete'
    SNIPPET_DELETED = 'snippet_deleted'
    SNIPPET_CREATED = 'snippet_created'  # Broadcast event

    # Collection Events
    COLLECTION_CREATE = 'collection_create'
    COLLECTION_CREATED = 'collection_created'
    COLLECTION_UPDATE = 'collection_update'
    COLLECTION_UPDATED = 'collection_updated'
    COLLECTION_DELETE = 'collection_delete'
    COLLECTION_DELETED = 'collection_deleted'

    # Sync Events
    SYNC_REQUEST = 'sync_request'
    SYNC_RESPONSE = 'sync_response'
    SYNC_STATUS = 'sync_status'

    # Search Events
    SEARCH_REQUEST = 'search_request'
    SEARCH_RESULTS = 'search_results'

    # Error Events
    ERROR = 'error'
    WARNING = 'warning'
    SUCCESS = 'success'

    # User Events
    USER_ACTIVITY = 'user_activity'
    USER_PREFERENCES = 'user_preferences'

    # Real-time Collaboration (Future use)
    USER_JOINED = 'user_joined'
    USER_LEFT = 'user_left'
    CURSOR_MOVE = 'cursor_move'
    TYPING_START = 'typing_start'
    TYPING_STOP = 'typing_stop'


class SnippetEvents:
    """
    Snippet-specific events for backward compatibility
    """

    # Basic snippet events
    CREATED = "snippet_created"
    UPDATED = "snippet_updated"
    DELETED = "snippet_deleted"
    VIEWED = "snippet_viewed"

    # Snippet interaction events
    SAVED = "snippet_saved"
    SHARED = "snippet_shared"
    DUPLICATED = "snippet_duplicated"
    EXECUTED = "snippet_executed"

    # Snippet collection events
    ADDED_TO_COLLECTION = "snippet_added_to_collection"
    REMOVED_FROM_COLLECTION = "snippet_removed_from_collection"

    # Snippet sync events
    SYNC_STARTED = "snippet_sync_started"
    SYNC_COMPLETED = "snippet_sync_completed"
    SYNC_FAILED = "snippet_sync_failed"


class CollaborationEvents:
    """
    Collaboration-specific events for team features
    """

    # Real-time collaboration events
    EDIT_START = "collaboration_edit_start"
    EDIT_LIVE = "collaboration_edit_live"
    EDIT_END = "collaboration_edit_end"
    CURSOR_MOVE = "collaboration_cursor_move"
    SELECTION_CHANGE = "collaboration_selection_change"

    # Team presence events
    USER_JOINED_ROOM = "collaboration_user_joined_room"
    USER_LEFT_ROOM = "collaboration_user_left_room"
    USER_TYPING = "collaboration_user_typing"
    USER_IDLE = "collaboration_user_idle"

    # Comment and review events
    COMMENT_ADDED = "collaboration_comment_added"
    COMMENT_UPDATED = "collaboration_comment_updated"
    COMMENT_DELETED = "collaboration_comment_deleted"
    REVIEW_REQUESTED = "collaboration_review_requested"
    REVIEW_COMPLETED = "collaboration_review_completed"

    # Conflict resolution
    CONFLICT_DETECTED = "collaboration_conflict_detected"
    CONFLICT_RESOLVED = "collaboration_conflict_resolved"
    MERGE_CONFLICT = "collaboration_merge_conflict"


# ===== PHASE 3C: REAL-TIME COLLABORATION EVENTS =====
class CollaborativeEditingEvents:
    """Real-time collaborative editing events"""

    # Session Management
    JOIN_EDITING_SESSION = "join_editing_session"
    LEAVE_EDITING_SESSION = "leave_editing_session"
    EDITING_SESSION_JOINED = "editing_session_joined"
    EDITING_SESSION_ERROR = "editing_session_error"

    # Live Editing
    LIVE_CODE_CHANGE = "live_code_change"
    LIVE_CODE_UPDATED = "live_code_updated"
    LIVE_CHANGE_ERROR = "live_change_error"
    SNIPPET_CONTENT_SYNC = "snippet_content_sync"

    # User Presence
    USER_JOINED_EDITING = "user_joined_editing"
    USER_LEFT_EDITING = "user_left_editing"
    CURSOR_POSITION_CHANGE = "cursor_position_change"
    CURSOR_POSITION_UPDATED = "cursor_position_updated"

    # Typing Indicators
    TYPING_INDICATOR_CHANGE = "typing_indicator_change"
    TYPING_STATUS_UPDATED = "typing_status_updated"

    # Comments & Chat
    COLLABORATIVE_COMMENT = "collaborative_comment"
    COMMENT_ADDED = "comment_added"
    COMMENT_ERROR = "comment_error"

    # Conflict Resolution
    CONFLICT_DETECTED = "conflict_detected"
    CONFLICT_RESOLVED = "conflict_resolved"


class EventMessages:
    """
    Standard message templates for WebSocket events
    """
    
    # Success Messages
    SNIPPET_SAVED_SUCCESS = "Snippet saved successfully"
    SNIPPET_UPDATED_SUCCESS = "Snippet updated successfully"
    SNIPPET_DELETED_SUCCESS = "Snippet deleted successfully"
    COLLECTION_CREATED_SUCCESS = "Collection created successfully"
    SYNC_COMPLETED = "Data synchronized successfully"
    
    # Error Messages
    AUTH_REQUIRED = "Authentication required"
    SNIPPET_NOT_FOUND = "Snippet not found"
    COLLECTION_NOT_FOUND = "Collection not found"
    INVALID_DATA = "Invalid data provided"
    SAVE_FAILED = "Failed to save snippet"
    UPDATE_FAILED = "Failed to update snippet"
    DELETE_FAILED = "Failed to delete snippet"
    SYNC_FAILED = "Failed to synchronize data"
    CONNECTION_FAILED = "Connection failed"
    
    # Warning Messages
    OFFLINE_MODE = "Working in offline mode"
    SYNC_PENDING = "Synchronization pending"
    STORAGE_LIMIT = "Storage limit approaching"

class EventPayloadSchemas:
    """
    Payload schemas for WebSocket events to ensure consistency
    """
    
    SNIPPET_SAVE = {
        "type": "object",
        "required": ["code", "language", "title"],
        "properties": {
            "code": {"type": "string", "minLength": 1},
            "language": {"type": "string", "minLength": 1},
            "title": {"type": "string", "minLength": 1, "maxLength": 200},
            "source_url": {"type": "string", "format": "uri"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "collection_id": {"type": "integer"},
            "description": {"type": "string", "maxLength": 1000}
        }
    }
    
    SNIPPET_UPDATE = {
        "type": "object",
        "required": ["snippet_id"],
        "properties": {
            "snippet_id": {"type": "integer"},
            "title": {"type": "string", "maxLength": 200},
            "code": {"type": "string"},
            "language": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "description": {"type": "string", "maxLength": 1000}
        }
    }
    
    COLLECTION_CREATE = {
        "type": "object",
        "required": ["name"],
        "properties": {
            "name": {"type": "string", "minLength": 1, "maxLength": 100},
            "description": {"type": "string", "maxLength": 500},
            "color": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
            "is_public": {"type": "boolean"}
        }
    }
    
    SEARCH_REQUEST = {
        "type": "object",
        "required": ["query"],
        "properties": {
            "query": {"type": "string", "minLength": 1},
            "language": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "collection_id": {"type": "integer"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            "offset": {"type": "integer", "minimum": 0}
        }
    }

class ConnectionStates:
    """
    WebSocket connection state constants
    """
    
    CONNECTING = 'connecting'
    CONNECTED = 'connected'
    DISCONNECTED = 'disconnected'
    RECONNECTING = 'reconnecting'
    ERROR = 'error'

class SyncStates:
    """
    Synchronization state constants
    """
    
    IDLE = 'idle'
    SYNCING = 'syncing'
    SUCCESS = 'success'
    FAILED = 'failed'
    PENDING = 'pending'
    OFFLINE = 'offline'

class Priority:
    """
    Event priority levels for queue management
    """
    
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


# Event metadata for processing
EVENT_METADATA = {
    WebSocketEvents.SNIPPET_SAVE: {
        'priority': Priority.HIGH,
        'requires_auth': True,
        'rate_limit': 60,  # per minute
        'timeout': 5000,   # milliseconds
    },
    WebSocketEvents.SNIPPET_UPDATE: {
        'priority': Priority.NORMAL,
        'requires_auth': True,
        'rate_limit': 120,
        'timeout': 3000,
    },
    WebSocketEvents.SYNC_REQUEST: {
        'priority': Priority.NORMAL,
        'requires_auth': True,
        'rate_limit': 10,
        'timeout': 10000,
    },
    WebSocketEvents.HEARTBEAT: {
        'priority': Priority.LOW,
        'requires_auth': False,
        'rate_limit': 300,
        'timeout': 1000,
    }
}
class EventType(Enum):
    """Modern event types for advanced collaboration"""

    # Core Collaboration Events
    SNIPPET_EDIT_START = "snippet_edit_start"
    SNIPPET_EDIT_LIVE = "snippet_edit_live"
    SNIPPET_EDIT_END = "snippet_edit_end"
    SNIPPET_CURSOR_MOVE = "snippet_cursor_move"
    SNIPPET_SELECTION = "snippet_selection"

    # Advanced Collaboration Features
    COLLABORATIVE_COMMENT = "collaborative_comment"
    COLLABORATIVE_SUGGESTION = "collaborative_suggestion"
    LIVE_CODE_REVIEW = "live_code_review"
    PAIR_PROGRAMMING_SESSION = "pair_programming_session"

    # Team Presence & Activity
    USER_PRESENCE_UPDATE = "user_presence_update"
    USER_TYPING_INDICATOR = "user_typing_indicator"
    USER_FOCUS_CHANGE = "user_focus_change"
    TEAM_ACTIVITY_FEED = "team_activity_feed"

    # Smart Notifications
    SMART_MENTION = "smart_mention"
    AI_SUGGESTION = "ai_suggestion"
    CONFLICT_DETECTION = "conflict_detection"
    MERGE_REQUEST = "merge_request"

    # Collection Collaboration
    COLLECTION_SHARED = "collection_shared"
    COLLECTION_PERMISSION_CHANGED = "collection_permission_changed"
    COLLECTION_REAL_TIME_UPDATE = "collection_real_time_update"

    # Integration Events
    GITHUB_SYNC_STATUS = "github_sync_status"
    SLACK_NOTIFICATION = "slack_notification"
    WEBHOOK_TRIGGERED = "webhook_triggered"

    # Advanced Team Features
    TEAM_WORKSPACE_UPDATE = "team_workspace_update"
    LIVE_DASHBOARD_UPDATE = "live_dashboard_update"
    ANALYTICS_REAL_TIME = "analytics_real_time"

    # Security & Audit
    SECURITY_ALERT = "security_alert"
    AUDIT_LOG_ENTRY = "audit_log_entry"
    PERMISSION_VIOLATION = "permission_violation"


@dataclass
class BaseEvent:
    """Base event structure with modern features"""

    event_type: EventType
    user_id: str
    team_id: Optional[str]
    timestamp: datetime
    session_id: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "user_id": self.user_id,
            "team_id": self.team_id,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "metadata": self.metadata,
        }


@dataclass
class SnippetCollaborationEvent(BaseEvent):
    """Advanced snippet collaboration with live features"""

    snippet_id: str
    operation: str  # 'insert', 'delete', 'replace', 'format'
    position: Dict[str, int]  # {'line': 10, 'column': 5}
    content: str
    selection_range: Optional[Dict[str, int]] = None
    conflict_resolution: Optional[str] = None
    ai_assisted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "snippet_id": self.snippet_id,
                "operation": self.operation,
                "position": self.position,
                "content": self.content,
                "selection_range": self.selection_range,
                "conflict_resolution": self.conflict_resolution,
                "ai_assisted": self.ai_assisted,
            }
        )
        return data


@dataclass
class UserPresenceEvent(BaseEvent):
    """Modern user presence with rich status"""

    status: str  # 'online', 'coding', 'reviewing', 'away', 'focused'
    current_snippet: Optional[str] = None
    current_collection: Optional[str] = None
    activity_summary: Optional[str] = None
    device_info: Optional[Dict[str, str]] = None
    focus_mode: bool = False

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "status": self.status,
                "current_snippet": self.current_snippet,
                "current_collection": self.current_collection,
                "activity_summary": self.activity_summary,
                "device_info": self.device_info,
                "focus_mode": self.focus_mode,
            }
        )
        return data


@dataclass
class SmartNotificationEvent(BaseEvent):
    """AI-powered smart notifications"""

    notification_type: str  # 'mention', 'suggestion', 'conflict', 'insight'
    title: str
    message: str
    priority: str  # 'low', 'medium', 'high', 'urgent'
    action_buttons: List[Dict[str, str]]
    ai_generated: bool = False
    context_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "notification_type": self.notification_type,
                "title": self.title,
                "message": self.message,
                "priority": self.priority,
                "action_buttons": self.action_buttons,
                "ai_generated": self.ai_generated,
                "context_data": self.context_data,
            }
        )
        return data


@dataclass
class LiveCodeReviewEvent(BaseEvent):
    """Advanced live code review features"""

    snippet_id: str
    review_type: str  # 'suggestion', 'improvement', 'bug_fix', 'optimization'
    reviewer_id: str
    comments: List[Dict[str, Any]]
    suggestions: List[Dict[str, Any]]
    approval_status: str  # 'pending', 'approved', 'needs_changes'
    automated_checks: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "snippet_id": self.snippet_id,
                "review_type": self.review_type,
                "reviewer_id": self.reviewer_id,
                "comments": self.comments,
                "suggestions": self.suggestions,
                "approval_status": self.approval_status,
                "automated_checks": self.automated_checks,
            }
        )
        return data


@dataclass
class IntegrationEvent(BaseEvent):
    """Third-party integration events"""

    integration_type: str  # 'github', 'slack', 'vscode', 'webhook'
    action: str
    status: str  # 'success', 'failure', 'pending'
    external_id: Optional[str] = None
    sync_data: Optional[Dict[str, Any]] = None
    error_details: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "integration_type": self.integration_type,
                "action": self.action,
                "status": self.status,
                "external_id": self.external_id,
                "sync_data": self.sync_data,
                "error_details": self.error_details,
            }
        )
        return data


class EventManager:
    """Advanced event management with modern features"""

    def __init__(self):
        self.event_handlers = {}
        self.event_queue = []
        self.analytics_buffer = []

    def register_handler(self, event_type: EventType, handler):
        """Register event handler with type safety"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    def emit_event(self, event: BaseEvent) -> bool:
        """Emit event with advanced processing"""
        try:
            # Add to analytics buffer
            self.analytics_buffer.append(event.to_dict())

            # Process event handlers
            if event.event_type in self.event_handlers:
                for handler in self.event_handlers[event.event_type]:
                    handler(event)

            # Add to event queue for processing
            self.event_queue.append(event)

            return True
        except Exception as e:
            print(f"Error emitting event: {e}")
            return False

    def create_snippet_edit_event(
        self,
        user_id: str,
        team_id: str,
        snippet_id: str,
        operation: str,
        position: Dict[str, int],
        content: str,
    ) -> SnippetCollaborationEvent:
        """Factory method for snippet collaboration events"""
        return SnippetCollaborationEvent(
            event_type=EventType.SNIPPET_EDIT_LIVE,
            user_id=user_id,
            team_id=team_id,
            timestamp=datetime.utcnow(),
            session_id=f"session_{user_id}_{datetime.utcnow().timestamp()}",
            metadata={"real_time": True, "collaborative": True},
            snippet_id=snippet_id,
            operation=operation,
            position=position,
            content=content,
        )

    def create_presence_event(
        self, user_id: str, team_id: str, status: str
    ) -> UserPresenceEvent:
        """Factory method for user presence events"""
        return UserPresenceEvent(
            event_type=EventType.USER_PRESENCE_UPDATE,
            user_id=user_id,
            team_id=team_id,
            timestamp=datetime.utcnow(),
            session_id=f"presence_{user_id}",
            metadata={"persistent": True},
            status=status,
        )

    def create_smart_notification(
        self,
        user_id: str,
        team_id: str,
        notification_type: str,
        title: str,
        message: str,
    ) -> SmartNotificationEvent:
        """Factory method for smart notifications"""
        return SmartNotificationEvent(
            event_type=EventType.SMART_MENTION,
            user_id=user_id,
            team_id=team_id,
            timestamp=datetime.utcnow(),
            session_id=f"notification_{datetime.utcnow().timestamp()}",
            metadata={"ai_powered": True},
            notification_type=notification_type,
            title=title,
            message=message,
            priority="medium",
            action_buttons=[],
        )

    def get_analytics_data(self) -> List[Dict[str, Any]]:
        """Get analytics data for real-time insights"""
        return self.analytics_buffer.copy()

    def clear_analytics_buffer(self):
        """Clear analytics buffer after processing"""
        self.analytics_buffer.clear()


# Event routing configuration for modern WebSocket handling
EVENT_ROUTING = {
    # Real-time collaboration routes
    EventType.SNIPPET_EDIT_LIVE: "team_room",
    EventType.SNIPPET_CURSOR_MOVE: "team_room",
    EventType.COLLABORATIVE_COMMENT: "team_room",
    EventType.LIVE_CODE_REVIEW: "team_room",
    # Presence updates
    EventType.USER_PRESENCE_UPDATE: "team_presence",
    EventType.USER_TYPING_INDICATOR: "team_presence",
    # Notifications
    EventType.SMART_MENTION: "user_notifications",
    EventType.AI_SUGGESTION: "user_notifications",
    # Team-wide updates
    EventType.TEAM_WORKSPACE_UPDATE: "team_broadcast",
    EventType.COLLECTION_SHARED: "team_broadcast",
    # Integration events
    EventType.GITHUB_SYNC_STATUS: "integration_status",
    EventType.SLACK_NOTIFICATION: "integration_status",
    # Security events
    EventType.SECURITY_ALERT: "admin_alerts",
    EventType.AUDIT_LOG_ENTRY: "admin_logs",
}

# Export the event manager instance
event_manager = EventManager()


# ADD THESE NEW EVENT CLASSES TO YOUR EXISTING events.py FILE


class SnippetEditEvents:
    """
    Snippet edit tracking events for real-time collaboration
    """

    # Edit lifecycle events
    EDIT_CREATED = "snippet_edit_created"
    EDIT_UPDATED = "snippet_edit_updated"
    EDIT_DELETED = "snippet_edit_deleted"
    EDIT_VIEWED = "snippet_edit_viewed"

    # Real-time notifications
    EDIT_NOTIFICATION = "snippet_edit_notification"
    EDIT_ACTIVITY_UPDATE = "snippet_edit_activity_update"

    # Team collaboration
    TEAM_EDIT_SUMMARY = "team_edit_summary"
    EDITOR_JOINED = "editor_joined_team"
    EDITOR_LEFT = "editor_left_team"


class EditTrackingEventMessages:
    """
    Standard message templates for edit tracking events
    """

    # Success Messages
    EDIT_CREATED_SUCCESS = "Snippet edit created successfully"
    EDIT_DELETED_SUCCESS = "Snippet edit deleted successfully"
    EDIT_VIEWED_SUCCESS = "Snippet edit viewed"

    # Notification Messages
    NEW_EDIT_NOTIFICATION = "{editor_name} created a new edit: {description}"
    EDIT_DELETED_NOTIFICATION = "{editor_name} deleted their edit"
    TEAM_ACTIVITY_UPDATE = "New editing activity in {team_name}"

    # Error Messages
    EDIT_NOT_FOUND = "Snippet edit not found"
    EDIT_ACCESS_DENIED = "Access denied to snippet edit"
    EDIT_CREATION_FAILED = "Failed to create snippet edit"
    EDIT_DELETION_FAILED = "Failed to delete snippet edit"
    DESCRIPTION_REQUIRED = "Edit description is required"


@dataclass
class SnippetEditEvent(BaseEvent):
    """
    Snippet edit event with comprehensive data
    """

    edit_id: str
    original_snippet_id: str
    team_id: str
    editor_user_id: str
    edit_description: str
    action: str  # 'created', 'deleted', 'viewed'
    edit_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "edit_id": self.edit_id,
                "original_snippet_id": self.original_snippet_id,
                "team_id": self.team_id,
                "editor_user_id": self.editor_user_id,
                "edit_description": self.edit_description,
                "action": self.action,
                "edit_data": self.edit_data,
            }
        )
        return data


# ADD TO EVENT_ROUTING CONFIGURATION
EDIT_TRACKING_EVENT_ROUTING = {
    SnippetEditEvents.EDIT_CREATED: "team_room",
    SnippetEditEvents.EDIT_DELETED: "team_room",
    SnippetEditEvents.EDIT_NOTIFICATION: "team_room",
    SnippetEditEvents.TEAM_EDIT_SUMMARY: "team_room",
    SnippetEditEvents.EDITOR_JOINED: "team_presence",
    SnippetEditEvents.EDITOR_LEFT: "team_presence",
}

# UPDATE EVENT_METADATA WITH EDIT TRACKING EVENTS
EDIT_TRACKING_EVENT_METADATA = {
    SnippetEditEvents.EDIT_CREATED: {
        "priority": Priority.HIGH,
        "requires_auth": True,
        "rate_limit": 30,  # per minute
        "timeout": 5000,  # milliseconds
    },
    SnippetEditEvents.EDIT_DELETED: {
        "priority": Priority.NORMAL,
        "requires_auth": True,
        "rate_limit": 60,
        "timeout": 3000,
    },
    SnippetEditEvents.EDIT_NOTIFICATION: {
        "priority": Priority.NORMAL,
        "requires_auth": False,
        "rate_limit": 120,
        "timeout": 2000,
    },
}


# EXTEND EventManager WITH EDIT TRACKING METHODS
class ExtendedEventManager(EventManager):
    """Extended event manager with edit tracking capabilities"""

    def create_snippet_edit_event(
        self,
        edit_id: str,
        original_snippet_id: str,
        team_id: str,
        editor_user_id: str,
        edit_description: str,
        action: str = "created",
    ) -> SnippetEditEvent:
        """Factory method for snippet edit events"""
        return SnippetEditEvent(
            event_type=EventType.SNIPPET_EDIT_LIVE,
            user_id=editor_user_id,
            team_id=team_id,
            timestamp=datetime.utcnow(),
            session_id=f"edit_{edit_id}_{datetime.utcnow().timestamp()}",
            metadata={"edit_tracking": True, "real_time": True},
            edit_id=edit_id,
            original_snippet_id=original_snippet_id,
            editor_user_id=editor_user_id,
            edit_description=edit_description,
            action=action,
        )

    def emit_edit_created_event(self, edit_data: Dict[str, Any]) -> bool:
        """Emit edit created event to team room"""
        try:
            from app.extensions import socketio

            socketio.emit(
                SnippetEditEvents.EDIT_CREATED,
                {
                    "type": SnippetEditEvents.EDIT_CREATED,
                    "data": edit_data,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                room=f"team_{edit_data.get('team_id')}",
            )
            return True
        except Exception as e:
            print(f"❌ Failed to emit edit created event: {str(e)}")
            return False

    def emit_edit_deleted_event(self, edit_data: Dict[str, Any]) -> bool:
        """Emit edit deleted event to team room"""
        try:
            from app.extensions import socketio

            socketio.emit(
                SnippetEditEvents.EDIT_DELETED,
                {
                    "type": SnippetEditEvents.EDIT_DELETED,
                    "data": edit_data,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                room=f"team_{edit_data.get('team_id')}",
            )
            return True
        except Exception as e:
            print(f"❌ Failed to emit edit deleted event: {str(e)}")
            return False


# Create extended event manager instance
edit_event_manager = ExtendedEventManager()
