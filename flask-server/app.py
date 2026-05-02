#!/usr/bin/env python3
"""
CodeVault - Code Snippet Manager
Main Flask Application Entry Point
"""
import eventlet

eventlet.monkey_patch()

import os
import importlib
import inspect
import logging
from logging.handlers import RotatingFileHandler  # ✅ ADD THIS LINE
import hashlib
import json
from datetime import datetime
import subprocess  # ✅ ADD THIS
import atexit  # ✅ ADD THIS
import signal  # ✅ ADD THIS
import sys  # ✅ ADD THIS


# ✅ ADD THESE REDIS MANAGEMENT FUNCTIONS:
def start_redis():
    """Start Redis/Valkey service automatically with multiple fallback methods"""
    try:
        # Check if Redis/Valkey is already running
        result = subprocess.run(
            ["redis-cli", "ping"], capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            print("✅ Redis/Valkey is already running")
            return True
    except:
        pass

    # Method 1: Try Valkey service (Arch Linux default)
    try:
        print("🚀 Attempting to start Valkey service...")
        subprocess.run(["sudo", "systemctl", "start", "valkey"], check=True, timeout=10)

        # Wait and verify
        import time

        for i in range(10):
            try:
                result = subprocess.run(
                    ["redis-cli", "ping"], capture_output=True, text=True, timeout=1
                )
                if result.returncode == 0:
                    print("✅ Valkey started successfully")
                    return True
            except:
                pass
            time.sleep(0.5)

    except subprocess.CalledProcessError as e:
        print(f"⚠️ Valkey systemctl method failed: {e}")
    except Exception as e:
        print(f"⚠️ Valkey systemctl error: {e}")

    # Method 2: Try Redis service (fallback)
    try:
        print("🚀 Attempting to start Redis service...")
        subprocess.run(["sudo", "systemctl", "start", "redis"], check=True, timeout=10)

        # Wait for Redis to start and verify
        import time

        for i in range(10):
            try:
                result = subprocess.run(
                    ["redis-cli", "ping"], capture_output=True, text=True, timeout=1
                )
                if result.returncode == 0:
                    print("✅ Redis started successfully")
                    return True
            except:
                pass
            time.sleep(0.5)

    except subprocess.CalledProcessError as e:
        print(f"⚠️ Redis systemctl method failed: {e}")
    except Exception as e:
        print(f"⚠️ Redis systemctl error: {e}")

    print("❌ All Redis/Valkey start methods failed")
    return False


def stop_redis():
    """Stop Redis/Valkey service with multiple methods"""
    stopped = False

    # Method 1: Try stopping Valkey service
    try:
        print("🛑 Stopping Valkey service...")
        subprocess.run(["sudo", "systemctl", "stop", "valkey"], timeout=5, check=True)
        print("✅ Valkey stopped via systemctl")
        stopped = True
    except:
        print("⚠️ Valkey systemctl stop failed, trying Redis...")

    # Method 2: Try stopping Redis service
    if not stopped:
        try:
            print("🛑 Stopping Redis service...")
            subprocess.run(
                ["sudo", "systemctl", "stop", "redis"], timeout=5, check=True
            )
            print("✅ Redis stopped via systemctl")
            stopped = True
        except:
            print("⚠️ Redis systemctl stop failed")

    if not stopped:
        print("⚠️ Could not stop Redis/Valkey cleanly")


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n🛑 Shutting down Flask app...")
    stop_redis()
    sys.exit(0)


def setup_redis_auto_management():
    """Setup automatic Redis management"""
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Register cleanup function for normal exit
    atexit.register(stop_redis)

    print("🔧 Redis auto-management configured")


def check_redis_installation():
    """Check if Redis/Valkey is properly installed"""
    try:
        # Check if redis-cli exists
        result = subprocess.run(["which", "redis-cli"], capture_output=True, text=True)
        redis_cli_found = result.returncode == 0

        # Check if valkey-cli exists
        result = subprocess.run(["which", "valkey-cli"], capture_output=True, text=True)
        valkey_cli_found = result.returncode == 0

        if not redis_cli_found and not valkey_cli_found:
            print("❌ Neither redis-cli nor valkey-cli found")
            print("   Valkey should be installed. Try: sudo pacman -S valkey")
            return False

        # Check if server binaries exist
        result = subprocess.run(
            ["which", "valkey-server"], capture_output=True, text=True
        )
        valkey_server_found = result.returncode == 0

        result = subprocess.run(
            ["which", "redis-server"], capture_output=True, text=True
        )
        redis_server_found = result.returncode == 0

        if not valkey_server_found and not redis_server_found:
            print("❌ Neither valkey-server nor redis-server found")
            return False

        if valkey_cli_found or valkey_server_found:
            print("✅ Valkey binaries found")
        elif redis_cli_found or redis_server_found:
            print("✅ Redis binaries found")

        return True

    except Exception as e:
        print(f"❌ Error checking Redis/Valkey installation: {e}")
        return False


import jwt as pyjwt
from flask import (
    Flask,
    render_template,
    jsonify,
    request,
    send_from_directory,
    abort,
    current_app,
)
from flask_jwt_extended import (
    JWTManager,
    verify_jwt_in_request,
    get_jwt_identity,
    get_jwt,
    create_access_token,
    jwt_required,
)
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from flask_migrate import Migrate, init, migrate, upgrade
from sqlalchemy import MetaData, Table

from app import create_app
from config import DevelopmentConfig, ProductionConfig
from app.extensions import socketio, db
from app.routes.main import main
from app.routes.auth import auth_bp
from app.models.user import User
from app.models.snippet import Snippet
from app.models.collection import Collection
from app.websocket.handlers import WebSocketHandlers, register_websocket_handlers
from database_manager import initialize_database


def setup_comprehensive_logging(app):
    """Setup comprehensive logging for debugging"""
    # Create logs directory
    log_dir = os.path.join(os.path.dirname(app.instance_path), "data", "logs")
    os.makedirs(log_dir, exist_ok=True)

    # Clear existing handlers
    for handler in app.logger.handlers[:]:
        app.logger.removeHandler(handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
    console_handler.setFormatter(console_formatter)

    # Route access logger
    route_handler = RotatingFileHandler(
        os.path.join(log_dir, "route_access.log"), maxBytes=10240000, backupCount=5
    )
    route_handler.setLevel(logging.INFO)
    route_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    route_handler.setFormatter(route_formatter)

    # Error logger
    error_handler = RotatingFileHandler(
        os.path.join(log_dir, "errors.log"), maxBytes=10240000, backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(route_formatter)

    # Authentication logger
    auth_handler = RotatingFileHandler(
        os.path.join(log_dir, "auth.log"), maxBytes=10240000, backupCount=5
    )
    auth_handler.setLevel(logging.INFO)
    auth_handler.setFormatter(route_formatter)

    # Add handlers
    app.logger.addHandler(console_handler)
    app.logger.addHandler(route_handler)
    app.logger.addHandler(error_handler)
    app.logger.setLevel(logging.DEBUG)

    # Setup specific loggers
    route_logger = logging.getLogger("routes")
    route_logger.addHandler(route_handler)
    route_logger.setLevel(logging.INFO)

    auth_logger = logging.getLogger("auth")
    auth_logger.addHandler(auth_handler)
    auth_logger.setLevel(logging.INFO)

    app.logger.info("Comprehensive logging initialized")
    return app.logger


connected_clients = {
    "chrome": {"connected": False, "sid": None},
    "vscode": {"connected": False, "sid": None},
}
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Then use:
config_name = os.getenv("FLASK_CONFIG", "development")
if config_name == "production":
    app = create_app(ProductionConfig)
else:
    app = create_app(DevelopmentConfig)

from database_manager import initialize_database


CORS(
    app,
    origins=["chrome-extension://*", "http://localhost:*"],
    supports_credentials=True,
)

# Import JWT functions after app is created
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt

jwt = JWTManager(app)


# Initialize logging BEFORE any Socket.IO setup
def setup_enhanced_logging():
    """Setup enhanced logging for the entire application"""
    # Clear any existing handlers
    logging.getLogger().handlers.clear()

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
    console_handler.setFormatter(formatter)

    # Add handler to root logger
    root_logger.addHandler(console_handler)

    # Create specific loggers
    main_logger = logging.getLogger("main")
    main_logger.setLevel(logging.INFO)

    socketio_logger = logging.getLogger("socketio.server")
    socketio_logger.setLevel(logging.INFO)

    return main_logger


# Initialize logging
connection_logger = setup_enhanced_logging()

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="eventlet",
    logger=False,  # ✅ FIXED: Disable verbose logging
    engineio_logger=False,  # ✅ FIXED: Disable engine logging
    ping_timeout=60,  # ✅ FIXED: Increase timeout
    ping_interval=25,  # ✅ FIXED: Increase interval
    upgrade=True,
    transports=["websocket", "polling"],  # ✅ FIXED: Prefer websocket first
    allow_upgrades=True,  # ✅ ADDED: Allow transport upgrades
    cookie=None,  # ✅ ADDED: Disable cookies for WebSocket
)

# Register WebSocket handlers from handlers.py
from app.websocket.handlers import register_websocket_handlers

register_websocket_handlers(socketio, db, app)

# Add debug logging to confirm handlers are registered
if app.debug:
    print("🔌 WebSocket authentication handlers registered successfully!")

from app.websocket.team_chat_namespace import TeamChatNamespace

socketio.on_namespace(TeamChatNamespace("/team-chat"))
print("🔌 Team chat namespace registered successfully!")


# Add focused connection logging - insert after socketio initialization
connection_logger = logging.getLogger("main")

# Store session info like universal version
app.session_info = {}


# ✅ Register the blueprint
app.register_blueprint(main)
from app.routes.auth import auth_bp

app.register_blueprint(auth_bp)

# ADD THIS LINE:
from app.routes.teams import teams_bp


@app.cli.command()
def deploy():
    """Run deployment tasks."""
    # Create database tables
    db.create_all()

    # Migrate database to latest revision
    upgrade()

    print("Database deployment completed successfully!")


@app.cli.command()
def create_admin():
    """Create an admin user."""
    from app.models.user import User
    from werkzeug.security import generate_password_hash

    email = input("Enter admin email: ")
    password = input("Enter admin password: ")

    if User.query.filter_by(email=email).first():
        print(f"User with email {email} already exists!")
        return

    admin = User(
        email=email,
        password_hash=generate_password_hash(password),
        is_admin=True,
        created_at=datetime.utcnow(),
    )

    db.session.add(admin)
    db.session.commit()
    print(f"Admin user {email} created successfully!")


@app.route("/api/status", methods=["GET"])
def status():
    """Return server status with debug info"""
    session_info = getattr(app, "session_info", {})
    chrome_connected = any(
        info.get("client_type") == "chrome" for info in session_info.values()
    )
    vscode_connected = any(
        info.get("client_type") == "vscode" for info in session_info.values()
    )

    print(f"📊 STATUS CHECK: {len(session_info)} active sessions")
    connection_logger.info(f"Status check - Active sessions: {len(session_info)}")

    return jsonify(
        {
            "status": "running",
            "connectedClients": {
                "chrome": chrome_connected,
                "vscode": vscode_connected,
            },
            "debug": {
                "total_sessions": len(session_info),
                "session_details": session_info,
            },
            "serverTime": datetime.now().isoformat(),
        }
    )


@app.route("/api/ping", methods=["GET"])
def ping():
    """Health check endpoint for Chrome extension"""
    return (
        jsonify(
            {
                "status": "ok",
                "message": "Server is running",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
            }
        ),
        200,
    )


@app.route("/api/debug/auth", methods=["POST"])
def debug_auth():
    """Debug endpoint to test authentication flow"""
    print("=== DEBUG AUTH ENDPOINT CALLED ===")
    print(f"Request method: {request.method}")
    print(f"Request headers: {dict(request.headers)}")
    print(f"Request data: {request.get_json()}")

    return jsonify(
        {
            "status": "debug_received",
            "method": request.method,
            "headers": dict(request.headers),
            "data": request.get_json(),
        }
    )


@app.route("/api/auth/verify", methods=["POST"])
def verify_auth():
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return (
                jsonify(
                    {"success": False, "valid": False, "error": "No token provided"}
                ),
                401,
            )

        token = auth_header.split(" ")[1]

        # Use PyJWT directly for verification
        payload = pyjwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
        user_id = payload.get("user_id")
        email = payload.get("email")

        # Check if user still exists
        user = User.query.filter_by(id=user_id).first()
        if not user:
            return (
                jsonify({"success": False, "valid": False, "error": "User not found"}),
                401,
            )

        # Log successful token verification
        logger.info(f"Token verification successful for user: {email} (ID: {user_id})")

        return jsonify(
            {"success": True, "valid": True, "user": {"id": user_id, "email": email}}
        )

    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        return (
            jsonify({"success": False, "valid": False, "error": "Invalid token"}),
            401,
        )


@app.route("/api/auth/status", methods=["GET"])
def auth_status():
    """Check authentication status"""
    auth_header = request.headers.get("Authorization")
    if auth_header:
        try:
            token = auth_header.split(" ")[1]
            from app.routes.auth import verify_token

            payload = verify_token(token)
            return jsonify({"authenticated": bool(payload), "payload": payload})
        except:
            return jsonify({"authenticated": False, "error": "Invalid token format"})

    return jsonify({"authenticated": False, "error": "No token provided"})


@app.cli.command()
def init_db():
    """Initialize the database with sample data."""
    # Create tables
    db.create_all()

    # Check if we already have data
    if User.query.first():
        print("Database already initialized!")
        return

    # Create sample user
    from werkzeug.security import generate_password_hash

    sample_user = User(
        email="demo@codevault.com",
        password_hash=generate_password_hash("demo123"),
        created_at=datetime.utcnow(),
    )

    db.session.add(sample_user)
    db.session.commit()

    # Create sample collection
    sample_collection = Collection(
        name="JavaScript Utilities",
        description="Useful JavaScript helper functions",
        user_id=sample_user.id,
        created_at=datetime.utcnow(),
    )

    db.session.add(sample_collection)
    db.session.commit()

    # Create sample snippets
    sample_snippets = [
        {
            "title": "Debounce Function",
            "code": """function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}""",
            "language": "javascript",
            "tags": "utility,performance,javascript",
            "source_url": "https://example.com/debounce",
        },
        {
            "title": "Python List Comprehension",
            "code": """# Filter and transform data in one line
squared_evens = [x**2 for x in range(10) if x % 2 == 0]
print(squared_evens)  # [0, 4, 16, 36, 64]

# Dictionary comprehension
word_lengths = {word: len(word) for word in ['hello', 'world', 'python']}
print(word_lengths)  # {'hello': 5, 'world': 5, 'python': 6}""",
            "language": "python",
            "tags": "python,comprehension,functional",
            "source_url": "https://python.org/examples",
        },
        {
            "title": "CSS Flexbox Center",
            "code": """.center-container {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
}

.centered-content {
    text-align: center;
    padding: 2rem;
    border-radius: 8px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}""",
            "language": "css",
            "tags": "css,flexbox,layout,centering",
            "source_url": "https://css-tricks.com/centering",
        },
    ]

    for snippet_data in sample_snippets:
        snippet = Snippet(
            title=snippet_data["title"],
            code=snippet_data["code"],
            language=snippet_data["language"],
            tags=snippet_data["tags"],
            source_url=snippet_data["source_url"],
            user_id=sample_user.id,
            created_at=datetime.utcnow(),
        )
        db.session.add(snippet)

    db.session.commit()
    print("Database initialized with sample data!")


# Error Handlers
@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors with custom page."""
    if request.is_json:
        return (
            jsonify(
                {
                    "error": "Not Found",
                    "message": "The requested resource was not found.",
                    "status_code": 404,
                }
            ),
            404,
        )

    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors with custom page."""
    db.session.rollback()

    if request.is_json:
        return (
            jsonify(
                {
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred.",
                    "status_code": 500,
                }
            ),
            500,
        )

    return render_template("errors/500.html"), 500


@app.errorhandler(403)
def forbidden_error(error):
    """Handle 403 errors with custom page."""
    if request.is_json:
        return (
            jsonify(
                {
                    "error": "Forbidden",
                    "message": "You do not have permission to access this resource.",
                    "status_code": 403,
                }
            ),
            403,
        )

    return render_template("errors/403.html"), 403


# Health Check Endpoint
@app.route("/health")
def app_health_check():
    """Simple health check endpoint for monitoring."""
    try:
        # Test database connection
        db.session.execute("SELECT 1")
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "healthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "version": app.config.get("VERSION", "1.0.0"),
                    "database": "connected",
                }
            ),
            200,
        )
    except Exception as e:
        return (
            jsonify(
                {
                    "status": "unhealthy",
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": str(e),
                    "database": "disconnected",
                }
            ),
            503,
        )


# API Info Endpoint
@app.route("/api/info")
def app_api_info():
    """Provide API information and available endpoints."""
    return jsonify(
        {
            "name": "CodeVault API",
            "version": app.config.get("VERSION", "1.0.0"),
            "description": "Code Snippet Manager API",
            "endpoints": {
                "authentication": "/auth/",
                "snippets": "/api/snippets/",
                "collections": "/api/collections/",
                "users": "/api/users/",
                "health": "/health",
            },
            "documentation": "/api/docs",
            "status": "active",
        }
    )


# Shell Context Processor
@app.shell_context_processor
def make_shell_context():
    """Make database models available in Flask shell."""
    return {"db": db, "User": User, "Snippet": Snippet, "Collection": Collection}


@app.route("/debug/migration-status")
def debug_migration_status():
    """Debug migration and database status"""
    try:
        from flask_migrate import current
        from sqlalchemy import inspect

        info = {
            "app_name": app.name,
            "db_uri": app.config.get("SQLALCHEMY_DATABASE_URI"),
            "tables": [],
            "migration_current": None,
            "migrations_dir_exists": False,
        }

        # Get table info
        try:
            inspector = inspect(db.engine)
            info["tables"] = inspector.get_table_names()
        except Exception as e:
            info["tables_error"] = str(e)

        # Check migration status
        try:
            info["migration_current"] = current()
        except Exception as e:
            info["migration_error"] = str(e)

        # Check migrations directory
        migrations_dir = os.path.join(app.root_path, "..", "migrations")
        info["migrations_dir_exists"] = os.path.exists(migrations_dir)
        info["migrations_dir_path"] = migrations_dir

        return jsonify(info)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Shell Context Processor
@app.shell_context_processor
def make_shell_context():
    """Make database models available in Flask shell."""
    return {"db": db, "User": User, "Snippet": Snippet, "Collection": Collection}


def auto_detect_and_migrate(app, db):
    """
    Automatically detect model changes and create/apply migrations
    NOTE: This function should only be called from within an app context
    """
    print("🔍 Starting intelligent migration detection...")

    try:
        # DON'T create nested app context - we're already in one
        # Initialize migration if not exists
        migrations_dir = os.path.join(app.root_path, "..", "migrations")
        if not os.path.exists(migrations_dir):
            print("📁 Initializing migrations directory...")
            init()
            print("✅ Migrations initialized!")

        # Auto-discover all model files
        model_changes = detect_model_changes(app, db)

        if model_changes:
            print(f"🔄 Detected {len(model_changes)} model changes:")
            for change in model_changes:
                print(f"   - {change}")

            # Create migration for detected changes
            create_auto_migration(model_changes)

        # Apply any pending migrations
        print("🔄 Applying pending migrations...")
        upgrade()
        print("✅ All migrations applied successfully!")

        return True

    except Exception as e:
        print(f"❌ Error in auto-migration: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def detect_model_changes(app, db):
    """
    Detect changes in model files by scanning the models directory
    """
    print("🔍 Starting model change detection...")
    changes = []
    models_dir = os.path.join(app.root_path, "models")

    print(f"🔍 Scanning models directory: {models_dir}")

    if not os.path.exists(models_dir):
        print("⚠️ Models directory not found!")
        return changes

    # Get all Python files in models directory
    model_files = [
        f for f in os.listdir(models_dir) if f.endswith(".py") and f != "__init__.py"
    ]

    print(f"📁 Found {len(model_files)} model files: {model_files}")

    # Import all model files to register them with SQLAlchemy
    for model_file in model_files:
        try:
            module_name = f"app.models.{model_file[:-3]}"
            print(f"📥 Importing {module_name}")
            importlib.import_module(module_name)
            print(f"✅ Successfully imported {module_name}")
        except Exception as e:
            print(f"❌ Error importing {model_file}: {e}")
            import traceback

            traceback.print_exc()

    # Force model registration
    print("🔧 Forcing model registration with SQLAlchemy...")
    force_model_registration(db)

    # Add a small delay to ensure all models are registered
    import time

    time.sleep(0.1)

    print("🔍 All models imported, checking database schema...")

    # Check for missing tables/columns with enhanced error handling
    try:
        missing_items = check_database_schema(db)
        changes.extend(missing_items)
        print(f"✅ Schema check completed. Found {len(missing_items)} changes.")
    except Exception as e:
        print(f"❌ Error during schema check: {e}")
        import traceback

        traceback.print_exc()

    return changes


def check_database_schema(db):
    """
    Compare SQLAlchemy models with actual database schema
    """
    changes = []

    try:
        print("🔍 Starting database schema comparison...")

        # Debug SQLAlchemy metadata first
        debug_sqlalchemy_metadata(db)

        # Use the app's database engine directly
        from flask import current_app

        # Get current database metadata using current app context
        current_metadata = MetaData()

        # Use current_app to get the proper engine
        with current_app.app_context():
            engine = current_app.extensions["sqlalchemy"].engines[None]
            current_metadata.reflect(bind=engine)
            current_tables = set(current_metadata.tables.keys())
            print(
                f"🔍 Found {len(current_tables)} existing database tables: {current_tables}"
            )

            # FORCE metadata refresh - this is the key fix
            print("🔄 Forcing SQLAlchemy metadata refresh...")

            # Import models explicitly to ensure they're registered
            from app.models.user import User
            from app.models.snippet import Snippet
            from app.models.collection import Collection
            from app.models.team import Team
            from app.models.team_member import TeamMember

            # Force metadata to include all model tables
            db.metadata.create_all(bind=engine, checkfirst=True)

            # Now get model metadata after forcing registration
            model_metadata = db.metadata
            model_tables = set(model_metadata.tables.keys())
            print(
                f"🔍 Found {len(model_tables)} model tables after refresh: {model_tables}"
            )

            if len(model_tables) == 0:
                print("❌ CRITICAL: No model tables found in metadata!")
                print("🔧 Attempting manual model registration...")

                # Manual registration as fallback
                model_classes = [User, Snippet, Collection, Team, TeamMember]
                manual_tables = set()

                for model_class in model_classes:
                    if hasattr(model_class, "__table__"):
                        table_name = model_class.__table__.name
                        manual_tables.add(table_name)
                        print(f"   ✅ Found model table: {table_name}")

                model_tables = manual_tables
                print(f"🔧 Using manually discovered tables: {model_tables}")

            # Check for missing tables
            missing_tables = model_tables - current_tables
            if missing_tables:
                print(f"❌ Missing tables detected: {missing_tables}")
                for table in missing_tables:
                    changes.append(f"Missing table: {table}")
                    print(f"❌ Missing table: {table}")
            else:
                print("✅ All model tables exist in database")

            # Check for missing columns in existing tables
            for table_name in model_tables.intersection(current_tables):
                try:
                    print(f"🔍 Checking columns in table: {table_name}")

                    # Get model table info
                    if table_name in model_metadata.tables:
                        model_table = model_metadata.tables[table_name]
                    else:
                        # Fallback: get from model class directly
                        model_class = None
                        if table_name == "users":
                            model_class = User
                        elif table_name == "snippets":
                            model_class = Snippet
                        elif table_name == "collections":
                            model_class = Collection
                        elif table_name == "teams":
                            model_class = Team
                        elif table_name == "team_members":
                            model_class = TeamMember

                        if model_class and hasattr(model_class, "__table__"):
                            model_table = model_class.__table__
                        else:
                            print(f"⚠️ Could not find model for table: {table_name}")
                            continue

                    current_table = current_metadata.tables[table_name]

                    model_columns = set(model_table.columns.keys())
                    current_columns = set(current_table.columns.keys())

                    missing_columns = model_columns - current_columns
                    if missing_columns:
                        print(f"❌ Missing columns in {table_name}: {missing_columns}")
                        for column in missing_columns:
                            changes.append(f"Missing column: {table_name}.{column}")
                            print(f"❌ Missing column: {table_name}.{column}")
                    else:
                        print(f"✅ All columns exist in table: {table_name}")

                except Exception as e:
                    print(f"⚠️ Error checking table {table_name}: {e}")
                    import traceback

                    traceback.print_exc()

        print(f"🎯 Schema comparison complete. Found {len(changes)} missing items.")
        return changes

    except Exception as e:
        print(f"❌ Error checking database schema: {e}")
        import traceback

        traceback.print_exc()
        return []


def create_auto_migration(changes):
    """
    Create migration file for detected changes
    """
    try:
        print("📝 Creating automatic migration...")

        # Generate migration message
        message = f"auto_migration_{len(changes)}_changes"

        # Use flask-migrate to generate migration
        from flask_migrate import migrate as flask_migrate

        flask_migrate(message=message)

        print(f"✅ Created migration: {message}")
        return True

    except Exception as e:
        print(f"❌ Error creating migration: {e}")
        import traceback

        traceback.print_exc()
        return False


def discover_all_models(app):
    """
    Automatically discover and import all model files
    """
    print("🔍 Discovering all models...")

    # Define directories to scan
    scan_dirs = [
        os.path.join(app.root_path, "models"),
        os.path.join(app.root_path, "routes"),  # Routes might import models
        os.path.join(app.root_path, "services"),  # Services might define models
    ]

    discovered_models = []

    for scan_dir in scan_dirs:
        if os.path.exists(scan_dir):
            print(f"📁 Scanning directory: {scan_dir}")

            for file in os.listdir(scan_dir):
                if file.endswith(".py") and file != "__init__.py":
                    try:
                        # Determine module path
                        relative_path = os.path.relpath(scan_dir, app.root_path)
                        module_path = relative_path.replace(os.sep, ".")
                        module_name = f"app.{module_path}.{file[:-3]}"

                        # Import module
                        module = importlib.import_module(module_name)

                        # Find SQLAlchemy models in module
                        for name, obj in inspect.getmembers(module):
                            if (
                                inspect.isclass(obj)
                                and hasattr(obj, "__tablename__")
                                and hasattr(obj, "metadata")
                            ):
                                discovered_models.append(f"{module_name}.{name}")
                                print(f"✅ Discovered model: {name}")

                    except Exception as e:
                        print(f"⚠️ Error scanning {file}: {e}")

    print(f"🎯 Total models discovered: {len(discovered_models)}")
    return discovered_models


def debug_sqlalchemy_metadata(db):
    """Debug SQLAlchemy metadata registration"""
    print("🔍 DEBUGGING SQLALCHEMY METADATA:")
    print(f"   - db.metadata: {db.metadata}")
    print(f"   - db.metadata.tables: {list(db.metadata.tables.keys())}")
    print(f"   - db.Model registry: {hasattr(db.Model, 'registry')}")

    # Try to get all registered models
    try:
        if hasattr(db.Model, "registry"):
            print(f"   - Registry mappers: {len(db.Model.registry.mappers)}")
            for mapper in db.Model.registry.mappers:
                print(f"     * {mapper.class_.__name__}: {mapper.class_.__tablename__}")
    except Exception as e:
        print(f"   - Registry error: {e}")

    # Check if models are in metadata
    from app.models.user import User
    from app.models.snippet import Snippet
    from app.models.collection import Collection

    print(
        f"   - User.__table__ in metadata: {User.__table__.name in db.metadata.tables}"
    )
    print(
        f"   - Snippet.__table__ in metadata: {Snippet.__table__.name in db.metadata.tables}"
    )
    print(
        f"   - Collection.__table__ in metadata: {Collection.__table__.name in db.metadata.tables}"
    )


def setup_enhanced_migration_logging():
    """Setup enhanced logging for migration detection"""
    migration_logger = logging.getLogger("migration_detector")
    migration_logger.setLevel(logging.DEBUG)

    # Create console handler with detailed formatting
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    # Create detailed formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
    )
    console_handler.setFormatter(formatter)

    # Add handler to logger
    if not migration_logger.handlers:
        migration_logger.addHandler(console_handler)

    return migration_logger


def force_model_registration(db):
    """Force registration of all models with SQLAlchemy metadata"""
    print("🔧 Forcing model registration...")

    try:
        # Import all models to ensure they're loaded
        from app.models.user import User
        from app.models.snippet import Snippet, SnippetHistory, SnippetShare
        from app.models.collection import (
            Collection,
            CollectionActivity,
            CollectionPermission,
        )
        from app.models.team import Team
        from app.models.team_member import TeamMember

        # List of all model classes
        model_classes = [
            User,
            Snippet,
            SnippetHistory,
            SnippetShare,
            Collection,
            CollectionActivity,
            CollectionPermission,
            Team,
            TeamMember,
        ]

        registered_count = 0
        for model_class in model_classes:
            if hasattr(model_class, "__table__"):
                table_name = model_class.__table__.name
                print(f"   ✅ Registered: {model_class.__name__} -> {table_name}")
                registered_count += 1
            else:
                print(f"   ⚠️ No __table__ found for: {model_class.__name__}")

        print(f"🎯 Successfully registered {registered_count} models")
        return registered_count > 0

    except Exception as e:
        print(f"❌ Error in model registration: {e}")
        import traceback

        traceback.print_exc()
        return False


# Initialize enhanced logging
migration_logger = setup_enhanced_migration_logging()


# Enhanced logging configuration for Chrome extension tracking
def setup_chrome_extension_logging(app):
    """Setup focused logging for Chrome extension connections only"""

    # Create main logger
    main_logger = logging.getLogger("main")
    main_logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates
    main_logger.handlers.clear()

    # Create console handler with custom format
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Custom formatter to match your desired output
    formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
    console_handler.setFormatter(formatter)

    main_logger.addHandler(console_handler)
    main_logger.propagate = False  # Prevent duplicate logs

    return main_logger


# Create the logger instance
connection_logger = setup_chrome_extension_logging(app)

# Also create a socketio logger for connection events
socketio_logger = logging.getLogger("socketio")
socketio_logger.setLevel(logging.INFO)
if not socketio_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    socketio_logger.addHandler(handler)
    socketio_logger.propagate = False


# Simple Socket.IO handlers like universal version
# Socket.IO Event Handlers with Enhanced Logging
# Socket.IO Event Handlers - WORKING VERSION
@socketio.on("connect")
def handle_connect():
    """Handle client connection"""
    print(f"🔌 SOCKET.IO: Client connected - SID: {request.sid}")
    connection_logger.info(f"Client connected: {request.sid}")

    # Initialize session info
    if not hasattr(app, "session_info"):
        app.session_info = {}

    app.session_info[request.sid] = {
        "connected_at": datetime.now().isoformat(),
        "client_type": None,
        "remote_addr": getattr(request, "remote_addr", "unknown"),
    }

    # Send immediate response
    socketio.emit(
        "server_message",
        {
            "type": "connection_established",
            "message": "Connected to CodeVault server",
            "sid": request.sid,
            "timestamp": datetime.now().isoformat(),
        },
        room=request.sid,
    )

    print(f"✅ SOCKET.IO: Welcome message sent to {request.sid}")


@socketio.on("disconnect")
def handle_disconnect():
    """Handle client disconnection"""
    print(f"🔌 SOCKET.IO: Client disconnected - SID: {request.sid}")
    connection_logger.info(f"Client disconnected: {request.sid}")

    # Clean up session
    if hasattr(app, "session_info") and request.sid in app.session_info:
        client_type = app.session_info[request.sid].get("client_type", "unknown")
        del app.session_info[request.sid]
        print(f"🧹 SOCKET.IO: Cleaned up {client_type} session")


@socketio.on("register_client")
def handle_register_client(data):
    """Handle client registration with fixed broadcast issue"""
    try:
        client_type = data.get("clientType", "unknown") if data else "unknown"
        print(
            f"📝 SOCKET.IO: Registration request - Type: {client_type}, SID: {request.sid}"
        )
        connection_logger.info(
            f"Client registration request: {client_type} from {request.sid}"
        )

        if client_type in ["chrome", "vscode"]:
            # Update session info
            if hasattr(app, "session_info") and request.sid in app.session_info:
                app.session_info[request.sid]["client_type"] = client_type
                app.session_info[request.sid][
                    "registered_at"
                ] = datetime.now().isoformat()

            print(f"✅ SOCKET.IO: Successfully registered {client_type} client")
            connection_logger.info(f"Registered {client_type} client: {request.sid}")

            # Send success response to specific client
            socketio.emit(
                "registration_success",
                {
                    "success": True,
                    "clientType": client_type,
                    "sid": request.sid,
                    "message": f"{client_type.title()} client registered successfully",
                    "timestamp": datetime.now().isoformat(),
                },
                room=request.sid,  # Send only to this client
            )

            # ✅ FIXED: Remove broadcast parameter and send to all clients properly
            socketio.emit(
                "client_status_update",
                {
                    "chrome_connected": any(
                        info.get("client_type") == "chrome"
                        for info in app.session_info.values()
                    ),
                    "vscode_connected": any(
                        info.get("client_type") == "vscode"
                        for info in app.session_info.values()
                    ),
                    "total_clients": len(app.session_info),
                },
                # ✅ REMOVED: broadcast=True parameter
            )

        else:
            print(f"❌ SOCKET.IO: Invalid client type: {client_type}")
            connection_logger.warning(
                f"Invalid client type: {client_type} from {request.sid}"
            )

            socketio.emit(
                "registration_failed",
                {
                    "success": False,
                    "error": "Invalid client type",
                    "received": client_type,
                    "expected": ["chrome", "vscode"],
                },
                room=request.sid,
            )

    except Exception as e:
        connection_logger.error(f"Error in register_client handler: {str(e)}")
        socketio.emit(
            "registration_failed",
            {
                "success": False,
                "error": "Server error during registration",
                "details": str(e),
            },
            room=request.sid,
        )


@socketio.on("ping")
def handle_ping(data=None):
    """Handle ping from clients"""
    print(f"🏓 SOCKET.IO: Ping received from {request.sid}")
    connection_logger.info(f"Ping received from {request.sid}")

    socketio.emit(
        "pong",
        {
            "message": "Server alive",
            "timestamp": datetime.now().isoformat(),
            "sid": request.sid,
        },
        room=request.sid,
    )


@socketio.on("unregister_client")
def handle_unregister_client(data):
    """Handle client unregistration with enhanced logging"""
    client_type = data.get("clientType", "unknown")
    connection_logger.info(
        f"Client unregistration request: {client_type} from {request.sid}"
    )

    if hasattr(app, "session_info") and request.sid in app.session_info:
        app.session_info[request.sid]["client_type"] = None
        app.session_info[request.sid]["unregistered_at"] = datetime.now().isoformat()

    connection_logger.info(f"Unregistered {client_type} client: {request.sid}")

    emit(
        "unregistration_success",
        {
            "clientType": client_type,
            "message": f"{client_type.title()} client unregistered successfully",
        },
    )


# Test endpoint for Socket.IO connection
@socketio.on("ping")
def handle_ping(data):
    """Handle ping requests with logging"""
    connection_logger.info(f"Ping received from {request.sid}: {data}")
    emit(
        "pong",
        {
            "message": "Server is alive",
            "timestamp": datetime.now().isoformat(),
            "your_sid": request.sid,
        },
    )


# ADD THESE TEAM WEBSOCKET HANDLERS:
@socketio.on("join_team_room")
def handle_join_team_room(data):
    """Handle team room joining"""
    try:
        team_id = data.get("team_id")
        user_id = data.get("user_id")

        print(f"🏢 JOIN TEAM ROOM: Team {team_id}, User {user_id}")

        # Verify team membership
        from app.models.team_member import TeamMember

        membership = TeamMember.query.filter_by(
            team_id=team_id, user_id=user_id, is_active=True
        ).first()

        if not membership:
            socketio.emit(
                "team_join_error", {"error": "Not a team member"}, room=request.sid
            )
            return

        team_room = f"team_{team_id}"
        join_room(team_room)

        print(f"✅ TEAM ROOM: User {user_id} joined {team_room}")

        socketio.emit(
            "team_joined",
            {"team_id": team_id, "room": team_room, "role": membership.role.value},
            room=request.sid,
        )

    except Exception as e:
        print(f"❌ TEAM ROOM JOIN ERROR: {str(e)}")
        socketio.emit("team_join_error", {"error": str(e)}, room=request.sid)


@socketio.on("team_activity")
def handle_team_activity(data):
    """Handle team activity broadcasting"""
    try:
        team_id = data.get("team_id")
        activity_type = data.get("type")

        print(f"🏢 TEAM ACTIVITY: {activity_type} in team {team_id}")

        team_room = f"team_{team_id}"
        socketio.emit(
            "team_activity_update",
            {
                "team_id": team_id,
                "type": activity_type,
                "data": data.get("data", {}),
                "timestamp": datetime.now().isoformat(),
            },
            room=team_room,
        )

    except Exception as e:
        print(f"❌ TEAM ACTIVITY ERROR: {str(e)}")


# ADD THIS ENHANCED TEAM LOGGING after your existing logging setup:


def setup_team_collaboration_logging():
    """Setup enhanced logging specifically for team collaboration"""
    team_logger = logging.getLogger("team_collaboration")
    team_logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates
    team_logger.handlers.clear()

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Custom formatter for team events
    formatter = logging.Formatter("🏢 TEAM:%(levelname)s:%(message)s")
    console_handler.setFormatter(formatter)

    team_logger.addHandler(console_handler)
    team_logger.propagate = False

    return team_logger


# Initialize team collaboration logging
team_logger = setup_team_collaboration_logging()


# Error handler for Socket.IO
@socketio.on_error_default
def default_error_handler(e):
    """Handle Socket.IO errors with enhanced logging"""
    connection_logger.error(f"Socket.IO error from {request.sid}: {str(e)}")
    socketio_logger.error(f"Socket.IO error: {str(e)}", exc_info=True)


@socketio.on("create_collection")
def create_collection_wrapper(data):
    return WebSocketHandlers.handle_collection_create(data)


# Logging Configuration
def setup_logging(app):
    """Configure logging for the application."""
    if not app.debug and not app.testing:
        # File logging for production
        if not os.path.exists("logs"):
            os.mkdir("logs")

        file_handler = logging.FileHandler("logs/codevault.log")
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s: %(message)s " "[in %(pathname)s:%(lineno)d]"
            )
        )
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info("CodeVault startup")


# # ADD THIS ENHANCED TEAM LOGGING:
# @app.before_request
# def log_team_requests():
#     """Enhanced logging for team requests"""
#     if request.path.startswith("/api/v1/teams"):
#         print(f"🏢 TEAM REQUEST: {request.method} {request.path}")
#         print(
#             f"🏢 TEAM HEADERS: Authorization={request.headers.get('Authorization', 'None')}"
#         )
#         if request.is_json and request.get_json():
#             print(f"🏢 TEAM DATA: {request.get_json()}")


# Add this to handle 400 errors specifically
@app.errorhandler(400)
def bad_request_error(error):
    """Handle 400 errors with enhanced logging"""
    logger.error(f"❌ 400 Bad Request: {request.method} {request.url}")
    logger.error(f"❌ Request data: {request.get_data()}")
    logger.error(f"❌ Request headers: {dict(request.headers)}")
    logger.error(f"❌ Request args: {dict(request.args)}")
    logger.error(f"❌ Request form: {dict(request.form)}")
    logger.error(f"❌ Request endpoint: {request.endpoint}")
    logger.error(f"❌ Request view args: {request.view_args}")

    # Check if user is authenticated
    try:
        from flask_login import current_user

        if current_user.is_authenticated:
            logger.error(f"❌ Authenticated user: {current_user.email}")
        else:
            logger.error(f"❌ User not authenticated")
    except Exception as e:
        logger.error(f"❌ Auth check error: {e}")

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return (
            jsonify(
                {
                    "error": "Bad Request",
                    "message": "The request could not be processed.",
                    "status_code": 400,
                    "debug_info": {
                        "endpoint": request.endpoint,
                        "method": request.method,
                        "path": request.path,
                    },
                }
            ),
            400,
        )

    return render_template("errors/404.html"), 400


@app.after_request
def log_response_info(response):
    """Log all outgoing responses"""
    route_logger = logging.getLogger("routes")
    route_logger.info(
        f"RESPONSE: {request.method} {request.path} -> {response.status_code}"
    )
    return response


if __name__ == "__main__":
    # ✅ SETUP REDIS AUTO-MANAGEMENT FIRST
    setup_redis_auto_management()

    # ✅ START REDIS BEFORE ANYTHING ELSE
    # ✅ CHECK REDIS INSTALLATION
if not check_redis_installation():
    print("⚠️ Redis/Valkey not installed properly.")
    print("💡 Install Valkey: sudo pacman -S valkey")

    # Ask user if they want to continue without Redis
    response = input("Continue without Redis? (y/N): ").lower()
    if response != "y":
        sys.exit(1)

    print("⚠️ Running without Redis - real-time features disabled")
else:
    # ✅ START REDIS/VALKEY
    print("🔧 Checking Redis/Valkey status...")
    if not start_redis():
        print("⚠️ Redis/Valkey failed to start. Some features will be limited.")
        response = input("Continue without Redis? (y/N): ").lower()
        if response != "y":
            sys.exit(1)

    # Single database initialization
    with app.app_context():
        try:
            print("🔧 Initializing database...")
            initialize_database()
            print("✅ Database ready!")

            # Add enhanced logging
            logger = setup_comprehensive_logging(app)
            logger.info("Application starting with enhanced logging")
            print("✅ Enhanced logging initialized!")

            # 🔥 ULTIMATE ENHANCED AUTO-MIGRATION SYSTEM 🔥
            print("\n" + "=" * 60)
            print("🚀 ULTIMATE ENHANCED AUTO-MIGRATION SYSTEM STARTING")
            print("=" * 60)

            # Import the ULTIMATE enhanced migration system
            from ultimate_auto_migration_system import (
                run_ultimate_enhanced_auto_migration,
                check_user_avatar_columns_ultimate,
                force_add_user_avatar_columns_ultimate,
                debug_flask_sqlalchemy_setup,
            )

            # Add this function right after your auto-migration call (around line 1050)
            def debug_collection_team_shares():
                """Debug collection team shares table creation"""
                try:
                    print("\n" + "=" * 60)
                    print("🔍 DEBUGGING COLLECTION TEAM SHARES TABLE")
                    print("=" * 60)

                    with app.app_context():
                        from sqlalchemy import text, inspect as sql_inspect
                        from flask import current_app

                        # Check if table definition exists in models
                        try:
                            from app.models.collection import collection_team_shares

                            print(
                                "✅ collection_team_shares table definition found in models"
                            )
                            print(
                                f"📋 Table columns: {list(collection_team_shares.columns.keys())}"
                            )
                        except ImportError as e:
                            print(
                                f"❌ collection_team_shares table definition NOT found: {e}"
                            )
                            return False

                        # Check if table exists in database
                        engine = current_app.extensions["sqlalchemy"].engines[None]
                        inspector = sql_inspect(engine)

                        all_tables = inspector.get_table_names()
                        print(f"📋 All database tables: {all_tables}")

                        if "collection_team_shares" in all_tables:
                            print("✅ collection_team_shares table EXISTS in database")

                            columns = inspector.get_columns("collection_team_shares")
                            print("📋 Database columns:")
                            for col in columns:
                                print(
                                    f"   - {col['name']}: {col['type']} (nullable: {col['nullable']})"
                                )

                            return True
                        else:
                            print(
                                "❌ collection_team_shares table MISSING from database"
                            )
                            print(
                                "🔧 This means the auto-migration didn't detect the new table"
                            )
                            return False

                except Exception as e:
                    print(f"❌ Debug error: {e}")
                    import traceback

                    traceback.print_exc()
                    return False
                finally:
                    print("=" * 60 + "\n")

                # Add this call right after your existing auto-migration code (around line 1080)
                # Find this section in your code:

            # Debug Flask-SQLAlchemy setup first
            print("\n🔍 DEBUGGING FLASK-SQLALCHEMY SETUP...")
            debug_flask_sqlalchemy_setup(app)

            # Run the ULTIMATE enhanced auto-migration
            print("\n🚀 RUNNING ULTIMATE AUTO-MIGRATION...")
            migration_success = run_ultimate_enhanced_auto_migration(app)

            if migration_success:
                print("\n✅ ULTIMATE AUTO-MIGRATION COMPLETED SUCCESSFULLY!")

                debug_collection_team_shares()

                # Specifically check for your user avatar columns
                print("\n🔍 VERIFYING USER AVATAR COLUMNS...")
                avatar_columns_ok = check_user_avatar_columns_ultimate(app)

                if not avatar_columns_ok:
                    print(
                        "⚠️ SOME USER AVATAR COLUMNS ARE MISSING - FORCE ADDING THEM..."
                    )
                    force_success = force_add_user_avatar_columns_ultimate(app)

                    if force_success:
                        print("✅ AVATAR COLUMNS ADDED SUCCESSFULLY!")
                        # Verify again
                        avatar_columns_ok = check_user_avatar_columns_ultimate(app)
                    else:
                        print("❌ FAILED TO ADD AVATAR COLUMNS!")

                if avatar_columns_ok:
                    print("✅ ALL USER AVATAR COLUMNS ARE PRESENT!")
                    print("   - avatar_url")
                    print("   - avatar_filename")
                    print("   - avatar_uploaded_at")

                # Final verification with enhanced logging
                print("\n🔍 RUNNING FINAL DATABASE VERIFICATION...")
                from sqlalchemy import inspect as sql_inspect

                with app.app_context():
                    try:
                        engine = current_app.extensions["sqlalchemy"].engines[None]
                        inspector = sql_inspect(engine)

                        if "users" in inspector.get_table_names():
                            user_columns = [
                                col["name"] for col in inspector.get_columns("users")
                            ]
                            print(f"📋 ACTUAL USER TABLE COLUMNS: {user_columns}")

                            # Check each avatar column specifically
                            user_avatar_columns = [
                                "avatar_url",
                                "avatar_filename",
                                "avatar_uploaded_at",
                            ]

                            for col in user_avatar_columns:
                                if col in user_columns:
                                    print(f"   ✅ {col} - PRESENT")
                                else:
                                    print(f"   ❌ {col} - MISSING")
                            else:
                                print("❌ USERS TABLE NOT FOUND!")

                        # Also check all other tables
                        all_tables = inspector.get_table_names()
                        print(f"📋 ALL DATABASE TABLES: {all_tables}")

                        # Log table details for debugging
                        for table_name in all_tables:
                            try:
                                columns = [
                                    col["name"]
                                    for col in inspector.get_columns(table_name)
                                ]
                                print(f"   📋 {table_name}: {columns}")
                            except Exception as e:
                                print(
                                    f"   ❌ Error getting columns for {table_name}: {e}"
                                )

                    except Exception as e:
                        print(f"❌ Final verification failed: {e}")
                        import traceback

                        traceback.print_exc()

            else:
                print("\n❌ ULTIMATE AUTO-MIGRATION FAILED!")
                print("Check the detailed logs above for error information")

            print("=" * 60)
            print("ULTIMATE AUTO-MIGRATION SYSTEM COMPLETE")
            print("=" * 60 + "\n")

        except Exception as e:
            print(f"⚠️ Database initialization error: {e}")
            import traceback

            traceback.print_exc()
            # ✅ STOP REDIS ON DATABASE ERROR
            stop_redis()
            sys.exit(1)

    # Server configuration continues...
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "True").lower() == "true"

    # Print startup information
    print(
        f"""
╔═══════════════════════════════════════════════════════════════╗
║                         CodeVault                             ║
║                   Code Snippet Manager                        ║
╠═══════════════════════════════════════════════════════════════╣
║  🚀 Server running on: http://{host}:{port}                    ║
║  🔧 Environment: {os.getenv('FLASK_CONFIG', 'development')}    ║
║  🔄 Debug mode: {'On' if debug else 'Off'}                    ║
║  📊 Database: {app.config.get('SQLALCHEMY_DATABASE_URI', 'SQLite')} ║
║  🔴 Redis/Valkey: Auto-managed (will stop when app closes)    ║
╚═══════════════════════════════════════════════════════════════╝
    """
    )

    # ✅ RUN THE APPLICATION WITH REDIS AUTO-MANAGEMENT
    try:
        print("🎯 Starting SocketIO server with Redis support...")
        socketio.run(app, host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        print("\n🛑 Flask app interrupted by user")
    except Exception as e:
        print(f"❌ Flask app error: {e}")
    finally:
        # ✅ ENSURE REDIS STOPS EVEN IF SOMETHING GOES WRONG
        print("🧹 Cleaning up...")
        stop_redis()
