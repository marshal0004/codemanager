# flask-server/app/services/__init__.py
"""
Services package initialization
Provides centralized access to all application services
"""

from .syntax_highlighter import SyntaxHighlighter
from .snippet_analyzer import SnippetAnalyzer
from .search_engine import SearchEngine
from .export_service import ExportService

# Initialize service instances
syntax_highlighter = SyntaxHighlighter()
snippet_analyzer = SnippetAnalyzer()
search_engine = SearchEngine()
export_service = ExportService()

# Export all services for easy importing
__all__ = [
    "SyntaxHighlighter",
    "SnippetAnalyzer",
    "SearchEngine",
    "ExportService",
    "syntax_highlighter",
    "snippet_analyzer",
    "search_engine",
    "export_service",
]


def initialize_services(app):
    """
    Initialize all services with Flask app configuration

    Args:
        app: Flask application instance
    """
    # Initialize services that need app context
    search_engine.init_app(app)
    export_service.init_app(app)

    # Configure service settings from app config
    if hasattr(app, "config"):
        # Configure syntax highlighter
        syntax_highlighter.configure(
            theme=app.config.get("HIGHLIGHT_THEME", "github"),
            line_numbers=app.config.get("HIGHLIGHT_LINE_NUMBERS", True),
        )

        # Configure snippet analyzer
        snippet_analyzer.configure(
            confidence_threshold=app.config.get("LANGUAGE_DETECTION_THRESHOLD", 0.8),
            auto_tag_enabled=app.config.get("AUTO_TAGGING_ENABLED", True),
        )

        # Configure search engine
        search_engine.configure(
            max_results=app.config.get("SEARCH_MAX_RESULTS", 100),
            highlight_matches=app.config.get("SEARCH_HIGHLIGHT_MATCHES", True),
        )

        # Configure export service
        export_service.configure(
            max_export_size=app.config.get("MAX_EXPORT_SIZE", 50),
            allowed_formats=app.config.get(
                "EXPORT_FORMATS", ["json", "markdown", "zip"]
            ),
        )


def get_service_status():
    """
    Get status information for all services

    Returns:
        dict: Service status information
    """
    return {
        "syntax_highlighter": {
            "available": syntax_highlighter.is_available(),
            "supported_languages": len(syntax_highlighter.get_supported_languages()),
        },
        "snippet_analyzer": {
            "available": snippet_analyzer.is_available(),
            "detection_enabled": snippet_analyzer.language_detection_enabled,
            "tagging_enabled": snippet_analyzer.auto_tagging_enabled,
        },
        "search_engine": {
            "available": search_engine.is_available(),
            "indexed_snippets": search_engine.get_index_count(),
        },
        "export_service": {
            "available": export_service.is_available(),
            "supported_formats": export_service.get_supported_formats(),
        },
    }
