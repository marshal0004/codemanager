import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration class"""

    # Flask settings
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev-secret-key-change-in-production"

    # Code Execution Environment Settings
    ENABLE_CODE_EXECUTION = os.environ.get('ENABLE_CODE_EXECUTION', 'False').lower() == 'true'
    CODE_EXECUTION_TIMEOUT = int(os.environ.get('CODE_EXECUTION_TIMEOUT', '10'))  # seconds
    MAX_CODE_OUTPUT_SIZE = int(os.environ.get('MAX_CODE_OUTPUT_SIZE', '10240'))  # bytes

    # Supported languages for execution
    SUPPORTED_EXECUTION_LANGUAGES = [
        'python', 'javascript', 'typescript', 'bash', 'sql'
    ]

    # Docker settings for secure execution
    DOCKER_ENABLED = os.environ.get('DOCKER_ENABLED', 'False').lower() == 'true'
    DOCKER_IMAGE = os.environ.get('DOCKER_IMAGE', 'python:3.11-alpine')
    DOCKER_MEMORY_LIMIT = os.environ.get('DOCKER_MEMORY_LIMIT', '128m')
    DOCKER_CPU_LIMIT = os.environ.get('DOCKER_CPU_LIMIT', '0.5')

    # Security Settings
    EXECUTION_BLACKLIST = [
        'import os', 'import sys', 'import subprocess', 'import socket',
        '__import__', 'eval', 'exec', 'compile', 'open', 'file',
        'input', 'raw_input', 'reload'
    ]

    MAX_EXECUTION_MEMORY = int(os.environ.get('MAX_EXECUTION_MEMORY', '50'))  # MB
    RESTRICT_NETWORK_ACCESS = True
    RESTRICT_FILE_ACCESS = True

    # Code Comparison Settings
    DIFF_CONTEXT_LINES = int(os.environ.get('DIFF_CONTEXT_LINES', '3'))
    MAX_DIFF_SIZE = int(os.environ.get('MAX_DIFF_SIZE', '1048576'))  # 1MB
    DIFF_ALGORITHMS = ['unified', 'context', 'side-by-side']

    # Analytics & Performance
    ENABLE_PERFORMANCE_MONITORING = os.environ.get('ENABLE_PERF_MONITORING', 'True').lower() == 'true'
    ANALYTICS_RETENTION_DAYS = int(os.environ.get('ANALYTICS_RETENTION_DAYS', '90'))

    # Rate Limiting for Code Execution
    EXECUTION_RATE_LIMIT = {
        'free_tier': '10/hour',
        'premium_tier': '100/hour',
        'enterprise_tier': '1000/hour'
    }

    # Redis Configuration for Caching
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))
    REDIS_DB = int(os.environ.get('REDIS_DB', '0'))
    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)

    # Celery Configuration for Background Tasks
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

    # Dashboard Settings
    DEFAULT_THEME = os.environ.get('DEFAULT_THEME', 'dark')
    ENABLE_THEME_CUSTOMIZATION = True
    MAX_CUSTOM_THEMES = int(os.environ.get('MAX_CUSTOM_THEMES', '5'))

    # Editor Settings
    SUPPORTED_EDITOR_THEMES = [
        'vs-dark', 'vs-light', 'hc-black', 'monokai', 'dracula',
        'github-dark', 'github-light', 'solarized-dark', 'solarized-light'
    ]

    SUPPORTED_FONTS = [
        'Fira Code', 'Monaco', 'Consolas', 'Ubuntu Mono',
        'Source Code Pro', 'JetBrains Mono', 'Cascadia Code'
    ]

    # WebSocket Configuration
    SOCKETIO_REDIS_URL = os.environ.get("SOCKETIO_REDIS_URL") or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    SOCKETIO_CORS_ALLOWED_ORIGINS = "*"
    SOCKETIO_ASYNC_MODE = "eventlet"

    # File Upload Settings for Execution
    MAX_UPLOAD_SIZE = int(os.environ.get('MAX_UPLOAD_SIZE', '5242880'))  # 5MB
    ALLOWED_UPLOAD_EXTENSIONS = {'.py', '.js', '.ts', '.sql', '.sh', '.json', '.yaml', '.yml'}

    # API Settings
    API_RATE_LIMIT = os.environ.get('API_RATE_LIMIT', '1000/hour')
    MAX_SNIPPET_SIZE = int(os.environ.get('MAX_SNIPPET_SIZE', '1048576'))  # 1MB
    MAX_COLLECTION_SIZE = int(os.environ.get('MAX_COLLECTION_SIZE', '1000'))  # snippets per collection

    # Database Configuration
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL") or "sqlite:///code_snippets.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
    }

    # JWT settings
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

    # CORS settings
    CORS_ORIGINS = [
        "chrome-extension://*",
        "http://localhost:3000",
        "http://localhost:5000",
        "http://127.0.0.1:5000",
    ]

    # Rate limiting
    RATELIMIT_STORAGE_URL = os.environ.get("REDIS_URL") or "memory://"

    # Redis Configuration (for WebSocket and caching)
    REDIS_URL = os.environ.get("REDIS_URL") or "redis://localhost:6379/0"

    # Pagination
    SNIPPETS_PER_PAGE = 20
    COLLECTIONS_PER_PAGE = 12

    # Search settings
    SEARCH_RESULTS_LIMIT = 50

    # Plan limits
    FREE_PLAN_SNIPPET_LIMIT = 100
    FREE_PLAN_COLLECTION_LIMIT = 10
    PRO_PLAN_SNIPPET_LIMIT = -1  # Unlimited
    PRO_PLAN_COLLECTION_LIMIT = -1  # Unlimited

    # PHASE 3 ADDITIONS - Search Engine Configuration
    SEARCH_MAX_RESULTS = int(os.environ.get("SEARCH_MAX_RESULTS", 100))
    SEARCH_HIGHLIGHT_MATCHES = (
        os.environ.get("SEARCH_HIGHLIGHT_MATCHES", "true").lower() == "true"
    )
    SEARCH_MIN_QUERY_LENGTH = int(os.environ.get("SEARCH_MIN_QUERY_LENGTH", 2))
    SEARCH_FUZZY_THRESHOLD = float(os.environ.get("SEARCH_FUZZY_THRESHOLD", 0.6))

    # Syntax Highlighting Configuration
    HIGHLIGHT_THEME = os.environ.get("HIGHLIGHT_THEME", "github")
    HIGHLIGHT_LINE_NUMBERS = (
        os.environ.get("HIGHLIGHT_LINE_NUMBERS", "true").lower() == "true"
    )
    HIGHLIGHT_TAB_SIZE = int(os.environ.get("HIGHLIGHT_TAB_SIZE", 4))
    HIGHLIGHT_WRAP_LONG_LINES = (
        os.environ.get("HIGHLIGHT_WRAP_LONG_LINES", "false").lower() == "true"
    )

    # Language Detection Configuration
    LANGUAGE_DETECTION_THRESHOLD = float(
        os.environ.get("LANGUAGE_DETECTION_THRESHOLD", 0.8)
    )
    AUTO_TAGGING_ENABLED = (
        os.environ.get("AUTO_TAGGING_ENABLED", "true").lower() == "true"
    )
    MAX_AUTO_TAGS = int(os.environ.get("MAX_AUTO_TAGS", 5))

    # Export Service Configuration
    EXPORT_FORMATS = os.environ.get("EXPORT_FORMATS", "json,markdown,zip,csv").split(
        ","
    )
    MAX_EXPORT_SIZE = int(
        os.environ.get("MAX_EXPORT_SIZE", 50)
    )  # Max snippets per export
    MAX_EXPORT_FILE_SIZE = int(
        os.environ.get("MAX_EXPORT_FILE_SIZE", 10 * 1024 * 1024)
    )  # 10MB
    EXPORT_TEMP_DIR = os.environ.get("EXPORT_TEMP_DIR", "temp/exports")
    EXPORT_CLEANUP_HOURS = int(os.environ.get("EXPORT_CLEANUP_HOURS", 24))

    # Snippet Analytics Configuration
    ANALYTICS_ENABLED = os.environ.get("ANALYTICS_ENABLED", "true").lower() == "true"
    ANALYTICS_RETENTION_DAYS = int(os.environ.get("ANALYTICS_RETENTION_DAYS", 90))

    # Performance Configuration
    SNIPPET_CACHE_TIMEOUT = int(
        os.environ.get("SNIPPET_CACHE_TIMEOUT", 300)
    )  # 5 minutes
    SEARCH_CACHE_TIMEOUT = int(
        os.environ.get("SEARCH_CACHE_TIMEOUT", 600)
    )  # 10 minutes

    # File Upload Configuration
    MAX_CONTENT_LENGTH = int(
        os.environ.get("MAX_CONTENT_LENGTH", 5 * 1024 * 1024)
    )  # 5MB
    ALLOWED_EXTENSIONS = os.environ.get("ALLOWED_EXTENSIONS", "json,md,txt,zip").split(
        ","
    )

    # Rate Limiting Configuration

    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "100 per hour")
    RATELIMIT_SEARCH = os.environ.get("RATELIMIT_SEARCH", "50 per minute")
    RATELIMIT_EXPORT = os.environ.get("RATELIMIT_EXPORT", "10 per hour")
    # Search Engine Configuration
    ELASTICSEARCH_URL = os.environ.get("ELASTICSEARCH_URL") or None
    SEARCH_BACKEND = "whoosh"  # fallback to whoosh if elasticsearch not available
    WHOOSH_BASE = os.path.join(os.path.dirname(__file__), "search.db")

    # Export Service Configuration
    EXPORT_FORMATS = ["json", "markdown", "html", "txt", "csv"]
    MAX_EXPORT_SIZE = 50 * 1024 * 1024  # 50MB
    EXPORT_TIMEOUT = 300  # 5 minutes

    # Code Execution Configuration (Sandboxed)
    EXECUTION_ENABLED = os.environ.get("EXECUTION_ENABLED", "false").lower() == "true"
    EXECUTION_TIMEOUT = 10  # seconds
    EXECUTION_MEMORY_LIMIT = "128m"
    DOCKER_EXECUTION = True
    SUPPORTED_LANGUAGES = [
        "python",
        "javascript",
        "java",
        "c",
        "cpp",
        "go",
        "rust",
        "php",
        "ruby",
        "shell",
        "sql",
    ]

    # File Upload Configuration
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
    ALLOWED_EXTENSIONS = {"txt", "py", "js", "html", "css", "json", "md", "yml", "yaml"}

    # Rate Limiting Configuration
    RATELIMIT_STORAGE_URL = REDIS_URL
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_DEFAULT = "1000 per hour"
    RATELIMIT_PER_METHOD = True

    # Security Configuration
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # CORS Configuration
    CORS_ORIGINS = [
        "chrome-extension://*",
        "http://localhost:3000",
        "http://localhost:5000",
        "https://code-snippet-manager.com",
    ]

    # Analytics Configuration
    ANALYTICS_ENABLED = os.environ.get("ANALYTICS_ENABLED", "true").lower() == "true"
    ANALYTICS_BATCH_SIZE = 100
    ANALYTICS_FLUSH_INTERVAL = 300  # 5 minutes

    # **NEW: Integration API Configuration**
    # GitHub Integration
    GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET")
    GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET")
    GITHUB_API_BASE_URL = "https://api.github.com"
    GITHUB_OAUTH_SCOPE = "repo,user:email"

    # Slack Integration
    SLACK_CLIENT_ID = os.environ.get("SLACK_CLIENT_ID")
    SLACK_CLIENT_SECRET = os.environ.get("SLACK_CLIENT_SECRET")
    SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
    SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
    SLACK_API_BASE_URL = "https://slack.com/api"

    # Discord Integration
    DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID")
    DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET")
    DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
    DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

    # VS Code Extension Integration
    VSCODE_EXTENSION_ID = "code-snippet-manager"
    VSCODE_MARKETPLACE_URL = "https://marketplace.visualstudio.com"

    # JetBrains Plugin Integration
    JETBRAINS_PLUGIN_ID = "com.codesnippetmanager.plugin"
    JETBRAINS_MARKETPLACE_URL = "https://plugins.jetbrains.com"

    # **NEW: Webhook Configuration**
    WEBHOOK_SECRET_KEY = os.environ.get("WEBHOOK_SECRET_KEY") or "webhook-secret-key"
    WEBHOOK_TIMEOUT = 30  # seconds
    WEBHOOK_RETRY_ATTEMPTS = 3
    WEBHOOK_RETRY_DELAY = 5  # seconds
    WEBHOOK_MAX_PAYLOAD_SIZE = 1024 * 1024  # 1MB

    # Supported Webhook Events
    WEBHOOK_EVENTS = [
        "snippet.created",
        "snippet.updated",
        "snippet.deleted",
        "collection.created",
        "collection.updated",
        "collection.deleted",
        "team.member_added",
        "team.member_removed",
        "user.authenticated",
        "integration.connected",
        "integration.disconnected",
    ]

    # **NEW: Third-party Service Integration**
    # Pastebin Integration
    PASTEBIN_API_KEY = os.environ.get("PASTEBIN_API_KEY")
    PASTEBIN_USERNAME = os.environ.get("PASTEBIN_USERNAME")
    PASTEBIN_PASSWORD = os.environ.get("PASTEBIN_PASSWORD")

    # GitHub Gist Integration
    GIST_PERSONAL_ACCESS_TOKEN = os.environ.get("GIST_PERSONAL_ACCESS_TOKEN")

    # CodePen Integration
    CODEPEN_CLIENT_ID = os.environ.get("CODEPEN_CLIENT_ID")
    CODEPEN_CLIENT_SECRET = os.environ.get("CODEPEN_CLIENT_SECRET")

    # Repl.it Integration
    REPLIT_CLIENT_ID = os.environ.get("REPLIT_CLIENT_ID")
    REPLIT_CLIENT_SECRET = os.environ.get("REPLIT_CLIENT_SECRET")

    # **NEW: Advanced Feature Configuration**
    # AI/ML Integration for Smart Features
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    OPENAI_MODEL = "gpt-3.5-turbo"
    AI_FEATURES_ENABLED = (
        os.environ.get("AI_FEATURES_ENABLED", "false").lower() == "true"
    )

    # Code Analysis Features
    CODE_ANALYSIS_ENABLED = True
    DUPLICATE_DETECTION_THRESHOLD = 0.85  # 85% similarity
    AUTO_TAGGING_CONFIDENCE = 0.7

    # Performance Monitoring
    SENTRY_DSN = os.environ.get("SENTRY_DSN")
    MONITORING_ENABLED = os.environ.get("MONITORING_ENABLED", "false").lower() == "true"

    # CDN Configuration
    CDN_DOMAIN = os.environ.get("CDN_DOMAIN")
    STATIC_URL_PATH = "/static"

    # Email Configuration (for notifications)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER")

    # Team Features Configuration
    MAX_TEAM_SIZE = int(os.environ.get("MAX_TEAM_SIZE", "50"))
    MAX_TEAMS_PER_USER = int(os.environ.get("MAX_TEAMS_PER_USER", "5"))
    TEAM_INVITATION_EXPIRY = timedelta(days=7)

    # Collaboration Features
    COLLABORATIVE_EDITING_ENABLED = True
    MAX_CONCURRENT_EDITORS = 10
    CONFLICT_RESOLUTION_STRATEGY = "last_write_wins"  # or 'operational_transform'

    # Backup Configuration
    BACKUP_ENABLED = os.environ.get("BACKUP_ENABLED", "false").lower() == "true"
    BACKUP_INTERVAL = int(os.environ.get("BACKUP_INTERVAL", "3600"))  # seconds
    BACKUP_RETENTION_DAYS = int(os.environ.get("BACKUP_RETENTION_DAYS", "30"))

    # Feature Flags
    FEATURE_FLAGS = {
        "advanced_search": True,
        "code_execution": EXECUTION_ENABLED,
        "team_collaboration": True,
        "webhook_support": True,
        "ai_suggestions": AI_FEATURES_ENABLED,
        "real_time_sync": True,
        "bulk_operations": True,
        "version_history": True,
        "integration_marketplace": True,
        "custom_themes": True,
        "mobile_app_sync": False,  # Future feature
        "blockchain_verification": False,  # Future feature
    }

    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "static", "uploads"
    )
    AVATAR_FOLDER = os.path.join(UPLOAD_FOLDER, "avatars")

    # Allowed file extensions
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

    # Create upload directories
    @staticmethod
    def init_app(app):
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.AVATAR_FOLDER, exist_ok=True)


class DevelopmentConfig(Config):
    """Development configuration"""

    DEBUG = True
    TESTING = False

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL"
    ) or "sqlite:///" + os.path.join(
        os.path.dirname(__file__), "data", "dev_snippets.db"
    )

    # Create data directory if it doesn't exist
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    # Logging
    LOG_LEVEL = "DEBUG"

    # Development-specific settings
    TEMPLATES_AUTO_RELOAD = True
    EXPLAIN_TEMPLATE_LOADING = False


class ProductionConfig(Config):
    """Production configuration"""

    DEBUG = False
    TESTING = False

    # Database - Use PostgreSQL in production
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL")
        or "postgresql://user:password@localhost/snippet_manager"
    )

    # Security
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Logging
    LOG_LEVEL = "INFO"

    # Performance
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,
        "pool_recycle": 120,
        "pool_pre_ping": True,
        "max_overflow": 20,
    }


class TestingConfig(Config):
    """Testing configuration"""

    DEBUG = True
    TESTING = True

    # Use in-memory database for testing
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False

    # Faster password hashing for tests
    BCRYPT_LOG_ROUNDS = 4

    # Logging
    LOG_LEVEL = "ERROR"


# Configuration mapping
config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
