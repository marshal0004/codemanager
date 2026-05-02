# flask-server/app/websocket/team_chat_namespace.py
from flask_socketio import Namespace, emit, join_room, leave_room
from flask import request
from datetime import datetime
from app.models.user import User
from app.models.team_chat import TeamChat  # ✅ USE YOUR EXISTING MODEL
from app import db
from sqlalchemy import text

# ✅ SEPARATE SESSION TRACKING FOR TEAM CHAT ONLY
team_chat_sessions = {}


class TeamChatNamespace(Namespace):
    def on_connect(self, auth):
        print(f"🔌 TEAM_CHAT_SOCKET: Connected: {request.sid}")

    def on_disconnect(self, auth=None):
        """Enhanced disconnect with immediate broadcast and error handling"""
        print(f"🚨 TEAM_CHAT_SOCKET: Disconnected: {request.sid}")
        
        try:
            # ✅ IMMEDIATE cleanup with broadcast
            if request.sid in team_chat_sessions:
                user_data = team_chat_sessions[request.sid]
                user_id = user_data.get('user_id')
                team_id = user_data.get('team_id')
                username = user_data.get('username')
                
                print(f"🔧 DISCONNECT: Processing user {username} (ID: {user_id}) from team {team_id}")
                
                # ✅ REMOVE IMMEDIATELY
                del team_chat_sessions[request.sid]
                print(f"✅ IMMEDIATE_CLEANUP: Removed {username} from sessions")
                print(f"✅ SESSIONS_REMAINING: {len(team_chat_sessions)} total sessions")
                
                # ✅ BROADCAST TO ALL CONNECTIONS IMMEDIATELY
                if team_id and user_id and username:
                    disconnect_data = {
                        'user_id': user_id,
                        'username': username,
                        'team_id': team_id,
                        'reason': 'socket_disconnect',
                        'immediate': True,
                        'timestamp': datetime.utcnow().isoformat(),
                        'session_id': request.sid
                    }
                    
                    # Emit to team chat room
                    try:
                        self.emit('user_left_team_chat', disconnect_data, room=f"team_chat_{team_id}")
                        print(f"✅ TEAM_CHAT_EMIT: Sent user_left_team_chat to room team_chat_{team_id}")
                    except Exception as emit_error:
                        print(f"❌ TEAM_CHAT_EMIT_ERROR: {str(emit_error)}")
                    
                    # ✅ ENHANCED: Also emit to main WebSocket namespace with error handling
                    try:
                        from app import socketio
                        socketio.emit('user_left_team_chat_broadcast', {
                            'user_id': user_id,
                            'username': username,
                            'team_id': team_id,
                            'reason': 'socket_disconnect',
                            'timestamp': datetime.utcnow().isoformat()
                        }, room=f"team_{team_id}", namespace='/')
                        print(f"✅ MAIN_SOCKET_EMIT: Sent broadcast to room team_{team_id}")
                    except Exception as main_emit_error:
                        print(f"❌ MAIN_SOCKET_EMIT_ERROR: {str(main_emit_error)}")
                    
                    print(f"✅ IMMEDIATE_BROADCAST: Notified team {team_id} about {username} leaving")
                else:
                    print(f"⚠️ DISCONNECT: Missing required data - team_id: {team_id}, user_id: {user_id}, username: {username}")
                    
            else:
                print(f"⚠️ DISCONNECT: Session {request.sid} not found in team_chat_sessions")
                print(f"🔍 CURRENT_SESSIONS: {list(team_chat_sessions.keys())}")
                
                # ✅ ENHANCED: Try to find and clean up any orphaned sessions for safety
                orphaned_sessions = []
                for sid, session_data in team_chat_sessions.items():
                    if not hasattr(session_data, 'get') or not session_data.get('user_id'):
                        orphaned_sessions.append(sid)
                
                for orphaned_sid in orphaned_sessions:
                    del team_chat_sessions[orphaned_sid]
                    print(f"🧹 CLEANUP: Removed orphaned session {orphaned_sid}")
                    
        except Exception as disconnect_error:
            print(f"❌ DISCONNECT_ERROR: {str(disconnect_error)}")
            import traceback
            print(f"❌ DISCONNECT_TRACEBACK: {traceback.format_exc()}")
            
            # ✅ SAFETY: Try to clean up the session even if there's an error
            try:
                if request.sid in team_chat_sessions:
                    del team_chat_sessions[request.sid]
                    print(f"🛡️ SAFETY_CLEANUP: Removed session {request.sid} after error")
            except Exception as safety_error:
                print(f"❌ SAFETY_CLEANUP_ERROR: {str(safety_error)}")

    
    def on_join_team_chat(self, data):
        try:
            team_id = data.get("team_id")
            user_id = data.get("user_id")

            print(f"💬 JOIN_TEAM_CHAT: User {user_id} joining team {team_id}")

            # Verify membership
            member_check = db.session.execute(
                text(
                    "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
                ),
                {"team_id": team_id, "user_id": str(user_id)},
            ).first()

            if not member_check:
                emit("team_chat_error", {"error": "Not a team member"})
                return

            # Get user info
            user = User.query.get(user_id)
            username = (
                user.username or user.email.split("@")[0]
                if user.email
                else f"User_{user_id}"
            )

            # ✅ CLEANUP: Remove any existing sessions for this user first
            sessions_to_remove = []
            for sid, session_data in team_chat_sessions.items():
                if (session_data.get('user_id') == str(user_id) and 
                    session_data.get('team_id') == str(team_id) and
                    sid != request.sid):
                    sessions_to_remove.append(sid)

            for sid in sessions_to_remove:
                if sid in team_chat_sessions:
                    old_data = team_chat_sessions[sid]
                    del team_chat_sessions[sid]
                    print(f"✅ CLEANUP_OLD_SESSION: Removed stale session {sid} for {old_data.get('username')}")

            print(f"✅ CLEANUP_COMPLETE: Removed {len(sessions_to_remove)} stale sessions")

            # Join room
            join_room(f"team_chat_{team_id}")

            # ✅ TRACK IN SEPARATE SESSIONS
            team_chat_sessions[request.sid] = {
                "user_id": str(user_id),
                "team_id": str(team_id),
                "username": username,
                "role": member_check.role,
                "joined_at": datetime.utcnow().isoformat(),
            }

            print(f"✅ SESSION_ADDED: {username} added with SID {request.sid}")
            print(f"✅ TOTAL_SESSIONS: {len(team_chat_sessions)} active sessions")

            # ✅ GET ONLY TEAM CHAT ONLINE MEMBERS (DEDUPLICATED)
            online_members = []
            seen_users = set()
            
            for sid, session_data in team_chat_sessions.items():
                if session_data.get("team_id") == str(team_id):
                    user_id_key = session_data["user_id"]
                    
                    # ✅ DEDUPLICATE: Only add each user once
                    if user_id_key not in seen_users:
                        seen_users.add(user_id_key)
                        online_members.append({
                            "user_id": session_data["user_id"],
                            "username": session_data["username"],
                            "user_role": session_data["role"],
                        })
                        print(f"✅ ONLINE_MEMBER: Added {session_data['username']} ({session_data['role']})")
                    else:
                        print(f"⚠️ DUPLICATE_SKIPPED: {session_data['username']} already in online list")

            print(f"✅ ONLINE_MEMBERS_FINAL: {len(online_members)} unique members online")

            # ✅ USE YOUR EXISTING MODEL
            recent_chats = TeamChat.get_recent_team_chats(team_id, hours=24)
            chats_data = [chat.to_dict() for chat in recent_chats]

            # Send responses
            emit("team_chat_history", {"team_id": team_id, "chats": chats_data})
            emit(
                "team_chat_joined",
                {
                    "team_id": team_id,
                    "user_role": member_check.role,
                    "online_members": online_members,
                },
            )

            # Notify others
            emit(
                "user_joined_team_chat",
                {
                    "user_id": user_id,
                    "username": username,
                    "team_id": team_id,
                    "user_role": member_check.role,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                room=f"team_chat_{team_id}",
            )

            print(f"✅ JOIN_COMPLETE: {username} successfully joined team chat")

        except Exception as e:
            print(f"❌ JOIN ERROR: {str(e)}")
            import traceback
            print(f"❌ JOIN_TRACEBACK: {traceback.format_exc()}")
            emit("team_chat_error", {"error": str(e)})

    def on_send_team_chat_message(self, data):
        try:
            team_id = data.get("team_id")
            user_id = data.get("user_id")
            message = data.get("message", "").strip()

            # ✅ USE YOUR EXISTING MODEL
            chat = TeamChat(
                team_id=team_id, user_id=user_id, message=message, message_type="text"
            )
            db.session.add(chat)
            db.session.commit()

            # Get user info
            user = User.query.get(user_id)
            username = (
                user.username or user.email.split("@")[0]
                if user.email
                else f"User_{user_id}"
            )

            # Broadcast message
            emit(
                "team_chat_message_received",
                {
                    "team_id": team_id,
                    "chat": {
                        "id": str(chat.id),
                        "user_id": str(chat.user_id),
                        "username": username,
                        "message": chat.message,
                        "created_at": chat.created_at.isoformat() + "Z",
                        "user": {
                            "username": username,
                            "email": user.email if user else None,
                        },
                    },
                },
                room=f"team_chat_{team_id}",
            )

        except Exception as e:
            print(f"❌ SEND ERROR: {str(e)}")
            emit("team_chat_error", {"error": str(e)})

    def on_leave_team_chat(self, data):
        try:
            team_id = data.get("team_id")
            user_id = data.get("user_id")

            if request.sid in team_chat_sessions:
                user_data = team_chat_sessions[request.sid]
                username = user_data.get("username")

                # Remove from sessions
                del team_chat_sessions[request.sid]

                # Notify others
                emit(
                    "user_left_team_chat",
                    {
                        "user_id": user_id,
                        "username": username,
                        "team_id": team_id,
                        "reason": "manual_leave",
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                    room=f"team_chat_{team_id}",
                )

                # Leave room
                leave_room(f"team_chat_{team_id}")

        except Exception as e:
            print(f"❌ LEAVE ERROR: {str(e)}")


    def on_force_leave_team_chat(self, data):
        """Handle force leave team chat (browser close, navigation)"""
        try:
            team_id = data.get("team_id")
            user_id = data.get("user_id")
            reason = data.get("reason", "force_leave")
            
            print(f"🚨 FORCE_LEAVE_TEAM_CHAT: User {user_id} force leaving team {team_id} - Reason: {reason}")
            
            # ✅ FIND AND REMOVE ALL SESSIONS FOR THIS USER
            sessions_to_remove = []
            for sid, session_data in team_chat_sessions.items():
                if (session_data.get('user_id') == str(user_id) and 
                    session_data.get('team_id') == str(team_id)):
                    sessions_to_remove.append(sid)
            
            # ✅ REMOVE ALL MATCHING SESSIONS
            for sid in sessions_to_remove:
                if sid in team_chat_sessions:
                    user_data = team_chat_sessions[sid]
                    username = user_data.get('username')
                    del team_chat_sessions[sid]
                    print(f"✅ FORCE_CLEANUP: Removed session {sid} for {username}")
            
            print(f"✅ FORCE_CLEANUP: Removed {len(sessions_to_remove)} sessions")
            print(f"✅ SESSIONS_REMAINING: {len(team_chat_sessions)} total sessions")
            
            # ✅ NOTIFY TEAM IMMEDIATELY
            if team_id and sessions_to_remove:
                user = User.query.get(user_id)
                username = user.username or user.email.split("@")[0] if user and user.email else f"User_{user_id}"
                
                self.emit('user_left_team_chat', {
                    'user_id': user_id,
                    'username': username,
                    'team_id': team_id,
                    'reason': reason,
                    'force_cleanup': True,
                    'timestamp': datetime.utcnow().isoformat()
                }, room=f"team_chat_{team_id}")
                
                print(f"✅ FORCE_BROADCAST: Notified team {team_id} about {username} force leaving")
                
        except Exception as e:
            print(f"❌ FORCE_LEAVE_TEAM_CHAT ERROR: {str(e)}")        

    def on_clear_team_chat(self, data):
        try:
            team_id = data.get("team_id")
            user_id = data.get("user_id")

            # Check permissions
            member_check = db.session.execute(
                text(
                    "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
                ),
                {"team_id": team_id, "user_id": str(user_id)},
            ).first()

            if not member_check or member_check.role not in ["OWNER", "ADMIN"]:
                emit("team_chat_error", {"error": "Insufficient permissions"})
                return

            # ✅ USE YOUR EXISTING MODEL
            cleared_count = TeamChat.clear_team_chats(team_id, user_id)

            # Get user info
            user = User.query.get(user_id)
            username = (
                user.username or user.email.split("@")[0]
                if user.email
                else f"User_{user_id}"
            )

            # Broadcast clear
            emit(
                "team_chat_cleared",
                {
                    "team_id": team_id,
                    "cleared_count": cleared_count,
                    "cleared_by": user_id,
                    "cleared_by_username": username,
                    "cleared_by_role": member_check.role,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                room=f"team_chat_{team_id}",
            )

        except Exception as e:
            print(f"❌ CLEAR ERROR: {str(e)}")
            emit("team_chat_error", {"error": str(e)})
