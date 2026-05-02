import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from flask_socketio import emit, join_room, leave_room
from sqlalchemy import and_
from app.models.snippet import Snippet
import traceback

# Add this import after line 10:
from app import db
from app.models.user import User
from app.models.team_member import TeamMember
from app.websocket.events import CollaborationEvents
import redis
import uuid
from difflib import SequenceMatcher

# ADD THIS IMPORT
from app.models.activity import Activity


def log_collaboration_error(context, error, additional_data=None):
    """Enhanced error logging for collaboration operations with detailed tracking"""
    import traceback
    from datetime import datetime
    import os

    error_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "context": context,
        "error": str(error),
        "error_type": type(error).__name__,
        "traceback": traceback.format_exc(),
        "additional_data": additional_data or {},
        "session_info": {
            "active_sessions": len(
                getattr(collaboration_service, "active_sessions", {})
            ),
            "operations_queue": len(
                getattr(collaboration_service, "operations_queue", {})
            ),
            "cursors": len(getattr(collaboration_service, "cursors", {})),
        },
    }

    # Console logging with color coding
    print(f"🔥 COLLABORATION_ERROR [{context}]:")
    print(f"   ❌ Error: {error}")
    print(f"   📍 Type: {type(error).__name__}")
    print(f"   📊 Additional Data: {additional_data}")
    print(f"   🔍 Traceback: {traceback.format_exc()}")

    # File logging for persistent tracking
    try:
        log_dir = "flask-server/data/logs"
        os.makedirs(log_dir, exist_ok=True)

        log_file = os.path.join(log_dir, "collaboration_errors.log")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"TIMESTAMP: {error_data['timestamp']}\n")
            f.write(f"CONTEXT: {context}\n")
            f.write(f"ERROR: {error}\n")
            f.write(f"TYPE: {error_data['error_type']}\n")
            f.write(f"ADDITIONAL_DATA: {additional_data}\n")
            f.write(f"SESSION_INFO: {error_data['session_info']}\n")
            f.write(f"TRACEBACK:\n{error_data['traceback']}\n")
            f.write(f"{'='*80}\n")

        print(f"✅ Error logged to: {log_file}")

    except Exception as log_error:
        print(f"🔥 Failed to write error log: {str(log_error)}")

    # Store in Redis for debugging if available
    try:
        if (
            hasattr(log_collaboration_error, "redis_client")
            and log_collaboration_error.redis_client
        ):
            log_collaboration_error.redis_client.lpush(
                "collaboration_errors", json.dumps(error_data, default=str)
            )
            log_collaboration_error.redis_client.ltrim("collaboration_errors", 0, 99)
            print(f"✅ Error stored in Redis")
    except Exception as redis_error:
        print(f"🔥 Failed to store collaboration error in Redis: {str(redis_error)}")

    return error_data


@dataclass
class CollaborationSession:
    session_id: str
    snippet_id: int
    participants: List[Dict]
    created_at: datetime
    last_activity: datetime
    locked_by: Optional[int] = None
    version: int = 1


@dataclass
class Operation:
    id: str
    type: str  # 'insert', 'delete', 'replace'
    position: int
    content: str
    user_id: int
    timestamp: datetime
    applied: bool = False


@dataclass
class Cursor:
    user_id: int
    username: str
    position: int
    selection_start: int
    selection_end: int
    color: str
    last_seen: datetime


class CollaborationService:
    def __init__(self, redis_client=None):
        try:
            self.redis_client = redis_client or redis.Redis(decode_responses=True)
            # Test Redis connection
            self.redis_client.ping()
            print("✅ COLLABORATION: Redis connected successfully")
        except Exception as redis_error:
            print(f"⚠️ COLLABORATION: Redis connection failed: {redis_error}")
            print("⚠️ COLLABORATION: Running without Redis persistence")
            self.redis_client = None

        self.active_sessions: Dict[str, CollaborationSession] = {}
        self.operations_queue: Dict[str, List[Operation]] = {}
        self.cursors: Dict[str, Dict[int, Cursor]] = {}
        self.user_colors = [
            "#FF6B6B",
            "#4ECDC4",
            "#45B7D1",
            "#96CEB4",
            "#FFEAA7",
            "#DDA0DD",
            "#98D8C8",
            "#F7DC6F",
            "#BB8FCE",
            "#85C1E9",
        ]

        # Set up error logging Redis client
        if self.redis_client:
            log_collaboration_error.redis_client = self.redis_client

    def safe_date_format(self, date_value):
        """Safely convert date to ISO format with enhanced error logging"""
        try:
            if date_value is None:
                return None

            # If it's already a string, return as-is (database already formatted it)
            if isinstance(date_value, str):
                print(f"🔍 SAFE_DATE: Already string format: {date_value}")
                return date_value

            # If it's a datetime object, convert to ISO format
            if hasattr(date_value, "isoformat"):
                result = date_value.isoformat()
                print(f"✅ SAFE_DATE: Converted datetime to ISO: {result}")
                return result

            # If it's something else, convert to string safely
            result = str(date_value)
            print(
                f"⚠️ SAFE_DATE: Converted unknown type {type(date_value)} to string: {result}"
            )
            return result

        except Exception as e:
            print(
                f"❌ SAFE_DATE ERROR: {str(e)} for value: {date_value} (type: {type(date_value)})"
            )
            print(f"❌ SAFE_DATE TRACEBACK: {traceback.format_exc()}")
            return str(date_value) if date_value else None

    def create_collaboration_session(self, snippet_id: int, user_id: int) -> str:
        """Create a new collaboration session for a snippet"""
        try:
            session_id = f"collab_{snippet_id}_{uuid.uuid4().hex[:8]}"

            # Get user info
            user = User.query.get(user_id)
            if not user:
                raise ValueError(f"User not found: {user_id}")

            participant = {
                "user_id": user_id,
                "username": getattr(user, "username", f"User_{user_id}"),
                "avatar": getattr(user, "profile_picture", None),
                "color": self.user_colors[user_id % len(self.user_colors)],
                "joined_at": datetime.utcnow().isoformat(),
                "is_active": True,
            }

            session = CollaborationSession(
                session_id=session_id,
                snippet_id=snippet_id,
                participants=[participant],
                created_at=datetime.utcnow(),
                last_activity=datetime.utcnow(),
            )

            self.active_sessions[session_id] = session
            self.operations_queue[session_id] = []
            self.cursors[session_id] = {}

            # Store in Redis for persistence (with error handling)
            try:
                self.redis_client.setex(
                    f"collab_session:{session_id}",
                    3600,
                    json.dumps(asdict(session), default=str),
                )
            except Exception as redis_error:
                print(
                    f"⚠️ Redis storage failed, continuing without persistence: {redis_error}"
                )

            print(f"✅ COLLABORATION: Session created - {session_id}")
            return session_id

        except Exception as e:
            log_collaboration_error(
                "SESSION_CREATION", e, {"snippet_id": snippet_id, "user_id": user_id}
            )
            raise

    def join_collaboration_session(self, session_id: str, user_id: int) -> Dict:
        """Add a user to an existing collaboration session"""
        if session_id not in self.active_sessions:
            # Try to load from Redis
            session_data = self.redis_client.get(f"collab_session:{session_id}")
            if not session_data:
                raise ValueError("Collaboration session not found")

            session_dict = json.loads(session_data)
            self.active_sessions[session_id] = CollaborationSession(**session_dict)

        session = self.active_sessions[session_id]
        user = User.query.get(user_id)

        # Check if user already in session
        existing_participant = next(
            (p for p in session.participants if p["user_id"] == user_id), None
        )

        if not existing_participant:
            participant = {
                "user_id": user_id,
                "username": user.username,
                "avatar": user.profile_picture,
                "color": self.user_colors[user_id % len(self.user_colors)],
                "joined_at": datetime.utcnow().isoformat(),
                "is_active": True,
            }
            session.participants.append(participant)
        else:
            existing_participant["is_active"] = True
            existing_participant["joined_at"] = datetime.utcnow().isoformat()

        session.last_activity = datetime.utcnow()

        # Update Redis
        self.redis_client.setex(
            f"collab_session:{session_id}",
            3600,
            json.dumps(asdict(session), default=str),
        )

        # Notify other participants
        emit(
            "user_joined",
            {
                "session_id": session_id,
                "user": (
                    participant if not existing_participant else existing_participant
                ),
                "participants_count": len(
                    [p for p in session.participants if p["is_active"]]
                ),
            },
            room=session_id,
            include_self=False,
        )

        return {
            "session_id": session_id,
            "participants": session.participants,
            "operations": [
                asdict(op) for op in self.operations_queue.get(session_id, [])
            ],
            "version": session.version,
        }

    def leave_collaboration_session(self, session_id: str, user_id: int):
        """Remove a user from collaboration session"""
        if session_id not in self.active_sessions:
            return

        session = self.active_sessions[session_id]

        # Mark user as inactive
        for participant in session.participants:
            if participant["user_id"] == user_id:
                participant["is_active"] = False
                participant["left_at"] = datetime.utcnow().isoformat()
                break

        # Remove cursor
        if session_id in self.cursors and user_id in self.cursors[session_id]:
            del self.cursors[session_id][user_id]

        # Notify other participants
        emit(
            "user_left",
            {
                "session_id": session_id,
                "user_id": user_id,
                "participants_count": len(
                    [p for p in session.participants if p["is_active"]]
                ),
            },
            room=session_id,
        )

        # Clean up if no active participants
        active_participants = [p for p in session.participants if p["is_active"]]
        if not active_participants:
            self.cleanup_session(session_id)

    def apply_operation(self, session_id: str, operation_data: Dict) -> Dict:
        """Apply a collaborative editing operation"""
        if session_id not in self.active_sessions:
            raise ValueError("Collaboration session not found")

        session = self.active_sessions[session_id]

        # Create operation
        operation = Operation(
            id=operation_data.get("id", str(uuid.uuid4())),
            type=operation_data["type"],
            position=operation_data["position"],
            content=operation_data.get("content", ""),
            user_id=operation_data["user_id"],
            timestamp=datetime.utcnow(),
        )

        # Add to operations queue
        if session_id not in self.operations_queue:
            self.operations_queue[session_id] = []

        self.operations_queue[session_id].append(operation)

        # Transform operation against concurrent operations
        transformed_op = self.transform_operation(session_id, operation)

        # Apply to snippet
        snippet = Snippet.query.get(session.snippet_id)
        if snippet:
            snippet.code = self.apply_operation_to_content(snippet.code, transformed_op)
            snippet.updated_at = datetime.utcnow()
            # Note: Remove snippet.version += 1 as your model doesn't have this field
            db.session.commit()
        session.last_activity = datetime.utcnow()

        # Broadcast to other participants
        emit(
            "operation_applied",
            {
                "session_id": session_id,
                "operation": asdict(transformed_op),
                "version": session.version,
                "snippet_id": session.snippet_id,
            },
            room=session_id,
            include_self=False,
        )

        return {
            "success": True,
            "operation_id": transformed_op.id,
            "version": session.version,
        }

    def transform_operation(self, session_id: str, operation: Operation) -> Operation:
        """Transform operation against concurrent operations (Operational Transformation)"""
        if session_id not in self.operations_queue:
            return operation

        # Get concurrent operations (operations that happened after this one started)
        concurrent_ops = [
            op
            for op in self.operations_queue[session_id]
            if op.timestamp > operation.timestamp - timedelta(seconds=1)
            and op.user_id != operation.user_id
        ]

        transformed_op = operation

        for concurrent_op in concurrent_ops:
            transformed_op = self.transform_against_operation(
                transformed_op, concurrent_op
            )

        return transformed_op

    def transform_against_operation(
        self, op: Operation, against: Operation
    ) -> Operation:
        """Transform one operation against another"""
        if op.type == "insert" and against.type == "insert":
            if against.position <= op.position:
                op.position += len(against.content)
        elif op.type == "delete" and against.type == "insert":
            if against.position <= op.position:
                op.position += len(against.content)
        elif op.type == "insert" and against.type == "delete":
            if against.position < op.position:
                op.position -= len(against.content)
        elif op.type == "delete" and against.type == "delete":
            if against.position < op.position:
                op.position -= len(against.content)
            elif against.position == op.position:
                # Concurrent delete at same position - skip
                return None

        return op

    def apply_operation_to_content(self, content: str, operation: Operation) -> str:
        """Apply an operation to text content"""
        if operation.type == "insert":
            return (
                content[: operation.position]
                + operation.content
                + content[operation.position :]
            )
        elif operation.type == "delete":
            end_pos = operation.position + len(operation.content)
            return content[: operation.position] + content[end_pos:]
        elif operation.type == "replace":
            end_pos = operation.position + len(operation.content)
            return content[: operation.position] + operation.content + content[end_pos:]

        return content

    def update_cursor(self, session_id: str, user_id: int, cursor_data: Dict):
        """Update user cursor position"""
        if session_id not in self.cursors:
            self.cursors[session_id] = {}

        user = User.query.get(user_id)
        cursor = Cursor(
            user_id=user_id,
            username=user.username,
            position=cursor_data["position"],
            selection_start=cursor_data.get("selection_start", cursor_data["position"]),
            selection_end=cursor_data.get("selection_end", cursor_data["position"]),
            color=self.user_colors[user_id % len(self.user_colors)],
            last_seen=datetime.utcnow(),
        )

        self.cursors[session_id][user_id] = cursor

        # Broadcast cursor update
        emit(
            "cursor_update",
            {"session_id": session_id, "cursor": asdict(cursor)},
            room=session_id,
            include_self=False,
        )

    # ADD THESE 3 METHODS TO YOUR EXISTING CollaborationService CLASS (around line 400)

    def invite_member(
        self, team_id: str, inviter_id: int, email: str, role: str = "member"
    ) -> Dict:
        """Send team invitation to email address"""
        try:
            from app.models.user import User
            from app.models.team_member import MemberRole
            from sqlalchemy import text
            from datetime import datetime, timedelta
            import uuid

            print(f"🎯 INVITE: {email} to team {team_id} by user {inviter_id}")

            # Find team using raw SQL
            team_result = db.session.execute(
                text("SELECT * FROM teams WHERE id = :team_id"), {"team_id": team_id}
            ).first()

            if not team_result:
                raise ValueError("Team not found")

            print(f"✅ Found team: {team_result.name}")

            # Check inviter permissions
            inviter_result = db.session.execute(
                text(
                    """
                    SELECT tm.role FROM team_members tm 
                    WHERE tm.team_id = :team_id AND tm.user_id = :user_id AND tm.is_active = 1
                """
                ),
                {"team_id": team_id, "user_id": str(inviter_id)},
            ).first()

            if not inviter_result or inviter_result.role not in [
                "OWNER",
                "ADMIN",
                "MemberRole.OWNER",
                "MemberRole.ADMIN",
            ]:
                raise ValueError("Insufficient permissions to invite members")

            print(f"✅ Inviter permissions verified")

            # Check if user exists
            existing_user_result = db.session.execute(
                text("SELECT id, email FROM users WHERE email = :email"),
                {"email": email},
            ).first()

            if not existing_user_result:
                print(f"❌ User {email} does not exist")
                raise ValueError(
                    f"User {email} does not exist. Please ask them to register first."
                )

            user_id_to_use = existing_user_result.id
            print(f"✅ Using existing user ID: {user_id_to_use}")

            # Check if already a member
            existing_member_result = db.session.execute(
                text(
                    """
                    SELECT invitation_status FROM team_members 
                    WHERE team_id = :team_id AND user_id = :user_id
                """
                ),
                {"team_id": team_id, "user_id": str(user_id_to_use)},
            ).first()

            if existing_member_result:
                if existing_member_result.invitation_status == "PENDING":
                    raise ValueError("User already has a pending invitation")
                elif existing_member_result.invitation_status == "ACCEPTED":
                    raise ValueError("User is already a team member")

            # Convert role
            try:
                member_role = MemberRole(role.upper())
            except ValueError:
                member_role = MemberRole.MEMBER

            # Create invitation using raw SQL
            member_id = str(uuid.uuid4())
            invitation_token = str(uuid.uuid4())

            now = datetime.utcnow()
            expires_at = now + timedelta(days=7)

            print(f"🔧 Creating invitation for user_id: {user_id_to_use}")

            try:
                db.session.execute(
                    text(
                        """
                        INSERT INTO team_members (
                            id, team_id, user_id, role, is_active, invitation_status,
                            invited_at, invited_by_id, invitation_token, invitation_expires_at
                        ) VALUES (
                            :id, :team_id, :user_id, :role, :is_active, :invitation_status,
                            :invited_at, :invited_by_id, :invitation_token, :invitation_expires_at
                        )
                    """
                    ),
                    {
                        "id": member_id,
                        "team_id": team_id,
                        "user_id": user_id_to_use,
                        "role": member_role.value,
                        "is_active": False,
                        "invitation_status": "PENDING",
                        "invited_at": now,
                        "invited_by_id": str(inviter_id),
                        "invitation_token": invitation_token,
                        "invitation_expires_at": expires_at,
                    },
                )

                db.session.commit()
                print(f"✅ Invitation created successfully")

            except Exception as insert_error:
                db.session.rollback()
                print(f"❌ Failed to create invitation: {insert_error}")
                raise ValueError(f"Failed to create invitation: {insert_error}")

                # ADD ACTIVITY LOGGING
            Activity.log_activity(
                action_type="member_invited",
                user_id=inviter_id,
                description=f"Invited {email} to join team as {role}",
                team_id=team_id,
                target_type="user",
                target_name=email,
                metadata={"role": role, "invitation_token": invitation_token},
            )

            print(f"✅ INVITE: Invitation sent to {email}")

            return {
                "success": True,
                "invitation_id": member_id,
                "invitation_token": invitation_token,
                "message": f"Invitation sent to {email}",
                "user_existed": True,
            }

        except Exception as e:
            print(f"❌ INVITE ERROR: {str(e)}")
            raise

    def accept_invitation(self, token: str, user_id: int = None) -> Dict:
        """Accept team invitation using token"""
        try:
            from sqlalchemy import text
            from datetime import datetime

            print(f"🎯 ACCEPT: Token {token[:8]}... by user {user_id}")

            # Check invitation exists using raw SQL (avoids enum issue)
            invitation_check = db.session.execute(
                text(
                    """
                    SELECT tm.id, tm.team_id, tm.user_id, tm.role, tm.invitation_status,
                        tm.invitation_expires_at, t.name as team_name
                    FROM team_members tm
                    JOIN teams t ON tm.team_id = t.id
                    WHERE tm.invitation_token = :token
                """
                ),
                {"token": token},
            ).first()

            if not invitation_check:
                raise ValueError("Invalid invitation token")

                # ✅ ENHANCED STATUS CHECK WITH PROPER LOGIC
            status = str(invitation_check.invitation_status).upper()
            print(
                f"🔍 ACCEPT: Status check - Expected: PENDING, Got: {invitation_check.invitation_status} (normalized: {status})"
            )

            if status == "ACCEPTED":
                print(
                    f"✅ ACCEPT: Invitation already accepted - user is already a team member"
                )
                return {
                    "success": True,
                    "team_id": str(invitation_check.team_id),
                    "team_name": invitation_check.team_name,
                    "role": invitation_check.role.upper(),
                    "message": f"You are already a member of {invitation_check.team_name}",
                    "already_member": True,
                }
            elif status not in ["PENDING"]:
                print(f"❌ ACCEPT: Invalid status: {status} - cannot accept invitation")
                raise ValueError(
                    f"Invitation status is {status.lower()}, cannot accept"
                )

                # Check expiration
            if invitation_check.invitation_expires_at:
                from datetime import datetime

                try:
                    expires_at = datetime.fromisoformat(
                        str(invitation_check.invitation_expires_at).replace(" ", "T")
                    )
                except:
                    expires_at = datetime.strptime(
                        str(invitation_check.invitation_expires_at),
                        "%Y-%m-%d %H:%M:%S.%f",
                    )
                if datetime.utcnow() > expires_at:
                    # Mark as expired
                    db.session.execute(
                        text(
                            "UPDATE team_members SET invitation_status = 'EXPIRED' WHERE invitation_token = :token"
                        ),
                        {"token": token},
                    )
                    db.session.commit()
                    raise ValueError("Invitation has expired")

            print(
                f"✅ ACCEPT: Valid invitation found for team: {invitation_check.team_name}"
            )

            # Accept invitation using raw SQL
            db.session.execute(
                text(
                    """
                    UPDATE team_members 
                    SET invitation_status = 'ACCEPTED', 
                        joined_at = :joined_at,
                        is_active = 1
                    WHERE invitation_token = :token
                """
                ),
                {"token": token, "joined_at": datetime.utcnow()},
            )

            db.session.commit()
            print(f"✅ ACCEPT: Invitation accepted successfully")

            # ADD ACTIVITY LOGGING
            Activity.log_activity(
                action_type="member_joined",
                user_id=invitation_check.user_id,
                description=f"Joined team {invitation_check.team_name} as {invitation_check.role}",
                team_id=invitation_check.team_id,
                target_type="team",
                target_name=invitation_check.team_name,
                metadata={"role": invitation_check.role},
            )

            # ✅ VERIFY THE UPDATE WORKED
            verify_result = db.session.execute(
                text(
                    "SELECT invitation_status, is_active FROM team_members WHERE invitation_token = :token"
                ),
                {"token": token},
            ).first()
            print(
                f"✅ ACCEPT: Database verification - Status: {verify_result[0]}, Active: {verify_result[1]}"
            )

            # Get user info
            user_info = db.session.execute(
                text("SELECT username FROM users WHERE id = :user_id"),
                {"user_id": str(invitation_check.user_id)},
            ).first()

            return {
                "success": True,
                "team_id": str(invitation_check.team_id),
                "team_name": invitation_check.team_name,
                "role": invitation_check.role.upper(),
                "message": f"Successfully joined {invitation_check.team_name}",
            }

        except Exception as e:
            print(f"❌ ACCEPT ERROR: {str(e)}")
            raise

    def get_pending_invitations(self, team_id: str) -> List[Dict]:
        """Get all pending invitations for a team"""
        try:
            from app.models.team_member import TeamMember, InvitationStatus
            from app.models.user import User

            print(f"🎯 PENDING: Getting invitations for team {team_id}")

            pending_invitations = TeamMember.query.filter_by(
                team_id=team_id, invitation_status=InvitationStatus.PENDING
            ).all()

            invitations = []
            for invitation in pending_invitations:
                inviter = User.query.get(invitation.invited_by_id)

                invitation_data = {
                    "id": str(invitation.id),
                    "invitation_token": invitation.invitation_token,
                    "role": invitation.role.value,
                    "invited_at": invitation.invited_at.isoformat(),
                    "expires_at": (
                        invitation.invitation_expires_at.isoformat()
                        if invitation.invitation_expires_at
                        else None
                    ),
                    "is_expired": invitation.is_invitation_expired,
                    "invited_by": (
                        {"id": str(inviter.id), "username": inviter.username}
                        if inviter
                        else None
                    ),
                }

                # Add user info if invitation is for existing user
                if invitation.user_id:
                    user = User.query.get(invitation.user_id)
                    invitation_data["user"] = {
                        "id": str(user.id),
                        "username": user.username,
                        "email": user.email,
                    }

                invitations.append(invitation_data)

            print(f"✅ PENDING: Found {len(invitations)} pending invitations")
            return invitations

        except Exception as e:
            print(f"❌ PENDING ERROR: {str(e)}")
            return []

    def get_session_state(self, session_id: str) -> Dict:
        """Get current state of collaboration session"""
        if session_id not in self.active_sessions:
            return None

        session = self.active_sessions[session_id]

        return {
            "session_id": session_id,
            "snippet_id": session.snippet_id,
            "participants": session.participants,
            "version": session.version,
            "cursors": [
                asdict(cursor) for cursor in self.cursors.get(session_id, {}).values()
            ],
            "last_activity": session.last_activity.isoformat(),
        }

    def update_member_role(
        self, team_id: str, member_id: str, new_role: str, updated_by: int
    ) -> Dict:
        """Update team member role with validation and activity logging"""
        try:
            from app.models.team_member import MemberRole
            from sqlalchemy import text

            print(f"🔧 ROLE_UPDATE: Member {member_id} to {new_role} in team {team_id}")

            # Validate role
            try:
                role_enum = MemberRole(new_role.lower())
            except ValueError:
                raise ValueError(f"Invalid role: {new_role}")

            # Check if updater has permission
            updater_result = db.session.execute(
                text(
                    "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
                ),
                {"team_id": team_id, "user_id": str(updated_by)},
            ).first()

            if not updater_result or updater_result.role not in ["OWNER", "ADMIN"]:
                raise ValueError("Insufficient permissions to update roles")

            # Get target member info (including username for better logging)
            target_result = db.session.execute(
                text(
                    """
                    SELECT tm.role, tm.user_id, u.username 
                    FROM team_members tm 
                    JOIN users u ON tm.user_id = u.id 
                    WHERE tm.id = :member_id AND tm.team_id = :team_id
                """
                ),
                {"member_id": member_id, "team_id": team_id},
            ).first()

            if not target_result:
                raise ValueError("Member not found")

            if target_result.role == "OWNER":
                raise ValueError("Cannot change owner role")

            # Store old role for logging
            old_role = target_result.role
            target_username = target_result.username

            # Update role
            db.session.execute(
                text(
                    "UPDATE team_members SET role = :role WHERE id = :member_id AND team_id = :team_id"
                ),
                {"role": new_role.upper(), "member_id": member_id, "team_id": team_id},
            )

            # Commit the role change first
            db.session.commit()

            # Log activity with comprehensive error handling
            try:
                from app.models.activity import Activity

                # Ensure we have all required data
                if not all([updated_by, team_id, member_id]):
                    raise ValueError("Missing required data for activity logging")

                Activity.log_activity(
                    action_type="role_changed",
                    user_id=updated_by,
                    description=f"Changed {target_username}'s role from {old_role} to {new_role.upper()}",
                    team_id=team_id,
                    target_type="member",
                    target_id=member_id,
                    target_name=target_username,
                    metadata={
                        "old_role": old_role,
                        "new_role": new_role.upper(),
                        "target_user_id": str(target_result.user_id),
                        "target_username": target_username,
                    },
                )

                # Force commit the activity log
                db.session.commit()
                print(
                    f"✅ ROLE_CHANGE: Activity logged successfully for {target_username}"
                )

            except ImportError as import_error:
                print(f"❌ ROLE_CHANGE: Activity import failed: {str(import_error)}")
            except Exception as activity_error:
                print(f"❌ ROLE_CHANGE: Activity logging failed: {str(activity_error)}")
                # Don't fail the entire operation if activity logging fails
                db.session.rollback()  # Rollback only the activity, not the role change
                try:
                    # Try a simpler activity log as fallback
                    db.session.execute(
                        text(
                            """
                            INSERT INTO activities (action_type, user_id, description, team_id, target_type, target_id, created_at)
                            VALUES (:action_type, :user_id, :description, :team_id, :target_type, :target_id, NOW())
                        """
                        ),
                        {
                            "action_type": "role_changed",
                            "user_id": updated_by,
                            "description": f"Changed member role to {new_role.upper()}",
                            "team_id": team_id,
                            "target_type": "member",
                            "target_id": member_id,
                        },
                    )
                    db.session.commit()
                    print(f"✅ ROLE_CHANGE: Fallback activity logging succeeded")
                except Exception as fallback_error:
                    print(
                        f"❌ ROLE_CHANGE: Even fallback activity logging failed: {str(fallback_error)}"
                    )

            print(
                f"✅ ROLE_UPDATE: Successfully updated member {member_id} to {new_role}"
            )

            return {
                "success": True,
                "member_id": member_id,
                "new_role": new_role.upper(),
                "old_role": old_role,
                "target_username": target_username,
                "message": f"Role updated from {old_role} to {new_role.upper()}",
            }

        except Exception as e:
            db.session.rollback()
            print(f"❌ ROLE_UPDATE ERROR: {str(e)}")
            raise

    def remove_team_member(self, team_id: str, member_id: str, removed_by: int) -> Dict:
        """Remove team member with validation"""
        try:
            from sqlalchemy import text

            print(
                f"🗑️ REMOVE_MEMBER: Member {member_id} from team {team_id} by user {removed_by}"
            )

            # Check if remover has permission
            remover_result = db.session.execute(
                text(
                    "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
                ),
                {"team_id": team_id, "user_id": str(removed_by)},
            ).first()

            if not remover_result or remover_result.role not in ["OWNER", "ADMIN"]:
                print(
                    f"❌ REMOVE_MEMBER: Insufficient permissions for user {removed_by}"
                )
                raise ValueError("Insufficient permissions to remove members")

            # 🔥 FIX: Check if member_id is actually user_id (from frontend)
            print(f"🔍 REMOVE_MEMBER: Checking if {member_id} is user_id or member_id")

            # First try as user_id (most likely from frontend)
            target_result = db.session.execute(
                text(
                    "SELECT role, user_id, id FROM team_members WHERE user_id = :user_id AND team_id = :team_id AND is_active = 1"
                ),
                {"user_id": member_id, "team_id": team_id},
            ).first()

            # If not found, try as actual member_id
            if not target_result:
                print(f"🔍 REMOVE_MEMBER: Not found as user_id, trying as member_id")
                target_result = db.session.execute(
                    text(
                        "SELECT role, user_id, id FROM team_members WHERE id = :member_id AND team_id = :team_id AND is_active = 1"
                    ),
                    {"member_id": member_id, "team_id": team_id},
                ).first()

            if not target_result:
                print(
                    f"❌ REMOVE_MEMBER: Member {member_id} not found in team {team_id}"
                )
                print(f"🔍 REMOVE_MEMBER: Available members in team:")
                all_members = db.session.execute(
                    text(
                        "SELECT id, user_id, role FROM team_members WHERE team_id = :team_id AND is_active = 1"
                    ),
                    {"team_id": team_id},
                ).fetchall()
                for m in all_members:
                    print(
                        f"  - Member ID: {m.id}, User ID: {m.user_id}, Role: {m.role}"
                    )
                raise ValueError("Member not found")

            actual_member_id = target_result.id
            print(
                f"✅ REMOVE_MEMBER: Found member - ID: {actual_member_id}, User: {target_result.user_id}, Role: {target_result.role}"
            )

            if target_result.role == "OWNER":
                print(f"❌ REMOVE_MEMBER: Cannot remove team owner")
                raise ValueError("Cannot remove team owner")

            # Check if removing last admin
            admin_count = db.session.execute(
                text(
                    "SELECT COUNT(*) FROM team_members WHERE team_id = :team_id AND role IN ('OWNER', 'ADMIN') AND is_active = 1"
                ),
                {"team_id": team_id},
            ).scalar()

            if target_result.role in ["ADMIN", "OWNER"] and admin_count <= 1:
                print(f"❌ REMOVE_MEMBER: Cannot remove last admin from team")
                raise ValueError("Cannot remove the last admin from team")

            # Remove member using actual member_id
            result = db.session.execute(
                text(
                    "UPDATE team_members SET is_active = 0, left_at = :left_at WHERE id = :member_id AND team_id = :team_id"
                ),
                {
                    "member_id": actual_member_id,  # Use actual member ID
                    "team_id": team_id,
                    "left_at": datetime.utcnow(),
                },
            )

            if result.rowcount == 0:
                print(
                    f"❌ REMOVE_MEMBER: No rows updated - member may already be inactive"
                )
                raise ValueError("Failed to remove member - no rows updated")

            # Update team member count
            db.session.execute(
                text(
                    "UPDATE teams SET member_count = member_count - 1 WHERE id = :team_id"
                ),
                {"team_id": team_id},
            )

            db.session.commit()
            # ADD ACTIVITY LOGGING
            Activity.log_activity(
                action_type="member_removed",
                user_id=removed_by,
                description=f"Removed team member",
                team_id=team_id,
                target_type="member",
                target_id=member_id,
                metadata={"removed_role": target_result.role},
            )
            print(f"✅ REMOVE_MEMBER: Successfully removed member {member_id}")

            return {
                "success": True,
                "member_id": member_id,
                "message": "Member removed successfully",
            }

        except Exception as e:
            db.session.rollback()
            print(f"❌ REMOVE_MEMBER ERROR: {str(e)}")
            import traceback

            print(f"❌ REMOVE_MEMBER TRACEBACK: {traceback.format_exc()}")

            raise

    def get_user_teams_for_sharing(self, user_id: int) -> Dict:
        """Get user's teams for collection sharing - COMPLETELY FIXED"""
        try:
            from sqlalchemy import text
            from flask_login import current_user

            print(f"🎯 GET_USER_TEAMS_SHARING: Getting teams for user {user_id}")

            # 🔥 FIX: Ensure user is properly authenticated
            if not current_user or not current_user.is_authenticated:
                print(f"❌ GET_USER_TEAMS_SHARING: User not authenticated")
                return {
                    "success": False,
                    "teams": [],
                    "error": "Authentication required",
                }

            # 🔥 FIX: Use current_user.id instead of passed user_id for security
            actual_user_id = current_user.id
            print(
                f"🔍 GET_USER_TEAMS_SHARING: Using authenticated user ID: {actual_user_id}"
            )

            # 🔥 FIX: Add session refresh to ensure latest data
            db.session.commit()  # Commit any pending transactions
            db.session.expire_all()  # Refresh all objects from database

            # 🔥 FIXED QUERY: Include owner_id and created_by fields
            # 🔥 FIXED QUERY - More inclusive member counting
            teams_query = text(
                """
                SELECT DISTINCT t.id, t.name, t.description, tm.role, 
                    t.created_at, tm.joined_at, t.owner_id, t.created_by,
                    (SELECT COUNT(*) FROM team_members tm2 
                        WHERE tm2.team_id = t.id 
                        AND tm2.is_active = 1 
                        AND (tm2.invitation_status IN ('ACCEPTED', 'accepted', 'Accepted') 
                            OR tm2.invitation_status IS NULL
                            OR tm2.role IN ('owner', 'OWNER', 'admin', 'ADMIN'))
                    ) as real_member_count
                FROM teams t
                JOIN team_members tm ON t.id = tm.team_id
                WHERE tm.user_id = :user_id 
                AND tm.is_active = 1
                AND (tm.invitation_status IN ('ACCEPTED', 'accepted', 'Accepted') 
                    OR tm.invitation_status IS NULL
                    OR tm.role IN ('owner', 'OWNER', 'admin', 'ADMIN'))
                ORDER BY t.name ASC
            """
            )

            result = db.session.execute(teams_query, {"user_id": str(actual_user_id)})
            teams_data = result.fetchall()

            print(
                f"✅ GET_USER_TEAMS_SHARING: Found {len(teams_data)} teams for user {actual_user_id}"
            )

            teams = []
            for team in teams_data:
                # Safe date formatting
                try:
                    created_at = self.safe_date_format(team.created_at)
                    joined_at = self.safe_date_format(team.joined_at)
                except Exception as date_error:
                    print(f"⚠️ Date formatting error: {date_error}")
                    created_at = str(team.created_at) if team.created_at else None
                    joined_at = str(team.joined_at) if team.joined_at else None

                # 🔥 FIXED: Proper ownership detection
                owner_id = str(team.owner_id) if team.owner_id else None
                created_by = str(team.created_by) if team.created_by else None
                user_id_str = str(actual_user_id)

                # 🔥 BULLETPROOF OWNERSHIP CHECK
                is_owner = owner_id == user_id_str if owner_id else False
                is_creator = created_by == user_id_str if created_by else False
                is_admin_or_owner = str(team.role).upper().strip() in ["OWNER", "ADMIN"]

                # Final ownership determination
                is_team_creator = is_owner or is_creator or is_admin_or_owner

                team_data = {
                    "id": str(team.id),
                    "name": team.name,
                    "description": team.description or "",
                    "role": team.role,
                    "member_count": team.real_member_count or 1,
                    "created_at": created_at,
                    "joined_at": joined_at,
                    "can_share": str(team.role).upper().strip()
                    in ["OWNER", "ADMIN", "EDITOR", "MEMBER"],
                    # 🔥 FIXED: Proper ownership fields
                    "owner_id": owner_id,
                    "created_by": created_by,
                    "is_owner": is_owner,
                    "is_creator": is_creator,
                    "is_team_creator": is_team_creator,
                    "team_type": "created" if is_team_creator else "joined",
                }

                teams.append(team_data)

                print(f"  ✅ Team: {team.name}")
                print(f"    - Role: {team.role}")
                print(f"    - Owner ID: {owner_id}")
                print(f"    - Created By: {created_by}")
                print(f"    - User ID: {user_id_str}")
                print(f"    - Is Creator: {is_team_creator}")
                print(f"    - Team Type: {'CREATED' if is_team_creator else 'JOINED'}")

            return {"success": True, "teams": teams, "total_count": len(teams)}

        except Exception as e:
            print(f"❌ GET_USER_TEAMS_SHARING ERROR: {str(e)}")
            import traceback

            print(f"❌ TRACEBACK: {traceback.format_exc()}")
            return {"success": False, "teams": [], "error": str(e)}

   
    def resolve_conflicts(self, session_id: str) -> Dict:
        """Resolve conflicts in collaborative editing"""
        if session_id not in self.operations_queue:
            return {"conflicts_resolved": 0}

        operations = self.operations_queue[session_id]
        conflicts_resolved = 0

        # Group operations by position and timestamp
        position_groups = {}
        for op in operations:
            key = f"{op.position}_{op.timestamp.timestamp():.3f}"
            if key not in position_groups:
                position_groups[key] = []
            position_groups[key].append(op)

        # Resolve conflicts in each group
        for group in position_groups.values():
            if len(group) > 1:
                # Sort by timestamp and user_id for deterministic resolution
                group.sort(key=lambda x: (x.timestamp, x.user_id))
                # Keep first operation, mark others as resolved
                for op in group[1:]:
                    op.applied = False
                    conflicts_resolved += 1

        return {"conflicts_resolved": conflicts_resolved}

    def get_collection_shared_teams(self, collection_id: str, user_id: int) -> Dict:
        """Get teams that collection is shared with and user's available teams"""
        try:
            from sqlalchemy import text

            print(
                f"🔍 GET_COLLECTION_SHARED_TEAMS: Collection {collection_id} for user {user_id}"
            )

            # Get user's teams (created + joined)
            user_teams_result = self.get_user_teams_for_sharing(user_id)
            if not user_teams_result.get("success"):
                return {"success": False, "error": "Failed to get user teams"}

            user_teams = user_teams_result["teams"]

            # Get teams collection is already shared with
            shared_teams = db.session.execute(
                text(
                    """
                    SELECT team_id FROM collection_team_shares 
                    WHERE collection_id = :collection_id
                """
                ),
                {"collection_id": collection_id},
            ).fetchall()

            shared_team_ids = {str(team.team_id) for team in shared_teams}

            # Separate created vs joined teams
            created_teams = []
            joined_teams = []

            for team in user_teams:
                # 🔥 BULLETPROOF ROLE NORMALIZATION (same as snippet method)
                raw_role = str(team.get("role", "")).strip()
                normalized_role = raw_role.upper()

                # Handle enum format like "MemberRole.OWNER"
                if "." in normalized_role:
                    normalized_role = normalized_role.split(".")[-1]

                # 🔥 BULLETPROOF OWNERSHIP CHECK
                is_team_creator = (
                    normalized_role in ["OWNER", "ADMIN"]
                    or str(team.get("created_by", "")) == str(user_id)
                    or str(team.get("owner_id", "")) == str(user_id)
                    or team.get("team_type") == "created"
                )

                team_data = {
                    **team,
                    "role": normalized_role,
                    "is_shared": team["id"] in shared_team_ids,
                    "is_creator": is_team_creator,
                }

                if is_team_creator:
                    created_teams.append(team_data)
                else:
                    joined_teams.append(team_data)

            print(
                f"✅ GET_COLLECTION_SHARED_TEAMS: Created: {len(created_teams)}, Joined: {len(joined_teams)}"
            )

            return {
                "success": True,
                "created_teams": created_teams,
                "joined_teams": joined_teams,
                "shared_team_ids": list(shared_team_ids),
            }

        except Exception as e:
            print(f"❌ GET_COLLECTION_SHARED_TEAMS ERROR: {str(e)}")
            return {"success": False, "error": str(e)}

    def share_snippet_with_teams(
        self, snippet_id: str, team_ids: list, user_id: int, permissions: dict = None
    ) -> Dict:
        """Share snippet with multiple teams - ENHANCED LOGGING"""
        try:
            from sqlalchemy import text

            print(
                f"🔗 SHARE_SNIPPET_TEAMS: Snippet {snippet_id} with teams {team_ids} by user {user_id}"
            )

            # Verify snippet ownership
            snippet_check = db.session.execute(
                text(
                    "SELECT user_id FROM snippets WHERE id = :snippet_id AND is_deleted = 0"
                ),
                {"snippet_id": snippet_id},
            ).first()

            if not snippet_check:
                return {"success": False, "message": "Snippet not found"}

            if str(snippet_check.user_id) != str(user_id):
                return {
                    "success": False,
                    "message": "Not authorized to share this snippet",
                }

            # Verify user has permission to share with these teams
            user_teams_result = self.get_user_teams_for_sharing(user_id)
            if not user_teams_result.get("success"):
                return {"success": False, "message": "Failed to get user teams"}

            user_teams = user_teams_result["teams"]
            # 🔥 FIX: Updated permission check for MEMBER role
            user_team_ids = [
                t["id"]
                for t in user_teams
                if str(t.get("role", "")).upper().strip()
                in ["OWNER", "ADMIN", "EDITOR", "MEMBER"]
            ]

            # Check permissions for each team
            for team_id in team_ids:
                if str(team_id) not in user_team_ids:
                    return {
                        "success": False,
                        "message": f"No permission to share with team {team_id}",
                    }

            # Update snippet with team sharing info
            team_ids_json = json.dumps(team_ids) if team_ids else None
            permissions_json = json.dumps(permissions) if permissions else None

            db.session.execute(
                text(
                    """
                    UPDATE snippets 
                    SET shared_team_ids = :team_ids, team_permissions = :permissions
                    WHERE id = :snippet_id
                """
                ),
                {
                    "snippet_id": snippet_id,
                    "team_ids": team_ids_json,
                    "permissions": permissions_json,
                },
            )

            db.session.commit()
            for team_id_item in team_ids:
                Activity.log_activity(
                    action_type="snippet_shared",
                    user_id=user_id,
                    description=f"Shared snippet with team",
                    team_id=team_id_item,
                    target_type="snippet",
                    target_id=snippet_id,
                    metadata={
                        "permissions": permissions,
                        "total_teams_shared": len(team_ids),
                    },
                )

            print(
                f"✅ SHARE_SNIPPET_TEAMS: Successfully shared snippet {snippet_id} with {len(team_ids)} teams"
            )

            return {
                "success": True,
                "message": f"Snippet shared with {len(team_ids)} teams",
                "shared_teams": team_ids,
            }

        except Exception as e:
            db.session.rollback()
            print(f"❌ SHARE_SNIPPET_TEAMS ERROR: {str(e)}")
            import traceback

            print(f"❌ TRACEBACK: {traceback.format_exc()}")
            return {"success": False, "message": str(e)}

    def get_snippet_shared_teams(self, snippet_id: str, user_id: int) -> Dict:
        """Get teams that snippet is shared with and user's available teams"""
        try:
            from sqlalchemy import text

            print(
                f"🔍 GET_SNIPPET_SHARED_TEAMS: Snippet {snippet_id} for user {user_id}"
            )

            # Verify snippet ownership
            snippet_check = db.session.execute(
                text(
                    """
                    SELECT user_id, shared_team_ids, team_permissions 
                    FROM snippets 
                    WHERE id = :snippet_id AND is_deleted = 0
                """
                ),
                {"snippet_id": snippet_id},
            ).first()

            if not snippet_check:
                return {"success": False, "message": "Snippet not found"}

            if str(snippet_check.user_id) != str(user_id):
                return {
                    "success": False,
                    "message": "Not authorized to view this snippet",
                }

            # Get user's teams (created + joined)
            user_teams_result = self.get_user_teams_for_sharing(user_id)
            if not user_teams_result.get("success"):
                return {"success": False, "error": "Failed to get user teams"}

            user_teams = user_teams_result["teams"]

            # Get teams snippet is already shared with
            shared_team_ids = []
            if snippet_check.shared_team_ids:
                try:
                    shared_team_ids = json.loads(snippet_check.shared_team_ids)
                except (json.JSONDecodeError, TypeError):
                    shared_team_ids = []

            shared_team_ids_set = {str(tid) for tid in shared_team_ids}

            # Get permissions
            permissions = {}
            if snippet_check.team_permissions:
                try:
                    permissions = json.loads(snippet_check.team_permissions)
                except (json.JSONDecodeError, TypeError):
                    permissions = {}

            # Separate created vs joined teams
            # Separate created vs joined teams
            created_teams = []
            joined_teams = []

            for team in user_teams:
                # 🔥 BULLETPROOF ROLE NORMALIZATION
                raw_role = str(team.get("role", "")).strip()
                normalized_role = raw_role.upper()

                # Handle enum format like "MemberRole.OWNER"
                if "." in normalized_role:
                    normalized_role = normalized_role.split(".")[-1]

                # 🔥 BULLETPROOF OWNERSHIP CHECK - Use user_id directly
                is_team_creator = (
                    normalized_role in ["OWNER", "ADMIN"]
                    or str(team.get("created_by", "")) == str(user_id)
                    or str(team.get("owner_id", "")) == str(user_id)
                    or team.get("team_type") == "created"
                )

                team_data = {
                    **team,
                    "role": normalized_role,
                    "is_creator": is_team_creator,
                }

                if is_team_creator:
                    created_teams.append(team_data)
                else:
                    joined_teams.append(team_data)

            print(
                f"✅ GET_SNIPPET_SHARED_TEAMS: Created: {len(created_teams)}, Joined: {len(joined_teams)}"
            )

            return {
                "success": True,
                "created_teams": created_teams,
                "joined_teams": joined_teams,
                "shared_team_ids": list(shared_team_ids_set),
                "permissions": permissions,
            }

        except Exception as e:
            print(f"❌ GET_SNIPPET_SHARED_TEAMS ERROR: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_team_snippets(self, team_id: str, user_id: int) -> Dict:
        """Get all snippets shared with a specific team"""
        try:
            from sqlalchemy import text

            print(f"🔍 GET_TEAM_SNIPPETS: Team {team_id} for user {user_id}")

            # 🔥 FIX: Flexible role checking for team membership
            member_check = db.session.execute(
                text(
                    """
                    SELECT UPPER(TRIM(role)) as role FROM team_members 
                    WHERE team_id = :team_id AND user_id = :user_id 
                    AND is_active = 1 
                    AND (UPPER(TRIM(invitation_status)) = 'ACCEPTED' OR invitation_status IS NULL)
                """
                ),
                {"team_id": team_id, "user_id": str(user_id)},
            ).first()

            if not member_check:
                return {"success": False, "message": "Not a member of this team"}

            # Get snippets shared with this team
            snippets_query = text(
                """
                SELECT s.id, s.title, s.code, s.language, s.tags, s.created_at, s.updated_at,
                       s.user_id, s.shared_team_ids, s.team_permissions,
                       u.username as owner_username
                FROM snippets s
                JOIN users u ON s.user_id = u.id
                WHERE s.is_deleted = 0 
                AND s.shared_team_ids IS NOT NULL
                AND s.shared_team_ids LIKE '%' || :team_id || '%'
                ORDER BY s.updated_at DESC
            """
            )

            result = db.session.execute(snippets_query, {"team_id": team_id})
            snippets_data = result.fetchall()

            snippets = []
            for row in snippets_data:
                # Verify team is actually in shared_team_ids (JSON check)
                try:
                    shared_teams = (
                        json.loads(row.shared_team_ids) if row.shared_team_ids else []
                    )
                    if str(team_id) not in [str(t) for t in shared_teams]:
                        continue
                except (json.JSONDecodeError, TypeError):
                    continue

                # Get permissions for this team
                permissions = {}
                if row.team_permissions:
                    try:
                        all_permissions = json.loads(row.team_permissions)
                        permissions = all_permissions.get(str(team_id), {})
                    except (json.JSONDecodeError, TypeError):
                        permissions = {}

                snippet_data = {
                    "id": row.id,
                    "title": row.title,
                    "code": row.code,
                    "language": row.language,
                    "tags": row.tags.split(",") if row.tags else [],
                    "created_at": self.safe_date_format(row.created_at),
                    "updated_at": self.safe_date_format(row.updated_at),
                    "owner_id": row.user_id,
                    "owner_username": row.owner_username,
                    "team_permissions": permissions,
                    "can_edit": permissions.get("allow_editing", False),
                    "can_comment": permissions.get("allow_comments", True),
                }
                snippets.append(snippet_data)

            print(
                f"✅ GET_TEAM_SNIPPETS: Found {len(snippets)} snippets for team {team_id}"
            )

            return {
                "success": True,
                "snippets": snippets,
                "team_id": team_id,
                "user_role": member_check.role,
                "count": len(snippets),
            }

        except Exception as e:
            print(f"❌ GET_TEAM_SNIPPETS ERROR: {str(e)}")
            import traceback

            print(f"❌ TRACEBACK: {traceback.format_exc()}")
            return {"success": False, "message": str(e)}

    def cleanup_session(self, session_id: str):
        """Clean up inactive collaboration session"""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]

        if session_id in self.operations_queue:
            del self.operations_queue[session_id]

        if session_id in self.cursors:
            del self.cursors[session_id]

        # Remove from Redis
        self.redis_client.delete(f"collab_session:{session_id}")



        # 🆕 COPY-BASED SHARING METHODS - ADD TO YOUR EXISTING CLASS

    def share_snippet_with_team_copy(self, snippet_id: str, team_id: str, user_id: int) -> Dict:
        """Share personal snippet with team by creating INDEPENDENT COPY - DEBUG VERSION"""
        try:
            from sqlalchemy import text
            
            print(f"🔗 SHARE_SNIPPET_COPY: {snippet_id} to team {team_id} by user {user_id}")
            
            # 1. Verify snippet ownership
            print("🔍 Step 1: Checking snippet ownership...")
            snippet_check = db.session.execute(
                text("SELECT id, title, code, language, description, tags, user_id FROM snippets WHERE id = :snippet_id AND user_id = :user_id AND (is_deleted = 0 OR is_deleted IS NULL)"),
                {"snippet_id": snippet_id, "user_id": str(user_id)}
            ).first()
            
            if not snippet_check:
                print("❌ Step 1 FAILED: Snippet not found")
                return {"success": False, "message": "Snippet not found or access denied"}
            
            print(f"✅ Step 1 SUCCESS: Found snippet '{snippet_check.title}'")
            
            # 2. Enhanced team membership check
            print("🔍 Step 2: Checking team membership...")
            member_check = db.session.execute(
                text("""
                    SELECT role FROM team_members 
                    WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1 
                    AND (
                        invitation_status = 'ACCEPTED' 
                        OR invitation_status IS NULL 
                        OR role LIKE '%OWNER%' 
                        OR role LIKE '%ADMIN%'
                        OR role = 'OWNER'
                        OR role = 'ADMIN'
                    )
                """),
                {"team_id": team_id, "user_id": str(user_id)}
            ).first()
            
            if not member_check:
                print("❌ Step 2 FAILED: Not a team member")
                return {"success": False, "message": "Not a member of this team"}
            
            print(f"✅ Step 2 SUCCESS: User has role {member_check.role}")
            
            # 3. Check if already shared
            print("🔍 Step 3: Checking for existing share...")
            existing_check = db.session.execute(
                text("SELECT id, is_active FROM team_snippets WHERE original_snippet_id = :snippet_id AND team_id = :team_id"),
                {"snippet_id": snippet_id, "team_id": team_id}
            ).first()

            if existing_check:
                if existing_check.is_active:
                    print(f"❌ Step 3 FAILED: Already shared (active record)")
                    return {"success": False, "message": "Snippet already shared with this team"}
                else:
                    print(f"🔄 Step 3: Found inactive record, will reactivate")
                    # Reactivate existing record instead of creating new one
                    db.session.execute(
                        text("UPDATE team_snippets SET is_active = 1, shared_at = :shared_at WHERE id = :id"),
                        {"shared_at": datetime.utcnow(), "id": existing_check.id}
                    )
                    db.session.commit()
                    return {
                        "success": True,
                        "message": f"Snippet '{snippet_check.title}' shared with team (reactivated)",
                        "team_snippet_id": existing_check.id,
                        "original_snippet_id": snippet_id,
                        "sharing_type": "copy_based"
                    }
            
            
            
            print("✅ Step 3 SUCCESS: Not already shared")
            
            # 4. Create INDEPENDENT team snippet copy
            print("🔍 Step 4: Creating team snippet copy...")
            import uuid
            team_snippet_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            print(f"🔍 Generated team_snippet_id: {team_snippet_id}")
            print(f"🔍 Current timestamp: {now}")
            
            # Prepare data
            insert_data = {
                "id": team_snippet_id,
                "team_id": team_id,
                "original_snippet_id": snippet_id,
                "shared_by_id": str(user_id),
                "title": snippet_check.title,
                "code": snippet_check.code,
                "language": snippet_check.language,
                "description": snippet_check.description or "",
                "tags": snippet_check.tags or "",
                "created_at": now,
                "updated_at": now,
                "shared_at": now,
                "is_active": True,
                "version": 1,
                "view_count": 0,
                "edit_count": 0,
                "team_permissions": '{"can_edit": true, "can_delete": false, "can_comment": true, "visibility": "team_only"}',
                "last_accessed": now
            }
            
            print(f"🔍 Insert data prepared: {list(insert_data.keys())}")
            
            team_snippet_sql = text("""
                INSERT INTO team_snippets (
                    id, team_id, original_snippet_id, shared_by_id, title, code, language, 
                    description, tags, created_at, updated_at, shared_at, is_active, version,
                    view_count, edit_count, team_permissions, last_accessed
                ) VALUES (
                    :id, :team_id, :original_snippet_id, :shared_by_id, :title, :code, :language,
                    :description, :tags, :created_at, :updated_at, :shared_at, :is_active, :version,
                    :view_count, :edit_count, :team_permissions, :last_accessed
                )
            """)
            
            print("🔍 About to execute INSERT...")
            db.session.execute(team_snippet_sql, insert_data)
            print("✅ INSERT executed successfully")
            
            print("🔍 About to commit transaction...")
            db.session.commit()
            print("✅ Transaction committed successfully")
            
            print(f"✅ SHARE_SNIPPET_COPY: Created independent copy {team_snippet_id}")
            
            return {
                "success": True,
                "message": f"Snippet '{snippet_check.title}' shared with team (independent copy)",
                "team_snippet_id": team_snippet_id,
                "original_snippet_id": snippet_id,
                "sharing_type": "copy_based"
            }
            
        except Exception as e:
            print(f"❌ SHARE_SNIPPET_COPY ERROR at step: {str(e)}")
            import traceback
            print(f"❌ FULL TRACEBACK: {traceback.format_exc()}")
            db.session.rollback()
            return {"success": False, "message": str(e)}


    def share_collection_with_team_copy(self, collection_id: str, team_id: str, user_id: int) -> Dict:
        """Share personal collection with team by creating INDEPENDENT COPY - FIXED VERSION"""
        try:
            from sqlalchemy import text
            
            print(f"🔗 SHARE_COLLECTION_COPY: {collection_id} to team {team_id} by user {user_id}")
            
            # 1. Verify collection ownership
            collection_check = db.session.execute(
                text("SELECT id, name, description, color, icon, user_id FROM collections WHERE id = :collection_id AND user_id = :user_id AND (is_deleted = 0 OR is_deleted IS NULL)"),
                {"collection_id": collection_id, "user_id": str(user_id)}
            ).first()
            
            if not collection_check:
                return {"success": False, "message": "Collection not found or access denied"}
            
            # 2. 🔥 FIXED: Same enhanced membership check as snippets
            member_check = db.session.execute(
                text("""
                    SELECT role FROM team_members 
                    WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1 
                    AND (
                        invitation_status = 'ACCEPTED' 
                        OR invitation_status IS NULL 
                        OR role LIKE '%OWNER%' 
                        OR role LIKE '%ADMIN%'
                        OR role = 'OWNER'
                        OR role = 'ADMIN'
                    )
                """),
                {"team_id": team_id, "user_id": str(user_id)}
            ).first()
            
            if not member_check:
                # 🔥 DEBUG: Show what we found
                debug_check = db.session.execute(
                    text("SELECT role, invitation_status, is_active FROM team_members WHERE team_id = :team_id AND user_id = :user_id"),
                    {"team_id": team_id, "user_id": str(user_id)}
                ).first()
                
                if debug_check:
                    print(f"🔍 DEBUG COLLECTION: Found member but failed check - Role: {debug_check.role}, Status: {debug_check.invitation_status}, Active: {debug_check.is_active}")
                else:
                    print(f"🔍 DEBUG COLLECTION: No membership record found for user {user_id} in team {team_id}")
                    
                return {"success": False, "message": "Not a member of this team"}
            
            print(f"✅ COLLECTION MEMBERSHIP: User {user_id} has role {member_check.role} in team {team_id}")
            
            # 3. Check if already shared
            existing_check = db.session.execute(
                text("SELECT id FROM team_collections WHERE original_collection_id = :collection_id AND team_id = :team_id AND is_active = 1"),
                {"collection_id": collection_id, "team_id": team_id}
            ).first()
            
            if existing_check:
                return {"success": False, "message": "Collection already shared with this team"}
            
            # 4. Create INDEPENDENT team collection copy
            import uuid
            team_collection_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            team_collection_sql = text("""
                INSERT INTO team_collections (
                    id, team_id, original_collection_id, shared_by_id, name, description, 
                    color, icon, created_at, updated_at, shared_at, is_active,
                    view_count, access_count, team_permissions, sort_order
                ) VALUES (
                    :id, :team_id, :original_collection_id, :shared_by_id, :name, :description,
                    :color, :icon, :created_at, :updated_at, :shared_at, :is_active,
                    :view_count, :access_count, :team_permissions, :sort_order
                )
            """)
            
            db.session.execute(team_collection_sql, {
                "id": team_collection_id,
                "team_id": team_id,
                "original_collection_id": collection_id,
                "shared_by_id": str(user_id),
                "name": collection_check.name,
                "description": collection_check.description or "",
                "color": collection_check.color or "#3B82F6",
                "icon": collection_check.icon or "📁",
                "created_at": now,
                "updated_at": now,
                "shared_at": now,
                "is_active": True,
                "view_count": 0,
                "access_count": 0,
                "team_permissions": '{"can_edit": true, "can_delete": false, "can_add_snippets": true, "visibility": "team_only"}',
                "sort_order": 0
            })
            
            # 5. Copy snippets from original collection to team collection
            snippets_in_collection = db.session.execute(
                text("""
                    SELECT s.id, s.title, s.code, s.language, s.description, s.tags
                    FROM snippets s
                    JOIN snippet_collections sc ON s.id = sc.snippet_id
                    WHERE sc.collection_id = :collection_id AND (s.is_deleted = 0 OR s.is_deleted IS NULL)
                """),
                {"collection_id": collection_id}
            ).fetchall()
            
            copied_snippets = 0
            for snippet in snippets_in_collection:
                try:
                    # Create team snippet copy
                    team_snippet_id = str(uuid.uuid4())
                    
                    team_snippet_sql = text("""
                        INSERT INTO team_snippets (
                            id, team_id, original_snippet_id, shared_by_id, title, code, language, 
                            description, tags, created_at, updated_at, shared_at, is_active, version,
                            view_count, edit_count, team_permissions
                        ) VALUES (
                            :id, :team_id, :original_snippet_id, :shared_by_id, :title, :code, :language,
                            :description, :tags, :created_at, :updated_at, :shared_at, :is_active, :version,
                            :view_count, :edit_count, :team_permissions
                        )
                    """)
                    
                    db.session.execute(team_snippet_sql, {
                        "id": team_snippet_id,
                        "team_id": team_id,
                        "original_snippet_id": str(snippet.id),
                        "shared_by_id": str(user_id),
                        "title": snippet.title,
                        "code": snippet.code,
                        "language": snippet.language,
                        "description": snippet.description or "",
                        "tags": snippet.tags or "",
                        "created_at": now,
                        "updated_at": now,
                        "shared_at": now,
                        "is_active": True,
                        "version": 1,
                        "view_count": 0,
                        "edit_count": 0,
                        "team_permissions": '{"can_edit": true, "can_delete": false, "can_comment": true, "visibility": "team_only"}'
                    })
                    
                    # Add to team collection
                    db.session.execute(
                        text("INSERT INTO team_snippet_collections (team_snippet_id, team_collection_id) VALUES (:snippet_id, :collection_id)"),
                        {"snippet_id": team_snippet_id, "collection_id": team_collection_id}
                    )
                    
                    copied_snippets += 1
                    
                except Exception as snippet_error:
                    print(f"⚠️ Failed to copy snippet {snippet.id}: {snippet_error}")
                    continue
            
            db.session.commit()
            
            print(f"✅ SHARE_COLLECTION_COPY: Created independent copy {team_collection_id} with {copied_snippets} snippets")
            
            return {
                "success": True,
                "message": f"Collection '{collection_check.name}' shared with team (independent copy)",
                "team_collection_id": team_collection_id,
                "original_collection_id": collection_id,
                "snippets_copied": copied_snippets,
                "sharing_type": "copy_based"
            }
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ SHARE_COLLECTION_COPY ERROR: {str(e)}")
            import traceback
            print(f"❌ TRACEBACK: {traceback.format_exc()}")
            return {"success": False, "message": str(e)}


    def get_team_content_snippets(self, team_id: str, user_id: int) -> Dict:
        """Get all team snippets (independent copies) - FIXED VERSION"""
        try:
            from sqlalchemy import text
            
            # 🔥 FIXED: Enhanced team membership check (same as sharing methods)
            member_check = db.session.execute(
                text("""
                    SELECT role FROM team_members 
                    WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1 
                    AND (
                        invitation_status = 'ACCEPTED' 
                        OR invitation_status IS NULL 
                        OR role LIKE '%OWNER%' 
                        OR role LIKE '%ADMIN%'
                        OR role = 'OWNER'
                        OR role = 'ADMIN'
                    )
                """),
                {"team_id": team_id, "user_id": str(user_id)}
            ).first()
            
            if not member_check:
                return {"success": False, "message": "Not a member of this team"}
            
            # Get team snippets
            team_snippets = db.session.execute(
                text("""
                    SELECT ts.id, ts.title, ts.code, ts.language, ts.description, ts.tags,
                        ts.shared_by_id, ts.shared_at, ts.view_count, ts.edit_count,
                        ts.team_permissions, u.username as shared_by_name
                    FROM team_snippets ts
                    LEFT JOIN users u ON ts.shared_by_id = u.id
                    WHERE ts.team_id = :team_id AND ts.is_active = 1
                    ORDER BY ts.updated_at DESC
                """),
                {"team_id": team_id}
            ).fetchall()
            
            snippets_data = []
            for ts in team_snippets:
                # Check if user can edit this snippet
                can_edit = (
                    str(ts.shared_by_id) == str(user_id) or  # Shared by user
                    member_check.role.upper() in ['OWNER', 'ADMIN', 'EDITOR', 'MEMBER']  # Role-based
                )
                
                snippet_data = {
                    "id": str(ts.id),
                    "title": ts.title,
                    "code": ts.code,
                    "language": ts.language,
                    "description": ts.description or "",
                    "tags": ts.tags.split(",") if ts.tags else [],
                    "shared_by_id": str(ts.shared_by_id),
                    "shared_by_name": ts.shared_by_name or "Unknown",
                    "shared_at": str(ts.shared_at),
                    "view_count": ts.view_count,
                    "edit_count": ts.edit_count,
                    "can_edit": can_edit,
                    "team_permissions": json.loads(ts.team_permissions) if ts.team_permissions else {},
                    "content_type": "team_snippet"
                }
                snippets_data.append(snippet_data)
            
            return {
                "success": True,
                "snippets": snippets_data,
                "count": len(snippets_data),
                "team_id": team_id
            }
            
        except Exception as e:
            print(f"❌ GET_TEAM_CONTENT_SNIPPETS ERROR: {str(e)}")
            return {"success": False, "message": str(e)}

    def get_team_content_collections(self, team_id: str, user_id: int) -> Dict:
        """Get all team collections (independent copies) - FIXED VERSION"""
        try:
            from sqlalchemy import text
            
            # 🔥 FIXED: Enhanced team membership check (same as sharing methods)
            member_check = db.session.execute(
                text("""
                    SELECT role FROM team_members 
                    WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1 
                    AND (
                        invitation_status = 'ACCEPTED' 
                        OR invitation_status IS NULL 
                        OR role LIKE '%OWNER%' 
                        OR role LIKE '%ADMIN%'
                        OR role = 'OWNER'
                        OR role = 'ADMIN'
                    )
                """),
                {"team_id": team_id, "user_id": str(user_id)}
            ).first()
            
            if not member_check:
                return {"success": False, "message": "Not a member of this team"}
            
            # Get team collections with snippet counts
            team_collections = db.session.execute(
                text("""
                    SELECT tc.id, tc.name, tc.description, tc.color, tc.icon,
                        tc.shared_by_id, tc.shared_at, tc.view_count, tc.access_count,
                        tc.team_permissions, u.username as shared_by_name,
                        COUNT(tsc.team_snippet_id) as snippet_count
                    FROM team_collections tc
                    LEFT JOIN users u ON tc.shared_by_id = u.id
                    LEFT JOIN team_snippet_collections tsc ON tc.id = tsc.team_collection_id
                    WHERE tc.team_id = :team_id AND tc.is_active = 1
                    GROUP BY tc.id, tc.name, tc.description, tc.color, tc.icon,
                            tc.shared_by_id, tc.shared_at, tc.view_count, tc.access_count,
                            tc.team_permissions, u.username
                    ORDER BY tc.updated_at DESC
                """),
                {"team_id": team_id}
            ).fetchall()
            
            collections_data = []
            for tc in team_collections:
                # Check if user can edit this collection
                can_edit = (
                    str(tc.shared_by_id) == str(user_id) or  # Shared by user
                    member_check.role.upper() in ['OWNER', 'ADMIN', 'EDITOR', 'MEMBER']  # Role-based
                )
                
                collection_data = {
                    "id": str(tc.id),
                    "name": tc.name,
                    "description": tc.description or "",
                    "color": tc.color or "#3B82F6",
                    "icon": tc.icon or "📁",
                    "shared_by_id": str(tc.shared_by_id),
                    "shared_by_name": tc.shared_by_name or "Unknown",
                    "shared_at": str(tc.shared_at),
                    "view_count": tc.view_count,
                    "access_count": tc.access_count,
                    "snippet_count": tc.snippet_count or 0,
                    "can_edit": can_edit,
                    "team_permissions": json.loads(tc.team_permissions) if tc.team_permissions else {},
                    "content_type": "team_collection"
                }
                collections_data.append(collection_data)
            
            return {
                "success": True,
                "collections": collections_data,
                "count": len(collections_data),
                "team_id": team_id
            }
            
        except Exception as e:
            print(f"❌ GET_TEAM_CONTENT_COLLECTIONS ERROR: {str(e)}")
            return {"success": False, "message": str(e)}

    def get_user_collaboration_history(
        self, user_id: int, limit: int = 50
    ) -> List[Dict]:
        """Get user's collaboration history"""
        # This would typically query a collaboration_history table
        # For now, return mock data structure
        return []

    def force_save_snapshot(self, session_id: str) -> bool:
        """Force save current state as snapshot"""
        if session_id not in self.active_sessions:
            return False

        session = self.active_sessions[session_id]
        snippet = Snippet.query.get(session.snippet_id)

        if snippet:
            # Save current content as a version snapshot
            snapshot_data = {
                "content": snippet.code,  # ← Changed from snippet.content to snippet.code
                "version": session.version,
                "participants": session.participants,
                "timestamp": datetime.utcnow().isoformat(),
            }

            try:
                if self.redis_client:
                    self.redis_client.setex(
                        f"collab_snapshot:{session_id}:{session.version}",
                        86400,  # 24 hours
                        json.dumps(snapshot_data),
                    )
                    print(f"✅ COLLABORATION: Snapshot saved for session {session_id}")
                else:
                    print(f"⚠️ COLLABORATION: Redis unavailable, snapshot not saved")
            except Exception as redis_error:
                print(f"⚠️ COLLABORATION: Failed to save snapshot: {redis_error}")

        return True


# Global instance
collaboration_service = CollaborationService()
