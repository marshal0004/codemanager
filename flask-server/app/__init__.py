import eventlet

eventlet.monkey_patch()

from flask import Flask, jsonify, request, send_from_directory, current_app
from flask_cors import CORS
import logging
from logging.handlers import RotatingFileHandler
from config import Config
from datetime import datetime
from .services import initialize_services
import os
from flask_login import LoginManager, current_user  # Add current_user here
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import redis
from celery import Celery
from .extensions import migrate, login_manager, jwt, socketio

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
from .models.user import User
from .models.snippet import Snippet
from .models.collection import Collection
from .models.team import Team
from .models.team_member import TeamMember
from app.models import db
import uuid

# load order
from app.models.user import User
from app.models.team import Team
from app.models.team_member import TeamMember
from app.models.custom_types import UUIDType, JSONType
from .models.team_member import TeamMember

# Simple client tracking like universal version
connected_clients = {
    "chrome": {"connected": False, "sid": None},
    "vscode": {"connected": False, "sid": None},
}

# Store session info
session_info = {}


def create_app(config_class=Config, config_name=None):
    """Application factory pattern with enhanced static file handling"""

    # CRITICAL: Set static folder to the correct path
    static_folder = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "static"
    )

    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder=static_folder,
        static_url_path="/static",
    )

    print(f"🔍 APP INIT - ===== FLASK APP CONFIGURATION =====")
    print(f"🔍 APP INIT - App root path: {app.root_path}")
    print(f"🔍 APP INIT - Static folder: {app.static_folder}")
    print(f"🔍 APP INIT - Static URL path: {app.static_url_path}")
    print(f"🔍 APP INIT - Template folder: {app.template_folder}")

    # Load configuration
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    if config_class:
        app.config.from_object(config_class)
    else:
        from config import Config

        app.config.from_object(Config)

    if config_name == "production":
        app.config.from_object("config.ProductionConfig")
    elif config_name == "testing":
        app.config.from_object("config.TestingConfig")
    else:
        app.config.from_object("config.DevelopmentConfig")

    # CRITICAL: Create upload directories immediately
    upload_directories = [
        os.path.join(app.static_folder, "uploads"),
        os.path.join(app.static_folder, "uploads", "avatars"),
        # Also create in app/static for backward compatibility
        os.path.join(app.root_path, "static", "uploads"),
        os.path.join(app.root_path, "static", "uploads", "avatars"),
    ]

    for directory in upload_directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"✅ APP INIT - Created/verified directory: {directory}")
        except Exception as e:
            print(f"❌ APP INIT - Failed to create directory {directory}: {str(e)}")

    # CRITICAL: Add custom route for uploaded files with enhanced logging
    @app.route("/static/uploads/<path:filename>")
    def uploaded_file(filename):
        """Serve uploaded files with comprehensive logging"""
        print(f"🔍 STATIC FILE REQUEST - ===== STARTING =====")
        print(f"🔍 STATIC FILE REQUEST - Filename: {filename}")
        print(f"🔍 STATIC FILE REQUEST - Request URL: {request.url}")
        print(f"🔍 STATIC FILE REQUEST - Request path: {request.path}")

        # Try multiple possible locations
        possible_locations = [
            os.path.join(app.static_folder, "uploads"),
            os.path.join(app.root_path, "static", "uploads"),
            os.path.join(app.root_path, "app", "static", "uploads"),
        ]

        for upload_dir in possible_locations:
            file_path = os.path.join(upload_dir, filename)
            print(f"🔍 STATIC FILE - Checking: {file_path}")
            print(f"🔍 STATIC FILE - Exists: {os.path.exists(file_path)}")

            if os.path.exists(file_path):
                print(f"✅ STATIC FILE - Found and serving: {filename}")
                print(f"✅ STATIC FILE - From directory: {upload_dir}")
                try:
                    return send_from_directory(upload_dir, filename)
                except Exception as e:
                    print(f"❌ STATIC FILE - Error serving file: {str(e)}")
                    continue

        print(f"❌ STATIC FILE - File not found in any location: {filename}")
        print(f"❌ STATIC FILE - Searched locations: {possible_locations}")
        return "File not found", 404

    # Initialize extensions with app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    jwt.init_app(app)

    # Simple CORS setup like universal version
    CORS(app, origins=["chrome-extension://*", "http://localhost:*"])

    # Initialize SocketIO with CORS support
    socketio.init_app(
        app,
        cors_allowed_origins="*",
        async_mode="eventlet",
        logger=False,  # Disable socketio logging to reduce noise
        engineio_logger=False,
        ping_timeout=60,
        ping_interval=25,
        transports=["websocket"],  # Force websocket only
    )

    # Store session info like universal version
    app.session_info = {}

    # Configure Flask-Login
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            # First try direct lookup
            user = User.query.get(user_id)
            if user:
                return user

            # If that fails, try converting to UUID
            uid = uuid.UUID(user_id)
            return User.query.get(uid)
        except (ValueError, TypeError):
            # If all conversion attempts fail, return None
            return None

    # Import and register blueprints
    from app.routes.snippets import bp as snippets_bp

    app.register_blueprint(snippets_bp, url_prefix="/api/snippets")

    from app.routes.collections import bp as collections_bp

    app.register_blueprint(collections_bp, url_prefix="/api/collections")

    from app.routes.sync import bp as sync_bp

    app.register_blueprint(sync_bp, url_prefix="/api/sync")

    from app.routes.dashboard import dashboard_bp

    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")

    from app.routes.integrations import integrations_bp

    app.register_blueprint(integrations_bp, url_prefix="/api/v1/integrations")

    from app.routes.teams import teams_bp, teams_public_bp

    from app.routes.snippet_edits import bp as snippet_edits_bp
    app.register_blueprint(snippet_edits_bp, url_prefix="/api/snippet-edits")
    print("✅ Snippet edits blueprint registered successfully")

    # Register both blueprints
    app.register_blueprint(teams_bp)  # API routes: /api/teams/*
    app.register_blueprint(teams_public_bp)  # Public routes: /teams/*

    print("✅ Teams blueprint registered successfully")
    print("✅ Teams public blueprint registered successfully")

    # Initialize database
    with app.app_context():
        try:
            # Register all models
            from app.models import user, snippet, collection, team

            # Create tables if they don't exist
            db.create_all()
            print("✅ Database tables created successfully")
        except Exception as e:
            print(f"❌ Database initialization error: {e}")

    # Debug endpoint for connected clients
    @app.route("/debug/clients")
    def debug_clients():
        """Return connected clients for debugging"""
        return jsonify(
            {
                "connected_clients": connected_clients,
                "session_info": session_info,
                "active_sessions": len(session_info),
            }
        )

    # ENHANCED: Debug endpoint for static file configuration
    @app.route("/debug/static-config")
    def debug_static_config():
        """Debug static file configuration"""
        try:
            debug_info = {
                "app_root_path": app.root_path,
                "static_folder": app.static_folder,
                "static_url_path": app.static_url_path,
                "template_folder": app.template_folder,
            }

            # Check upload directories
            upload_dirs = [
                os.path.join(app.static_folder, "uploads", "avatars"),
                os.path.join(app.root_path, "static", "uploads", "avatars"),
                os.path.join(app.root_path, "app", "static", "uploads", "avatars"),
            ]

            debug_info["upload_directories"] = {}
            for upload_dir in upload_dirs:
                debug_info["upload_directories"][upload_dir] = {
                    "exists": os.path.exists(upload_dir),
                    "files": (
                        os.listdir(upload_dir) if os.path.exists(upload_dir) else []
                    ),
                }

            return jsonify(debug_info)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # Health check endpoint - simplified
    @app.route("/health")
    def health_check():
        """Simple health check"""
        try:
            # Test database connection
            db.session.execute("SELECT 1")
            return (
                jsonify(
                    {
                        "status": "healthy",
                        "database": "connected",
                        "chrome_extension_connected": connected_clients["chrome"][
                            "connected"
                        ],
                        "timestamp": datetime.now().isoformat(),
                    }
                ),
                200,
            )
        except Exception as e:
            return (
                jsonify(
                    {
                        "status": "unhealthy",
                        "database": "disconnected",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    }
                ),
                500,
            )

    @socketio.on("unregister_client")
    def handle_unregister_client(data):
        """Handle client unregistration"""
        client_type = data.get("clientType")

        if client_type in connected_clients:
            connected_clients[client_type]["connected"] = False
            connected_clients[client_type]["sid"] = None
            print(f"Unregistered {client_type} client: {request.sid}")

            # Broadcast status change
            socketio.emit(
                "client_status_change",
                {
                    "chrome": connected_clients["chrome"]["connected"],
                    "vscode": connected_clients["vscode"]["connected"],
                },
            )

    # @app.before_request
    # def log_request_info():
    #     """Log all incoming requests"""
    #     route_logger = logging.getLogger("routes")
    #     route_logger.info(
    #         f"REQUEST: {request.method} {request.path} from {request.remote_addr}"
    #     )

    #     if hasattr(request, "endpoint"):
    #         route_logger.info(f"ENDPOINT: {request.endpoint}")

    #     # Simple auth logging without causing errors
    #     try:
    #         from flask_login import current_user

    #         if current_user.is_authenticated:
    #             route_logger.info(f"AUTH_STATUS: authenticated")
    #             route_logger.info(f"USER: {current_user.email}")
    #         else:
    #             route_logger.info(f"AUTH_STATUS: anonymous")
    #     except:
    #         pass

    # # ADD THIS AFTER THE EXISTING @app.before_request FUNCTION:

    # @app.before_request
    # def log_team_requests():
    #     """Enhanced logging for team-related requests"""
    #     if request.path.startswith("/api/v1/teams") or request.path.startswith(
    #         "/api/teams"
    #     ):
    #         app.logger.info(f"🏢 TEAM REQUEST: {request.method} {request.path}")
    #         app.logger.info(f"🏢 TEAM HEADERS: {dict(request.headers)}")
    #         if request.is_json and request.get_json():
    #             app.logger.info(f"🏢 TEAM DATA: {request.get_json()}")

    @app.after_request
    def log_response_info(response):
        """Log response information"""
        if request.path.startswith("/api/collections/"):
            app.logger.info(f"🔍 RESPONSE LOG:")
            app.logger.info(f"   Status: {response.status_code}")
            app.logger.info(f"   Content Type: {response.content_type}")
            if response.status_code >= 400:
                app.logger.error(
                    f"   Response Data: {response.get_data(as_text=True)[:500]}"
                )
        return response

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        if request.is_json:
            return jsonify({"error": "Resource not found"}), 404
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        if request.is_json:
            return jsonify({"error": "Internal server error"}), 500
        return jsonify({"error": "Internal server error"}), 500

    # Simple logging setup
    if not app.debug and not app.testing:
        if not os.path.exists("logs"):
            os.mkdir("logs")

        file_handler = RotatingFileHandler(
            "logs/code_snippet_manager.log", maxBytes=10240000, backupCount=10
        )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)

    # Context processors
    @app.context_processor
    def inject_user():
        from flask_login import current_user

        return dict(current_user=current_user)

    @app.context_processor
    def inject_config():
        return dict(
            app_name=app.config.get("APP_NAME", "CodeVault"),
            app_version=app.config.get("APP_VERSION", "1.0.0"),
        )

    print(f"✅ APP INIT - ===== FLASK APP INITIALIZED SUCCESSFULLY =====")
    return app


# Import models to ensure they're registered with SQLAlchemy
from app.models import user, snippet, collection
