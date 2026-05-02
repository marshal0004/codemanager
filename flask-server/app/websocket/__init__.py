# flask-server/app/websocket/__init__.py
from flask_socketio import SocketIO
from flask import request
from flask_login import current_user
import logging
import jwt
from datetime import datetime
import redis
import json

# Initialize Redis for session management (optional but recommended)
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    REDIS_AVAILABLE = True
except:
    REDIS_AVAILABLE = False
    redis_client = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebSocketManager:
    """
    Centralized WebSocket management for the Code Snippet Manager
    Handles initialization, authentication, and connection management
    """
    
    def __init__(self):
        self.socketio = None
        self.active_connections = {}  # user_id -> socket_id mapping
        self.connection_stats = {
            'total_connections': 0,
            'active_connections': 0,
            'failed_connections': 0
        }
    
    def init_socketio(self, app):
        """
        Initialize SocketIO with Flask app
        """
        # SocketIO Configuration
        socketio_config = {
            'cors_allowed_origins': [
                "chrome-extension://*",  # Allow Chrome extension
                "http://localhost:3000",  # Development frontend
                "http://localhost:5000",  # Flask development
                app.config.get('FRONTEND_URL', 'http://localhost:3000')
            ],
            'async_mode': 'threading',  # Use threading for better performance
            'logger': True,
            'engineio_logger': True,
            'ping_timeout': 60,
            'ping_interval': 25,
            'max_http_buffer_size': 1000000  # 1MB for code snippets
        }
        
        # Initialize SocketIO
        self.socketio = SocketIO(app, **socketio_config)
        
        # Register authentication handler
        self._register_auth_handler()
        
        # Register connection handlers
        self._register_connection_handlers()
        
        # Import and register event handlers
        self._register_event_handlers()
        
        logger.info("WebSocket initialized successfully")
        return self.socketio
    
    def _register_auth_handler(self):
        """
        Register authentication handler for WebSocket connections
        """
        @self.socketio.on('connect')
        def handle_connect(auth=None):
            """
            Handle new WebSocket connections with authentication
            """
            try:
                # Get authentication data
                auth_token = None
                
                # Try multiple authentication methods
                if auth and isinstance(auth, dict):
                    auth_token = auth.get('token')
                
                # Check query parameters for token
                if not auth_token and request.args.get('token'):
                    auth_token = request.args.get('token')
                
                # Check headers for token
                if not auth_token and request.headers.get('Authorization'):
                    auth_header = request.headers.get('Authorization')
                    if auth_header.startswith('Bearer '):
                        auth_token = auth_header[7:]
                
                # Validate authentication
                if not self._validate_auth_token(auth_token):
                    logger.warning(f"Unauthorized WebSocket connection attempt from {request.remote_addr}")
                    return False  # Reject connection
                
                # Get user info from token
                user_info = self._decode_auth_token(auth_token)
                if not user_info:
                    logger.warning("Invalid token provided for WebSocket connection")
                    return False
                
                # Store connection info
                user_id = user_info.get('user_id')
                session_id = request.sid
                
                self.active_connections[user_id] = {
                    'session_id': session_id,
                    'connected_at': datetime.utcnow().isoformat(),
                    'ip_address': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent', ''),
                    'last_activity': datetime.utcnow().isoformat()
                }
                
                # Update connection stats
                self.connection_stats['total_connections'] += 1
                self.connection_stats['active_connections'] += 1
                
                # Store in Redis if available
                if REDIS_AVAILABLE:
                    redis_client.hset(
                        f"ws_connection:{user_id}",
                        mapping=self.active_connections[user_id]
                    )
                    redis_client.expire(f"ws_connection:{user_id}", 3600)  # 1 hour
                
                logger.info(f"User {user_id} connected to WebSocket from {request.remote_addr}")
                return True  # Accept connection
                
            except Exception as e:
                logger.error(f"Error in WebSocket connect handler: {str(e)}")
                self.connection_stats['failed_connections'] += 1
                return False
    
    def _register_connection_handlers(self):
        """
        Register connection management handlers
        """
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """
            Handle WebSocket disconnections
            """
            try:
                session_id = request.sid
                
                # Find and remove user connection
                user_id = None
                for uid, conn_info in self.active_connections.items():
                    if conn_info['session_id'] == session_id:
                        user_id = uid
                        break
                
                if user_id:
                    # Remove from active connections
                    del self.active_connections[user_id]
                    
                    # Update stats
                    self.connection_stats['active_connections'] -= 1
                    
                    # Remove from Redis
                    if REDIS_AVAILABLE:
                        redis_client.delete(f"ws_connection:{user_id}")
                    
                    logger.info(f"User {user_id} disconnected from WebSocket")
                else:
                    logger.warning(f"Unknown session {session_id} disconnected")
                    
            except Exception as e:
                logger.error(f"Error in WebSocket disconnect handler: {str(e)}")
        
        @self.socketio.on('ping')
        def handle_ping(data):
            """
            Handle ping requests for connection health check
            """
            try:
                user_id = self._get_user_id_from_session()
                if user_id and user_id in self.active_connections:
                    # Update last activity
                    self.active_connections[user_id]['last_activity'] = datetime.utcnow().isoformat()
                    
                    # Update Redis
                    if REDIS_AVAILABLE:
                        redis_client.hset(
                            f"ws_connection:{user_id}",
                            'last_activity',
                            self.active_connections[user_id]['last_activity']
                        )
                
                # Send pong response
                self.socketio.emit('pong', {
                    'timestamp': datetime.utcnow().isoformat(),
                    'server_time': datetime.utcnow().timestamp()
                })
                
            except Exception as e:
                logger.error(f"Error in ping handler: {str(e)}")
    
    def _register_event_handlers(self):
        """
        Import and register all WebSocket event handlers
        """
        try:
            # Import handlers (this will register them via decorators)
            from .handlers import WebSocketHandlers
            
            # Register additional custom handlers if needed
            logger.info("WebSocket event handlers registered successfully")
            
        except ImportError as e:
            logger.error(f"Failed to import WebSocket handlers: {str(e)}")
        except Exception as e:
            logger.error(f"Error registering WebSocket handlers: {str(e)}")
    
    def _validate_auth_token(self, token):
        """
        Validate authentication token
        """
        if not token:
            return False
        
        try:
            # Decode and validate JWT token
            from flask import current_app
            jwt.decode(
                token, 
                current_app.config['SECRET_KEY'], 
                algorithms=['HS256']
            )
            return True
        except jwt.InvalidTokenError:
            return False
        except Exception:
            return False
    
    def _decode_auth_token(self, token):
        """
        Decode authentication token and return user info
        """
        try:
            from flask import current_app
            payload = jwt.decode(
                token, 
                current_app.config['SECRET_KEY'], 
                algorithms=['HS256']
            )
            return payload
        except:
            return None
    
    def _get_user_id_from_session(self):
        """
        Get user ID from current WebSocket session
        """
        try:
            session_id = request.sid
            for user_id, conn_info in self.active_connections.items():
                if conn_info['session_id'] == session_id:
                    return user_id
            return None
        except:
            return None
    
    def get_connection_stats(self):
        """
        Get WebSocket connection statistics
        """
        return {
            **self.connection_stats,
            'active_users': list(self.active_connections.keys()),
            'redis_available': REDIS_AVAILABLE
        }
    
    def broadcast_to_user(self, user_id, event, data):
        """
        Broadcast message to specific user
        """
        try:
            if user_id in self.active_connections:
                session_id = self.active_connections[user_id]['session_id']
                self.socketio.emit(event, data, room=session_id)
                return True
            return False
        except Exception as e:
            logger.error(f"Error broadcasting to user {user_id}: {str(e)}")
            return False
    
    def broadcast_to_all(self, event, data):
        """
        Broadcast message to all connected users
        """
        try:
            self.socketio.emit(event, data, broadcast=True)
            return True
        except Exception as e:
            logger.error(f"Error broadcasting to all users: {str(e)}")
            return False
    
    def cleanup_stale_connections(self):
        """
        Cleanup stale connections (run periodically)
        """
        try:
            current_time = datetime.utcnow()
            stale_users = []
            
            for user_id, conn_info in self.active_connections.items():
                last_activity = datetime.fromisoformat(conn_info['last_activity'])
                if (current_time - last_activity).total_seconds() > 3600:  # 1 hour
                    stale_users.append(user_id)
            
            # Remove stale connections
            for user_id in stale_users:
                del self.active_connections[user_id]
                if REDIS_AVAILABLE:
                    redis_client.delete(f"ws_connection:{user_id}")
                logger.info(f"Cleaned up stale connection for user {user_id}")
            
            # Update stats
            self.connection_stats['active_connections'] = len(self.active_connections)
            
        except Exception as e:
            logger.error(f"Error cleaning up stale connections: {str(e)}")

# Global WebSocket manager instance
websocket_manager = WebSocketManager()

def init_websocket(app):
    """
    Initialize WebSocket for the Flask application
    """
    try:
        socketio = websocket_manager.init_socketio(app)
        
        # Start cleanup task (optional - run in background)
        import threading
        import time
        
        def cleanup_task():
            while True:
                time.sleep(1800)  # Every 30 minutes
                websocket_manager.cleanup_stale_connections()
        
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()
        
        logger.info("WebSocket initialization completed")
        return socketio
        
    except Exception as e:
        logger.error(f"Failed to initialize WebSocket: {str(e)}")
        raise

# Export the manager and initialization function
__all__ = ['websocket_manager', 'init_websocket']