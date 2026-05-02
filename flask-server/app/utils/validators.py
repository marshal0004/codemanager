# flask-server/app/utils/validators.py
"""
Input validation utilities for API endpoints
Provides comprehensive validation for all user inputs
"""

import re
from functools import wraps
from flask import request, jsonify
from marshmallow import Schema, fields, ValidationError, validates, validates_schema

# Constants for validation
MAX_SNIPPET_LENGTH = 50000  # 50KB
MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 1000
MAX_TAG_LENGTH = 50
MAX_TAGS_PER_SNIPPET = 20
MAX_COLLECTION_NAME_LENGTH = 100
ALLOWED_LANGUAGES = [
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
    "sql",
    "bash",
    "powershell",
    "json",
    "xml",
    "yaml",
    "markdown",
    "plaintext",
]


class ValidationMixin:
    """Mixin class for common validation methods"""

    @staticmethod
    def validate_code_content(content):
        """Validate code snippet content"""
        if not content or not isinstance(content, str):
            raise ValidationError("Code content is required and must be a string")

        if len(content.strip()) == 0:
            raise ValidationError("Code content cannot be empty")

        if len(content) > MAX_SNIPPET_LENGTH:
            raise ValidationError(
                f"Code content too long (max {MAX_SNIPPET_LENGTH} characters)"
            )

    @staticmethod
    def validate_language(language):
        """Validate programming language"""
        if language and language.lower() not in ALLOWED_LANGUAGES:
            raise ValidationError(
                f"Unsupported language. Allowed: {', '.join(ALLOWED_LANGUAGES)}"
            )

    @staticmethod
    def validate_tags(tags):
        """Validate tags list"""
        if not isinstance(tags, list):
            raise ValidationError("Tags must be a list")

        if len(tags) > MAX_TAGS_PER_SNIPPET:
            raise ValidationError(f"Too many tags (max {MAX_TAGS_PER_SNIPPET})")

        for tag in tags:
            if not isinstance(tag, str):
                raise ValidationError("All tags must be strings")
            if len(tag) > MAX_TAG_LENGTH:
                raise ValidationError(f"Tag too long (max {MAX_TAG_LENGTH} characters)")
            if not re.match(r"^[a-zA-Z0-9_-]+$", tag):
                raise ValidationError(
                    "Tags can only contain letters, numbers, hyphens, and underscores"
                )


class SnippetCreateSchema(Schema, ValidationMixin):
    """Schema for creating new snippets"""

    title = fields.Str(
        required=True,
        validate=lambda x: len(x.strip()) > 0 and len(x) <= MAX_TITLE_LENGTH,
    )
    code = fields.Str(required=True)  # CHANGED FROM content TO code

    description = fields.Str(
        allow_none=True,
        validate=lambda x: x is None or len(x) <= MAX_DESCRIPTION_LENGTH,
    )
    language = fields.Str(allow_none=True)
    tags = fields.List(fields.Str(), load_default=[])
    is_public = fields.Bool(load_default=False)
    collection_id = fields.Str(allow_none=True)  # Changed to Str for UUID

    @validates("content")
    def validate_content(self, value, **kwargs):  # FIXED: Added **kwargs
        self.validate_code_content(value)

    @validates("language")
    def validate_lang(self, value, **kwargs):  # FIXED: Added **kwargs
        self.validate_language(value)

    @validates("tags")
    def validate_tag_list(self, value, **kwargs):  # FIXED: Added **kwargs
        self.validate_tags(value)


class SnippetUpdateSchema(Schema, ValidationMixin):
    """Schema for updating existing snippets"""

    title = fields.Str(
        validate=lambda x: len(x.strip()) > 0 and len(x) <= MAX_TITLE_LENGTH
    )
    code = fields.Str()
    description = fields.Str(
        allow_none=True,
        validate=lambda x: x is None or len(x) <= MAX_DESCRIPTION_LENGTH,
    )
    language = fields.Str(allow_none=True)
    tags = fields.Raw()  # Accept both string and list
    is_public = fields.Bool()
    collection_id = fields.Str(allow_none=True)

    @validates("code")
    def validate_code(self, value, **kwargs):
        if value is not None:
            self.validate_code_content(value)

    @validates("language")
    def validate_lang(self, value, **kwargs):
        self.validate_language(value)

    @validates("tags")
    def validate_tag_list(self, value, **kwargs):
        if value is not None:
            # Handle both string and list formats
            if isinstance(value, str):
                # Split comma-separated string into list
                if value.strip():  # Only process non-empty strings
                    tag_list = [tag.strip() for tag in value.split(",") if tag.strip()]
                else:
                    tag_list = []
            elif isinstance(value, list):
                tag_list = value
            else:
                raise ValidationError("Tags must be a string or list")

            # Validate the processed list
            if tag_list:  # Only validate if there are tags
                self.validate_tags(tag_list)


class SnippetSearchSchema(Schema):
    """Schema for snippet search parameters"""

    query = fields.Str(allow_none=True)
    language = fields.Str(allow_none=True)
    tags = fields.List(fields.Str(), load_default=[])
    collection_id = fields.Int(allow_none=True)
    is_public = fields.Bool(allow_none=True)
    page = fields.Int(load_default=1, validate=lambda x: x > 0)
    per_page = fields.Int(load_default=20, validate=lambda x: 1 <= x <= 100)
    sort_by = fields.Str(
        load_default="created_at",
        validate=lambda x: x in ["created_at", "updated_at", "title", "language"],
    )
    sort_order = fields.Str(load_default="desc", validate=lambda x: x in ["asc", "desc"])


# Collection Schemas
class CollectionCreateSchema(Schema):
    """Schema for creating new collections"""

    name = fields.Str(
        required=True,
        validate=lambda x: len(x.strip()) > 0 and len(x) <= MAX_COLLECTION_NAME_LENGTH,
    )
    description = fields.Str(
        allow_none=True,
        validate=lambda x: x is None or len(x) <= MAX_DESCRIPTION_LENGTH,
    )
    is_public = fields.Bool(load_default=False)
    parent_id = fields.Int(allow_none=True)
    tags = fields.Str(allow_none=True)  # ADD THIS LINE


class CollectionUpdateSchema(Schema):
    """Schema for updating existing collections"""

    name = fields.Str(
        validate=lambda x: len(x.strip()) > 0 and len(x) <= MAX_COLLECTION_NAME_LENGTH
    )
    description = fields.Str(
        allow_none=True,
        validate=lambda x: x is None or len(x) <= MAX_DESCRIPTION_LENGTH,
    )
    color = fields.Str(allow_none=True)  # ADD THIS LINE - MISSING FIELD
    is_public = fields.Bool()
    parent_id = fields.Int(allow_none=True)
    tags = fields.Str(allow_none=True)


# User Schemas
class UserRegistrationSchema(Schema):
    """Schema for user registration"""

    username = fields.Str(
        required=True, validate=lambda x: len(x.strip()) >= 3 and len(x) <= 50
    )
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=lambda x: len(x) >= 8)

    @validates("username")
    def validate_username(self, value):
        if not re.match(r"^[a-zA-Z0-9_-]+$", value):
            raise ValidationError(
                "Username can only contain letters, numbers, hyphens, and underscores"
            )


class UserLoginSchema(Schema):
    """Schema for user login"""

    email = fields.Email(required=True)
    password = fields.Str(required=True)


class UserUpdateSchema(Schema):
    """Schema for updating user profile"""

    username = fields.Str(validate=lambda x: len(x.strip()) >= 3 and len(x) <= 50)
    email = fields.Email()
    current_password = fields.Str()
    new_password = fields.Str(validate=lambda x: len(x) >= 8)

    @validates_schema
    def validate_password_change(self, data, **kwargs):
        if "new_password" in data and "current_password" not in data:
            raise ValidationError("Current password required to change password")


# Export Schemas
class ExportSchema(Schema):
    """Schema for export requests"""

    format = fields.Str(
        required=True, validate=lambda x: x in ["json", "markdown", "zip", "csv"]
    )
    snippet_ids = fields.List(fields.Int(), allow_none=True)
    collection_ids = fields.List(fields.Int(), allow_none=True)
    include_private = fields.Bool(load_default=False)

    @validates_schema
    def validate_export_data(self, data, **kwargs):
        if not data.get("snippet_ids") and not data.get("collection_ids"):
            raise ValidationError(
                "Either snippet_ids or collection_ids must be provided"
            )


# Validation Decorator
def validate_json(schema_class):
    """
    Decorator to validate JSON input against a schema

    Args:
        schema_class: Marshmallow schema class to validate against
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                if not request.is_json:
                    return (
                        jsonify({"error": "Content-Type must be application/json"}),
                        400,
                    )

                schema = schema_class()
                data = schema.load(request.get_json())

                # Add validated data to kwargs
                kwargs["validated_data"] = data
                return f(*args, **kwargs)

            except ValidationError as e:
                return (
                    jsonify({"error": "Validation failed", "details": e.messages}),
                    400,
                )
            except Exception as e:
                return jsonify({"error": "Invalid JSON data"}), 400

        return decorated_function

    return decorator


def validate_query_params(schema_class):
    """
    Decorator to validate query parameters against a schema

    Args:
        schema_class: Marshmallow schema class to validate against
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                schema = schema_class()
                data = schema.load(request.args.to_dict(flat=False))

                # Handle list parameters from query string
                for key, value in data.items():
                    if isinstance(value, list) and len(value) == 1:
                        if "," in value[0]:
                            data[key] = value[0].split(",")

                kwargs["validated_params"] = data
                return f(*args, **kwargs)

            except ValidationError as e:
                return (
                    jsonify(
                        {"error": "Invalid query parameters", "details": e.messages}
                    ),
                    400,
                )

        return decorated_function

    return decorator


# Utility validation functions
def is_valid_object_id(obj_id):
    """Check if object ID is valid integer"""
    try:
        return int(obj_id) > 0
    except (ValueError, TypeError):
        return False


def sanitize_filename(filename):
    """Sanitize filename for safe storage"""
    # Remove dangerous characters
    safe_filename = re.sub(r'[<>:"/\\|?*]', "", filename)
    # Limit length
    return safe_filename[:100] if safe_filename else "untitled"


def validate_file_upload(file):
    """Validate uploaded file"""
    if not file or not file.filename:
        raise ValidationError("No file provided")

    # Check file size (5MB limit)
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)  # Reset to beginning

    if size > 5 * 1024 * 1024:  # 5MB
        raise ValidationError("File too large (max 5MB)")

    # Check file extension
    allowed_extensions = {".json", ".md", ".txt", ".zip"}
    ext = "." + file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""

    if ext not in allowed_extensions:
        raise ValidationError(
            f"File type not allowed. Allowed: {', '.join(allowed_extensions)}"
        )

    return True

    # Add this function at the bottom of validators.py


def validate_snippet_data(data, is_update=False):
    """
    Validate snippet data for create/update operations

    Args:
        data: Dictionary containing snippet data
        is_update: Boolean indicating if this is an update operation

    Returns:
        Dict with 'valid' boolean and 'errors' list
    """
    try:
        if is_update:
            schema = SnippetUpdateSchema()
        else:
            schema = SnippetCreateSchema()

        # Validate the data
        validated_data = schema.load(data)

        return {"valid": True, "errors": [], "data": validated_data}
    except ValidationError as e:
        return {"valid": False, "errors": e.messages}
    except Exception as e:
        return {"valid": False, "errors": {"general": [str(e)]}}


def validate_collection_data(data, is_update=False):
    """
    Validate collection data for create/update operations

    Args:
        data: Dictionary containing collection data
        is_update: Boolean indicating if this is an update operation

    Returns:
        Dict with 'valid' boolean and 'errors' list
    """
    try:
        if is_update:
            schema = CollectionUpdateSchema()
        else:
            schema = CollectionCreateSchema()

        # Validate the data
        validated_data = schema.load(data)

        return {"valid": True, "errors": [], "data": validated_data}
    except ValidationError as e:
        return {"valid": False, "errors": e.messages}
    except Exception as e:
        return {"valid": False, "errors": {"general": [str(e)]}}


# Team Schemas
class TeamCreateSchema(Schema):
    """Schema for creating new teams"""

    name = fields.Str(
        required=True, validate=lambda x: len(x.strip()) > 0 and len(x) <= 100
    )
    description = fields.Str(
        allow_none=True,
        validate=lambda x: x is None or len(x) <= MAX_DESCRIPTION_LENGTH,
    )
    is_private = fields.Bool(load_default=False)


class TeamUpdateSchema(Schema):
    """Schema for updating existing teams"""

    name = fields.Str(validate=lambda x: len(x.strip()) > 0 and len(x) <= 100)
    description = fields.Str(
        allow_none=True,
        validate=lambda x: x is None or len(x) <= MAX_DESCRIPTION_LENGTH,
    )
    is_private = fields.Bool()


class TeamMemberSchema(Schema):
    """Schema for team member operations"""

    user_id = fields.Int(required=True, validate=lambda x: x > 0)
    role = fields.Str(
        required=True, validate=lambda x: x in ["owner", "admin", "member", "viewer"]
    )


# Team validation functions
def validate_team_data(data, is_update=False):
    """
    Validate team data for create/update operations

    Args:
        data: Dictionary containing team data
        is_update: Boolean indicating if this is an update operation

    Returns:
        Dict with 'valid' boolean and 'errors' list
    """
    try:
        if is_update:
            schema = TeamUpdateSchema()
        else:
            schema = TeamCreateSchema()

        # Validate the data
        validated_data = schema.load(data)

        return {"valid": True, "errors": [], "data": validated_data}
    except ValidationError as e:
        return {"valid": False, "errors": e.messages}
    except Exception as e:
        return {"valid": False, "errors": {"general": [str(e)]}}


def validate_member_data(data):
    """
    Validate team member data

    Args:
        data: Dictionary containing member data

    Returns:
        Dict with 'valid' boolean and 'errors' list
    """
    try:
        schema = TeamMemberSchema()

        # Validate the data
        validated_data = schema.load(data)

        return {"valid": True, "errors": [], "data": validated_data}
    except ValidationError as e:
        return {"valid": False, "errors": e.messages}
    except Exception as e:
        return {"valid": False, "errors": {"general": [str(e)]}}


# Integration Schemas
class IntegrationCreateSchema(Schema):
    """Schema for creating new integrations"""

    name = fields.Str(
        required=True, validate=lambda x: len(x.strip()) > 0 and len(x) <= 100
    )
    type = fields.Str(
        required=True,
        validate=lambda x: x in ["github", "gitlab", "bitbucket", "webhook", "api"],
    )
    config = fields.Dict(required=True)
    is_active = fields.Bool(load_default=True)


class IntegrationUpdateSchema(Schema):
    """Schema for updating existing integrations"""

    name = fields.Str(validate=lambda x: len(x.strip()) > 0 and len(x) <= 100)
    type = fields.Str(
        validate=lambda x: x in ["github", "gitlab", "bitbucket", "webhook", "api"]
    )
    config = fields.Dict()
    is_active = fields.Bool()


def validate_integration_data(data, is_update=False):
    """
    Validate integration data for create/update operations

    Args:
        data: Dictionary containing integration data
        is_update: Boolean indicating if this is an update operation

    Returns:
        Dict with 'valid' boolean and 'errors' list
    """
    try:
        if is_update:
            schema = IntegrationUpdateSchema()
        else:
            schema = IntegrationCreateSchema()

        # Validate the data
        validated_data = schema.load(data)

        return {"valid": True, "errors": [], "data": validated_data}
    except ValidationError as e:
        return {"valid": False, "errors": e.messages}
    except Exception as e:
        return {"valid": False, "errors": {"general": [str(e)]}}
