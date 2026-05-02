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
import hashlib
import json
from datetime import datetime

import jwt as pyjwt
from flask import Flask, render_template, jsonify, request
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

from app.extensions import socketio

# Don't import db here - we'll get it from the app instance
from app.routes.main import main
from app.routes.auth import auth_bp
from app.models.user import User
from app.models.snippet import Snippet
from app.models.collection import Collection
from app.websocket.handlers import WebSocketHandlers, register_websocket_handlers
from database_manager import initialize_database


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
try:
    # Get database instance with proper error handling
    from app.extensions import db

    connection_logger.info("✅ Database imported from app.extensions")
except ImportError:
    try:
        # Fallback: try to get from app
        from flask import current_app

        db = current_app.extensions.get("sqlalchemy")
        if db:
            connection_logger.info("✅ Database retrieved from current_app.extensions")
        else:
            connection_logger.error("❌ No database instance found in app extensions")
            db = None
    except Exception as e:
        connection_logger.error(f"❌ Database import failed: {e}")
        db = None

try:
    connection_logger.info("🔌 Initializing SocketIO server...")

    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode="eventlet",
        logger=True,
        engineio_logger=True,
        ping_timeout=30,
        ping_interval=10,
        upgrade=True,
        transports=["polling", "websocket"],
    )

    connection_logger.info("✅ SocketIO server initialized successfully")
    print("🔌 SocketIO server created successfully")

except Exception as e:
    connection_logger.error(f"❌ SocketIO initialization failed: {e}")
    print(f"❌ SocketIO failed to initialize: {e}")
    import traceback

    traceback.print_exc()
    raise


def check_websocket_handlers_file():
    """Check if WebSocket handlers file exists and is properly structured"""
    try:
        handlers_path = os.path.join(app.root_path, "websocket", "handlers.py")
        connection_logger.info(f"🔍 Checking WebSocket handlers file: {handlers_path}")

        if not os.path.exists(handlers_path):
            connection_logger.warning(
                "⚠️ WebSocket handlers file not found, creating minimal version..."
            )

            # Create minimal handlers file
            os.makedirs(os.path.dirname(handlers_path), exist_ok=True)

            minimal_handlers = '''"""
Minimal WebSocket Handlers for CodeVault
"""
import logging
from flask_socketio import emit
from flask import request

logger = logging.getLogger(__name__)

def register_websocket_handlers(socketio, app):
    """Register minimal WebSocket handlers"""
    logger.info("Registering minimal WebSocket handlers")
    
    @socketio.on('connect')
    def handle_connect():
        logger.info(f"Client connected: {request.sid}")
        emit('connection_status', {'status': 'connected', 'sid': request.sid})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info(f"Client disconnected: {request.sid}")
    
    logger.info("Minimal WebSocket handlers registered successfully")

class WebSocketHandlers:
    """WebSocket handlers class"""
    
    @staticmethod
    def handle_collection_create(data):
        """Handle collection creation"""
        logger.info(f"Collection create request: {data}")
        return {"success": True, "message": "Collection creation handler"}
'''

            with open(handlers_path, "w") as f:
                f.write(minimal_handlers)

            connection_logger.info("✅ Created minimal WebSocket handlers file")
            return True
        else:
            connection_logger.info("✅ WebSocket handlers file exists")
            return True

    except Exception as e:
        connection_logger.error(f"❌ Error checking WebSocket handlers: {e}")
        return False


# Register WebSocket handlers with enhanced error handling
try:
    connection_logger.info("🔌 Attempting to register WebSocket handlers...")

    from app.websocket.handlers import register_websocket_handlers

    # Simple, direct registration
    register_websocket_handlers(socketio, app)

    connection_logger.info("✅ WebSocket handlers registered successfully")
    print("🔌 WebSocket authentication handlers registered successfully!")

except ImportError as e:
    connection_logger.error(f"❌ Failed to import WebSocket handlers: {e}")
    connection_logger.info("🔧 Creating fallback WebSocket handlers...")

    # Create minimal fallback handlers
    @socketio.on("test_connection")
    def handle_test_connection():
        connection_logger.info(f"Test connection from {request.sid}")
        socketio.emit("test_response", {"status": "ok", "sid": request.sid})

    print("🔧 Fallback WebSocket handlers created")

except Exception as e:
    connection_logger.error(f"❌ WebSocket handler registration failed: {e}")
    print(f"❌ WebSocket handlers failed: {e}")

    # Continue without crashing
    connection_logger.info("🔧 Continuing with basic handlers...")

# Add debug logging to confirm handlers are registered
if app.debug:
    print("🔌 WebSocket authentication handlers registered successfully!")
# Add focused connection logging - insert after socketio initialization
connection_logger = logging.getLogger("main")

# Store session info like universal version
app.session_info = {}


# ✅ Register the blueprint
app.register_blueprint(main)
from app.routes.auth import auth_bp

app.register_blueprint(auth_bp)


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


def ensure_db_context(app):
    """Ensure proper database context and handle SQLAlchemy instance issues"""
    try:
        from flask import current_app

        # Check if we're in an app context
        if not current_app:
            raise RuntimeError("No Flask app context available")

        # Check if SQLAlchemy is properly initialized
        if "sqlalchemy" not in current_app.extensions:
            raise RuntimeError("SQLAlchemy not initialized with this Flask app")

        db = current_app.extensions["sqlalchemy"]
        migration_logger.info("✅ Database context verified successfully")
        return db

    except Exception as e:
        migration_logger.error(f"Database context error: {e}")
        raise


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


def force_import_all_models(app):
    """Force import all models with enhanced logging"""
    migration_logger.info("🔧 Force importing all models...")

    try:
        # Get db from app context instead of importing it globally
        from flask import current_app

        db = current_app.extensions["sqlalchemy"]

        # Import core models
        from app.models.user import User
        from app.models.snippet import Snippet
        from app.models.collection import Collection

        models_imported = ["User", "Snippet", "Collection"]
        migration_logger.info(f"Core models imported: {models_imported}")

        # Try to import additional models
        try:
            from app.models.team import Team
            from app.models.team_member import TeamMember

            models_imported.extend(["Team", "TeamMember"])
            migration_logger.info("Additional models imported: Team, TeamMember")
        except ImportError as e:
            migration_logger.info(f"Optional models not available: {e}")

        # Force SQLAlchemy to recognize all models
        db.create_all()
        migration_logger.info("SQLAlchemy create_all() called to register models")

        # Log registered tables
        registered_tables = list(db.metadata.tables.keys())
        migration_logger.info(f"Registered tables in metadata: {registered_tables}")
        print(f"📋 Registered tables: {registered_tables}")

        return models_imported

    except Exception as e:
        migration_logger.error(f"Error importing models: {e}", exc_info=True)
        raise


def enhanced_detect_model_changes(app, db):
    """Enhanced model change detection with detailed logging"""
    migration_logger.info("🔍 Starting enhanced model change detection")
    changes = []

    try:
        from sqlalchemy import inspect
        from flask import current_app

        # Use current_app to get the proper db instance
        if db is None:
            db = current_app.extensions["sqlalchemy"]

        # Get database inspector
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())
        migration_logger.info(f"Existing database tables: {existing_tables}")

        # Get model tables from metadata
        model_tables = set(db.metadata.tables.keys())
        migration_logger.info(f"Model tables from metadata: {model_tables}")

        # Check for missing tables
        missing_tables = model_tables - existing_tables
        if missing_tables:
            migration_logger.warning(f"Missing tables detected: {missing_tables}")
            for table in missing_tables:
                changes.append(f"Missing table: {table}")
                print(f"❌ Missing table: {table}")

        # Check for missing columns in existing tables
        for table_name in model_tables.intersection(existing_tables):
            migration_logger.info(f"Checking columns in table: {table_name}")

            # Get existing columns
            existing_columns = set(
                col["name"] for col in inspector.get_columns(table_name)
            )
            migration_logger.debug(
                f"Existing columns in {table_name}: {existing_columns}"
            )

            # Get model columns
            model_table = db.metadata.tables[table_name]
            model_columns = set(model_table.columns.keys())
            migration_logger.debug(f"Model columns for {table_name}: {model_columns}")

            # Find missing columns
            missing_columns = model_columns - existing_columns
            if missing_columns:
                migration_logger.warning(
                    f"Missing columns in {table_name}: {missing_columns}"
                )
                for column in missing_columns:
                    changes.append(f"Missing column: {table_name}.{column}")
                    print(f"❌ Missing column: {table_name}.{column}")
            else:
                migration_logger.info(f"All columns present in {table_name}")

        migration_logger.info(
            f"Model change detection completed. Found {len(changes)} changes"
        )
        return changes

    except Exception as e:
        migration_logger.error(f"Error in model change detection: {e}", exc_info=True)
        return []


def create_enhanced_migration(changes):
    """Create migration with enhanced logging"""
    migration_logger.info("📝 Creating enhanced auto-migration")

    try:
        from flask_migrate import migrate as flask_migrate

        # Create descriptive message
        message = f"auto_migration_{len(changes)}_changes_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        migration_logger.info(f"Creating migration with message: {message}")

        # Generate migration
        flask_migrate(message=message)
        migration_logger.info("Migration file created successfully")

        return True

    except Exception as e:
        migration_logger.error(f"Error creating migration: {e}", exc_info=True)
        return False


def verify_migration_results(app, original_changes):
    """Verify that migration was successful"""
    migration_logger.info("🔍 Verifying migration results")

    try:
        from flask import current_app

        db = current_app.extensions["sqlalchemy"]

        # Re-run change detection
        remaining_changes = enhanced_detect_model_changes(app, db)

        if not remaining_changes:
            print("✅ Migration verification successful - all changes applied!")
            migration_logger.info(
                "Migration verification successful - no remaining changes"
            )
        else:
            print(
                f"⚠️ Migration verification found {len(remaining_changes)} remaining issues:"
            )
            migration_logger.warning(
                f"Migration verification found remaining issues: {remaining_changes}"
            )
            for change in remaining_changes:
                print(f"   - {change}")
                migration_logger.warning(f"Remaining issue: {change}")

        return len(remaining_changes) == 0

    except Exception as e:
        migration_logger.error(f"Error verifying migration: {e}", exc_info=True)
        return False


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
    """Handle client registration"""
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
            app.session_info[request.sid]["registered_at"] = datetime.now().isoformat()

        print(f"✅ SOCKET.IO: Successfully registered {client_type} client")
        connection_logger.info(f"Registered {client_type} client: {request.sid}")

        # Send success response
        socketio.emit(
            "registration_success",
            {
                "success": True,
                "clientType": client_type,
                "sid": request.sid,
                "message": f"{client_type.title()} client registered successfully",
                "timestamp": datetime.now().isoformat(),
            },
            room=request.sid,
        )

        # Broadcast status update
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
            broadcast=True,
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


if __name__ == "__main__":
    # Enhanced startup logging
    startup_logger = logging.getLogger("startup")
    startup_logger.setLevel(logging.INFO)

    if not startup_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
        startup_logger.addHandler(handler)

    startup_logger.info("🚀 Starting CodeVault application...")

    # Server configuration
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "True").lower() == "true"

    startup_logger.info(f"Server config - Host: {host}, Port: {port}, Debug: {debug}")

    # Database initialization with enhanced error handling
    with app.app_context():
        try:
            startup_logger.info("🔧 Starting database initialization...")

            # Get db instance with error handling
            try:
                from flask import current_app

                db = current_app.extensions.get("sqlalchemy")
                if not db:
                    startup_logger.error("❌ No SQLAlchemy instance found")
                    raise ValueError("SQLAlchemy not properly initialized")
                startup_logger.info("✅ Database instance retrieved")
            except Exception as e:
                startup_logger.error(f"❌ Database instance error: {e}")
                raise

            # Initialize database
            initialize_database()
            startup_logger.info("✅ Database initialization completed")

            # Enhanced Auto-Migration Detection with better error handling
            startup_logger.info("🔍 Starting Enhanced Auto-Migration Detection...")

            try:
                # Force import all models
                force_import_all_models(app)
                startup_logger.info("✅ All models imported successfully")

                # Initialize migrations if needed
                migrations_dir = os.path.join(app.root_path, "..", "migrations")
                if not os.path.exists(migrations_dir):
                    startup_logger.info("📁 Initializing migrations directory...")
                    init()
                    startup_logger.info("✅ Migrations initialized!")

                # Enhanced model change detection
                model_changes = enhanced_detect_model_changes(app, db)

                if model_changes:
                    startup_logger.info(
                        f"🔄 Detected {len(model_changes)} database changes"
                    )
                    for change in model_changes:
                        startup_logger.warning(f"Database change needed: {change}")

                    # Create and apply migration
                    if create_enhanced_migration(model_changes):
                        startup_logger.info("✅ Auto-migration created successfully")
                        upgrade()
                        startup_logger.info("✅ Migration applied successfully")
                        verify_migration_results(app, model_changes)
                    else:
                        startup_logger.error("❌ Failed to create auto-migration")
                else:
                    startup_logger.info("✅ Database is up to date - no changes needed")

                # Final migration check
                upgrade()
                startup_logger.info("✅ All migrations verified and applied!")

            except Exception as migration_error:
                startup_logger.error(
                    f"⚠️ Migration error (non-fatal): {migration_error}"
                )
                # Don't crash on migration errors, continue with startup

        except Exception as db_error:
            startup_logger.error(f"❌ Database initialization error: {db_error}")
            import traceback

            traceback.print_exc()
            # Continue startup even with DB errors for debugging
            startup_logger.warning("⚠️ Continuing startup despite database errors...")

    # Print enhanced startup information
    print(
        f"""
╔═══════════════════════════════════════════════════════════════╗
║                         CodeVault                             ║
║                   Code Snippet Manager                        ║
╠═══════════════════════════════════════════════════════════════╣
║  🚀 Server: http://{host}:{port}                               ║
║  🔧 Environment: {os.getenv('FLASK_CONFIG', 'development')}    ║
║  🔄 Debug: {'On' if debug else 'Off'}                         ║
║  📊 Database: Ready                                           ║
║  🔌 WebSocket: Enhanced Logging Enabled                      ║
╚═══════════════════════════════════════════════════════════════╝
    """
    )

    try:
        startup_logger.info(
            "🎯 Starting SocketIO server with enhanced error handling..."
        )
        socketio.run(app, host=host, port=port, debug=debug)
    except Exception as server_error:
        startup_logger.error(f"❌ Server startup failed: {server_error}")
        import traceback

        traceback.print_exc()
        raise
