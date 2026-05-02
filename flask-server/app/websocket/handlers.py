# flask-server/app/websocket/handlers.py
from flask_socketio import emit, disconnect, join_room, leave_room
from flask_login import current_user
from flask import request
import json
from datetime import datetime

from sqlalchemy import text
from app.models.user import User
from app.models.snippet import Snippet
from app.models.collection import Collection
from app.services.snippet_analyzer import SnippetAnalyzer
from app.services.syntax_highlighter import SyntaxHighlighter
from app.models.team import Team
from app.services.collaboration_service import collaboration_service

# ADD THESE IMPORTS
from app.models.snippet_comment import SnippetComment
from app.models.snippet_chat import SnippetChat
# ADD THIS IMPORT
from app.models.activity import Activity

from app.models.team_member import TeamMember
from app.websocket.events import *
from app import db, socketio
from .events import WebSocketEvents, EventType
import time
import logging
import re
from werkzeug.security import check_password_hash, generate_password_hash
import jwt
from datetime import datetime, timedelta
from flask import request, current_app


logger = logging.getLogger(__name__)
_cursor_update_cache = {}
_typing_state_cache = {}
active_editing_sessions = {}


def add_user_to_session(snippet_id, user_id, username, color, sid):
    """Add user to active editing session"""
    if snippet_id not in active_editing_sessions:
        active_editing_sessions[snippet_id] = {}

    active_editing_sessions[snippet_id][user_id] = {
        "username": username,
        "color": color,
        "sid": sid,
        "joined_at": datetime.utcnow().isoformat(),
    }
    print(
        f"📊 Session {snippet_id} now has {len(active_editing_sessions[snippet_id])} users"
    )


def remove_user_from_session(snippet_id, user_id):
    """Remove user from active editing session"""
    if (
        snippet_id in active_editing_sessions
        and user_id in active_editing_sessions[snippet_id]
    ):
        del active_editing_sessions[snippet_id][user_id]
        if not active_editing_sessions[snippet_id]:
            del active_editing_sessions[snippet_id]
        print(f"📊 User {user_id} removed from session {snippet_id}")


def get_session_users(snippet_id):
    """Get all users in editing session"""
    return active_editing_sessions.get(snippet_id, {})


def log_websocket_error(context, error, additional_data=None):
    """Enhanced error logging for WebSocket operations"""
    import traceback

    error_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "context": context,
        "error": str(error),
        "traceback": traceback.format_exc(),
        "client_sid": request.sid,
        "client_ip": request.remote_addr,
        "user_agent": request.headers.get("User-Agent", "Unknown"),
        "additional_data": additional_data or {},
    }

    logger.error(f"🔥 WEBSOCKET_ERROR [{context}]: {error_data}")

    # Store in a global error log for debugging
    try:
        if not hasattr(log_websocket_error, "error_log"):
            log_websocket_error.error_log = []

        log_websocket_error.error_log.append(error_data)

        # Keep only last 100 errors
        if len(log_websocket_error.error_log) > 100:
            log_websocket_error.error_log = log_websocket_error.error_log[-100:]

    except Exception as log_error:
        logger.error(f"🔥 Failed to store WebSocket error log: {str(log_error)}")

    return error_data


def validate_email(email):
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


def validate_password(password):
    # At least 8 chars, 1 uppercase, 1 lowercase, 1 number
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    return True, "Valid password"


# 4. REPLACE YOUR PLACEHOLDER authenticate_user FUNCTION WITH THIS REAL ONE
def authenticate_user(email, password):
    """
    Real authentication using your existing User model and password checking
    """
    try:
        email = email.strip().lower()
        logger.info(f"🔍 Authenticating user: {email}")

        # Validate email format
        if not validate_email(email):
            logger.error(f"❌ Invalid email format: {email}")
            return None

        # Find user in database
        user = User.query.filter_by(email=email).first()

        if not user:
            logger.error(f"❌ User not found: {email}")
            return None

        logger.info(f"✅ User found: {user.id}")

        # Check password using your existing method
        if not check_password_hash(user.password_hash, password):
            logger.error(f"❌ Password check failed for: {email}")
            return None

        logger.info(f"✅ Password verified for: {email}")
        return user

    except Exception as e:
        logger.error(f"❌ Authentication error: {str(e)}")
        return None


# 5. REPLACE YOUR PLACEHOLDER generate_jwt_token FUNCTION WITH THIS REAL ONE
def generate_jwt_token(user):
    """
    Real JWT token generation using your existing method
    """
    try:
        # Use the exact same JWT generation as your auth.py
        payload = {
            "user_id": str(user.id),
            "email": user.email,
            "exp": datetime.utcnow() + timedelta(days=30),
        }

        logger.info(f"🔑 Creating JWT payload: {payload}")

        token = jwt.encode(
            payload,
            current_app.config["SECRET_KEY"],  # Uses your existing secret key
            algorithm="HS256",
        )

        logger.info(f"🔑 JWT token generated for user: {user.email}")
        logger.info(f"🔑 Token type: {type(token)}")
        logger.info(f"🔑 Token length: {len(token)} characters")

        return token

    except Exception as e:
        logger.error(f"❌ JWT token generation error: {str(e)}")
        logger.error(f"❌ Error type: {type(e)}")
        import traceback

        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return None


# 6. REPLACE YOUR PLACEHOLDER create_user FUNCTION WITH THIS REAL ONE
def create_user(email, password, name=""):
    """
    Real user creation using your existing User model
    """
    try:
        email = email.strip().lower()
        logger.info(f"👤 Creating new user: {email}")

        # Validate email format
        if not validate_email(email):
            logger.error(f"❌ Invalid email format: {email}")
            return None

        # Validate password
        is_valid, message = validate_password(password)
        if not is_valid:
            logger.error(f"❌ Password validation failed: {message}")
            return None

        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            logger.error(f"❌ User already exists: {email}")
            return None

        # Create new user using your existing User model constructor
        user = User(email=email, password=password)  # Your User model handles hashing

        logger.info(f"✅ User object created for: {email}")

        # Save to database
        db.session.add(user)
        db.session.commit()

        logger.info(f"✅ User saved to database: {email} with ID: {user.id}")
        return user

    except Exception as e:
        logger.error(f"❌ User creation error: {str(e)}")
        db.session.rollback()
        return None


# ===== CACHE MANAGEMENT =====
def cleanup_caches():
    """Periodic cleanup of module-level caches to prevent memory leaks"""
    global _cursor_update_cache, _typing_state_cache

    current_time = time.time()
    cutoff_time = current_time - 300  # 5 minutes old

    # Clean cursor cache
    if len(_cursor_update_cache) > 500:
        _cursor_update_cache = {
            k: v for k, v in _cursor_update_cache.items() if v > cutoff_time
        }
        print(f"🧹 Cleaned cursor cache: {len(_cursor_update_cache)} entries remaining")

    # Clean typing cache
    if len(_typing_state_cache) > 200:
        _typing_state_cache = {
            k: v for k, v in _typing_state_cache.items() if v > cutoff_time
        }
        print(f"🧹 Cleaned typing cache: {len(_typing_state_cache)} entries remaining")


# Schedule periodic cleanup
import threading


def schedule_cache_cleanup():
    cleanup_caches()
    # Schedule next cleanup in 5 minutes
    threading.Timer(300, schedule_cache_cleanup).start()


# Start cleanup scheduler
schedule_cache_cleanup()


@socketio.on("register")
def handle_register(data):
    """Handle registration requests from Chrome extension"""
    logger.info(f"🔵 REGISTRATION REQUEST RECEIVED from {request.sid}")
    logger.info(f"🔵 Register data: {data}")

    try:
        # Extract registration data
        email = data.get("email")
        password = data.get("password")
        name = data.get("name", "")

        if not email or not password:
            logger.error("❌ Missing email or password")
            emit(
                "register_response",
                {"success": False, "message": "Email and password required"},
            )
            return

        # Your existing registration logic here
        # Replace this with your actual user creation
        user = create_user(email, password, name)  # Your existing function

        if user:
            # Generate JWT token
            token = generate_jwt_token(user)  # Your existing function
            logger.info(f"✅ Registration successful for {email}")

            emit(
                "register_response",
                {"success": True, "token": token, "message": "Registration successful"},
            )
        else:
            logger.error(f"❌ Registration failed for {email}")
            emit(
                "register_response",
                {"success": False, "message": "Registration failed"},
            )

    except Exception as e:
        logger.error(f"❌ Registration error: {str(e)}")
        emit("register_response", {"success": False, "message": "Registration failed"})


@socketio.on("login")
def handle_login(data):
    """Handle login requests from Chrome extension"""
    logger.info(f"🔵 LOGIN REQUEST RECEIVED from {request.sid}")
    logger.info(f"🔵 Login data: {data}")

    try:
        # Extract credentials
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            logger.error("❌ Missing email or password")
            emit(
                "login_response",
                {"success": False, "message": "Email and password required"},
            )
            return

        # Your existing authentication logic here
        # Replace this with your actual user validation
        user = authenticate_user(email, password)  # Your existing function

        if user:
            # Generate JWT token
            token = generate_jwt_token(user)  # Your existing function
            if token:
                logger.info(f"✅ Login successful for {email}")

            # NEW: Log token sending details
            logger.info(f"📤 SENDING JWT TOKEN TO CLIENT {request.sid}")
            logger.info(f"📤 Token length: {len(token)} characters")
            logger.info(f"📤 Token preview: {token[:50]}...")

            response_data = {
                "success": True,
                "token": token,
                "message": "Login successful",
                "user": {"id": str(user.id), "email": user.email},
            }

            logger.info(f"📤 Emitting login_response to client: {request.sid}")
            emit("login_response", response_data)
            logger.info(f"✅ LOGIN_RESPONSE SENT TO CLIENT {request.sid}")
        else:
            logger.error(f"❌ Token generation failed for {email}")
            emit(
                "login_response",
                {"success": False, "message": "Token generation failed"},
            )
            logger.error(f"❌ Invalid credentials for {email}")
            emit("login_response", {"success": False, "message": "Invalid credentials"})

    except Exception as e:
        logger.error(f"❌ Login error: {str(e)}")
        emit("login_response", {"success": False, "message": "Login failed"})


@socketio.on("authenticate")
def handle_authenticate(data):
    """Handle authentication requests from frontend"""
    try:
        user_id = data.get("userId")
        timestamp = data.get("timestamp")
        user_agent = data.get("userAgent")

        print(f"🔐 AUTHENTICATE - User: {user_id}, Timestamp: {timestamp}")

        if not user_id:
            print("❌ AUTHENTICATE - Missing user ID")
            emit("auth_error", {"error": "User ID required"})
            return

        # Verify user exists
        user = User.query.get(user_id)
        if not user:
            print(f"❌ AUTHENTICATE - User not found: {user_id}")
            emit("auth_error", {"error": "User not found"})
            return

        # Join user room
        user_room = f"user_{user_id}"
        join_room(user_room)

        # Get user's team memberships
        team_memberships = TeamMember.query.filter_by(
            user_id=user_id, is_active=True
        ).all()

        team_rooms = []
        for membership in team_memberships:
            team_room = f"team_{membership.team_id}"
            join_room(team_room)
            team_rooms.append(team_room)
            print(f"✅ User {user_id} joined team room: {team_room}")

        # Send authentication success
        emit(
            "auth_success",
            {
                "user_id": user_id,
                "username": user.username,
                "rooms_joined": [user_room] + team_rooms,
                "team_count": len(team_memberships),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        print(f"✅ AUTHENTICATE - User {user_id} authenticated successfully")

    except Exception as e:
        print(f"❌ AUTHENTICATE ERROR: {str(e)}")
        import traceback

        print(f"❌ TRACEBACK: {traceback.format_exc()}")
        emit("auth_error", {"error": "Authentication failed"})


# ADD THESE HANDLERS in handlers.py (around line 800):
@socketio.on("start_collaboration")
def handle_start_collaboration(data):
    """Start collaborative editing session"""
    try:
        snippet_id = data.get("snippet_id")
        user_id = data.get("user_id")

        print(f"🤝 COLLABORATION: Starting session for snippet {snippet_id}")

        # Create collaboration session using the service
        session_id = collaboration_service.create_collaboration_session(
            snippet_id, user_id
        )

        # Join collaboration room
        join_room(f"collab_{session_id}")

        emit(
            "collaboration_started",
            {
                "session_id": session_id,
                "snippet_id": snippet_id,
                "message": "Collaboration session started",
            },
        )

        print(f"✅ COLLABORATION: Session {session_id} started successfully")

    except Exception as e:
        print(f"❌ COLLABORATION: Error starting session: {str(e)}")
        emit("collaboration_error", {"error": str(e)})


@socketio.on("join_collaboration")
def handle_join_collaboration(data):
    """Join existing collaboration session"""
    try:
        session_id = data.get("session_id")
        user_id = data.get("user_id")

        print(f"🤝 COLLABORATION: User {user_id} joining session {session_id}")

        # Join session using collaboration service
        session_data = collaboration_service.join_collaboration_session(
            session_id, user_id
        )

        # Join WebSocket room
        join_room(f"collab_{session_id}")

        emit("collaboration_joined", session_data)

        print(f"✅ COLLABORATION: User joined session successfully")

    except Exception as e:
        print(f"❌ COLLABORATION: Error joining session: {str(e)}")
        emit("collaboration_error", {"error": str(e)})


@socketio.on("collaborative_edit")
def handle_collaborative_edit(data):
    """Handle real-time collaborative editing with conflict resolution"""
    try:
        session_id = data.get("session_id")
        operation_data = data.get("operation")

        print(f"✏️ COLLABORATION: Processing edit operation in session {session_id}")

        # Apply operation using collaboration service (handles conflict resolution)
        result = collaboration_service.apply_operation(session_id, operation_data)

        if result["success"]:
            # Broadcast to all collaborators
            emit(
                "operation_applied",
                {
                    "session_id": session_id,
                    "operation": result,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                room=f"collab_{session_id}",
                include_self=True,
            )

            print(f"✅ COLLABORATION: Operation applied successfully")

            # ADD ACTIVITY LOGGING (only for significant edits)
            if result["success"] and operation_data.get("type") in [
                "insert",
                "replace",
            ]:
                Activity.log_activity(
                    action_type="snippet_edited",
                    user_id=operation_data["user_id"],
                    description=f"Edited snippet collaboratively",
                    target_type="snippet",
                    target_id=session_id.split("_")[1] if "_" in session_id else None,
                    metadata={
                        "operation_type": operation_data.get("type"),
                        "collaboration": True,
                    },
                )

    except Exception as e:
        print(f"❌ COLLABORATION: Error in collaborative edit: {str(e)}")
        emit("collaboration_error", {"error": str(e)})


@socketio.on_error()
def error_handler(e):
    """Handle WebSocket errors"""
    logger.error(f"❌ WebSocket error occurred: {str(e)}")
    logger.error(f"❌ Error type: {type(e)}")
    logger.error(f"❌ Client SID: {request.sid}")
    import traceback

    logger.error(f"❌ Traceback: {traceback.format_exc()}")


class WebSocketHandlers:
    """Handle all WebSocket events for real-time snippet synchronization"""

    @staticmethod
    def default_error_handler(e):
        """Default error handler for WebSocket events"""
        print(f"WebSocket error: {e}")
        emit("error", {"message": "An error occurred during the operation"})

    @socketio.on("connect")
    def handle_connect_debug():
        """Enhanced connection handler with detailed logging"""
        logger.info(f"🔌 CLIENT CONNECTED: {request.sid}")
        logger.info(f"🔌 Request args: {dict(request.args)}")
        logger.info(f"🔌 Request headers: {dict(request.headers)}")
        logger.info(f"🔌 Client origin: {request.headers.get('Origin', 'Unknown')}")

        emit(
            "connection_established",
            {
                "status": "connected",
                "client_id": request.sid,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        logger.info(f"✅ Connection established for client: {request.sid}")

    @staticmethod
    @socketio.on("connect")
    def handle_connect(auth):
        """Handle client connection with team room joining"""
        try:
            print(f"🔌 CLIENT CONNECTING: {request.sid}")

            # Get token from various sources
            token = (
                request.args.get("token")
                or request.headers.get("Authorization")
                or (auth.get("token") if auth else None)
            )

            if token and token.startswith("Bearer "):
                token = token[7:]

            if token:
                try:
                    import jwt as pyjwt

                    payload = pyjwt.decode(
                        token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
                    )
                    user_id = payload.get("user_id")

                    if user_id:
                        user = User.query.get(user_id)
                        if user:
                            # Join user room
                            user_room = f"user_{user_id}"
                            join_room(user_room)
                            print(f"✅ User {user_id} joined room: {user_room}")

                            # Join team rooms
                            team_memberships = TeamMember.query.filter_by(
                                user_id=user_id, is_active=True
                            ).all()

                            team_rooms = []
                            for membership in team_memberships:
                                team_room = f"team_{membership.team_id}"
                                join_room(team_room)
                                team_rooms.append(team_room)
                                print(
                                    f"✅ User {user_id} joined team room: {team_room}"
                                )

                            emit(
                                "connection_status",
                                {
                                    "status": "connected",
                                    "user_id": user_id,
                                    "rooms_joined": [user_room] + team_rooms,
                                    "timestamp": datetime.utcnow().isoformat(),
                                },
                            )

                            # Notify team members
                            for membership in team_memberships:
                                emit(
                                    "user_online",
                                    {
                                        "user_id": user_id,
                                        "username": user.username,
                                        "team_id": membership.team_id,
                                    },
                                    room=f"team_{membership.team_id}",
                                )

                            return

                except Exception as e:
                    print(f"❌ Token verification failed: {str(e)}")

            # If no valid token, still allow connection but limited access
            emit(
                "connection_status",
                {
                    "status": "connected_anonymous",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        except Exception as e:
            print(f"❌ Connection error: {str(e)}")
            emit("error", {"message": "Connection failed"})

    @staticmethod
    @socketio.on(WebSocketEvents.SNIPPET_CREATED)
    def handle_snippet_created(data):
        """Handle new snippet creation"""
        snippet_id = data.get("snippet_id")
        snippet = Snippet.query.get(snippet_id)

        if snippet and snippet.user_id == current_user.id:
            # Broadcast to user's devices
            emit(
                WebSocketEvents.SNIPPET_CREATED,
                {
                    "snippet": snippet.to_dict(),
                    "timestamp": datetime.utcnow().isoformat(),
                },
                room=f"user_{current_user.id}",
            )

            # If snippet belongs to a team collection, broadcast to team
            if snippet.collection and snippet.collection.team_id:
                emit(
                    WebSocketEvents.SNIPPET_CREATED,
                    {
                        "snippet": snippet.to_dict(),
                        "user": current_user.username,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                    room=f"team_{snippet.collection.team_id}",
                )

    @staticmethod
    @socketio.on("disconnect")
    def handle_disconnect(auth):
        """Handle client disconnection"""
        if current_user.is_authenticated:
            user_room = f"user_{current_user.id}"
            leave_room(user_room)
            print(f"User {current_user.id} disconnected from WebSocket")
        if current_user.is_authenticated:
            user_room = f"user_{current_user.id}"
            leave_room(user_room)
            print(f"User {current_user.id} disconnected from WebSocket")

            # Notify team members that user is offline
            team_memberships = TeamMember.query.filter_by(user_id=current_user.id).all()
            for membership in team_memberships:
                emit(
                    "user_offline",
                    {
                        "user_id": current_user.id,
                        "username": current_user.username,
                        "team_id": membership.team_id,
                    },
                    room=f"team_{membership.team_id}",
                )

    @staticmethod
    @socketio.on("save_snippet")
    def handle_snippet_save(data):
        """Handle real-time snippet saving from extension with enhanced services"""
        try:
            # 🚀 ENHANCED LOGGING - Add at the very beginning
            print(f"🔍 FULL DATA RECEIVED: {json.dumps(data, indent=2, default=str)}")
            print(f"🔍 COLLECTION_ID IN DATA: {data.get('collection_id')}")
            print(f"🔍 ALL DATA KEYS: {list(data.keys())}")

            print(f"🎯 SNIPPET SAVE - Received data: {data}")
            print(
                f"🔍 SNIPPET SAVE - Data keys: {list(data.keys()) if data else 'No data'}"
            )

            # Extract token and verify it
            token = data.get("token")
            user_id = data.get("userId")

            print(
                f"🔍 SNIPPET SAVE - Auth check: token={bool(token)}, user_id={user_id}"
            )

            if not token or not user_id:
                print("❌ SNIPPET SAVE - Missing authentication")
                emit(
                    "snippet_save_response",
                    {"success": False, "error": "Authentication required"},
                )
                return

            # Verify token
            try:
                import jwt as pyjwt

                payload = pyjwt.decode(
                    token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
                )
                if payload.get("user_id") != user_id:
                    print("❌ SNIPPET SAVE - Token user mismatch")
                    emit(
                        "snippet_save_response",
                        {"success": False, "error": "Invalid token"},
                    )
                    return
                print("✅ SNIPPET SAVE - Token verified successfully")
            except Exception as e:
                print(f"❌ SNIPPET SAVE - Token verification failed: {str(e)}")
                emit(
                    "snippet_save_response",
                    {"success": False, "error": "Token verification failed"},
                )
                return

            # Validate required fields
            required_fields = ["code", "language", "title"]
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                print(f"❌ SNIPPET SAVE - Missing fields: {missing_fields}")
                emit(
                    "snippet_save_response",
                    {
                        "success": False,
                        "error": f"Missing required fields: {', '.join(missing_fields)}",
                    },
                )
                return

            print("✅ SNIPPET SAVE - All validations passed")

            # 🚀 INTEGRATE SNIPPET ANALYZER SERVICE
            from app.services.snippet_analyzer import snippet_analyzer

            analysis_result = snippet_analyzer.analyze_snippet(
                data["code"], filename=None, provided_language=data.get("language")
            )

            print(f"🔍 SNIPPET ANALYSIS RESULT: {analysis_result}")

            # Use analyzed language and tags
            detected_language = analysis_result["language"]["detected_language"]
            auto_tags = analysis_result["auto_tags"]

            # Combine provided tags with auto-generated ones
            provided_tags = data.get("tags", [])
            if isinstance(provided_tags, str):
                provided_tags = [
                    tag.strip() for tag in provided_tags.split(",") if tag.strip()
                ]

            combined_tags = list(set(provided_tags + auto_tags))

            print(
                f"🏷️ TAGS: provided={provided_tags}, auto={auto_tags}, combined={combined_tags}"
            )

            # Create snippet data with analysis
            snippet_data = {
                "code": data["code"],
                "language": detected_language,  # Use analyzed language
                "title": data["title"],
                "source_url": data.get("source_url"),
                "tags": combined_tags,  # Use combined tags
                "collection_id": data.get("collection_id"),
                "complexity": analysis_result["complexity"],
                "functions": analysis_result["functions"],
                "imports": analysis_result["imports"],
            }

            print(f"📦 FINAL SNIPPET DATA: {snippet_data}")

            # Generate snippet ID
            import uuid

            snippet_id = str(uuid.uuid4())

            # Handle tags properly
            tags_str = ",".join([tag.strip() for tag in combined_tags if tag.strip()])

            # Insert snippet with analysis data
            sql = db.text(
                """
                INSERT INTO snippets (
                    id, user_id, title, code, language, source_url, tags, 
                    created_at, updated_at, is_deleted, version, is_team_snippet,
                    share_permission, is_public, is_collaborative, version_number,
                    is_version, execution_count, view_count, copy_count, share_count,
                    source_type, "order", status
                ) VALUES (
                    :id, :user_id, :title, :code, :language, :source_url, :tags,
                    :created_at, :updated_at, :is_deleted, :version, :is_team_snippet,
                    :share_permission, :is_public, :is_collaborative, :version_number,
                    :is_version, :execution_count, :view_count, :copy_count, :share_count,
                    :source_type, :order_val, :status
                )
            """
            )

            from datetime import datetime

            now = datetime.utcnow()

            db.session.execute(
                sql,
                {
                    "id": snippet_id,
                    "user_id": str(user_id),
                    "title": snippet_data["title"].strip(),
                    "code": snippet_data["code"],
                    "language": snippet_data["language"],
                    "source_url": snippet_data.get("source_url"),
                    "tags": tags_str,
                    "created_at": now,
                    "updated_at": now,
                    "is_deleted": False,
                    "version": 1,
                    "is_team_snippet": False,
                    "share_permission": "READ",
                    "is_public": False,
                    "is_collaborative": False,
                    "version_number": 1,
                    "is_version": False,
                    "execution_count": 0,
                    "view_count": 0,
                    "copy_count": 0,
                    "share_count": 0,
                    "source_type": "extension",
                    "order_val": 0,
                    "status": "ACTIVE",
                },
            )

            # 🔧 ENHANCED COLLECTION LINKING WITH DETAILED LOGGING
            collection_id = data.get("collection_id")  # ← GET DIRECTLY FROM DATA
            print(f"🔍 COLLECTION LINKING DEBUG:")
            print(f"   - collection_id from data: {collection_id}")
            print(f"   - collection_id type: {type(collection_id)}")
            print(f"   - collection_id bool: {bool(collection_id)}")
            print(f"   - collection_id str: '{str(collection_id)}'")

            if collection_id:
                print(f"🔗 ATTEMPTING TO LINK TO COLLECTION: {collection_id}")

                # Verify collection exists and belongs to user
                collection_check_sql = db.text(
                    """
                    SELECT id, name FROM collections 
                    WHERE id = :collection_id AND user_id = :user_id
                """
                )
                collection_result = db.session.execute(
                    collection_check_sql,
                    {"collection_id": str(collection_id), "user_id": str(user_id)},
                ).fetchone()

                if collection_result:
                    print(
                        f"✅ COLLECTION VERIFIED: {collection_result.name} (ID: {collection_result.id})"
                    )

                    relationship_sql = db.text(
                        """
                        INSERT INTO snippet_collections (snippet_id, collection_id)
                        VALUES (:snippet_id, :collection_id)
                    """
                    )
                    db.session.execute(
                        relationship_sql,
                        {
                            "snippet_id": snippet_id,
                            "collection_id": str(
                                collection_id
                            ),  # ← ENSURE STRING FORMAT
                        },
                    )
                    print(f"✅ COLLECTION LINK EXECUTED SUCCESSFULLY")

                    # Verify the link was created
                    verify_sql = db.text(
                        """
                        SELECT COUNT(*) as count FROM snippet_collections 
                        WHERE snippet_id = :snippet_id AND collection_id = :collection_id
                    """
                    )
                    verify_result = db.session.execute(
                        verify_sql,
                        {"snippet_id": snippet_id, "collection_id": str(collection_id)},
                    ).fetchone()
                    print(f"🔍 LINK VERIFICATION: {verify_result.count} links found")

                else:
                    print(f"❌ COLLECTION NOT FOUND OR ACCESS DENIED: {collection_id}")
                    print(f"   - Checking if collection exists at all...")
                    any_collection_sql = db.text(
                        "SELECT id, user_id FROM collections WHERE id = :collection_id"
                    )
                    any_result = db.session.execute(
                        any_collection_sql, {"collection_id": str(collection_id)}
                    ).fetchone()
                    if any_result:
                        print(
                            f"   - Collection exists but belongs to user: {any_result.user_id} (current user: {user_id})"
                        )
                    else:
                        print(f"   - Collection does not exist in database")
            else:
                print(f"❌ NO COLLECTION_ID FOUND IN DATA")

            db.session.commit()

            print(f"✅ SNIPPET SAVED SUCCESSFULLY - ID: {snippet_id}")
            # ADD ACTIVITY LOGGING
            try:
                from app.models.activity import Activity

                Activity.log_activity(
                    action_type="snippet_created",
                    user_id=user_id,
                    description=f"Created snippet '{snippet_data['title']}'",
                    team_id=None,  # Personal snippet initially
                    target_type="snippet",
                    target_id=snippet_id,
                    target_name=snippet_data["title"],
                    metadata={
                        "language": snippet_data["language"],
                        "source_type": "extension",
                        "auto_tags": auto_tags,
                        "collection_id": collection_id,
                    },
                )
                print(f"✅ SNIPPET_CREATED: Activity logged successfully")
            except Exception as activity_error:
                print(
                    f"❌ SNIPPET_CREATED: Activity logging failed: {str(activity_error)}"
                )

            # 🎨 INTEGRATE SYNTAX HIGHLIGHTER SERVICE
            from app.services.syntax_highlighter import syntax_highlighter

            highlight_result = syntax_highlighter.highlight_code(
                snippet_data["code"],
                snippet_data["language"],
                style="github",
                output_format="html",
            )

            print(f"🎨 SYNTAX HIGHLIGHTING: success={highlight_result['success']}")

            # Emit enhanced success response
            emit(
                "snippet_save_response",
                {
                    "success": True,
                    "snippet": {
                        "id": snippet_id,
                        "title": snippet_data["title"],
                        "code": snippet_data["code"],
                        "language": snippet_data["language"],
                        "collection_id": collection_id,
                        "created_at": now.isoformat(),
                        "tags": combined_tags,
                        "highlighted_code": highlight_result.get("highlighted_code"),
                        "analysis": {
                            "complexity": analysis_result["complexity"],
                            "functions": analysis_result["functions"],
                            "auto_tags": auto_tags,
                        },
                    },
                    "message": f"Snippet saved with {len(auto_tags)} auto-generated tags!",
                },
            )

            print(f"📤 SUCCESS RESPONSE SENT")

        except Exception as e:
            db.session.rollback()
            print(f"❌ SNIPPET SAVE ERROR: {str(e)}")
            import traceback

            print(f"❌ FULL TRACEBACK: {traceback.format_exc()}")
            emit(
                "snippet_save_response",
                {"success": False, "error": f"Failed to save snippet: {str(e)}"},
            )

    @staticmethod
    @socketio.on(WebSocketEvents.SNIPPET_UPDATE)
    def handle_snippet_update(data):
        """Handle real-time snippet updates"""
        try:
            if not current_user.is_authenticated:
                emit("error", {"message": "Authentication required"})
                return

            snippet_id = data.get("snippet_id")
            if not snippet_id:
                emit("error", {"message": "Snippet ID required"})
                return

            snippet = Snippet.query.filter_by(
                id=snippet_id, user_id=current_user.id
            ).first()

            if not snippet:
                emit("error", {"message": "Snippet not found"})
                return

            # Update snippet fields
            if "title" in data:
                snippet.title = data["title"]
            if "code" in data:
                snippet.code = data["code"]
            if "language" in data:
                snippet.language = data["language"]
            if "tags" in data:
                snippet.tags = data["tags"]

            snippet.updated_at = datetime.utcnow()
            db.session.commit()

            # Get updated highlighted code
            highlighter = SyntaxHighlighter()
            highlighted_code = highlighter.highlight(snippet.code, snippet.language)

            # ADD ACTIVITY LOGGING
            Activity.log_activity(
                action_type="snippet_edited",
                user_id=current_user.id,
                description=f"Edited snippet '{snippet.title}'",
                target_type="snippet",
                target_id=snippet.id,
                target_name=snippet.title,
                metadata={"fields_updated": list(data.keys()), "edit_type": "direct"},
            )

            # Emit success
            emit(
                WebSocketEvents.SNIPPET_UPDATED,
                {
                    "snippet_id": snippet.id,
                    "highlighted_code": highlighted_code,
                    "updated_at": snippet.updated_at.isoformat(),
                    "message": "Snippet updated successfully",
                },
            )

        except Exception as e:
            print(f"Error updating snippet: {str(e)}")
            emit("error", {"message": "Failed to update snippet"})

    @staticmethod
    @socketio.on(WebSocketEvents.SNIPPET_DELETE)
    def handle_snippet_delete(data):
        """Handle real-time snippet deletion"""
        try:
            if not current_user.is_authenticated:
                emit("error", {"message": "Authentication required"})
                return

            snippet_id = data.get("snippet_id")
            if not snippet_id:
                emit("error", {"message": "Snippet ID required"})
                return

            snippet = Snippet.query.filter_by(
                id=snippet_id, user_id=current_user.id
            ).first()

            if not snippet:
                emit("error", {"message": "Snippet not found"})
                return

            db.session.delete(snippet)
            db.session.commit()

            # Emit success
            emit(
                WebSocketEvents.SNIPPET_DELETED,
                {"snippet_id": snippet_id, "message": "Snippet deleted successfully"},
            )

        except Exception as e:
            print(f"Error deleting snippet: {str(e)}")
            emit("error", {"message": "Failed to delete snippet"})

    @staticmethod
    @socketio.on("create_collection")  # ← Change this to match what extension sends
    def handle_collection_create(data):
        """Handle real-time collection creation"""
        try:
            print(f"🎯 COLLECTION CREATE - Received data: {data}")

            # Extract token and verify it (since extension sends token, not current_user)
            token = data.get("token")
            user_id = data.get("userId")

            if not token or not user_id:
                emit(
                    "collection_create_response",
                    {  # ← Change event name
                        "success": False,
                        "error": "Authentication required",
                    },
                )
                return

            # Verify token
            try:
                import jwt as pyjwt

                payload = pyjwt.decode(
                    token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
                )
                if payload.get("user_id") != user_id:
                    emit(
                        "collection_create_response",
                        {"success": False, "error": "Invalid token"},
                    )
                    return
            except Exception as e:
                emit(
                    "collection_create_response",
                    {"success": False, "error": "Token verification failed"},
                )
                return

            name = data.get("name")
            if not name:
                emit(
                    "collection_create_response",
                    {  # ← Change event name
                        "success": False,
                        "error": "Collection name required",
                    },
                )
                return

            # Check for duplicate collection name
            existing_collection = Collection.query.filter_by(
                user_id=user_id, name=name.strip()
            ).first()

            if existing_collection:
                print(f"❌ COLLECTION CREATE - Duplicate name found: {name}")
                emit(
                    "collection_create_response",
                    {  # ← Change event name
                        "success": False,
                        "error": f"Collection '{name}' already exists. Please choose a different name.",
                        "error_type": "duplicate_name",
                    },
                )
                return

            collection = Collection(
                user_id=user_id,
                name=name.strip(),
                description=data.get("description", ""),
                color=data.get("color", "#3B82F6"),
                is_public=data.get("is_public", False),
            )

            db.session.add(collection)
            db.session.commit()

            print(
                f"✅ COLLECTION CREATED - ID: {collection.id}, Name: {collection.name}"
            )

            # ADD ACTIVITY LOGGING
            Activity.log_activity(
                action_type="collection_created",
                user_id=user_id,
                description=f"Created collection '{collection.name}'",
                target_type="collection",
                target_id=str(collection.id),
                target_name=collection.name,
                metadata={"color": collection.color, "is_public": collection.is_public},
            )

            emit(
                "collection_create_response",
                {  # ← Change event name
                    "success": True,
                    "collection": {
                        "id": str(collection.id),
                        "name": collection.name,
                        "description": collection.description,
                        "color": collection.color,
                        "snippet_count": 0,
                        "created_at": collection.created_at.isoformat(),
                    },
                    "message": "Collection created successfully",
                },
            )

        except Exception as e:
            print(f"❌ COLLECTION CREATE ERROR: {str(e)}")
            import traceback

            print(f"❌ FULL TRACEBACK: {traceback.format_exc()}")
            emit(
                "collection_create_response",
                {  # ← Change event name
                    "success": False,
                    "error": "Failed to create collection",
                },
            )

    @staticmethod
    @socketio.on(WebSocketEvents.SYNC_REQUEST)
    def handle_sync_request(data):
        """Handle sync request from extension"""
        try:
            if not current_user.is_authenticated:
                emit("error", {"message": "Authentication required"})
                return

            # Get user's recent snippets
            snippets = (
                Snippet.query.filter_by(user_id=current_user.id)
                .order_by(Snippet.created_at.desc())
                .limit(50)
                .all()
            )

            # Get user's collections
            collections = Collection.query.filter_by(user_id=current_user.id).all()

            # Prepare sync data
            sync_data = {
                "snippets": [
                    {
                        "id": s.id,
                        "title": s.title,
                        "code": s.code,
                        "language": s.language,
                        "source_url": s.source_url,
                        "tags": s.tags,
                        "created_at": s.created_at.isoformat(),
                        "updated_at": (
                            s.updated_at.isoformat() if s.updated_at else None
                        ),
                    }
                    for s in snippets
                ],
                "collections": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "description": c.description,
                        "color": c.color,
                        "snippet_count": len(c.snippets),
                    }
                    for c in collections
                ],
                "sync_timestamp": datetime.utcnow().isoformat(),
            }

            emit(WebSocketEvents.SYNC_RESPONSE, sync_data)

        except Exception as e:
            print(f"Error handling sync request: {str(e)}")
            emit("error", {"message": "Failed to sync data"})

    @staticmethod
    @socketio.on(WebSocketEvents.HEARTBEAT)
    def handle_heartbeat(data):
        """Handle client heartbeat to maintain connection"""
        emit(
            WebSocketEvents.HEARTBEAT_RESPONSE,
            {"timestamp": datetime.utcnow().isoformat(), "status": "alive"},
        )

    @staticmethod
    @socketio.on("join_team_room")
    def handle_join_team_room(data):
        """Join team collaboration room"""
        try:
            team_id = data.get("team_id")
            user_id = data.get("user_id")

            print(f"🏢 JOIN TEAM ROOM - Team: {team_id}, User: {user_id}")

            # Verify team membership
            membership = TeamMember.query.filter_by(
                team_id=team_id, user_id=user_id, is_active=True
            ).first()

            if not membership:
                emit("team_join_error", {"error": "Not a team member"})
                return

            team_room = f"team_{team_id}"
            join_room(team_room)

            # Get team info
            team = Team.query.get(team_id)
            user = User.query.get(user_id)

            emit(
                "team_joined",
                {
                    "team_id": team_id,
                    "team_name": team.name,
                    "user_role": membership.role.value,
                    "room": team_room,
                },
            )

            # Notify other team members
            emit(
                "team_member_online",
                {"user_id": user_id, "username": user.username, "team_id": team_id},
                room=team_room,
                include_self=True,
            )

            print(f"✅ User {user_id} joined team room: {team_room}")

        except Exception as e:
            print(f"❌ JOIN TEAM ROOM ERROR: {str(e)}")
            emit("team_join_error", {"error": "Failed to join team room"})

    @staticmethod
    @socketio.on("team_created")
    def handle_team_created(data):
        """Handle team creation WebSocket events"""
        try:
            team_data = data.get("team")
            user_id = data.get("userId")

            print(f"🏢 TEAM CREATED - Team: {team_data.get('name')}, User: {user_id}")

            if not team_data or not user_id:
                print("❌ TEAM CREATED - Missing team data or user ID")
                emit("team_creation_error", {"error": "Invalid team creation data"})
                return

            # Verify user exists
            user = User.query.get(user_id)
            if not user:
                print(f"❌ TEAM CREATED - User not found: {user_id}")
                emit("team_creation_error", {"error": "User not found"})
                return

            # Join user to their new team room
            team_room = f"team_{team_data['id']}"
            join_room(team_room)

            # Emit success response
            emit(
                "team_created_success",
                {
                    "team": team_data,
                    "message": f"Team '{team_data['name']}' created successfully",
                    "room_joined": team_room,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            print(f"✅ TEAM CREATED - User {user_id} joined team room: {team_room}")

        except Exception as e:
            log_websocket_error(
                "TEAM_CREATION", e, {"team_data": team_data, "user_id": user_id}
            )
            import traceback

            print(f"❌ TRACEBACK: {traceback.format_exc()}")
            emit("team_creation_error", {"error": "Failed to process team creation"})

    @staticmethod
    @socketio.on("join_team")
    def handle_join_team(data):
        """Handle user joining a team"""
        try:
            team_id = data.get("teamId")
            user_id = data.get("userId")

            print(f"🏢 JOIN TEAM - Team: {team_id}, User: {user_id}")

            if not team_id or not user_id:
                print("❌ JOIN TEAM - Missing team ID or user ID")
                emit("team_join_error", {"error": "Missing team or user ID"})
                return

            # Verify team exists
            team = Team.query.get(team_id)
            if not team:
                print(f"❌ JOIN TEAM - Team not found: {team_id}")
                emit("team_join_error", {"error": "Team not found"})
                return

            # Join team room
            team_room = f"team_{team_id}"
            join_room(team_room)

            # Get user info
            user = User.query.get(user_id)
            username = user.username if user else "Unknown User"

            # Emit to team room that user joined
            emit(
                "user_joined_team",
                {
                    "user_id": user_id,
                    "username": username,
                    "team_id": team_id,
                    "team_name": team.name,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                room=team_room,
                include_self=True,
            )

            # Confirm to user they joined
            emit(
                "team_joined_success",
                {
                    "team_id": team_id,
                    "team_name": team.name,
                    "room": team_room,
                    "message": f"Joined team '{team.name}'",
                },
            )

            print(f"✅ JOIN TEAM - User {user_id} joined team {team_id}")

        except Exception as e:
            print(f"❌ JOIN TEAM ERROR: {str(e)}")
            import traceback

            print(f"❌ TRACEBACK: {traceback.format_exc()}")
            emit("team_join_error", {"error": "Failed to join team"})

    @staticmethod
    @socketio.on("collection_delete")
    def handle_collection_delete(data):
        """Handle real-time collection deletion"""
        try:
            print(f"🎯 COLLECTION DELETE - Received data: {data}")

            if not current_user.is_authenticated:
                print("❌ COLLECTION DELETE - User not authenticated")
                emit("error", {"message": "Authentication required"})
                return

            collection_id = data.get("collection_id")
            action = data.get("action", "move_to_parent")

            print(f"🎯 COLLECTION DELETE - ID: {collection_id}, Action: {action}")

            # Handle UUID string format
            if isinstance(collection_id, str):
                try:
                    import uuid

                    uuid.UUID(collection_id)
                    print(f"✅ Valid UUID format: {collection_id}")
                except ValueError:
                    print(f"❌ Invalid UUID format: {collection_id}")
                    emit("error", {"message": "Invalid collection ID format"})
                    return

            # Query collection (without is_deleted filter since it might not exist)
            collection = Collection.query.filter_by(
                id=collection_id, user_id=current_user.id
            ).first()

            if not collection:
                print(f"❌ COLLECTION DELETE - Collection not found: {collection_id}")
                print(f"🔍 DEBUG - User ID: {current_user.id}")
                emit("error", {"message": "Collection not found or access denied"})
                return

            print(f"✅ COLLECTION DELETE - Found collection: {collection.name}")

            # Handle child collections and snippets (without is_deleted filter)
            child_collections = Collection.query.filter_by(
                parent_id=collection_id
            ).all()
            snippets = Snippet.query.filter_by(collection_id=collection_id).all()

            print(
                f"🎯 COLLECTION DELETE - Found {len(child_collections)} children, {len(snippets)} snippets"
            )

            if action == "move_to_parent":
                for child in child_collections:
                    child.parent_id = collection.parent_id
                    print(f"📁 Moved child collection: {child.name}")
                for snippet in snippets:
                    snippet.collection_id = collection.parent_id
                    print(f"📄 Moved snippet: {snippet.title}")

            elif action == "delete_all":
                # Check if models have is_deleted field, if not, delete permanently
                for child in child_collections:
                    if hasattr(child, "is_deleted"):
                        child.is_deleted = True
                        child.deleted_at = datetime.utcnow()
                        print(f"🗑️ Marked child collection for deletion: {child.name}")
                    else:
                        db.session.delete(child)
                        print(f"🗑️ Permanently deleted child collection: {child.name}")

                for snippet in snippets:
                    if hasattr(snippet, "is_deleted"):
                        snippet.is_deleted = True
                        snippet.deleted_at = datetime.utcnow()
                        print(f"🗑️ Marked snippet for deletion: {snippet.title}")
                    else:
                        db.session.delete(snippet)
                        print(f"🗑️ Permanently deleted snippet: {snippet.title}")

            # Delete the main collection
            if hasattr(collection, "is_deleted"):
                collection.is_deleted = True
                collection.deleted_at = datetime.utcnow()
                print(f"✅ Marked collection for deletion: {collection.name}")
            else:
                db.session.delete(collection)
                print(f"✅ Permanently deleted collection: {collection.name}")

            # Commit all changes
            db.session.commit()
            print(
                f"✅ COLLECTION DELETED SUCCESSFULLY - ID: {collection.id}, Name: {collection.name}"
            )

            # Emit success response
            emit(
                "collection_deleted",
                {
                    "collection_id": str(collection.id),
                    "collection_name": collection.name,
                    "action_taken": action,
                    "message": f"Collection '{collection.name}' deleted successfully",
                },
            )

        except Exception as e:
            db.session.rollback()
            print(f"❌ COLLECTION DELETE ERROR: {str(e)}")
            import traceback

            print(f"❌ FULL TRACEBACK: {traceback.format_exc()}")
            emit("error", {"message": f"Failed to delete collection: {str(e)}"})

    # ADD THESE NEW HANDLERS TO handlers.py

    @staticmethod
    @socketio.on("team_snippet_update")
    def handle_team_snippet_update(data):
        """Handle team snippet updates"""
        try:
            snippet_id = data.get("snippet_id")
            team_id = data.get("team_id")
            user_id = data.get("user_id")

            print(f"🔄 TEAM SNIPPET UPDATE - Snippet: {snippet_id}, Team: {team_id}")

            # Verify permissions
            membership = TeamMember.query.filter_by(
                team_id=team_id, user_id=user_id, is_active=True
            ).first()

            if not membership or not membership.can("edit", "snippets"):
                emit("team_update_error", {"error": "Insufficient permissions"})
                return

            # Broadcast to team
            emit(
                "team_snippet_updated",
                {
                    "snippet_id": snippet_id,
                    "updated_by": user_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "changes": data.get("changes", {}),
                },
                room=f"team_{team_id}",
            )

            print(f"✅ Team snippet update broadcasted to team_{team_id}")

        except Exception as e:
            print(f"❌ TEAM SNIPPET UPDATE ERROR: {str(e)}")
            emit("team_update_error", {"error": "Failed to update team snippet"})

    # =============================================
    # COLLABORATIVE EDITING EVENTS
    # =============================================

    @staticmethod
    @socketio.on("join_snippet_edit")
    def handle_join_snippet_edit(data):
        """User joins collaborative editing session for a snippet"""
        snippet_id = data.get("snippet_id")
        snippet = Snippet.query.get(snippet_id)

        if not snippet:
            emit("error", {"message": "Snippet not found"})
            return

        # Check permissions
        can_edit = snippet.user_id == current_user.id or (
            snippet.collection
            and snippet.collection.team_id
            and TeamMember.query.filter_by(
                user_id=current_user.id,
                team_id=snippet.collection.team_id,
                role="admin",
            ).first()
            or TeamMember.query.filter_by(
                user_id=current_user.id,
                team_id=snippet.collection.team_id,
                role="editor",
            ).first()
        )

        if not can_edit:
            emit("error", {"message": "Permission denied"})
            return

        # Join snippet editing room
        room_name = f"snippet_edit_{snippet_id}"
        join_room(room_name)

        # Notify all editors about new collaborator
        emit(
            "editor_joined",
            {
                "user_id": current_user.id,
                "username": current_user.username,
                "snippet_id": snippet_id,
            },
            room=room_name,
        )

        # Send current snippet content to new editor
        emit(
            "snippet_content",
            {
                "content": snippet.code,  # Changed from snippet.content to snippet.code
                "language": snippet.language,
                "last_modified": (
                    snippet.updated_at.isoformat() if snippet.updated_at else None
                ),
            },
        )

    @staticmethod
    @socketio.on("leave_snippet_edit")
    def handle_leave_snippet_edit(data):
        """User leaves collaborative editing session"""
        snippet_id = data.get("snippet_id")
        room_name = f"snippet_edit_{snippet_id}"

        # Notify other editors
        emit(
            "editor_left",
            {
                "user_id": current_user.id,
                "username": current_user.username,
                "snippet_id": snippet_id,
            },
            room=room_name,
        )

        leave_room(room_name)

    @staticmethod
    @socketio.on("snippet_content_change")
    def handle_snippet_content_change(data):
        """Handle real-time content changes during collaborative editing"""
        snippet_id = data.get("snippet_id")
        changes = data.get("changes")  # Array of change operations
        cursor_position = data.get("cursor_position", 0)

        snippet = Snippet.query.get(snippet_id)
        if not snippet:
            return

        # Broadcast changes to other editors (exclude sender)
        emit(
            "content_changed",
            {
                "snippet_id": snippet_id,
                "changes": changes,
                "user_id": current_user.id,
                "username": current_user.username,
                "cursor_position": cursor_position,
                "timestamp": datetime.utcnow().isoformat(),
            },
            room=f"snippet_edit_{snippet_id}",
            include_self=True,
        )

    # ADD THESE 3 METHODS TO YOUR EXISTING WebSocketHandlers CLASS (around line 1200)

    @staticmethod
    @socketio.on("team_invite_member")
    def handle_team_invite_member(data):
        """Handle team member invitation via WebSocket"""
        try:
            team_id = data.get("team_id")
            email = data.get("email", "").strip().lower()
            role = data.get("role", "member")
            user_id = data.get("user_id")

            print(f"🎯 WS INVITE: {email} to team {team_id}")

            if not all([team_id, email, user_id]):
                emit("team_invite_error", {"error": "Missing required fields"})
                return

            from app.services.collaboration_service import collaboration_service

            result = collaboration_service.invite_member(team_id, user_id, email, role)

            # Broadcast to team members
            emit(
                "member_invited",
                {
                    "team_id": team_id,
                    "email": email,
                    "role": role,
                    "invitation_id": result["invitation_id"],
                },
                room=f"team_{team_id}",
            )

            emit("team_invite_success", result)
            print(f"✅ WS INVITE: Success")

        except Exception as e:
            print(f"❌ WS INVITE ERROR: {str(e)}")
            emit("team_invite_error", {"error": str(e)})

    @staticmethod
    @socketio.on("team_accept_invitation")
    def handle_team_accept_invitation(data):
        """Handle invitation acceptance via WebSocket"""
        try:
            token = data.get("token")
            user_id = data.get("user_id")

            print(f"🎯 WS ACCEPT: Token {token[:8]}...")

            if not token or not user_id:
                emit("team_accept_error", {"error": "Missing token or user ID"})
                return

            from app.services.collaboration_service import collaboration_service

            result = collaboration_service.accept_invitation(token, user_id)

            # Join user to team room
            team_room = f"team_{result['team_id']}"
            join_room(team_room)

            # Broadcast to team
            emit(
                "member_joined",
                {
                    "team_id": result["team_id"],
                    "user_id": user_id,
                    "role": result["role"],
                },
                room=team_room,
            )

            emit("team_accept_success", result)
            print(f"✅ WS ACCEPT: Success")

        except Exception as e:
            print(f"❌ WS ACCEPT ERROR: {str(e)}")
            emit("team_accept_error", {"error": str(e)})

    @staticmethod
    @socketio.on("team_get_pending_invitations")
    def handle_get_pending_invitations(data):
        """Get pending invitations via WebSocket"""
        try:
            team_id = data.get("team_id")
            user_id = data.get("user_id")

            print(f"🎯 WS PENDING: Getting invitations for team {team_id}")

            if not team_id or not user_id:
                emit("team_pending_error", {"error": "Missing team ID or user ID"})
                return

            # Check permissions
            from app.models.team_member import TeamMember

            member = TeamMember.query.filter_by(
                team_id=team_id, user_id=user_id, is_active=True
            ).first()

            if not member or not member.can_invite():
                emit("team_pending_error", {"error": "Insufficient permissions"})
                return

            from app.services.collaboration_service import collaboration_service

            invitations = collaboration_service.get_pending_invitations(team_id)

            emit(
                "team_pending_invitations",
                {
                    "team_id": team_id,
                    "invitations": invitations,
                    "count": len(invitations),
                },
            )

            print(f"✅ WS PENDING: Found {len(invitations)} invitations")

        except Exception as e:
            print(f"❌ WS PENDING ERROR: {str(e)}")
            emit("team_pending_error", {"error": str(e)})

    # ===== PHASE 3C: REAL-TIME COLLABORATION HANDLERS =====
    @staticmethod
    @socketio.on("join_editing_session")
    def handle_join_editing_session(data):
        """Join real-time collaborative editing session"""
        try:
            snippet_id = data.get("snippet_id")
            team_id = data.get("team_id")
            user_id = data.get("user_id")

            print(
                f"🤝 JOIN_EDITING: User {user_id} joining snippet {snippet_id} in team {team_id}"
            )
            print(f"🔍 REQUEST SID: {request.sid}")

            if not all([snippet_id, team_id, user_id]):
                print("❌ JOIN_EDITING: Missing required fields")
                emit("editing_session_error", {"error": "Missing required fields"})
                return

            # Verify team membership
            member_check = db.session.execute(
                text(
                    "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
                ),
                {"team_id": team_id, "user_id": str(user_id)},
            ).first()

            if not member_check:
                print("❌ JOIN_EDITING: Not a team member")
                emit("editing_session_error", {"error": "Not a team member"})
                return

            print(f"✅ JOIN_EDITING: User verified as team member")

            # Join editing room FIRST
            editing_room = f"editing_{snippet_id}"
            join_room(editing_room)
            print(f"✅ JOIN_EDITING: User joined room: {editing_room}")

            # Get user info
            user = User.query.get(user_id)
            if not user:
                print(f"❌ JOIN_EDITING: User not found: {user_id}")
                emit("editing_session_error", {"error": "User not found"})
                return

            # Generate user color
            user_colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7"]
            user_color_index = hash(str(user_id)) % len(user_colors)
            user_color = user_colors[user_color_index]
            username = (
                user.username or user.email.split("@")[0]
                if user.email
                else f"User_{user_id}"
            )

            # ✅ FIX: Get existing users BEFORE adding new user
            existing_users = get_session_users(snippet_id)
            print(f"📊 Existing users in session: {len(existing_users)}")

            # ✅ FIX: Send existing users to new joiner
            for existing_user_id, user_data in existing_users.items():
                print(f"📤 Sending existing user {user_data['username']} to new joiner")
                emit(
                    "user_joined_editing",
                    {
                        "user_id": existing_user_id,
                        "username": user_data["username"],
                        "color": user_data["color"],
                        "snippet_id": snippet_id,
                        "timestamp": user_data["joined_at"],
                    },
                )

            # ✅ FIX: Add new user to session tracking
            add_user_to_session(snippet_id, user_id, username, user_color, request.sid)

            # ✅ FIX: Broadcast new user to ALL users in room (including existing ones)
            emit(
                "user_joined_editing",
                {
                    "user_id": user_id,
                    "username": username,
                    "color": user_color,
                    "snippet_id": snippet_id,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                room=editing_room,
                include_self=True,
            )

            # Send current snippet content to new user
            snippet = Snippet.query.get(snippet_id)
            if snippet:
                emit(
                    "snippet_content_sync",
                    {
                        "snippet_id": snippet_id,
                        "content": snippet.code,
                        "language": snippet.language,
                        "title": snippet.title,
                    },
                )

            # Confirm joining to user
            emit(
                "editing_session_joined",
                {
                    "snippet_id": snippet_id,
                    "room": editing_room,
                    "user_color": user_color,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            print(
                f"✅ JOIN_EDITING: User {user_id} successfully joined editing session"
            )

        except Exception as e:
            print(f"❌ JOIN_EDITING ERROR: {str(e)}")
            import traceback

            print(f"❌ TRACEBACK: {traceback.format_exc()}")
            emit("editing_session_error", {"error": str(e)})

    @staticmethod
    @socketio.on("live_code_change")
    def handle_live_code_change(data):
        """Handle real-time code changes"""
        try:
            snippet_id = data.get("snippet_id")
            user_id = data.get("user_id")
            changes = data.get("changes")
            cursor_position = data.get("cursor_position", 0)

            print(f"⌨️ LIVE_CHANGE: User {user_id} editing snippet {snippet_id}")

            if not all([snippet_id, user_id, changes]):
                print("❌ LIVE_CHANGE: Missing required fields")
                return

            # Get user info
            # Get user info
            user = User.query.get(user_id)
            if not user:
                return

            # ✅ FIXED: Get proper username with safety check
            username = (
                user.username or user.email.split("@")[0]
                if user.email
                else f"User_{user_id}"
            )

            # Generate user color
            user_colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7"]
            user_color_index = hash(str(user_id)) % len(user_colors)
            user_color = user_colors[user_color_index]

            # Broadcast to editing room
            editing_room = f"editing_{snippet_id}"
            emit(
                "live_code_updated",
                {
                    "snippet_id": snippet_id,
                    "user_id": user_id,
                    "username": username,  # ← FIXED
                    "changes": changes,
                    "cursor_position": cursor_position,
                    "user_color": user_color,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                room=editing_room,
                include_self=False,
            )

            print(f"✅ LIVE_CHANGE: Broadcasted changes to room {editing_room}")

        except Exception as e:
            print(f"❌ LIVE_CHANGE ERROR: {str(e)}")

    @staticmethod
    @socketio.on("cursor_position_change")
    def handle_cursor_position_change(data):
        """Handle real-time cursor position updates with throttling"""
        try:
            snippet_id = data.get("snippet_id")
            user_id = data.get("user_id")
            position = data.get("position", 0)
            line = data.get("line", 1)

            # ✅ ENHANCED: Input validation
            if not snippet_id or not user_id:
                return

            if not isinstance(position, (int, float)) or position < 0:
                return

            if not isinstance(line, (int, float)) or line < 1:
                line = 1

            # ✅ FIXED: Use module-level variable for throttling
            global _cursor_update_cache
            cursor_key = f"cursor_{user_id}_{snippet_id}"
            current_time = time.time()

            last_update = _cursor_update_cache.get(cursor_key, 0)

            # Only send update if 200ms have passed since last update
            if current_time - last_update < 0.2:
                return

            _cursor_update_cache[cursor_key] = current_time

            print(
                f"👆 CURSOR_MOVE: User {user_id} cursor at line {line}, pos {position}"
            )

            # Get user info with error handling
            try:
                user = User.query.get(user_id)
                if not user:
                    print(f"⚠️ User not found: {user_id}")
                    return
            except Exception as e:
                print(f"❌ Database error getting user {user_id}: {str(e)}")
                return

            user_colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7"]
            user_color_index = hash(str(user_id)) % len(user_colors)
            user_color = user_colors[user_color_index]

            username = (
                user.username or user.email.split("@")[0]
                if user and user.email
                else f"User_{user_id}"
            )

            # Broadcast cursor position
            editing_room = f"editing_{snippet_id}"
            emit(
                "cursor_position_updated",
                {
                    "snippet_id": snippet_id,
                    "user_id": user_id,
                    "username": username,
                    "position": int(position),  # ✅ ENSURE INTEGER
                    "line": int(line),  # ✅ ENSURE INTEGER
                    "color": user_color,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                room=editing_room,
                include_self=False,
            )

            # ✅ ENHANCED: Automatic cleanup with better logic
            if len(_cursor_update_cache) > 1000:
                cutoff_time = current_time - 60
                old_size = len(_cursor_update_cache)
                _cursor_update_cache = {
                    k: v for k, v in _cursor_update_cache.items() if v > cutoff_time
                }
                print(
                    f"🧹 Cursor cache cleanup: {old_size} → {len(_cursor_update_cache)} entries"
                )

        except Exception as e:
            print(f"❌ CURSOR_MOVE ERROR: {str(e)}")
            # Don't re-raise to avoid breaking the WebSocket connection

    @staticmethod
    @socketio.on("typing_indicator_change")
    def handle_typing_indicator(data):
        """Handle typing indicators with spam prevention"""
        try:
            snippet_id = data.get("snippet_id")
            user_id = data.get("user_id")
            is_typing = data.get("is_typing", False)
            line = data.get("line", 1)

            # ✅ ENHANCED: Input validation
            if not snippet_id or not user_id:
                return

            if not isinstance(is_typing, bool):
                is_typing = bool(is_typing)

            if not isinstance(line, (int, float)) or line < 1:
                line = 1

            print(
                f"⌨️ TYPING: User {user_id} {'typing' if is_typing else 'stopped'} on line {line}"
            )

            # ✅ FIXED: Use module-level variable for spam prevention
            global _typing_state_cache
            typing_key = f"typing_{user_id}_{snippet_id}"

            # Get user info with error handling
            try:
                user = User.query.get(user_id)
                if not user:
                    print(f"⚠️ User not found for typing: {user_id}")
                    return
            except Exception as e:
                print(f"❌ Database error getting user {user_id}: {str(e)}")
                return

            username = (
                user.username or user.email.split("@")[0]
                if user and user.email
                else f"User_{user_id}"
            )

            # ✅ ENHANCED: Only broadcast if typing state actually changed
            last_state = _typing_state_cache.get(typing_key)

            if last_state != is_typing:
                _typing_state_cache[typing_key] = is_typing

                # Broadcast typing status
                editing_room = f"editing_{snippet_id}"
                emit(
                    "typing_status_updated",
                    {
                        "snippet_id": snippet_id,
                        "user_id": user_id,
                        "username": username,
                        "is_typing": is_typing,
                        "line": int(line),  # ✅ ENSURE INTEGER
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                    room=editing_room,
                    include_self=False,
                )

                print(f"✅ TYPING: Broadcasted typing state change for {username}")
            else:
                print(f"🔄 TYPING: No state change for {username}, skipping broadcast")

        except Exception as e:
            print(f"❌ TYPING_INDICATOR ERROR: {str(e)}")
            # Don't re-raise to avoid breaking the WebSocket connection

    @staticmethod
    @socketio.on("leave_editing_session")
    def handle_leave_editing_session(data):
        """Leave collaborative editing session"""
        try:
            snippet_id = data.get("snippet_id")
            user_id = data.get("user_id")

            print(f"👋 LEAVE_EDITING: User {user_id} leaving snippet {snippet_id}")

            if not all([snippet_id, user_id]):
                return

            # ✅ FIX: Remove user from session tracking
            remove_user_from_session(snippet_id, user_id)

            # Leave editing room
            editing_room = f"editing_{snippet_id}"
            leave_room(editing_room)

            # Get user info
            user = User.query.get(user_id)
            username = (
                user.username or user.email.split("@")[0]
                if user and user.email
                else f"User_{user_id}"
            )

            # Notify others
            emit(
                "user_left_editing",
                {
                    "user_id": user_id,
                    "username": username,
                    "snippet_id": snippet_id,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                room=editing_room,
                include_self=False,
            )

            print(
                f"✅ LEAVE_EDITING: User {user_id} ({username}) left room {editing_room}"
            )

        except Exception as e:
            print(f"❌ LEAVE_EDITING ERROR: {str(e)}")

    @staticmethod
    @socketio.on("collaborative_comment")
    def handle_collaborative_comment(data):
        """Handle real-time comments"""
        try:
            snippet_id = data.get("snippet_id")
            user_id = data.get("user_id")
            comment = data.get("comment", "").strip()
            comment_type = data.get("comment_type", "comment")  # 'comment' or 'chat'

            print(
                f"💬 COMMENT: User {user_id} added {comment_type} to snippet {snippet_id}"
            )

            if not all([snippet_id, user_id, comment]):
                emit("comment_error", {"error": "Missing required fields"})
                return

            # Get user info
            user = User.query.get(user_id)
            if not user:
                emit("comment_error", {"error": "User not found"})
                return

            # ✅ FIXED: Get proper username
            username = (
                user.username or user.email.split("@")[0]
                if user.email
                else f"User_{user_id}"
            )

            # Broadcast comment
            editing_room = f"editing_{snippet_id}"
            emit(
                "comment_added",
                {
                    "snippet_id": snippet_id,
                    "user_id": user_id,
                    "username": username,  # ✅ FIXED
                    "comment": comment,
                    "type": comment_type,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                room=editing_room,
                include_self=True,
            )

            print(f"✅ COMMENT: Broadcasted {comment_type} to room {editing_room}")

        except Exception as e:
            print(f"❌ COMMENT ERROR: {str(e)}")
            emit("comment_error", {"error": str(e)})

    @staticmethod
    @socketio.on("user_state_change")
    def handle_user_state_change(data):
        """Handle smart user state changes (typing/editing/viewing)"""
        try:
            snippet_id = data.get("snippet_id")
            user_id = data.get("user_id")
            state = data.get("state")  # typing, editing, viewing
            line = data.get("line", 1)

            print(f"🔄 STATE_CHANGE: User {user_id} is {state} on line {line}")

            if not all([snippet_id, user_id, state]):
                return

            # Get user info
            user = User.query.get(user_id)
            if not user:
                return

            username = (
                user.username or user.email.split("@")[0]
                if user and user.email
                else f"User_{user_id}"
            )

            # Broadcast state change
            editing_room = f"editing_{snippet_id}"
            emit(
                "user_state_updated",
                {
                    "snippet_id": snippet_id,
                    "user_id": user_id,
                    "username": username,
                    "state": state,
                    "line": int(line),
                    "timestamp": datetime.utcnow().isoformat(),
                },
                room=editing_room,
                include_self=False,
            )

            print(f"✅ STATE_CHANGE: Broadcasted {state} state for {username}")

        except Exception as e:
            print(f"❌ STATE_CHANGE ERROR: {str(e)}")

    @staticmethod
    @socketio.on("collaborative_snippet_save")
    def handle_collaborative_snippet_save(data):
        """Handle saving snippet during collaborative editing"""
        snippet_id = data.get("snippet_id")
        content = data.get("content")

        snippet = Snippet.query.get(snippet_id)
        if not snippet:
            emit("error", {"message": "Snippet not found"})
            return

        # Check permissions
        can_edit = snippet.user_id == current_user.id or (
            snippet.collection
            and snippet.collection.team_id
            and TeamMember.query.filter_by(
                user_id=current_user.id, team_id=snippet.collection.team_id
            )
            .filter(TeamMember.role.in_(["admin", "editor"]))
            .first()
        )

        if not can_edit:
            emit("error", {"message": "Permission denied"})
            return

        # Update snippet
        snippet.code = content  # Changed from snippet.content to snippet.code
        snippet.updated_at = datetime.utcnow()
        db.session.commit()

        # Notify all editors about save
        emit(
            "snippet_saved",
            {
                "snippet_id": snippet_id,
                "saved_by": current_user.username,
                "timestamp": snippet.updated_at.isoformat(),
                "content_length": len(content),
            },
            room=f"snippet_edit_{snippet_id}",
        )

    @staticmethod
    @socketio.on("cursor_position_update")
    def handle_cursor_update(data):
        """Handle cursor position updates during collaborative editing"""
        snippet_id = data.get("snippet_id")
        cursor_position = data.get("cursor_position", 0)
        selection_start = data.get("selection_start")
        selection_end = data.get("selection_end")

        # Broadcast cursor position to other editors
        emit(
            "cursor_position_changed",
            {
                "user_id": current_user.id,
                "username": current_user.username,
                "cursor_position": cursor_position,
                "selection_start": selection_start,
                "selection_end": selection_end,
                "snippet_id": snippet_id,
            },
            room=f"snippet_edit_{snippet_id}",
            include_self=True,
        )

    @staticmethod
    @socketio.on("team_activity")
    def handle_team_activity(data):
        """Handle team activity notifications"""
        team_id = data.get("team_id")
        activity_type = data.get("type")
        activity_data = data.get("data", {})

        # Verify user is team member
        membership = TeamMember.query.filter_by(
            user_id=current_user.id, team_id=team_id
        ).first()

        if not membership:
            emit("error", {"message": "Not a team member"})
            return

        # Broadcast activity to team
        emit(
            "team_activity_update",
            {
                "team_id": team_id,
                "type": activity_type,
                "user": {"id": current_user.id, "username": current_user.username},
                "data": activity_data,
                "timestamp": datetime.utcnow().isoformat(),
            },
            room=f"team_{team_id}",
        )

    # ===== CHAT PERSISTENCE HANDLERS =====

    @staticmethod
    @socketio.on("load_snippet_history")
    def handle_load_snippet_history(data):
        """Load chat and comment history for a snippet"""
        try:
            snippet_id = data.get("snippet_id")
            user_id = data.get("user_id")

            print(f"📚 LOAD_HISTORY: Loading history for snippet {snippet_id}")

            if not all([snippet_id, user_id]):
                emit("history_error", {"error": "Missing required fields"})
                return

            # Get comments
            comments = SnippetComment.get_snippet_comments(snippet_id)
            comments_data = [comment.to_dict() for comment in comments]

            # Get chat messages
            chats = SnippetChat.get_snippet_chats(snippet_id)
            chats_data = [chat.to_dict() for chat in chats]

            emit(
                "snippet_history_loaded",
                {
                    "snippet_id": snippet_id,
                    "comments": comments_data,
                    "chats": chats_data,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            print(
                f"✅ LOAD_HISTORY: Sent {len(comments_data)} comments, {len(chats_data)} chats"
            )

        except Exception as e:
            print(f"❌ LOAD_HISTORY ERROR: {str(e)}")
            emit("history_error", {"error": str(e)})

    @staticmethod
    @socketio.on("save_snippet_comment")
    def handle_save_snippet_comment(data):
        """Save a snippet comment to database"""
        try:
            snippet_id = data.get("snippet_id")
            user_id = data.get("user_id")
            team_id = data.get("team_id")
            content = data.get("content", "").strip()

            print(f"💬 SAVE_COMMENT: User {user_id} commenting on snippet {snippet_id}")

            if not all([snippet_id, user_id, team_id, content]):
                emit("comment_save_error", {"error": "Missing required fields"})
                return

            # Create comment
            comment = SnippetComment(
                snippet_id=snippet_id, user_id=user_id, team_id=team_id, content=content
            )

            db.session.add(comment)
            db.session.commit()

            # Broadcast to editing room
            editing_room = f"editing_{snippet_id}"
            emit(
                "comment_saved",
                {"comment": comment.to_dict(), "snippet_id": snippet_id},
                room=editing_room,
                include_self=True,
            )

            print(f"✅ SAVE_COMMENT: Comment saved and broadcasted")

            # ADD ACTIVITY LOGGING
            Activity.log_activity(
                action_type="comment_added",
                user_id=user_id,
                description=f"Added comment to snippet",
                team_id=team_id,
                target_type="snippet",
                target_id=snippet_id,
                metadata={"comment_length": len(content)},
            )

        except Exception as e:
            db.session.rollback()
            print(f"❌ SAVE_COMMENT ERROR: {str(e)}")
            emit("comment_save_error", {"error": str(e)})

    @staticmethod
    @socketio.on("save_snippet_chat")
    def handle_save_snippet_chat(data):
        """Save a snippet chat message to database"""
        try:
            snippet_id = data.get("snippet_id")
            user_id = data.get("user_id")
            team_id = data.get("team_id")
            message = data.get("message", "").strip()

            print(f"💭 SAVE_CHAT: User {user_id} chatting on snippet {snippet_id}")

            if not all([snippet_id, user_id, team_id, message]):
                emit("chat_save_error", {"error": "Missing required fields"})
                return

            # Create chat message
            chat = SnippetChat(
                snippet_id=snippet_id, user_id=user_id, team_id=team_id, message=message
            )

            db.session.add(chat)
            db.session.commit()

            # Broadcast to editing room
            editing_room = f"editing_{snippet_id}"
            emit(
                "chat_saved",
                {"chat": chat.to_dict(), "snippet_id": snippet_id},
                room=editing_room,
                include_self=True,
            )

            print(f"✅ SAVE_CHAT: Chat message saved and broadcasted")

        except Exception as e:
            db.session.rollback()
            print(f"❌ SAVE_CHAT ERROR: {str(e)}")
            emit("chat_save_error", {"error": str(e)})

    @staticmethod
    @socketio.on("clear_snippet_comments")
    def handle_clear_snippet_comments(data):
        """Clear all comments for a snippet (Admin/Owner only)"""
        try:
            snippet_id = data.get("snippet_id")
            user_id = data.get("user_id")
            team_id = data.get("team_id")

            print(
                f"🧹 CLEAR_COMMENTS: User {user_id} clearing comments for snippet {snippet_id}"
            )

            if not all([snippet_id, user_id, team_id]):
                emit("clear_error", {"error": "Missing required fields"})
                return

            # Check permissions (Owner or Admin only)
            member_check = db.session.execute(
                text(
                    "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
                ),
                {"team_id": team_id, "user_id": str(user_id)},
            ).first()

            if not member_check or member_check.role not in ["OWNER", "ADMIN"]:
                emit("clear_error", {"error": "Insufficient permissions"})
                return

            # Clear comments
            cleared_count = SnippetComment.clear_snippet_comments(snippet_id, user_id)

            # Broadcast to editing room
            editing_room = f"editing_{snippet_id}"
            emit(
                "comments_cleared",
                {
                    "snippet_id": snippet_id,
                    "cleared_count": cleared_count,
                    "cleared_by": user_id,
                },
                room=editing_room,
                include_self=True,
            )

            print(f"✅ CLEAR_COMMENTS: Cleared {cleared_count} comments")

        except Exception as e:
            print(f"❌ CLEAR_COMMENTS ERROR: {str(e)}")
            emit("clear_error", {"error": str(e)})

    @staticmethod
    @socketio.on("clear_snippet_chats")
    def handle_clear_snippet_chats(data):
        """Clear all chat messages for a snippet (Admin/Owner only)"""
        try:
            snippet_id = data.get("snippet_id")
            user_id = data.get("user_id")
            team_id = data.get("team_id")

            print(
                f"🧹 CLEAR_CHATS: User {user_id} clearing chats for snippet {snippet_id}"
            )

            if not all([snippet_id, user_id, team_id]):
                emit("clear_error", {"error": "Missing required fields"})
                return

            # Check permissions (Owner or Admin only)
            member_check = db.session.execute(
                text(
                    "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
                ),
                {"team_id": team_id, "user_id": str(user_id)},
            ).first()

            if not member_check or member_check.role not in ["OWNER", "ADMIN"]:
                emit("clear_error", {"error": "Insufficient permissions"})
                return

            # Clear chats
            cleared_count = SnippetChat.clear_snippet_chats(snippet_id, user_id)

            # Broadcast to editing room
            editing_room = f"editing_{snippet_id}"
            emit(
                "chats_cleared",
                {
                    "snippet_id": snippet_id,
                    "cleared_count": cleared_count,
                    "cleared_by": user_id,
                },
                room=editing_room,
                include_self=True,
            )

            print(f"✅ CLEAR_CHATS: Cleared {cleared_count} chat messages")

        except Exception as e:
            print(f"❌ CLEAR_CHATS ERROR: {str(e)}")
            emit("clear_error", {"error": str(e)})

        # ===== TEAM CHAT WEBSOCKET HANDLERS =====

    # ===== IMPROVED TEAM CHAT WEBSOCKET HANDLERS =====

    @staticmethod
    @socketio.on("clear_team_chat")
    def handle_clear_team_chat(data):
        """Clear team chat messages - IMPROVED VERSION"""
        try:
            team_id = data.get("team_id")
            user_id = data.get("user_id")

            print(f"🧹 CLEAR_TEAM_CHAT: User {user_id} clearing team {team_id} chat")
            print(f"🔧 CLEAR_CHAT: Data received: {data}")
            print(f"🔧 CLEAR_CHAT: team_id type: {type(team_id)}, value: {team_id}")
            print(f"🔧 CLEAR_CHAT: user_id type: {type(user_id)}, value: {user_id}")

            if not all([team_id, user_id]):
                print(
                    f"❌ CLEAR_CHAT: Missing required fields - team_id: {team_id}, user_id: {user_id}"
                )
                emit("team_chat_error", {"error": "Missing required fields"})
                return

            # ✅ FIX: Ensure proper string format for database query
            team_id = str(team_id)
            user_id = str(user_id)
            print(
                f"🔧 CLEAR_CHAT: Normalized IDs - team_id: {team_id}, user_id: {user_id}"
            )

            # Check permissions (Owner or Admin only)
            # ✅ FIX: Enhanced permission check with debugging
            print(
                f"🔧 CLEAR_CHAT: Checking permissions for user {user_id} in team {team_id}"
            )

            member_check = db.session.execute(
                text(
                    "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
                ),
                {"team_id": team_id, "user_id": str(user_id)},
            ).first()

            print(f"🔧 CLEAR_CHAT: Member check result: {member_check}")
            if member_check:
                print(f"🔧 CLEAR_CHAT: User role: {member_check.role}")

            # ✅ FIX: Case-insensitive role check
            if not member_check:
                print(f"❌ CLEAR_CHAT: User not found in team members")
                emit("team_chat_error", {"error": "Not a team member"})
                return

            user_role = member_check.role.upper() if member_check.role else ""
            print(f"🔧 CLEAR_CHAT: Normalized role: {user_role}")

            if user_role not in ["OWNER", "ADMIN"]:
                print(f"❌ CLEAR_CHAT: Role '{member_check.role}' not in allowed roles")
                emit("team_chat_error", {"error": "Insufficient permissions"})
                return

            print(f"✅ CLEAR_CHAT: Permission granted for role: {user_role}")

            # Clear chat messages
            from app.models.team_chat import TeamChat

            cleared_count = TeamChat.clear_team_chats(team_id, user_id)

            # Broadcast to team chat room - SAME FORMAT AS SNIPPET EDITOR
            # ✅ FIX: Get user info and role for proper display
            user = User.query.get(user_id)
            username = (
                user.username or user.email.split("@")[0]
                if user and user.email
                else f"User_{user_id}"
            )

            # ✅ FIX: Get user's actual role in this team
            user_role = (
                member_check.role
            )  # We already have this from the permission check above

            # Broadcast to team chat room with role information
            chat_room = f"team_chat_{team_id}"
            emit(
                "team_chat_cleared",
                {
                    "team_id": team_id,
                    "cleared_count": cleared_count,
                    "cleared_by": user_id,
                    "cleared_by_username": username,
                    "cleared_by_role": user_role,  # ✅ FIX: Add role information
                    "timestamp": datetime.utcnow().isoformat(),
                },
                room=chat_room,
                include_self=True,
            )
            print(f"✅ CLEAR_TEAM_CHAT: Cleared {cleared_count} messages")

            # ADD ACTIVITY LOGGING
            Activity.log_activity(
                action_type="chat_cleared",
                user_id=user_id,
                description=f"Cleared team chat ({cleared_count} messages)",
                team_id=team_id,
                target_type="chat",
                metadata={"cleared_count": cleared_count, "cleared_by_role": user_role},
                importance_score=3,
            )

        except Exception as e:
            print(f"❌ CLEAR_TEAM_CHAT ERROR: {str(e)}")
            emit("team_chat_error", {"error": str(e)})

    @staticmethod
    @socketio.on("force_leave_team_chat")
    def handle_force_leave_team_chat(data):
        """Force leave team chat (for browser navigation, tab close, etc.)"""
        try:
            team_id = data.get("team_id")
            user_id = data.get("user_id")
            reason = data.get("reason", "force_leave")

            print(
                f"🚨 FORCE_LEAVE_TEAM_CHAT: User {user_id} force leaving team {team_id} - Reason: {reason}"
            )

            if not all([team_id, user_id]):
                return

            # Get user info
            user = User.query.get(user_id)
            username = (
                user.username or user.email.split("@")[0]
                if user and user.email
                else f"User_{user_id}"
            )

            # Notify team immediately
            chat_room = f"team_chat_{team_id}"
            emit(
                "user_left_team_chat",
                {
                    "user_id": user_id,
                    "username": username,
                    "team_id": team_id,
                    "reason": reason,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                room=chat_room,
                include_self=False,
            )

            # Leave room
            leave_room(chat_room)

            print(f"✅ FORCE_LEAVE_TEAM_CHAT: User {username} force left team chat")

        except Exception as e:
            print(f"❌ FORCE_LEAVE_TEAM_CHAT ERROR: {str(e)}")

    @staticmethod
    @socketio.on("edit_team_chat_message")
    def handle_edit_team_chat_message(data):
        """Edit team chat message via WebSocket"""
        try:
            team_id = data.get("team_id")
            user_id = data.get("user_id")
            message_id = data.get("message_id")
            new_message = data.get("message", "").strip()

            print(f"✏️ EDIT_TEAM_CHAT: User {user_id} editing message {message_id}")

            if not all([team_id, user_id, message_id, new_message]):
                emit("team_chat_error", {"error": "Missing required fields"})
                return

            # Verify team membership
            member_check = db.session.execute(
                text(
                    "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
                ),
                {"team_id": team_id, "user_id": str(user_id)},
            ).first()

            if not member_check:
                emit("team_chat_error", {"error": "Not a team member"})
                return

            # Get and edit the message
            from app.models.team_chat import TeamChat

            chat = TeamChat.query.filter_by(
                id=message_id, team_id=team_id, is_deleted=False
            ).first()

            if not chat:
                emit("team_chat_error", {"error": "Message not found"})
                return

            if chat.edit_message(new_message, user_id):
                # Broadcast edit to team chat room
                chat_room = f"team_chat_{team_id}"
                emit(
                    "team_chat_message_edited",
                    {
                        "chat": chat.to_dict(),
                        "team_id": team_id,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                    room=chat_room,
                    include_self=True,
                )

                print(f"✅ EDIT_TEAM_CHAT: Message edited successfully")
            else:
                emit("team_chat_error", {"error": "Cannot edit this message"})

        except Exception as e:
            print(f"❌ EDIT_TEAM_CHAT ERROR: {str(e)}")
            emit("team_chat_error", {"error": str(e)})

    @staticmethod
    @socketio.on("leave_team")
    def handle_leave_team(data):
        """Handle user leaving team via WebSocket"""
        try:
            team_id = data.get("team_id")
            user_id = data.get("user_id")

            print(f"🚪 WS_LEAVE_TEAM: User {user_id} leaving team {team_id}")

            if not all([team_id, user_id]):
                emit("leave_team_error", {"error": "Missing required fields"})
                return

            # Call the leave team logic (you can extract it to a service)
            # For now, emit success
            emit("leave_team_success", {
                "team_id": team_id,
                "message": "Successfully left team"
            })

            # Broadcast to team
            emit("member_left_team", {
                "user_id": user_id,
                "team_id": team_id,
                "timestamp": datetime.utcnow().isoformat()
            }, room=f"team_{team_id}")

            print(f"✅ WS_LEAVE_TEAM: User {user_id} left team successfully")

        except Exception as e:
            print(f"❌ WS_LEAVE_TEAM ERROR: {str(e)}")
            emit("leave_team_error", {"error": str(e)})

    @staticmethod
    @socketio.on("delete_team_chat_message")
    def handle_delete_team_chat_message(data):
        """Delete team chat message via WebSocket"""
        try:
            team_id = data.get("team_id")
            user_id = data.get("user_id")
            message_id = data.get("message_id")

            print(f"🗑️ DELETE_TEAM_CHAT: User {user_id} deleting message {message_id}")

            if not all([team_id, user_id, message_id]):
                emit("team_chat_error", {"error": "Missing required fields"})
                return

            # Verify team membership
            member_check = db.session.execute(
                text(
                    "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
                ),
                {"team_id": team_id, "user_id": str(user_id)},
            ).first()

            if not member_check:
                emit("team_chat_error", {"error": "Not a team member"})
                return

            # Get the message
            from app.models.team_chat import TeamChat

            chat = TeamChat.query.filter_by(
                id=message_id, team_id=team_id, is_deleted=False
            ).first()

            if not chat:
                emit("team_chat_error", {"error": "Message not found"})
                return

            # Check if user can delete (author or admin/owner)
            can_delete = str(chat.user_id) == str(user_id) or member_check.role in [
                "OWNER",
                "ADMIN",
            ]

            if not can_delete:
                emit("team_chat_error", {"error": "Cannot delete this message"})
                return

            if chat.soft_delete(user_id):
                # Broadcast deletion to team chat room
                chat_room = f"team_chat_{team_id}"
                emit(
                    "team_chat_message_deleted",
                    {
                        "message_id": message_id,
                        "team_id": team_id,
                        "deleted_by": user_id,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                    room=chat_room,
                    include_self=True,
                )

                print(f"✅ DELETE_TEAM_CHAT: Message deleted successfully")
            else:
                emit("team_chat_error", {"error": "Failed to delete message"})

        except Exception as e:
            print(f"❌ DELETE_TEAM_CHAT ERROR: {str(e)}")
            emit("team_chat_error", {"error": str(e)})

    @staticmethod
    @socketio.on("error")
    def handle_error(error):
        """Handle WebSocket errors"""
        print(f"WebSocket error: {error}")
        emit("error", {"message": "WebSocket connection error"})


# Register all handlers
def register_websocket_handlers(socketio, db, app):
    """Register all WebSocket event handlers"""

    # Register authentication handlers
    socketio.on_event("register", handle_register)
    socketio.on_event("login", handle_login)

    # Register other handlers
    # FIXED: Direct registration instead of on_event
    @socketio.on("save_snippet")
    def handle_snippet_save_wrapper(data):
        """Wrapper to ensure the handler is properly called"""
        print(f"🔥 WRAPPER CALLED - Data received: {data}")
        return WebSocketHandlers.handle_snippet_save(data)

    socketio.on_event("snippet_update", WebSocketHandlers.handle_snippet_update)
    socketio.on_event("snippet_delete", WebSocketHandlers.handle_snippet_delete)
    socketio.on_event("collection_create", WebSocketHandlers.handle_collection_create)
    socketio.on_event("collection_delete", WebSocketHandlers.handle_collection_delete)
    socketio.on_event("sync_request", WebSocketHandlers.handle_sync_request)
    socketio.on_event("heartbeat", WebSocketHandlers.handle_heartbeat)

    # Collaborative editing handlers
    socketio.on_event("join_snippet_edit", WebSocketHandlers.handle_join_snippet_edit)
    socketio.on_event("leave_snippet_edit", WebSocketHandlers.handle_leave_snippet_edit)
    socketio.on_event(
        "snippet_content_change", WebSocketHandlers.handle_snippet_content_change
    )
    socketio.on_event(
        "collaborative_snippet_save",
        WebSocketHandlers.handle_collaborative_snippet_save,
    )
    socketio.on_event("cursor_position_update", WebSocketHandlers.handle_cursor_update)
    socketio.on_event("team_activity", WebSocketHandlers.handle_team_activity)
    socketio.on_event("typing_indicator", WebSocketHandlers.handle_typing_indicator)

    # ===== PHASE 3C: REAL-TIME COLLABORATION REGISTRATIONS ===== ⬅️ ADD THIS
    socketio.on_event(
        "join_editing_session", WebSocketHandlers.handle_join_editing_session
    )
    socketio.on_event("live_code_change", WebSocketHandlers.handle_live_code_change)
    socketio.on_event(
        "cursor_position_change", WebSocketHandlers.handle_cursor_position_change
    )
    socketio.on_event(
        "typing_indicator_change", WebSocketHandlers.handle_typing_indicator
    )
    socketio.on_event(
        "leave_editing_session", WebSocketHandlers.handle_leave_editing_session
    )
    socketio.on_event(
        "collaborative_comment", WebSocketHandlers.handle_collaborative_comment
    )
    # Add this line in the registration section:
    socketio.on_event("user_state_change", WebSocketHandlers.handle_user_state_change)
    # ===== CHAT PERSISTENCE REGISTRATIONS =====
    socketio.on_event(
        "load_snippet_history", WebSocketHandlers.handle_load_snippet_history
    )
    socketio.on_event(
        "save_snippet_comment", WebSocketHandlers.handle_save_snippet_comment
    )
    socketio.on_event("save_snippet_chat", WebSocketHandlers.handle_save_snippet_chat)
    socketio.on_event(
        "clear_snippet_comments", WebSocketHandlers.handle_clear_snippet_comments
    )
    socketio.on_event(
        "clear_snippet_chats", WebSocketHandlers.handle_clear_snippet_chats
    )

    # team chat hanlder

    # ===== TEAM CHAT REGISTRATIONS =====

    
  


    # Store app reference for handlers that need it
    socketio.app = app

    logger.info("✅ WebSocket handlers registered successfully")

    # Debug logging for registered events
    if app.debug:
        events = [
            "register",
            "login",
            "snippet_save",
            "snippet_update",
            "snippet_delete",
            "collection_create",
            "sync_request",
            "heartbeat",
            "join_snippet_edit",
            "leave_snippet_edit",
            "snippet_content_change",
            "collaborative_snippet_save",
            "cursor_position_update",
            "team_activity",
            "typing_indicator",
            "join_editing_session",
            "live_code_change",
            "cursor_position_change",
            "typing_indicator_change",
            "leave_editing_session",
            "collaborative_comment",
        ]
        logger.info(f"🔌 Registered WebSocket events: {', '.join(events)}")

    return True


# Export functions for external imports
# Export functions for external imports
handle_snippet_save = WebSocketHandlers.handle_snippet_save
handle_snippet_update = WebSocketHandlers.handle_snippet_update
handle_snippet_delete = WebSocketHandlers.handle_snippet_delete
handle_snippet_created = WebSocketHandlers.handle_snippet_created
handle_collection_create = WebSocketHandlers.handle_collection_create

handle_sync_request = WebSocketHandlers.handle_sync_request
handle_join_snippet_edit = WebSocketHandlers.handle_join_snippet_edit
handle_leave_snippet_edit = WebSocketHandlers.handle_leave_snippet_edit
handle_snippet_content_change = WebSocketHandlers.handle_snippet_content_change
handle_collaborative_snippet_save = WebSocketHandlers.handle_collaborative_snippet_save
handle_cursor_update = WebSocketHandlers.handle_cursor_update
handle_team_activity = WebSocketHandlers.handle_team_activity
handle_typing_indicator = WebSocketHandlers.handle_typing_indicator
