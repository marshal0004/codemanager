# flask-server/app/utils/helpers.py
"""
General utility functions used throughout the application
Provides common functionality for data processing, formatting, and operations
"""

import os
import re
import json
import hashlib
import secrets
import mimetypes
from datetime import datetime, timedelta
from urllib.parse import urlparse, quote, urljoin  # <-- Add urljoin here
from flask import current_app, url_for, request  # <-- Add request here
from werkzeug.utils import secure_filename
from sqlalchemy import or_  # <-- Add this line
from app.models.snippet import Snippet


def generate_secure_token(length=32):
    """
    Generate a cryptographically secure random token

    Args:
        length (int): Length of the token to generate

    Returns:
        str: Secure random token
    """
    return secrets.token_urlsafe(length)


def generate_hash(content):
    """
    Generate SHA-256 hash of content for duplicate detection

    Args:
        content (str): Content to hash

    Returns:
        str: SHA-256 hash hex digest
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def generate_snippet_slug(title, max_length=50):
    """
    Generate URL-friendly slug from snippet title

    Args:
        title (str): Snippet title
        max_length (int): Maximum length of slug

    Returns:
        str: URL-friendly slug
    """
    # Convert to lowercase and replace spaces with hyphens
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[-\s]+", "-", slug)

    # Trim to max length and remove trailing hyphens
    slug = slug[:max_length].strip("-")

    return slug if slug else "untitled"


def format_file_size(size_bytes):
    """
    Format file size in human-readable format

    Args:
        size_bytes (int): Size in bytes

    Returns:
        str: Formatted size (e.g., "1.5 KB", "2.3 MB")
    """
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1

    return f"{size_bytes:.1f} {size_names[i]}"


def format_datetime(dt, format_type="relative"):
    """
    Format datetime for display

    Args:
        dt (datetime): Datetime object
        format_type (str): 'relative', 'short', or 'full'

    Returns:
        str: Formatted datetime string
    """
    if not dt:
        return "Never"

    if format_type == "relative":
        now = datetime.utcnow()
        diff = now - dt

        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            return "Just now"

    elif format_type == "short":
        return dt.strftime("%Y-%m-%d %H:%M")

    elif format_type == "full":
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    return str(dt)


def truncate_text(text, max_length=100, suffix="..."):
    """
    Truncate text to specified length with suffix

    Args:
        text (str): Text to truncate
        max_length (int): Maximum length
        suffix (str): Suffix to add if truncated

    Returns:
        str: Truncated text
    """
    if not text or len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def extract_code_info(content):
    """
    Extract useful information from code content

    Args:
        content (str): Code content

    Returns:
        dict: Code information (lines, chars, estimated_language)
    """
    lines = content.split("\n")
    line_count = len(lines)
    char_count = len(content)

    # Simple language detection based on patterns
    estimated_language = "plaintext"

    # Check for common patterns
    if re.search(r"def\s+\w+\s*\(.*\):", content):
        estimated_language = "python"
    elif re.search(r"function\s+\w+\s*\(.*\)\s*{", content):
        estimated_language = "javascript"
    elif re.search(r"public\s+class\s+\w+", content):
        estimated_language = "java"
    elif re.search(r"#include\s*<", content):
        estimated_language = "cpp"
    elif re.search(r"<\?php", content):
        estimated_language = "php"
    elif re.search(r"<html|<div|<span", content, re.IGNORECASE):
        estimated_language = "html"
    elif re.search(r"SELECT\s+.*\s+FROM", content, re.IGNORECASE):
        estimated_language = "sql"

    return {
        "line_count": line_count,
        "char_count": char_count,
        "estimated_language": estimated_language,
        "has_imports": bool(
            re.search(r"import\s+|from\s+.*\s+import|#include|require\s*\(", content)
        ),
        "has_functions": bool(
            re.search(r"def\s+|function\s+|public\s+.*\s+\w+\s*\(", content)
        ),
    }


def generate_public_url(snippet_id, token=None):
    """
    Generate public sharing URL for snippet

    Args:
        snippet_id (int): Snippet ID
        token (str): Optional security token

    Returns:
        str: Public URL
    """
    if token:
        return url_for(
            "snippets.public_snippet", id=snippet_id, token=token, _external=True
        )
    else:
        return url_for("snippets.view_snippet", id=snippet_id, _external=True)


def parse_tags(tags_input):
    """
    Parse tags from various input formats

    Args:
        tags_input: Tags as string, list, or comma-separated

    Returns:
        list: Cleaned and deduplicated tags
    """
    if not tags_input:
        return []

    if isinstance(tags_input, str):
        # Split by comma or space
        tags = re.split(r"[,\s]+", tags_input.strip())
    elif isinstance(tags_input, list):
        tags = tags_input
    else:
        return []

    # Clean and validate tags
    cleaned_tags = []
    for tag in tags:
        tag = str(tag).strip().lower()
        if tag and re.match(r"^[a-zA-Z0-9_-]+$", tag) and len(tag) <= 50:
            cleaned_tags.append(tag)

    # Remove duplicates while preserving order
    return list(dict.fromkeys(cleaned_tags))


def safe_filename(filename):
    """
    Generate safe filename for downloads

    Args:
        filename (str): Original filename

    Returns:
        str: Safe filename
    """
    # Use werkzeug's secure_filename and add timestamp if needed
    safe_name = secure_filename(filename)

    if not safe_name:
        safe_name = f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    return safe_name


def paginate_query(query, page, per_page, max_per_page=100):
    """
    Helper for pagination with safety limits

    Args:
        query: SQLAlchemy query object
        page (int): Page number
        per_page (int): Items per page
        max_per_page (int): Maximum allowed items per page

    Returns:
        dict: Pagination info and items
    """
    # Enforce limits
    page = max(1, page)
    per_page = min(max_per_page, max(1, per_page))

    # Get total count
    total = query.count()

    # Calculate pagination info
    total_pages = (total - 1) // per_page + 1 if total > 0 else 1
    has_prev = page > 1
    has_next = page < total_pages

    # Get items for current page
    items = query.offset((page - 1) * per_page).limit(per_page).all()

    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_prev": has_prev,
        "has_next": has_next,
        "prev_page": page - 1 if has_prev else None,
        "next_page": page + 1 if has_next else None,
    }


def build_search_query(base_query, search_params):
    """
    Build search query with filters

    Args:
        base_query: Base SQLAlchemy query
        search_params (dict): Search parameters

    Returns:
        SQLAlchemy query: Filtered query
    """
    query = base_query

    # Text search
    if search_params.get("query"):
        search_term = f"%{search_params['query']}%"
        query = query.filter(
            or_(
                Snippet.title.ilike(search_term),
                Snippet.content.ilike(search_term),
                Snippet.description.ilike(search_term),
            )
        )

    # Language filter
    if search_params.get("language"):
        query = query.filter(Snippet.language == search_params["language"])

    # Tags filter
    if search_params.get("tags"):
        for tag in search_params["tags"]:
            query = query.filter(Snippet.tags.contains([tag]))

    # Collection filter
    if search_params.get("collection_id"):
        query = query.filter(Snippet.collection_id == search_params["collection_id"])

    # Public/private filter
    if "is_public" in search_params:
        query = query.filter(Snippet.is_public == search_params["is_public"])

    # Date range filter
    if search_params.get("date_from"):
        query = query.filter(Snippet.created_at >= search_params["date_from"])

    if search_params.get("date_to"):
        query = query.filter(Snippet.created_at <= search_params["date_to"])

    return query


def apply_sorting(query, sort_by="created_at", sort_order="desc"):
    """
    Apply sorting to query

    Args:
        query: SQLAlchemy query
        sort_by (str): Field to sort by
        sort_order (str): 'asc' or 'desc'

    Returns:
        SQLAlchemy query: Sorted query
    """
    from sqlalchemy import desc, asc
    from app.models.snippet import Snippet

    # Map sort fields to model attributes
    sort_fields = {
        "created_at": Snippet.created_at,
        "updated_at": Snippet.updated_at,
        "title": Snippet.title,
        "language": Snippet.language,
        "views": getattr(
            Snippet, "view_count", Snippet.created_at
        ),  # Fallback if views not implemented
    }

    sort_field = sort_fields.get(sort_by, Snippet.created_at)

    if sort_order.lower() == "asc":
        return query.order_by(asc(sort_field))
    else:
        return query.order_by(desc(sort_field))


def json_response(data=None, message=None, status="success", status_code=200):
    """
    Create standardized JSON response

    Args:
        data: Response data
        message (str): Response message
        status (str): Response status
        status_code (int): HTTP status code

    Returns:
        tuple: (response_dict, status_code)
    """
    response = {"status": status, "timestamp": datetime.utcnow().isoformat() + "Z"}

    if message:
        response["message"] = message

    if data is not None:
        response["data"] = data

    return response, status_code


def error_response(message, details=None, status_code=400):
    """
    Create standardized error response

    Args:
        message (str): Error message
        details: Additional error details
        status_code (int): HTTP status code

    Returns:
        tuple: (response_dict, status_code)
    """
    response = {
        "status": "error",
        "message": message,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    if details:
        response["details"] = details

    return response, status_code


def log_user_activity(user_id, action, resource_type, resource_id=None, details=None):
    """
    Log user activity for analytics

    Args:
        user_id (int): User ID
        action (str): Action performed
        resource_type (str): Type of resource
        resource_id (int): Resource ID
        details (dict): Additional details
    """
    try:
        # This would integrate with your analytics system
        activity_log = {
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "timestamp": datetime.utcnow(),
            "ip_address": request.remote_addr if "request" in globals() else None,
        }

        # Log to file or database
        current_app.logger.info(
            f"User Activity: {json.dumps(activity_log, default=str)}"
        )

    except Exception as e:
        current_app.logger.error(f"Failed to log user activity: {str(e)}")


def cleanup_expired_tokens():
    """
    Clean up expired sharing tokens and temporary data
    This would be called by a scheduled task
    """
    try:
        from app.models.snippet import Snippet
        from app import db

        # Remove expired public tokens (older than 30 days)
        expire_date = datetime.utcnow() - timedelta(days=30)

        expired_snippets = Snippet.query.filter(
            Snippet.public_token.isnot(None),
            Snippet.updated_at < expire_date,
            Snippet.is_public == False,
        ).all()

        for snippet in expired_snippets:
            snippet.public_token = None

        db.session.commit()

        return len(expired_snippets)

    except Exception as e:
        current_app.logger.error(f"Failed to cleanup expired tokens: {str(e)}")
        return 0


def get_mime_type(filename):
    """
    Get MIME type for file

    Args:
        filename (str): Filename

    Returns:
        str: MIME type
    """
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"


def is_safe_url(target):
    """
    Check if URL is safe for redirects

    Args:
        target (str): Target URL

    Returns:
        bool: True if safe
    """
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


# Replace the get_user_preferences function in helpers.py
def get_user_preferences(user_id):
    """
    Get user preferences with defaults

    Args:
        user_id: User ID

    Returns:
        dict: User preferences
    """
    try:
        from app.models.user import User

        user = User.query.get(user_id)
        if not user:
            print(f"User {user_id} not found for preferences")
            return {
                "theme": "dark",
                "default_language": "javascript",
                "snippets_per_page": 20,
                "auto_save": True,
                "syntax_highlighting": True,
                "show_line_numbers": True,
                "notifications_enabled": True,
            }

        # Create a default preferences dictionary
        prefs = {
            "theme": "dark",
            "default_language": "javascript",
            "snippets_per_page": 20,
            "auto_save": True,
            "syntax_highlighting": True,
            "show_line_numbers": True,
            "notifications_enabled": True,
        }

        # Update with user's actual preferences if available
        if hasattr(user, "theme_preference"):
            prefs["theme"] = user.theme_preference or "dark"

        if hasattr(user, "snippets_per_page"):
            prefs["snippets_per_page"] = user.snippets_per_page or 20

        if hasattr(user, "auto_save_enabled"):
            prefs["auto_save"] = user.auto_save_enabled

        if hasattr(user, "email_notifications"):
            prefs["notifications_enabled"] = user.email_notifications

        print(f"Retrieved preferences for user {user_id}")
        return prefs

    except Exception as e:
        print(f"Error getting user preferences: {str(e)}")
        import traceback

        traceback.print_exc()
        return {
            "theme": "dark",
            "default_language": "javascript",
            "snippets_per_page": 20,
            "auto_save": True,
            "syntax_highlighting": True,
            "show_line_numbers": True,
            "notifications_enabled": True,
        }


def update_user_activity(user_id, activity_type, metadata=None):
    """
    Update user activity tracking

    Args:
        user_id (int): User ID
        activity_type (str): Type of activity
        metadata (dict): Additional activity metadata

    Returns:
        bool: Success status
    """
    try:
        from app.models.user import User
        from app import db

        user = User.query.get(user_id)
        if not user:
            return False

        # Update last activity timestamp
        user.last_activity = datetime.utcnow()

        # Update activity metadata if user model supports it
        if hasattr(user, "activity_log"):
            if not user.activity_log:
                user.activity_log = []

            activity_entry = {
                "type": activity_type,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": metadata or {},
                "ip_address": (
                    getattr(request, "remote_addr", None)
                    if "request" in globals()
                    else None
                ),
            }

            # Keep only last 100 activities
            user.activity_log.append(activity_entry)
            if len(user.activity_log) > 100:
                user.activity_log = user.activity_log[-100:]

        db.session.commit()

        # Log activity for analytics
        log_user_activity(user_id, activity_type, "user", user_id, metadata)

        return True

    except Exception as e:
        current_app.logger.error(f"Failed to update user activity: {str(e)}")
        return False


# Add this to helpers.py
def update_user_activity_simple(user_id):
    """
    Simple version that just updates the last activity timestamp

    Args:
        user_id: User ID

    Returns:
        bool: Success status
    """
    try:
        from app.models.user import User
        from app import db

        user = User.query.get(user_id)
        if not user:
            print(f"User {user_id} not found")
            return False

        # Update last activity timestamp based on available fields
        if hasattr(user, "last_active_at"):
            user.last_active_at = datetime.utcnow()
        elif hasattr(user, "last_active_date"):
            user.last_active_date = datetime.utcnow()

        db.session.commit()
        print(f"Updated activity timestamp for user {user_id}")
        return True

    except Exception as e:
        print(f"Error updating user activity: {str(e)}")
        import traceback

        traceback.print_exc()
        db.session.rollback()
        return False


def get_user_stats(user_id):
    """
    Get user statistics and metrics

    Args:
        user_id (int): User ID

    Returns:
        dict: User statistics
    """
    try:
        from app.models.user import User
        from app.models.snippet import Snippet
        from app.models.collection import Collection
        from app import db

        user = User.query.get(user_id)
        if not user:
            return {}

        # Calculate basic stats
        snippet_count = Snippet.query.filter_by(user_id=user_id).count()
        collection_count = Collection.query.filter_by(user_id=user_id).count()

        # Get recent activity
        recent_snippets = (
            Snippet.query.filter_by(user_id=user_id)
            .filter(Snippet.created_at >= datetime.utcnow() - timedelta(days=7))
            .count()
        )

        # Language breakdown
        language_stats = (
            db.session.query(Snippet.language, db.func.count(Snippet.id))
            .filter_by(user_id=user_id)
            .group_by(Snippet.language)
            .all()
        )

        language_breakdown = {lang: count for lang, count in language_stats}

        return {
            "total_snippets": snippet_count,
            "total_collections": collection_count,
            "recent_snippets": recent_snippets,
            "language_breakdown": language_breakdown,
            "member_since": (
                user.created_at.isoformat() if hasattr(user, "created_at") else None
            ),
            "last_activity": (
                user.last_activity.isoformat()
                if hasattr(user, "last_activity") and user.last_activity
                else None
            ),
        }

    except Exception as e:
        current_app.logger.error(f"Failed to get user stats: {str(e)}")
        return {}


def set_user_preference(user_id, preference_key, preference_value):
    """
    Set a specific user preference

    Args:
        user_id (int): User ID
        preference_key (str): Preference key
        preference_value: Preference value

    Returns:
        bool: Success status
    """
    try:
        from app.models.user import User
        from app import db

        user = User.query.get(user_id)
        if not user:
            return False

        # Initialize preferences if not exists
        if not hasattr(user, "preferences") or not user.preferences:
            user.preferences = {}

        # Handle nested preference keys (e.g., 'notifications.email')
        if "." in preference_key:
            keys = preference_key.split(".")
            current = user.preferences

            # Navigate to parent key
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]

            # Set final value
            current[keys[-1]] = preference_value
        else:
            user.preferences[preference_key] = preference_value

        # Mark as modified for SQLAlchemy
        if hasattr(user, "preferences"):
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(user, "preferences")

        db.session.commit()
        return True

    except Exception as e:
        current_app.logger.error(f"Failed to set user preference: {str(e)}")
        return False
