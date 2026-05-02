# flask-server/app/utils/__init__.py
"""
Utils package initialization
Provides centralized access to all utility functions and validators
"""

from .validators import (
    # Schema classes
    SnippetCreateSchema,
    SnippetUpdateSchema,
    SnippetSearchSchema,
    CollectionCreateSchema,
    CollectionUpdateSchema,
    UserRegistrationSchema,
    UserLoginSchema,
    UserUpdateSchema,
    ExportSchema,
    # Validation decorators
    validate_json,
    validate_query_params,
    # Utility validation functions
    is_valid_object_id,
    sanitize_filename,
    validate_file_upload,
)

from .helpers import (
    # Security functions
    generate_secure_token,
    generate_hash,
    # Formatting functions
    generate_snippet_slug,
    format_file_size,
    format_datetime,
    truncate_text,
    # Content analysis
    extract_code_info,
    parse_tags,
    # URL generation
    generate_public_url,
    # File handling
    safe_filename,
    get_mime_type,
    is_safe_url,
    # Database helpers
    paginate_query,
    build_search_query,
    apply_sorting,
    # Response helpers
    json_response,
    error_response,
    # Activity tracking
    log_user_activity,
    cleanup_expired_tokens,
)

# Export all utilities for easy importing
__all__ = [
    # Validation schemas
    "SnippetCreateSchema",
    "SnippetUpdateSchema",
    "SnippetSearchSchema",
    "CollectionCreateSchema",
    "CollectionUpdateSchema",
    "UserRegistrationSchema",
    "UserLoginSchema",
    "UserUpdateSchema",
    "ExportSchema",
    # Validation decorators
    "validate_json",
    "validate_query_params",
    # Validation utilities
    "is_valid_object_id",
    "sanitize_filename",
    "validate_file_upload",
    # Helper functions
    "generate_secure_token",
    "generate_hash",
    "generate_snippet_slug",
    "format_file_size",
    "format_datetime",
    "truncate_text",
    "extract_code_info",
    "parse_tags",
    "generate_public_url",
    "safe_filename",
    "get_mime_type",
    "is_safe_url",
    "paginate_query",
    "build_search_query",
    "apply_sorting",
    "json_response",
    "error_response",
    "log_user_activity",
    "cleanup_expired_tokens",
]

# Common validation patterns
VALIDATION_PATTERNS = {
    "username": r"^[a-zA-Z0-9_-]{3,50}$",
    "tag": r"^[a-zA-Z0-9_-]+$",
    "slug": r"^[a-zA-Z0-9_-]+$",
    "language_code": r"^[a-z]{2,10}$",
}

# Common constants
CONSTANTS = {
    "MAX_SNIPPET_LENGTH": 50000,
    "MAX_TITLE_LENGTH": 200,
    "MAX_DESCRIPTION_LENGTH": 1000,
    "MAX_TAG_LENGTH": 50,
    "MAX_TAGS_PER_SNIPPET": 20,
    "MAX_COLLECTION_NAME_LENGTH": 100,
    "DEFAULT_PAGE_SIZE": 20,
    "MAX_PAGE_SIZE": 100,
    "TOKEN_LENGTH": 32,
    "HASH_ALGORITHM": "sha256",
}

# Supported languages for syntax highlighting
SUPPORTED_LANGUAGES = [
    "javascript",
    "python",
    "java",
    "cpp",
    "c",
    "csharp",
    "php",
    "ruby",
    "go",
    "rust",
    "swift",
    "kotlin",
    "typescript",
    "html",
    "css",
    "scss",
    "sql",
    "bash",
    "powershell",
    "json",
    "xml",
    "yaml",
    "markdown",
    "dockerfile",
    "nginx",
    "apache",
    "plaintext",
]

# Export formats supported
EXPORT_FORMATS = {
    "json": {
        "mime_type": "application/json",
        "extension": ".json",
        "description": "JSON format with full metadata",
    },
    "markdown": {
        "mime_type": "text/markdown",
        "extension": ".md",
        "description": "Markdown format for documentation",
    },
    "zip": {
        "mime_type": "application/zip",
        "extension": ".zip",
        "description": "ZIP archive with individual files",
    },
    "csv": {
        "mime_type": "text/csv",
        "extension": ".csv",
        "description": "CSV format for spreadsheet import",
    },
}


def get_validation_schema(schema_name):
    """
    Get validation schema by name

    Args:
        schema_name (str): Name of the schema

    Returns:
        Schema class or None
    """
    schema_map = {
        "snippet_create": SnippetCreateSchema,
        "snippet_update": SnippetUpdateSchema,
        "snippet_search": SnippetSearchSchema,
        "collection_create": CollectionCreateSchema,
        "collection_update": CollectionUpdateSchema,
        "user_registration": UserRegistrationSchema,
        "user_login": UserLoginSchema,
        "user_update": UserUpdateSchema,
        "export": ExportSchema,
    }

    return schema_map.get(schema_name)


def validate_against_pattern(value, pattern_name):
    """
    Validate value against predefined pattern

    Args:
        value (str): Value to validate
        pattern_name (str): Name of pattern to use

    Returns:
        bool: True if valid
    """
    import re

    pattern = VALIDATION_PATTERNS.get(pattern_name)
    if not pattern:
        return False

    return bool(re.match(pattern, str(value)))


def get_supported_export_formats():
    """
    Get list of supported export formats

    Returns:
        list: List of format info dictionaries
    """
    return [
        {
            "format": fmt,
            "mime_type": info["mime_type"],
            "extension": info["extension"],
            "description": info["description"],
        }
        for fmt, info in EXPORT_FORMATS.items()
    ]


def get_language_info(language_code):
    """
    Get information about a programming language

    Args:
        language_code (str): Language code

    Returns:
        dict: Language information
    """
    language_map = {
        "javascript": {
            "name": "JavaScript",
            "category": "web",
            "extensions": [".js", ".mjs"],
        },
        "python": {
            "name": "Python",
            "category": "general",
            "extensions": [".py", ".pyw"],
        },
        "java": {"name": "Java", "category": "general", "extensions": [".java"]},
        "cpp": {
            "name": "C++",
            "category": "systems",
            "extensions": [".cpp", ".cc", ".cxx"],
        },
        "c": {"name": "C", "category": "systems", "extensions": [".c", ".h"]},
        "csharp": {"name": "C#", "category": "general", "extensions": [".cs"]},
        "php": {"name": "PHP", "category": "web", "extensions": [".php"]},
        "ruby": {"name": "Ruby", "category": "general", "extensions": [".rb"]},
        "go": {"name": "Go", "category": "systems", "extensions": [".go"]},
        "rust": {"name": "Rust", "category": "systems", "extensions": [".rs"]},
        "swift": {"name": "Swift", "category": "mobile", "extensions": [".swift"]},
        "kotlin": {"name": "Kotlin", "category": "mobile", "extensions": [".kt"]},
        "typescript": {
            "name": "TypeScript",
            "category": "web",
            "extensions": [".ts", ".tsx"],
        },
        "html": {"name": "HTML", "category": "web", "extensions": [".html", ".htm"]},
        "css": {"name": "CSS", "category": "web", "extensions": [".css"]},
        "sql": {"name": "SQL", "category": "database", "extensions": [".sql"]},
        "bash": {"name": "Bash", "category": "shell", "extensions": [".sh", ".bash"]},
        "markdown": {
            "name": "Markdown",
            "category": "markup",
            "extensions": [".md", ".markdown"],
        },
        "json": {"name": "JSON", "category": "data", "extensions": [".json"]},
        "yaml": {"name": "YAML", "category": "data", "extensions": [".yml", ".yaml"]},
        "xml": {"name": "XML", "category": "markup", "extensions": [".xml"]},
    }

    return language_map.get(
        language_code,
        {"name": language_code.title(), "category": "other", "extensions": []},
    )
