from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import get_jwt_identity
from flask_login import login_required, current_user
from sqlalchemy import desc, func, text
from datetime import datetime
import json
import uuid  # Add this import
import traceback  # Add this import

from ..models.collection import Collection
from ..models.snippet import Snippet
from ..models.user import User
from ..services.export_service import export_collections
from ..utils.validators import validate_collection_data
from .. import db
from flask import request, jsonify
from sqlalchemy import and_, or_

collections_bp = Blueprint("collections", __name__, url_prefix="/api/collections")


# ADD THIS DEBUG ROUTE AT THE TOP
@collections_bp.route("/debug/<collection_id>", methods=["GET"])
@login_required
def debug_collection_route(collection_id):
    """Debug route to test if routing works"""
    current_app.logger.info(f"🐛 DEBUG ROUTE CALLED with ID: {collection_id}")
    return jsonify(
        {
            "success": True,
            "message": "Debug route working",
            "collection_id": collection_id,
            "user_id": current_user.id,
        }
    )


@collections_bp.route("", methods=["GET"])  # Handles /api/collections
@collections_bp.route("/", methods=["GET"])
@login_required
def get_collections():
    """Get all collections for the current user"""
    try:
        # Get user from JWT token
        from flask_jwt_extended import get_jwt_identity

        current_user_id = current_user.id

        if not current_user_id:
            return jsonify({"success": False, "error": "Authentication required"}), 401

        # Query collections
        collections = Collection.query.filter_by(user_id=current_user_id).all()

        # Format response
        collections_data = []
        for collection in collections:
            collections_data.append(
                {
                    "id": str(collection.id),
                    "name": collection.name,
                    "description": collection.description or "",
                    "snippet_count": (
                        len(collection.snippets)
                        if hasattr(collection, "snippets")
                        else 0
                    ),
                    "created_at": (
                        collection.created_at.isoformat()
                        if collection.created_at
                        else None
                    ),
                }
            )

        return jsonify({"success": True, "collections": collections_data})

    except Exception as e:
        print(f"❌ GET_COLLECTIONS ERROR: {str(e)}")
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": "Internal server error"}), 500


@collections_bp.route("/<collection_id>", methods=["GET"])
@login_required
def get_collection_detail(collection_id):
    """Get collection details with comprehensive data for frontend - BULLETPROOF VERSION"""

    # Initialize logging with request ID for tracking
    import time

    request_id = str(int(time.time() * 1000))[-6:]  # Last 6 digits of timestamp

    try:
        current_app.logger.info(
            f"🔍 [{request_id}] ===== GET COLLECTION DETAIL START ====="
        )
        current_app.logger.info(
            f"🔍 [{request_id}] Raw collection_id: {repr(collection_id)}"
        )
        current_app.logger.info(
            f"🔍 [{request_id}] Collection ID type: {type(collection_id)}"
        )
        current_app.logger.info(f"🔍 [{request_id}] User ID: {current_user.id}")
        current_app.logger.info(f"🔍 [{request_id}] User email: {current_user.email}")
        current_app.logger.info(f"🔍 [{request_id}] Request method: {request.method}")
        current_app.logger.info(f"🔍 [{request_id}] Request URL: {request.url}")
        current_app.logger.info(f"🔍 [{request_id}] Request args: {dict(request.args)}")

        # Step 1: Validate collection_id format
        collection_id_str = str(collection_id).strip()
        current_app.logger.info(
            f"🔍 [{request_id}] Cleaned collection_id: {collection_id_str}"
        )

        if not collection_id_str:
            current_app.logger.error(f"❌ [{request_id}] Empty collection ID")
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Collection ID is required",
                        "error_code": "EMPTY_ID",
                    }
                ),
                400,
            )

        # Step 2: Validate UUID format
        try:
            import uuid

            uuid_obj = uuid.UUID(collection_id_str)
            current_app.logger.info(f"✅ [{request_id}] Valid UUID format: {uuid_obj}")
        except ValueError as e:
            current_app.logger.error(f"❌ [{request_id}] Invalid UUID format: {e}")
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Invalid collection ID format",
                        "error_code": "INVALID_UUID",
                    }
                ),
                400,
            )

        # Step 3: Check if user is properly authenticated
        if not current_user or not current_user.is_authenticated:
            current_app.logger.error(f"❌ [{request_id}] User not authenticated")
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Authentication required",
                        "error_code": "NOT_AUTHENTICATED",
                    }
                ),
                401,
            )

        # Step 4: Find collection with detailed logging
        current_app.logger.info(f"🔍 [{request_id}] Searching for collection...")

        # Try multiple query approaches
        collection = None

        # Method 1: Direct string comparison
        try:
            current_app.logger.info(f"🔍 [{request_id}] Method 1: Direct string query")
            collection = Collection.query.filter(
                Collection.id == collection_id_str,
                Collection.user_id == current_user.id,
            ).first()
            current_app.logger.info(f"🔍 [{request_id}] Method 1 result: {collection}")
        except Exception as e:
            current_app.logger.error(f"❌ [{request_id}] Method 1 failed: {e}")

        # Method 2: Cast to text (for different DB types)
        if not collection:
            try:
                current_app.logger.info(
                    f"🔍 [{request_id}] Method 2: Cast to text query"
                )
                from sqlalchemy import cast, String

                collection = Collection.query.filter(
                    cast(Collection.id, String) == collection_id_str,
                    cast(Collection.user_id, String) == str(current_user.id),
                ).first()
                current_app.logger.info(
                    f"🔍 [{request_id}] Method 2 result: {collection}"
                )
            except Exception as e:
                current_app.logger.error(f"❌ [{request_id}] Method 2 failed: {e}")

        # Method 3: Raw SQL query
        if not collection:
            try:
                current_app.logger.info(f"🔍 [{request_id}] Method 3: Raw SQL query")
                from sqlalchemy import text

                result = db.session.execute(
                    text(
                        "SELECT * FROM collections WHERE id = :id AND user_id = :user_id"
                    ),
                    {"id": collection_id_str, "user_id": str(current_user.id)},
                )
                row = result.fetchone()
                if row:
                    collection = Collection.query.get(row.id)
                current_app.logger.info(
                    f"🔍 [{request_id}] Method 3 result: {collection}"
                )
            except Exception as e:
                current_app.logger.error(f"❌ [{request_id}] Method 3 failed: {e}")

        # Step 5: Check if collection was found
        if not collection:
            current_app.logger.error(f"❌ [{request_id}] Collection not found")

            # Debug: Show what collections this user has
            try:
                user_collections = Collection.query.filter_by(
                    user_id=current_user.id
                ).all()
                current_app.logger.info(
                    f"🔍 [{request_id}] User has {len(user_collections)} collections:"
                )
                for i, coll in enumerate(user_collections[:5]):  # Show first 5
                    current_app.logger.info(f"   {i+1}. {coll.id} - {coll.name}")
            except Exception as e:
                current_app.logger.error(
                    f"❌ [{request_id}] Error listing user collections: {e}"
                )

            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Collection not found",
                        "error_code": "COLLECTION_NOT_FOUND",
                    }
                ),
                404,
            )

        current_app.logger.info(
            f"✅ [{request_id}] Found collection: {collection.name} (ID: {collection.id})"
        )

        # Step 6: Get snippets with bulletproof error handling
        active_snippets = []

        try:
            current_app.logger.info(
                f"🔍 [{request_id}] Getting snippets for collection..."
            )

            # Method 1: Try SQLAlchemy relationship
            try:
                current_app.logger.info(
                    f"🔍 [{request_id}] Trying relationship method..."
                )
                if hasattr(collection, "snippets"):
                    relationship_snippets = list(collection.snippets)
                    current_app.logger.info(
                        f"🔍 [{request_id}] Relationship found {len(relationship_snippets)} snippets"
                    )

                    for snippet in relationship_snippets:
                        if not getattr(snippet, "is_deleted", False):
                            active_snippets.append(snippet)
                            current_app.logger.info(
                                f"   ✅ [{request_id}] Added: {snippet.title}"
                            )
                else:
                    current_app.logger.warning(
                        f"⚠️ [{request_id}] Collection has no snippets attribute"
                    )

            except Exception as e:
                current_app.logger.error(
                    f"❌ [{request_id}] Relationship method failed: {e}"
                )

            # Method 2: Direct SQL query if relationship failed
            if len(active_snippets) == 0:
                try:
                    current_app.logger.info(
                        f"🔍 [{request_id}] Trying direct SQL method..."
                    )
                    from sqlalchemy import text

                    # First check if snippet_collections table exists
                    check_table = text(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='snippet_collections'"
                    )
                    table_result = db.session.execute(check_table)
                    table_exists = table_result.fetchone()

                    if table_exists:
                        current_app.logger.info(
                            f"✅ [{request_id}] snippet_collections table exists"
                        )

                        # Get snippets via junction table
                        snippet_query = text(
                            """
                            SELECT s.* FROM snippets s 
                            JOIN snippet_collections sc ON s.id = sc.snippet_id 
                            WHERE sc.collection_id = :collection_id 
                            AND s.user_id = :user_id
                            AND (s.is_deleted IS NULL OR s.is_deleted = 0)
                            ORDER BY s.updated_at DESC, s.created_at DESC
                        """
                        )

                        result = db.session.execute(
                            snippet_query,
                            {
                                "collection_id": collection_id_str,
                                "user_id": str(current_user.id),
                            },
                        )

                        snippet_rows = result.fetchall()
                        current_app.logger.info(
                            f"🔍 [{request_id}] SQL query found {len(snippet_rows)} snippets"
                        )

                        for row in snippet_rows:
                            snippet = Snippet.query.get(row.id)
                            if snippet:
                                active_snippets.append(snippet)
                                current_app.logger.info(
                                    f"   ✅ [{request_id}] Added via SQL: {snippet.title}"
                                )
                    else:
                        current_app.logger.error(
                            f"❌ [{request_id}] snippet_collections table does not exist!"
                        )

                except Exception as e:
                    current_app.logger.error(
                        f"❌ [{request_id}] SQL method failed: {e}"
                    )

            # Method 3: Fallback - get snippets by collection_id field (if exists)
            if len(active_snippets) == 0:
                try:
                    current_app.logger.info(
                        f"🔍 [{request_id}] Trying fallback method..."
                    )
                    fallback_snippets = (
                        Snippet.query.filter(
                            Snippet.collection_id == collection_id_str,
                            Snippet.user_id == current_user.id,
                        )
                        .filter(
                            (Snippet.is_deleted == False)
                            | (Snippet.is_deleted.is_(None))
                        )
                        .all()
                    )

                    active_snippets.extend(fallback_snippets)
                    current_app.logger.info(
                        f"🔍 [{request_id}] Fallback found {len(fallback_snippets)} snippets"
                    )

                except Exception as e:
                    current_app.logger.error(
                        f"❌ [{request_id}] Fallback method failed: {e}"
                    )

        except Exception as e:
            current_app.logger.error(
                f"❌ [{request_id}] Critical error getting snippets: {e}"
            )
            current_app.logger.error(
                f"❌ [{request_id}] Traceback: {traceback.format_exc()}"
            )

        # Remove duplicates
        seen_ids = set()
        unique_snippets = []
        for snippet in active_snippets:
            if snippet.id not in seen_ids:
                unique_snippets.append(snippet)
                seen_ids.add(snippet.id)
        active_snippets = unique_snippets

        current_app.logger.info(
            f"📊 [{request_id}] Final snippet count: {len(active_snippets)}"
        )

        # Step 7: Calculate statistics safely
        try:
            languages = []
            total_lines = 0
            view_count = 0

            for snippet in active_snippets:
                if snippet.language:
                    languages.append(snippet.language)
                if snippet.code:
                    total_lines += len(snippet.code.split("\n"))
                view_count += getattr(snippet, "view_count", 0)

            languages = list(set(languages))  # Remove duplicates

            current_app.logger.info(
                f"📊 [{request_id}] Statistics: {len(active_snippets)} snippets, {len(languages)} languages, {total_lines} lines"
            )

        except Exception as e:
            current_app.logger.error(
                f"❌ [{request_id}] Error calculating statistics: {e}"
            )
            languages = []
            total_lines = 0
            view_count = 0

        # Step 8: Get child collections safely
        try:
            children = (
                Collection.query.filter_by(parent_id=collection.id)
                .order_by(Collection.name.asc())
                .all()
            )
            current_app.logger.info(
                f"📁 [{request_id}] Found {len(children)} child collections"
            )
        except Exception as e:
            current_app.logger.error(f"❌ [{request_id}] Error getting children: {e}")
            children = []

        # Step 9: Get parent info safely
        parent_info = None
        try:
            if collection.parent_id:
                parent = Collection.query.get(collection.parent_id)
                if parent:
                    parent_info = {"id": parent.id, "name": parent.name}
                    current_app.logger.info(
                        f"👨‍👩‍👧‍👦 [{request_id}] Parent: {parent.name}"
                    )
        except Exception as e:
            current_app.logger.error(f"❌ [{request_id}] Error getting parent: {e}")

        # Step 10: Prepare snippets data safely
        snippets_data = []
        for i, snippet in enumerate(active_snippets):
            try:
                # Handle tags safely
                tags = []
                try:
                    if hasattr(snippet, "tags") and snippet.tags:
                        if isinstance(snippet.tags, str):
                            tags = [
                                tag.strip()
                                for tag in snippet.tags.split(",")
                                if tag.strip()
                            ]
                        elif isinstance(snippet.tags, list):
                            tags = snippet.tags
                except Exception as tag_error:
                    current_app.logger.error(
                        f"❌ [{request_id}] Error processing tags for snippet {snippet.id}: {tag_error}"
                    )

                snippet_data = {
                    "id": snippet.id,
                    "title": snippet.title or "Untitled",
                    "code": snippet.code or "",
                    "language": snippet.language or "text",
                    "description": getattr(snippet, "description", ""),
                    "tags": tags,
                    "created_at": (
                        snippet.created_at.isoformat() if snippet.created_at else None
                    ),
                    "updated_at": (
                        snippet.updated_at.isoformat() if snippet.updated_at else None
                    ),
                    "view_count": getattr(snippet, "view_count", 0),
                    "line_count": len(snippet.code.split("\n")) if snippet.code else 0,
                    "character_count": len(snippet.code) if snippet.code else 0,
                    "is_favorite": getattr(snippet, "is_favorite", False),
                }

                snippets_data.append(snippet_data)

            except Exception as e:
                current_app.logger.error(
                    f"❌ [{request_id}] Error processing snippet {snippet.id}: {e}"
                )

        # Step 11: Prepare final response
        try:
            collection_data = {
                "id": collection.id,
                "name": collection.name,
                "description": collection.description or "",
                "color": getattr(collection, "color", "#3B82F6"),
                "is_public": getattr(collection, "is_public", False),
                "created_at": (
                    collection.created_at.isoformat() if collection.created_at else None
                ),
                "updated_at": (
                    collection.updated_at.isoformat() if collection.updated_at else None
                ),
                # Statistics
                "snippet_count": len(active_snippets),
                "language_count": len(languages),
                "view_count": view_count,
                "fork_count": getattr(collection, "share_count", 0),
                # Additional metadata
                "languages": languages,
                "total_lines": total_lines,
                "is_favorited": getattr(collection, "is_favorite", False),
                # Relationships
                "parent": parent_info,
                "children": [
                    {"id": child.id, "name": child.name} for child in children
                ],
                "breadcrumb": [{"id": collection.id, "name": collection.name}],
                # Snippets data
                "snippets": snippets_data,
            }

            current_app.logger.info(
                f"✅ [{request_id}] Collection data prepared successfully"
            )
            current_app.logger.info(
                f"✅ [{request_id}] Final response: {len(snippets_data)} snippets"
            )
            current_app.logger.info(
                f"🔍 [{request_id}] ===== GET COLLECTION DETAIL END ====="
            )

            return jsonify(
                {
                    "success": True,
                    "data": collection_data,
                    "collection": collection_data,
                    "request_id": request_id,
                }
            )

        except Exception as e:
            current_app.logger.error(f"❌ [{request_id}] Error preparing response: {e}")
            raise

    except Exception as e:
        current_app.logger.error(
            f"❌ [{request_id}] CRITICAL ERROR in get_collection_detail: {str(e)}"
        )
        current_app.logger.error(f"❌ [{request_id}] Error type: {type(e).__name__}")
        current_app.logger.error(
            f"❌ [{request_id}] FULL TRACEBACK: {traceback.format_exc()}"
        )

        # Return detailed error for debugging
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Failed to fetch collection details",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "request_id": request_id,
                    "debug_info": {
                        "collection_id": collection_id,
                        "user_id": str(current_user.id) if current_user else None,
                        "authenticated": (
                            current_user.is_authenticated if current_user else False
                        ),
                    },
                }
            ),
            500,
        )


@collections_bp.before_request
def log_collection_requests():
    """Log all requests to collections blueprint"""
    current_app.logger.info(f"🔍 COLLECTIONS REQUEST: {request.method} {request.path}")
    current_app.logger.info(f"🔍 Request endpoint: {request.endpoint}")
    current_app.logger.info(f"🔍 Request view args: {request.view_args}")
    current_app.logger.info(f"🔍 User authenticated: {current_user.is_authenticated}")


@collections_bp.route("/<collection_id>/share-with-teams", methods=["POST"])
@login_required
def share_collection_with_teams(collection_id):
    """Share collection with multiple teams"""
    try:
        user_id = current_user.id
        data = request.get_json()
        team_ids = data.get("team_ids", [])

        current_app.logger.info(
            f"🔗 SHARE_COLLECTION: User {user_id} sharing collection {collection_id} with teams {team_ids}"
        )

        # Verify collection ownership/permission
        collection = Collection.query.get(collection_id)
        if not collection:
            current_app.logger.error(
                f"❌ SHARE_COLLECTION: Collection {collection_id} not found"
            )
            return jsonify({"success": False, "error": "Collection not found"}), 404

        if not collection.can_user_access(user_id, "admin"):
            current_app.logger.error(
                f"❌ SHARE_COLLECTION: User {user_id} lacks permission for collection {collection_id}"
            )
            return jsonify({"success": False, "error": "Insufficient permissions"}), 403

        shared_count = 0
        errors = []

        for team_id in team_ids:
            try:
                # Verify user is member of target team
                member_check = db.session.execute(
                    text(
                        """
                        SELECT role FROM team_members 
                        WHERE team_id = :team_id AND user_id = :user_id 
                        AND is_active = 1 AND invitation_status = 'ACCEPTED'
                    """
                    ),
                    {"team_id": team_id, "user_id": str(user_id)},
                ).first()

                if not member_check:
                    current_app.logger.warning(
                        f"⚠️ SHARE_COLLECTION: User {user_id} not member of team {team_id}"
                    )
                    errors.append(f"Not a member of team {team_id}")
                    continue

                # Create team collection copy or reference
                db.session.execute(
                    text(
                        """
                        INSERT OR IGNORE INTO collection_team_shares 
                        (collection_id, team_id, shared_by_id, shared_at, permission_level)
                        VALUES (:collection_id, :team_id, :shared_by_id, :shared_at, :permission_level)
                    """
                    ),
                    {
                        "collection_id": collection_id,
                        "team_id": team_id,
                        "shared_by_id": str(user_id),
                        "shared_at": datetime.utcnow(),
                        "permission_level": "view",
                    },
                )

                shared_count += 1
                current_app.logger.info(
                    f"✅ SHARE_COLLECTION: Shared with team {team_id}"
                )

            except Exception as team_error:
                current_app.logger.error(
                    f"❌ SHARE_COLLECTION: Error sharing with team {team_id}: {str(team_error)}"
                )
                errors.append(f"Failed to share with team {team_id}: {str(team_error)}")

        db.session.commit()

        current_app.logger.info(
            f"✅ SHARE_COLLECTION: Successfully shared with {shared_count} teams"
        )

        return (
            jsonify(
                {
                    "success": True,
                    "message": f"Collection shared with {shared_count} team(s)",
                    "shared_count": shared_count,
                    "errors": errors,
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ SHARE_COLLECTION ERROR: {str(e)}")
        import traceback

        current_app.logger.error(
            f"❌ SHARE_COLLECTION TRACEBACK: {traceback.format_exc()}"
        )
        return jsonify({"success": False, "error": "Failed to share collection"}), 500


@collections_bp.route("/<collection_id>/teams-for-sharing", methods=["GET"])
@login_required
def get_teams_for_sharing(collection_id):
    """Get teams user can share collection with"""
    try:
        user_id = current_user.id
        current_app.logger.info(
            f"🔍 TEAMS_FOR_SHARING: User {user_id} requesting teams for collection {collection_id}"
        )

        collection = Collection.query.get(collection_id)
        if not collection:
            return jsonify({"success": False, "error": "Collection not found"}), 404

        if not collection.can_user_access(user_id, "edit"):
            return jsonify({"success": False, "error": "Insufficient permissions"}), 403

        teams_data = collection.get_user_teams_for_sharing(user_id)

        return (
            jsonify(
                {
                    "success": True,
                    "data": teams_data,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"❌ TEAMS_FOR_SHARING ERROR: {str(e)}")
        return jsonify({"success": False, "error": "Failed to get teams"}), 500


@collections_bp.route("/", methods=["POST"])
@login_required
def create_collection():
    """Create a new collection with enhanced logging and validation"""
    try:
        data = request.get_json()

        # Enhanced logging
        current_app.logger.info(f"🎯 Creating collection for user {current_user.id}")
        current_app.logger.info(f"📤 Collection data received: {data}")

        # Validate required fields
        if not data or not data.get("name"):
            current_app.logger.error("❌ Collection name is required")
            return (
                jsonify({"success": False, "message": "Collection name is required"}),
                400,
            )

        # Validate name length
        name = data["name"].strip()
        if len(name) > 100:
            current_app.logger.error(
                f"❌ Collection name too long: {len(name)} characters"
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Collection name must be 100 characters or less",
                    }
                ),
                400,
            )

        # Check if collection with same name exists for this user
        existing = Collection.query.filter_by(
            user_id=current_user.id, name=name
        ).first()

        if existing:
            current_app.logger.error(
                f"❌ Collection '{name}' already exists for user {current_user.id}"
            )
            return (
                jsonify(
                    {"success": False, "message": f'Collection "{name}" already exists'}
                ),
                400,
            )

        # Validate description length
        description = data.get("description", "").strip()
        if len(description) > 500:
            current_app.logger.error(
                f"❌ Description too long: {len(description)} characters"
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Description must be 500 characters or less",
                    }
                ),
                400,
            )

        # Validate tags
        tags = data.get("tags", "").strip()
        if len(tags) > 200:
            current_app.logger.error(f"❌ Tags too long: {len(tags)} characters")
            return (
                jsonify(
                    {"success": False, "message": "Tags must be 200 characters or less"}
                ),
                400,
            )

        # Handle parent_id if provided
        parent_id = data.get("parent_id")
        if parent_id:
            parent_collection = Collection.query.filter_by(
                id=parent_id, user_id=current_user.id
            ).first()
            if not parent_collection:
                current_app.logger.error(f"❌ Parent collection not found: {parent_id}")
                return (
                    jsonify(
                        {"success": False, "message": "Parent collection not found"}
                    ),
                    404,
                )

        current_app.logger.info(f"💾 Creating collection with data:")
        current_app.logger.info(f"   - Name: {name}")
        current_app.logger.info(f"   - Description: {description}")
        current_app.logger.info(f"   - Tags: {tags}")
        current_app.logger.info(f"   - Is Public: {data.get('is_public', False)}")
        current_app.logger.info(f"   - Parent ID: {parent_id}")

        # Create new collection using your model's constructor
        new_collection = Collection(
            user_id=current_user.id,
            name=name,
            description=description if description else None,
            color=data.get("color", "#3B82F6"),
            tags=tags if tags else None,
            is_public=bool(data.get("is_public", False)),
            parent_id=parent_id,
        )

        current_app.logger.info(
            f"💾 Saving collection to database: {new_collection.name}"
        )

        db.session.add(new_collection)
        db.session.add(new_collection)
        db.session.flush()  # Get collection ID before commit

        # Share with teams if provided
        team_ids = data.get("team_ids", [])
        if team_ids:
            current_app.logger.info(
                f"🔗 CREATE_COLLECTION: Sharing with teams {team_ids}"
            )

            from app.services.collaboration_service import CollaborationService

            collaboration_service = CollaborationService()

            shared_count = 0
            for team_id in team_ids:
                try:
                    collaboration_service.share_collection_with_team_copy(
                        str(new_collection.id), str(team_id), current_user.id
                    )
                    shared_count += 1
                    current_app.logger.info(
                        f"✅ CREATE_COLLECTION: Shared with team {team_id}"
                    )
                except Exception as team_error:
                    current_app.logger.error(
                        f"❌ CREATE_COLLECTION: Failed to share with team {team_id}: {str(team_error)}"
                    )
                    continue

            current_app.logger.info(
                f"✅ CREATE_COLLECTION: Shared with {shared_count}/{len(team_ids)} teams"
            )

        db.session.commit()

        current_app.logger.info(
            f"✅ Collection created successfully with ID: {new_collection.id}"
        )

        # Return success response with collection data
        return (
            jsonify(
                {
                    "success": True,
                    "message": f'Collection "{name}" created successfully',
                    "collection": {
                        "id": new_collection.id,
                        "name": new_collection.name,
                        "description": new_collection.description,
                        "tags": new_collection.tags,
                        "is_public": new_collection.is_public,
                        "color": new_collection.color,
                        "parent_id": new_collection.parent_id,
                        "created_at": new_collection.created_at.isoformat(),
                    },
                }
            ),
            201,
        )

    except Exception as e:
        current_app.logger.error(f"❌ Error creating collection: {str(e)}")
        current_app.logger.error(f"❌ Exception type: {type(e).__name__}")
        current_app.logger.error(f"❌ Exception details: {e}")
        current_app.logger.error(f"❌ FULL TRACEBACK: {traceback.format_exc()}")

        db.session.rollback()

        return (
            jsonify(
                {
                    "success": False,
                    "message": "An error occurred while creating the collection",
                }
            ),
            500,
        )


@collections_bp.route("/user-teams", methods=["GET"])
@login_required
def get_user_teams_for_collection():
    """Get user's teams for collection sharing during creation - ENHANCED LOGGING"""
    try:
        current_app.logger.info(
            f"🎯 USER_TEAMS: Getting teams for user {current_user.id}"
        )

        from app.services.collaboration_service import CollaborationService

        collaboration_service = CollaborationService()

        teams_result = collaboration_service.get_user_teams_for_sharing(current_user.id)

        if not teams_result.get("success", False):
            current_app.logger.error(
                f"❌ USER_TEAMS: Failed to get teams: {teams_result.get('error')}"
            )
            return (
                jsonify(
                    {"success": False, "message": "Failed to load teams", "teams": []}
                ),
                500,
            )

        current_app.logger.info(
            f"✅ USER_TEAMS: Returning {len(teams_result['teams'])} teams"
        )

        return jsonify(
            {
                "success": True,
                "teams": teams_result["teams"],
                "message": f"Found {len(teams_result['teams'])} teams",
            }
        )

    except Exception as e:
        current_app.logger.error(f"❌ USER_TEAMS ERROR: {str(e)}")
        import traceback

        current_app.logger.error(f"❌ USER_TEAMS TRACEBACK: {traceback.format_exc()}")
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Failed to load teams",
                    "teams": [],
                    "error": str(e),
                }
            ),
            500,
        )


@collections_bp.route("/<collection_id>", methods=["PUT"])
@login_required
def update_collection(collection_id):
    """Update an existing collection with enhanced logging and error handling"""
    import time
    import traceback

    request_id = str(int(time.time() * 1000))[-6:]  # Request tracking ID

    try:
        current_app.logger.info(
            f"🔄 [{request_id}] ===== UPDATE COLLECTION START ====="
        )
        current_app.logger.info(f"🔄 [{request_id}] Collection ID: {collection_id}")
        current_app.logger.info(f"🔄 [{request_id}] User ID: {current_user.id}")
        current_app.logger.info(f"🔄 [{request_id}] User email: {current_user.email}")
        current_app.logger.info(f"🔄 [{request_id}] Request method: {request.method}")
        current_app.logger.info(f"🔄 [{request_id}] Request URL: {request.url}")

        # Step 1: Validate collection_id format
        collection_id_str = str(collection_id).strip()
        current_app.logger.info(
            f"🔄 [{request_id}] Cleaned collection_id: {collection_id_str}"
        )

        if not collection_id_str:
            current_app.logger.error(f"❌ [{request_id}] Empty collection ID")
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Collection ID is required",
                        "request_id": request_id,
                    }
                ),
                400,
            )

        # Step 2: Validate UUID format
        try:
            import uuid

            uuid_obj = uuid.UUID(collection_id_str)
            current_app.logger.info(f"✅ [{request_id}] Valid UUID format: {uuid_obj}")
        except ValueError as e:
            current_app.logger.error(f"❌ [{request_id}] Invalid UUID format: {e}")
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Invalid collection ID format",
                        "request_id": request_id,
                    }
                ),
                400,
            )

        # Step 3: Get and validate request data
        data = request.get_json()
        current_app.logger.info(f"🔄 [{request_id}] Raw request data: {data}")
        current_app.logger.info(f"🔄 [{request_id}] Data type: {type(data)}")

        if not data:
            current_app.logger.error(f"❌ [{request_id}] No JSON data provided")
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "No data provided",
                        "request_id": request_id,
                    }
                ),
                400,
            )

        current_app.logger.info(f"🔄 [{request_id}] Data keys: {list(data.keys())}")

        # Log each field being sent
        for key, value in data.items():
            current_app.logger.info(
                f"🔄 [{request_id}] Field '{key}': {repr(value)} (type: {type(value).__name__})"
            )

        # Step 4: Find collection with enhanced error handling
        current_app.logger.info(f"🔍 [{request_id}] Searching for collection...")

        collection = Collection.query.filter_by(
            id=collection_id_str, user_id=current_user.id
        ).first()

        if not collection:
            current_app.logger.error(f"❌ [{request_id}] Collection not found")

            # Debug: Show what collections this user has
            try:
                user_collections = Collection.query.filter_by(
                    user_id=current_user.id
                ).all()
                current_app.logger.info(
                    f"🔍 [{request_id}] User has {len(user_collections)} collections:"
                )
                for i, coll in enumerate(user_collections[:3]):  # Show first 3
                    current_app.logger.info(f"   {i+1}. {coll.id} - {coll.name}")
            except Exception as debug_error:
                current_app.logger.error(
                    f"❌ [{request_id}] Error listing user collections: {debug_error}"
                )

            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Collection not found",
                        "request_id": request_id,
                    }
                ),
                404,
            )

        current_app.logger.info(
            f"✅ [{request_id}] Found collection: {collection.name}"
        )
        current_app.logger.info(f"✅ [{request_id}] Collection current data:")
        current_app.logger.info(f"   - Name: {collection.name}")
        current_app.logger.info(f"   - Description: {collection.description}")
        current_app.logger.info(f"   - Color: {getattr(collection, 'color', 'N/A')}")
        current_app.logger.info(
            f"   - Is Public: {getattr(collection, 'is_public', 'N/A')}"
        )
        current_app.logger.info(f"   - Parent ID: {collection.parent_id}")

        # Step 5: Validate input data with enhanced logging
        current_app.logger.info(f"🔍 [{request_id}] Starting validation...")
        validation_result = validate_collection_data(data, is_update=True)
        current_app.logger.info(
            f"🔍 [{request_id}] Validation result: {validation_result}"
        )

        if not validation_result["valid"]:
            current_app.logger.error(f"❌ [{request_id}] Validation failed:")
            for field, errors in validation_result["errors"].items():
                current_app.logger.error(f"   - {field}: {errors}")

            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Invalid data",
                        "errors": validation_result["errors"],
                        "request_id": request_id,
                    }
                ),
                400,
            )

        current_app.logger.info(f"✅ [{request_id}] Validation passed")
        validated_data = validation_result.get("data", data)
        current_app.logger.info(f"✅ [{request_id}] Validated data: {validated_data}")

        # Step 6: Check for duplicate names if name is being updated
        if "name" in data and data["name"] != collection.name:
            current_app.logger.info(
                f"🔍 [{request_id}] Checking for duplicate name: {data['name']}"
            )

            existing = (
                Collection.query.filter_by(
                    user_id=current_user.id,
                    name=data["name"],
                    parent_id=collection.parent_id,
                )
                .filter(Collection.id != collection_id_str)
                .first()
            )

            if existing:
                current_app.logger.error(
                    f"❌ [{request_id}] Duplicate name found: {existing.id}"
                )
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Collection with this name already exists at this level",
                            "request_id": request_id,
                        }
                    ),
                    409,
                )

            current_app.logger.info(f"✅ [{request_id}] Name is unique")

        # Step 7: Handle parent_id changes (moving collections)
        if "parent_id" in data:
            new_parent_id = data["parent_id"]
            current_app.logger.info(
                f"🔄 [{request_id}] Parent ID change: {collection.parent_id} -> {new_parent_id}"
            )

            if new_parent_id != collection.parent_id:
                # Validate new parent
                if new_parent_id:
                    new_parent = Collection.query.filter_by(
                        id=new_parent_id, user_id=current_user.id
                    ).first()
                    if not new_parent:
                        current_app.logger.error(
                            f"❌ [{request_id}] New parent collection not found: {new_parent_id}"
                        )
                        return (
                            jsonify(
                                {
                                    "success": False,
                                    "message": "New parent collection not found",
                                    "request_id": request_id,
                                }
                            ),
                            404,
                        )

                    current_app.logger.info(
                        f"✅ [{request_id}] New parent found: {new_parent.name}"
                    )

                collection.parent_id = new_parent_id
                current_app.logger.info(f"✅ [{request_id}] Parent ID updated")

        # Step 8: Update other fields with detailed logging
        changes_made = []

        if "name" in data and data["name"] != collection.name:
            old_name = collection.name
            collection.name = data["name"]
            changes_made.append(f"name: '{old_name}' -> '{data['name']}'")
            current_app.logger.info(
                f"🔄 [{request_id}] Updated name: {old_name} -> {data['name']}"
            )

        if "description" in data:
            old_desc = collection.description
            collection.description = data["description"]
            changes_made.append(f"description: '{old_desc}' -> '{data['description']}'")
            current_app.logger.info(f"🔄 [{request_id}] Updated description")

        if "color" in data:
            old_color = getattr(collection, "color", None)
            collection.color = data["color"]
            changes_made.append(f"color: '{old_color}' -> '{data['color']}'")
            current_app.logger.info(
                f"🔄 [{request_id}] Updated color: {old_color} -> {data['color']}"
            )

        if "is_public" in data:
            old_public = getattr(collection, "is_public", None)
            collection.is_public = data["is_public"]
            changes_made.append(f"is_public: {old_public} -> {data['is_public']}")
            current_app.logger.info(
                f"🔄 [{request_id}] Updated is_public: {old_public} -> {data['is_public']}"
            )

        if "tags" in data:
            old_tags = getattr(collection, "tags", None)
            collection.tags = data["tags"]
            changes_made.append(f"tags: '{old_tags}' -> '{data['tags']}'")
            current_app.logger.info(
                f"🔄 [{request_id}] Updated tags: {old_tags} -> {data['tags']}"
            )

        # Step 9: Update timestamp and commit
        collection.updated_at = datetime.utcnow()
        current_app.logger.info(f"🔄 [{request_id}] Updated timestamp set")

        current_app.logger.info(f"💾 [{request_id}] Changes made: {changes_made}")
        current_app.logger.info(f"💾 [{request_id}] Committing to database...")

        db.session.commit()
        current_app.logger.info(f"✅ [{request_id}] Database commit successful")

        # Step 10: Prepare response
        try:
            collection_dict = collection.to_dict()
            current_app.logger.info(
                f"✅ [{request_id}] Collection dict created successfully"
            )
        except Exception as dict_error:
            current_app.logger.error(
                f"❌ [{request_id}] Error creating collection dict: {dict_error}"
            )
            # Fallback response
            collection_dict = {
                "id": collection.id,
                "name": collection.name,
                "description": collection.description,
                "color": getattr(collection, "color", "#3B82F6"),
                "is_public": getattr(collection, "is_public", False),
                "updated_at": (
                    collection.updated_at.isoformat() if collection.updated_at else None
                ),
            }

        current_app.logger.info(
            f"✅ [{request_id}] ===== UPDATE COLLECTION SUCCESS ====="
        )

        return jsonify(
            {
                "success": True,
                "message": "Collection updated successfully",
                "collection": collection_dict,
                "changes_made": changes_made,
                "request_id": request_id,
            }
        )

    except Exception as e:
        current_app.logger.error(
            f"❌ [{request_id}] CRITICAL ERROR in update_collection: {str(e)}"
        )
        current_app.logger.error(f"❌ [{request_id}] Error type: {type(e).__name__}")
        current_app.logger.error(
            f"❌ [{request_id}] FULL TRACEBACK: {traceback.format_exc()}"
        )

        # Rollback any database changes
        try:
            db.session.rollback()
            current_app.logger.info(f"🔄 [{request_id}] Database rollback successful")
        except Exception as rollback_error:
            current_app.logger.error(
                f"❌ [{request_id}] Rollback failed: {rollback_error}"
            )

        return (
            jsonify(
                {
                    "success": False,
                    "message": "Failed to update collection",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "request_id": request_id,
                }
            ),
            500,
        )

    finally:
        current_app.logger.info(f"🔄 [{request_id}] ===== UPDATE COLLECTION END =====")


@collections_bp.route("/<collection_id>", methods=["DELETE"])
@login_required
def delete_collection(collection_id):
    """Delete a collection and handle its contents with enhanced error handling"""
    import uuid
    import traceback
    from sqlalchemy import text

    try:
        current_app.logger.info(f"🗑️ ===== DELETE COLLECTION START =====")
        current_app.logger.info(f"🗑️ Collection ID received: {collection_id}")
        current_app.logger.info(f"🗑️ User ID: {current_user.id}")

        # Convert collection_id to UUID if it's a string
        if isinstance(collection_id, str):
            try:
                collection_uuid = uuid.UUID(collection_id)
                current_app.logger.info(
                    f"🗑️ Converted string to UUID: {collection_uuid}"
                )
            except ValueError as e:
                current_app.logger.error(f"❌ Invalid UUID format: {collection_id}")
                return (
                    jsonify(
                        {"success": False, "message": "Invalid collection ID format"}
                    ),
                    400,
                )
        else:
            collection_uuid = collection_id

        # Find the collection using string comparison for SQLite compatibility
        collection = Collection.query.filter(
            Collection.id == str(collection_uuid), Collection.user_id == current_user.id
        ).first()

        if not collection:
            current_app.logger.error(f"❌ Collection not found: {collection_uuid}")
            return jsonify({"success": False, "message": "Collection not found"}), 404

        # IMPORTANT: Store collection name BEFORE deletion
        collection_name = collection.name
        current_app.logger.info(f"✅ Found collection: {collection_name}")

        # Get request data for handling snippets and child collections
        data = request.get_json() or {}
        action = data.get("action", "move_to_parent")
        target_collection_id = data.get("target_collection_id")

        current_app.logger.info(f"🗑️ Delete action: {action}")
        current_app.logger.info(f"🗑️ Target collection ID: {target_collection_id}")

        # Use session.no_autoflush to prevent premature flushing
        with db.session.no_autoflush:
            current_app.logger.info("🗑️ Starting deletion process with no_autoflush...")

            # Step 1: Handle child collections
            child_collections = Collection.query.filter(
                Collection.parent_id == str(collection_uuid)
            ).all()
            current_app.logger.info(
                f"🗑️ Found {len(child_collections)} child collections"
            )

            # Step 2: Get all snippets in this collection
            try:
                snippet_collection_query = text(
                    """
                    SELECT snippet_id FROM snippet_collections 
                    WHERE collection_id = :collection_id
                """
                )

                result = db.session.execute(
                    snippet_collection_query, {"collection_id": str(collection_uuid)}
                )
                snippet_ids = [row[0] for row in result.fetchall()]
                current_app.logger.info(
                    f"🗑️ Found {len(snippet_ids)} snippets in collection"
                )

            except Exception as e:
                current_app.logger.error(f"❌ Error getting snippets: {str(e)}")
                snippet_ids = []

            # Step 3: Handle snippets based on action
            if action == "move_to_parent" and collection.parent_id:
                current_app.logger.info("🗑️ Moving snippets to parent collection...")
                parent_collection_id = str(collection.parent_id)

                for snippet_id in snippet_ids:
                    try:
                        db.session.execute(
                            text(
                                """
                            DELETE FROM snippet_collections 
                            WHERE snippet_id = :snippet_id AND collection_id = :collection_id
                        """
                            ),
                            {
                                "snippet_id": snippet_id,
                                "collection_id": str(collection_uuid),
                            },
                        )

                        db.session.execute(
                            text(
                                """
                            INSERT OR IGNORE INTO snippet_collections (snippet_id, collection_id)
                            VALUES (:snippet_id, :collection_id)
                        """
                            ),
                            {
                                "snippet_id": snippet_id,
                                "collection_id": parent_collection_id,
                            },
                        )
                        current_app.logger.info(
                            f"📄 Moved snippet {snippet_id} to parent collection"
                        )

                    except Exception as e:
                        current_app.logger.error(
                            f"❌ Error moving snippet {snippet_id}: {str(e)}"
                        )

                for child in child_collections:
                    child.parent_id = collection.parent_id
                    current_app.logger.info(f"📁 Moved child collection: {child.name}")

            else:
                # Default: orphan snippets (remove from collection)
                current_app.logger.info(
                    "🗑️ Orphaning snippets (removing from collection)..."
                )
                for snippet_id in snippet_ids:
                    try:
                        db.session.execute(
                            text(
                                """
                            DELETE FROM snippet_collections 
                            WHERE snippet_id = :snippet_id AND collection_id = :collection_id
                        """
                            ),
                            {
                                "snippet_id": snippet_id,
                                "collection_id": str(collection_uuid),
                            },
                        )
                        current_app.logger.info(f"📄 Orphaned snippet: {snippet_id}")
                    except Exception as e:
                        current_app.logger.error(
                            f"❌ Error orphaning snippet {snippet_id}: {str(e)}"
                        )

                for child in child_collections:
                    child.parent_id = None
                    current_app.logger.info(
                        f"📁 Moved child collection to root: {child.name}"
                    )

            # Step 4: Delete the collection itself
            current_app.logger.info("🗑️ Deleting the main collection...")

            # First, ensure no remaining relationships
            db.session.execute(
                text(
                    """
                DELETE FROM snippet_collections WHERE collection_id = :collection_id
            """
                ),
                {"collection_id": str(collection_uuid)},
            )

            # Then delete the collection
            db.session.execute(
                text(
                    """
                DELETE FROM collections WHERE id = :collection_id
            """
                ),
                {"collection_id": str(collection_uuid)},
            )

            current_app.logger.info(
                f"🗑️ Collection {collection_name} marked for deletion"
            )

        # Commit all changes
        current_app.logger.info("🗑️ Committing all changes...")
        db.session.commit()
        current_app.logger.info("✅ Collection deleted successfully")

        # Use stored collection name (not the deleted object)
        return jsonify(
            {
                "success": True,
                "message": f'Collection "{collection_name}" deleted successfully',
                "action_taken": action,
            }
        )

    except Exception as e:
        current_app.logger.error(f"❌ COLLECTION DELETE ERROR: {str(e)}")
        current_app.logger.error(f"❌ Error type: {type(e).__name__}")
        current_app.logger.error(f"❌ FULL TRACEBACK: {traceback.format_exc()}")

        db.session.rollback()

        return (
            jsonify(
                {"success": False, "message": f"Failed to delete collection: {str(e)}"}
            ),
            500,
        )

    finally:
        current_app.logger.info(f"🗑️ ===== DELETE COLLECTION END =====")


@collections_bp.route("/bulk", methods=["POST"])
@login_required
def bulk_collection_operations():
    """Handle bulk operations on collections"""
    try:
        data = request.get_json()
        operation = data.get("operation")
        collection_ids = data.get("collection_ids", [])

        if not operation or not collection_ids:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Operation and collection_ids are required",
                    }
                ),
                400,
            )

        # Verify all collections belong to current user
        collections = Collection.query.filter(
            Collection.id.in_(collection_ids),
            Collection.user_id == current_user.id,
            Collection.is_deleted == False,
        ).all()

        if len(collections) != len(collection_ids):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Some collections not found or access denied",
                    }
                ),
                403,
            )

        if operation == "delete":
            for collection in collections:
                collection.is_deleted = True
                collection.deleted_at = datetime.utcnow()
            message = f"{len(collections)} collections deleted successfully"

        elif operation == "move_to_parent":
            target_parent_id = data.get("target_parent_id")
            if target_parent_id:
                target_parent = Collection.query.filter_by(
                    id=target_parent_id, user_id=current_user.id, is_deleted=False
                ).first()
                if not target_parent:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "message": "Target parent collection not found",
                            }
                        ),
                        404,
                    )

            for collection in collections:
                # Check for circular references
                if target_parent_id and collection.is_ancestor_of_id(target_parent_id):
                    return (
                        jsonify(
                            {
                                "success": False,
                                "message": f'Cannot move collection "{collection.name}" to its own descendant',
                            }
                        ),
                        400,
                    )
                collection.parent_id = target_parent_id
            message = f"{len(collections)} collections moved successfully"

        elif operation == "change_color":
            new_color = data.get("color", "#007bff")
            for collection in collections:
                collection.color = new_color
            message = f"{len(collections)} collections updated successfully"

        elif operation == "export":
            format_type = data.get("format", "json")
            export_data = export_collections(collections, format_type)
            return jsonify(
                {"success": True, "export_data": export_data, "format": format_type}
            )

        else:
            return jsonify({"success": False, "message": "Invalid operation"}), 400

        db.session.commit()

        return jsonify(
            {"success": True, "message": message, "affected_count": len(collections)}
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in bulk collection operation: {str(e)}")
        return (
            jsonify({"success": False, "message": "Failed to perform bulk operation"}),
            500,
        )


@collections_bp.route("/<collection_id>/favorite", methods=["POST"])
@login_required
def toggle_collection_favorite(collection_id):
    """Toggle favorite status for a collection"""
    try:
        collection = Collection.query.filter_by(
            id=collection_id, user_id=current_user.id
        ).first()

        if not collection:
            return jsonify({"success": False, "message": "Collection not found"}), 404

        # Toggle favorite status
        collection.is_favorite = not (collection.is_favorite or False)
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "is_favorite": collection.is_favorite,
                "message": f'Collection {"added to" if collection.is_favorite else "removed from"} favorites',
            }
        )

    except Exception as e:
        db.session.rollback()
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Error updating favorite status: {str(e)}",
                }
            ),
            500,
        )


@collections_bp.route("/favorites", methods=["GET"])
@login_required
def get_favorite_collections():
    """Get all favorite collections for current user with enhanced logging"""
    try:
        current_app.logger.info(f"⭐ ===== GET FAVORITE COLLECTIONS START =====")
        current_app.logger.info(f"⭐ User ID: {current_user.id}")

        # Remove is_deleted=False since your model doesn't have this field
        collections = (
            Collection.query.filter_by(user_id=current_user.id, is_favorite=True)
            .order_by(Collection.updated_at.desc())
            .all()
        )

        current_app.logger.info(f"⭐ Found {len(collections)} favorite collections")

        collections_data = []
        for collection in collections:
            current_app.logger.info(
                f"⭐ Processing collection: {collection.id} - {collection.name}"
            )

            # Get snippet count for this collection
            snippet_count = len(
                [s for s in collection.snippets if not getattr(s, "is_deleted", False)]
            )

            collection_data = {
                "id": collection.id,
                "name": collection.name,
                "description": collection.description,
                "is_favorite": collection.is_favorite,
                "tags": collection.tags,
                "color": getattr(collection, "color", "#3B82F6"),
                "snippet_count": snippet_count,
                "created_at": (
                    collection.created_at.isoformat() if collection.created_at else None
                ),
                "updated_at": (
                    collection.updated_at.isoformat() if collection.updated_at else None
                ),
            }
            collections_data.append(collection_data)
            current_app.logger.info(f"⭐ Added collection data: {collection_data}")

        current_app.logger.info(
            f"⭐ Returning {len(collections_data)} favorite collections"
        )
        current_app.logger.info(f"⭐ ===== GET FAVORITE COLLECTIONS END =====")

        return jsonify({"success": True, "collections": collections_data})

    except Exception as e:
        current_app.logger.error(f"❌ Error loading favorite collections: {str(e)}")
        current_app.logger.error(f"❌ Exception type: {type(e).__name__}")
        current_app.logger.error(f"❌ FULL TRACEBACK: {traceback.format_exc()}")
        return (
            jsonify(
                {
                    "success": False,
                    "message": f"Error loading favorite collections: {str(e)}",
                }
            ),
            500,
        )


@collections_bp.route("/<collection_id>/share", methods=["POST"])
@login_required
def share_collection(collection_id):
    """Share existing collection with selected teams - COPY-BASED ONLY"""
    try:
        current_app.logger.info(
            f"🔗 SHARE_COLLECTION_COPY: Collection {collection_id} by user {current_user.id}"
        )

        data = request.get_json()
        team_ids = data.get("team_ids", [])

        if not team_ids:
            current_app.logger.error(f"❌ SHARE_COLLECTION_COPY: No teams selected")
            return jsonify({"success": False, "message": "No teams selected"}), 400

        # Verify collection ownership
        collection = Collection.query.filter_by(
            id=collection_id, user_id=current_user.id
        ).first()

        if not collection:
            current_app.logger.error(
                f"❌ SHARE_COLLECTION_COPY: Collection {collection_id} not found"
            )
            return jsonify({"success": False, "message": "Collection not found"}), 404

        current_app.logger.info(
            f"✅ SHARE_COLLECTION_COPY: Collection '{collection.name}' found"
        )

        # 🔥 COPY-BASED SHARING ONLY
        from app.services.collaboration_service import collaboration_service

        shared_count = 0
        already_shared_count = 0
        errors = []

        for team_id in team_ids:
            try:
                current_app.logger.info(
                    f"🔗 SHARE_COLLECTION_COPY: Creating copy for team {team_id}"
                )

                result = collaboration_service.share_collection_with_team_copy(
                    str(collection_id), str(team_id), current_user.id
                )

                if result.get("success"):
                    shared_count += 1
                    current_app.logger.info(
                        f"✅ SHARE_COLLECTION_COPY: Successfully created copy for team {team_id}"
                    )
                else:
                    error_msg = result.get("message", "Unknown error")
                    if "already shared" in error_msg.lower():
                        already_shared_count += 1
                        current_app.logger.info(
                            f"📋 SHARE_COLLECTION_COPY: Already shared with team {team_id}"
                        )
                    else:
                        current_app.logger.error(
                            f"❌ SHARE_COLLECTION_COPY: Failed to share with team {team_id}: {error_msg}"
                        )
                        errors.append(f"Team {team_id}: {error_msg}")

            except Exception as team_error:
                current_app.logger.error(
                    f"❌ SHARE_COLLECTION_COPY: Exception sharing with team {team_id}: {str(team_error)}"
                )
                errors.append(f"Team {team_id}: {str(team_error)}")
                continue

        current_app.logger.info(
            f"✅ SHARE_COLLECTION_COPY: Final result - New copies: {shared_count}, Already shared: {already_shared_count}, Errors: {len(errors)}"
        )

        # Prepare response message
        total_successful = shared_count + already_shared_count
        if total_successful > 0:
            message_parts = []
            if shared_count > 0:
                message_parts.append(f"{shared_count} new independent copies created")
            if already_shared_count > 0:
                message_parts.append(f"{already_shared_count} already shared")

            message = f"Collection shared with {total_successful} team(s) ({', '.join(message_parts)})"

            return jsonify(
                {
                    "success": True,
                    "message": message,
                    "shared_count": shared_count,
                    "already_shared_count": already_shared_count,
                    "total_teams": total_successful,
                    "sharing_type": "copy_based_only",
                    "errors": errors,
                }
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Failed to share with any teams",
                        "errors": errors,
                    }
                ),
                500,
            )

    except Exception as e:
        current_app.logger.error(f"❌ SHARE_COLLECTION_COPY CRITICAL ERROR: {str(e)}")
        import traceback

        current_app.logger.error(
            f"❌ SHARE_COLLECTION_COPY TRACEBACK: {traceback.format_exc()}"
        )
        return (
            jsonify(
                {"success": False, "message": f"Failed to share collection: {str(e)}"}
            ),
            500,
        )


@collections_bp.route("/import", methods=["POST"])
@login_required
def import_collection(self):
    """Import collection from various formats"""
    try:
        data = request.get_json()
        import_data = data.get("data")
        format_type = data.get("format", "json")
        parent_id = data.get("parent_id")

        if not import_data:
            return jsonify({"success": False, "message": "Import data required"}), 400

        # Validate parent collection if specified
        if parent_id:
            parent_collection = Collection.query.filter_by(
                id=parent_id, user_id=current_user.id, is_deleted=False
            ).first()
            if not parent_collection:
                return (
                    jsonify(
                        {"success": False, "message": "Parent collection not found"}
                    ),
                    404,
                )

        imported_collections = []
        imported_snippets = []

        if format_type == "json":
            # Handle JSON import
            if isinstance(import_data, dict):
                collection = self._import_collection_from_dict(import_data, parent_id)
                imported_collections.append(collection)
            elif isinstance(import_data, list):
                for coll_data in import_data:
                    collection = self._import_collection_from_dict(coll_data, parent_id)
                    imported_collections.append(collection)

        elif format_type == "markdown":
            # Handle Markdown import (parse structure from headers)
            collection = self._import_collection_from_markdown(import_data, parent_id)
            imported_collections.append(collection)

        else:
            return (
                jsonify({"success": False, "message": "Unsupported import format"}),
                400,
            )

        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": "Import completed successfully",
                "imported_collections": len(imported_collections),
                "collections": [c.to_dict() for c in imported_collections],
            }
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error importing collection: {str(e)}")
        return (
            jsonify({"success": False, "message": "Failed to import collection"}),
            500,
        )


def _import_collection_from_dict(self, data, parent_id):
    """Helper method to import collection from dictionary"""
    collection = Collection(
        name=data.get("name", "Imported Collection"),
        description=data.get("description", ""),
        color=data.get("color", "#007bff"),
        parent_id=parent_id,
        user_id=current_user.id,
    )

    db.session.add(collection)
    db.session.flush()  # Get the ID

    # Import child collections
    if "children" in data:
        for child_data in data["children"]:
            self._import_collection_from_dict(child_data, collection.id)

    # Import snippets
    if "snippets" in data:
        for snippet_data in data["snippets"]:
            snippet = Snippet(
                title=snippet_data.get("title", "Untitled"),
                code=snippet_data.get("code", ""),
                language=snippet_data.get("language", "text"),
                description=snippet_data.get("description", ""),
                tags=snippet_data.get("tags", []),
                collection_id=collection.id,
                user_id=current_user.id,
            )
            db.session.add(snippet)

    return collection


@collections_bp.route("/<collection_id>/shared-teams", methods=["GET"])
@login_required
def get_collection_shared_teams(collection_id):
    """Get teams that collection is already shared with - FIXED VERSION"""
    try:
        current_app.logger.info(f"🔍 GET_SHARED_TEAMS: Collection {collection_id}")

        # Verify collection ownership
        collection = Collection.query.filter_by(
            id=collection_id, user_id=current_user.id
        ).first()

        if not collection:
            return jsonify({"success": False, "message": "Collection not found"}), 404

        # 🔥 FIXED: Don't use collaboration service, do it directly here
        from sqlalchemy import text

        # Get user's teams directly without date formatting issues
        teams_query = text(
            """
            SELECT DISTINCT t.id, t.name, t.description, tm.role, 
                t.owner_id, t.created_by
            FROM teams t
            JOIN team_members tm ON t.id = tm.team_id
            WHERE tm.user_id = :user_id 
            AND tm.is_active = 1
            AND (tm.invitation_status IN ('ACCEPTED', 'accepted', 'Accepted') OR tm.invitation_status IS NULL)
            ORDER BY t.name ASC
        """
        )

        result = db.session.execute(teams_query, {"user_id": str(current_user.id)})
        teams_data = result.fetchall()

        # Get shared teams
        shared_teams = db.session.execute(
            text(
                "SELECT team_id FROM collection_team_shares WHERE collection_id = :collection_id"
            ),
            {"collection_id": collection_id},
        ).fetchall()

        shared_team_ids = {str(team.team_id) for team in shared_teams}

        # Separate created vs joined teams
        created_teams = []
        joined_teams = []

        for team in teams_data:
            # 🔥 FIXED: Proper ownership detection
            user_id_str = str(current_user.id)
            owner_id = str(team.owner_id) if team.owner_id else None
            created_by = str(team.created_by) if team.created_by else None

            is_owner = owner_id == user_id_str if owner_id else False
            is_creator = created_by == user_id_str if created_by else False
            is_admin_or_owner = str(team.role).upper().strip() in ["OWNER", "ADMIN"]

            is_team_creator = is_owner or is_creator or is_admin_or_owner

            team_data = {
                "id": str(team.id),
                "name": team.name,
                "description": team.description or "",
                "role": team.role,
                "is_shared": str(team.id) in shared_team_ids,
                "owner_id": owner_id,
                "created_by": created_by,
                "is_owner": is_owner,
                "is_creator": is_creator,
                "is_team_creator": is_team_creator,
            }

            if is_team_creator:
                created_teams.append(team_data)
            else:
                joined_teams.append(team_data)

        current_app.logger.info(
            f"✅ GET_SHARED_TEAMS: Created: {len(created_teams)}, Joined: {len(joined_teams)}"
        )

        return (
            jsonify(
                {
                    "success": True,
                    "created_teams": created_teams,
                    "joined_teams": joined_teams,
                    "shared_team_ids": list(shared_team_ids),
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"❌ GET_SHARED_TEAMS ERROR: {str(e)}")
        import traceback

        current_app.logger.error(f"❌ TRACEBACK: {traceback.format_exc()}")
        return jsonify({"success": False, "message": "Failed to get shared teams"}), 500


@collections_bp.route("/debug/database/<collection_id>", methods=["GET"])
@login_required
def debug_database_for_collection(collection_id):
    """Debug database structure and relationships for specific collection"""
    try:
        from sqlalchemy import text

        debug_info = {}

        # Check if collection exists
        collection = Collection.query.filter(
            Collection.id == str(collection_id), Collection.user_id == current_user.id
        ).first()

        debug_info["collection_found"] = collection is not None
        if collection:
            debug_info["collection_name"] = collection.name

        # Check snippet_collections table
        try:
            check_table = text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='snippet_collections'"
            )
            table_result = db.session.execute(check_table)
            debug_info["snippet_collections_table_exists"] = (
                table_result.fetchone() is not None
            )
        except Exception as e:
            debug_info["snippet_collections_table_error"] = str(e)

        # Check relationships in snippet_collections table
        try:
            relations_query = text(
                """
                SELECT snippet_id, collection_id FROM snippet_collections 
                WHERE collection_id = :collection_id
            """
            )
            relations_result = db.session.execute(
                relations_query, {"collection_id": str(collection_id)}
            )
            relations = relations_result.fetchall()
            debug_info["snippet_collection_relations"] = [
                {"snippet_id": r[0], "collection_id": r[1]} for r in relations
            ]
        except Exception as e:
            debug_info["relations_error"] = str(e)

        return jsonify(
            {
                "success": True,
                "debug_info": debug_info,
                "collection_id": collection_id,
                "user_id": str(current_user.id),
            }
        )

    except Exception as e:
        return (
            jsonify(
                {"success": False, "error": str(e), "traceback": traceback.format_exc()}
            ),
            500,
        )


@collections_bp.route("/templates", methods=["GET"])
@login_required
def get_collection_templates():
    """Get predefined collection templates"""
    try:
        templates = [
            {
                "id": "web_development",
                "name": "Web Development",
                "description": "Complete setup for web development snippets",
                "structure": {
                    "name": "Web Development",
                    "children": [
                        {
                            "name": "Frontend",
                            "children": [
                                {"name": "HTML"},
                                {"name": "CSS"},
                                {"name": "JavaScript"},
                                {"name": "React"},
                                {"name": "Vue.js"},
                            ],
                        },
                        {
                            "name": "Backend",
                            "children": [
                                {"name": "Node.js"},
                                {"name": "Python"},
                                {"name": "PHP"},
                                {"name": "API Routes"},
                            ],
                        },
                        {
                            "name": "Database",
                            "children": [
                                {"name": "SQL"},
                                {"name": "NoSQL"},
                                {"name": "Queries"},
                            ],
                        },
                    ],
                },
            },
            {
                "id": "algorithms",
                "name": "Algorithms & Data Structures",
                "description": "Organized structure for coding interview prep",
                "structure": {
                    "name": "Algorithms & Data Structures",
                    "children": [
                        {"name": "Sorting Algorithms"},
                        {"name": "Search Algorithms"},
                        {"name": "Dynamic Programming"},
                        {"name": "Trees & Graphs"},
                        {"name": "Array Problems"},
                        {"name": "String Problems"},
                    ],
                },
            },
            {
                "id": "devops",
                "name": "DevOps & Infrastructure",
                "description": "Infrastructure and deployment snippets",
                "structure": {
                    "name": "DevOps & Infrastructure",
                    "children": [
                        {"name": "Docker"},
                        {"name": "Kubernetes"},
                        {"name": "CI/CD"},
                        {"name": "AWS"},
                        {"name": "Monitoring"},
                        {"name": "Scripts"},
                    ],
                },
            },
        ]

        return jsonify({"success": True, "templates": templates})

    except Exception as e:
        current_app.logger.error(f"Error fetching templates: {str(e)}")
        return jsonify({"success": False, "message": "Failed to fetch templates"}), 500


@collections_bp.route("/templates/<template_id>", methods=["POST"])
@login_required
def create_from_template(template_id):
    """Create collection structure from template"""
    try:
        # Get template data (in real app, this would come from database)
        templates = {
            "web_development": {
                "name": "Web Development",
                "children": [
                    {
                        "name": "Frontend",
                        "color": "#61dafb",
                        "children": [
                            {"name": "HTML", "color": "#e34f26"},
                            {"name": "CSS", "color": "#1572b6"},
                            {"name": "JavaScript", "color": "#f7df1e"},
                            {"name": "React", "color": "#61dafb"},
                            {"name": "Vue.js", "color": "#4fc08d"},
                        ],
                    },
                    {
                        "name": "Backend",
                        "color": "#339933",
                        "children": [
                            {"name": "Node.js", "color": "#339933"},
                            {"name": "Python", "color": "#3776ab"},
                            {"name": "PHP", "color": "#777bb4"},
                            {"name": "API Routes", "color": "#ff6b6b"},
                        ],
                    },
                    {
                        "name": "Database",
                        "color": "#336791",
                        "children": [
                            {"name": "SQL", "color": "#336791"},
                            {"name": "NoSQL", "color": "#4db33d"},
                            {"name": "Queries", "color": "#ff9500"},
                        ],
                    },
                ],
            }
            # Add other templates...
        }

        template_data = templates.get(template_id)
        if not template_data:
            return jsonify({"success": False, "message": "Template not found"}), 404

        data = request.get_json() or {}
        parent_id = data.get("parent_id")
        custom_name = data.get("name")

        # Validate parent collection if specified
        if parent_id:
            parent_collection = Collection.query.filter_by(
                id=parent_id, user_id=current_user.id, is_deleted=False
            ).first()
            if not parent_collection:
                return (
                    jsonify(
                        {"success": False, "message": "Parent collection not found"}
                    ),
                    404,
                )

        # Create collection structure recursively
        def create_collection_recursive(coll_data, parent_id):
            collection = Collection(
                name=(
                    custom_name
                    if parent_id is None and custom_name
                    else coll_data["name"]
                ),
                description=coll_data.get("description", ""),
                color=coll_data.get("color", "#007bff"),
                parent_id=parent_id,
                user_id=current_user.id,
            )

            db.session.add(collection)
            db.session.flush()  # Get the ID

            # Create child collections
            if "children" in coll_data:
                for child_data in coll_data["children"]:
                    create_collection_recursive(child_data, collection.id)

            return collection

        root_collection = create_collection_recursive(template_data, parent_id)
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": "Collection structure created from template",
                "collection": root_collection.to_dict(),
            }
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating from template: {str(e)}")
        return (
            jsonify({"success": False, "message": "Failed to create from template"}),
            500,
        )


@collections_bp.route("/<int:collection_id>/reorder", methods=["PUT"])
@login_required
def reorder_collection_snippets(collection_id):
    """Reorder snippets within a collection via drag-and-drop"""
    try:
        collection = Collection.query.filter_by(
            id=collection_id, user_id=current_user.id
        ).first_or_404()

        data = request.get_json()
        snippet_ids = data.get("snippet_ids", [])

        if not snippet_ids:
            return jsonify({"error": "No snippet order provided"}), 400

        # Verify all snippets belong to this collection and user
        snippets = Snippet.query.filter(
            Snippet.id.in_(snippet_ids),
            Snippet.collection_id == collection_id,
            Snippet.user_id == current_user.id,
        ).all()

        if len(snippets) != len(snippet_ids):
            return jsonify({"error": "Invalid snippet IDs provided"}), 400

        # Update the order (if you have an order field in your Snippet model)
        # If you don't have an order field, you might need to add one
        for index, snippet_id in enumerate(snippet_ids):
            snippet = next((s for s in snippets if s.id == snippet_id), None)
            if snippet:
                # Assuming you have an 'order' field in your Snippet model
                # If not, you can add: order = db.Column(db.Integer, default=0)
                snippet.order = index

        db.session.commit()

        return jsonify(
            {
                "message": "Collection snippets reordered successfully",
                "collection_id": collection_id,
                "new_order": snippet_ids,
            }
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@collections_bp.route("/move-snippet", methods=["PUT"])
@login_required
def move_snippet_between_collections():
    """Move a snippet from one collection to another"""
    try:
        data = request.get_json()
        snippet_id = data.get("snippet_id")
        from_collection_id = data.get("from_collection_id")
        to_collection_id = data.get("to_collection_id")

        if not snippet_id:
            return jsonify({"error": "Snippet ID required"}), 400

        # Get the snippet
        snippet = Snippet.query.filter_by(
            id=snippet_id, user_id=current_user.id
        ).first_or_404()

        # Verify source collection ownership (if moving from a collection)
        if from_collection_id and from_collection_id != snippet.collection_id:
            return jsonify({"error": "Snippet not in source collection"}), 400

        # Verify destination collection ownership (if moving to a collection)
        if to_collection_id:
            dest_collection = Collection.query.filter_by(
                id=to_collection_id, user_id=current_user.id
            ).first()
            if not dest_collection:
                return jsonify({"error": "Destination collection not found"}), 404

        # Move the snippet
        snippet.collection_id = to_collection_id
        db.session.commit()

        return jsonify(
            {
                "message": "Snippet moved successfully",
                "snippet_id": snippet_id,
                "from_collection": from_collection_id,
                "to_collection": to_collection_id,
            }
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@collections_bp.route("/bulk-move", methods=["PUT"])
@login_required
def bulk_move_snippets():
    """Move multiple snippets to a collection"""
    try:
        data = request.get_json()
        snippet_ids = data.get("snippet_ids", [])
        to_collection_id = data.get("to_collection_id")

        if not snippet_ids:
            return jsonify({"error": "No snippet IDs provided"}), 400

        # Verify destination collection ownership (if moving to a collection)
        if to_collection_id:
            dest_collection = Collection.query.filter_by(
                id=to_collection_id, user_id=current_user.id
            ).first()
            if not dest_collection:
                return jsonify({"error": "Destination collection not found"}), 404

        # Get snippets
        snippets = Snippet.query.filter(
            Snippet.id.in_(snippet_ids), Snippet.user_id == current_user.id
        ).all()

        if not snippets:
            return jsonify({"error": "No valid snippets found"}), 404

        # Move all snippets
        for snippet in snippets:
            snippet.collection_id = to_collection_id

        db.session.commit()

        return jsonify(
            {
                "message": f"Successfully moved {len(snippets)} snippets",
                "moved_count": len(snippets),
                "to_collection": to_collection_id,
            }
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@collections_bp.route("/<int:collection_id>/nested", methods=["POST"])
@login_required
def create_nested_collection(collection_id):
    """Create a nested subcollection"""
    try:
        parent_collection = Collection.query.filter_by(
            id=collection_id, user_id=current_user.id
        ).first_or_404()

        data = request.get_json()
        name = data.get("name", "").strip()
        description = data.get("description", "").strip()

        if not name:
            return jsonify({"error": "Collection name is required"}), 400

        # Check if subcollection name already exists in this parent
        existing = Collection.query.filter_by(
            name=name, user_id=current_user.id, parent_id=collection_id
        ).first()

        if existing:
            return (
                jsonify({"error": "Subcollection with this name already exists"}),
                400,
            )

        # Create nested collection
        subcollection = Collection(
            name=name,
            description=description,
            user_id=current_user.id,
            parent_id=collection_id,
            is_private=parent_collection.is_private,  # Inherit privacy setting
        )

        db.session.add(subcollection)
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Nested collection created successfully",
                    "collection": {
                        "id": subcollection.id,
                        "name": subcollection.name,
                        "description": subcollection.description,
                        "parent_id": subcollection.parent_id,
                        "created_at": subcollection.created_at.isoformat(),
                    },
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@collections_bp.route("/<int:collection_id>/hierarchy", methods=["GET"])
@login_required
def get_collection_hierarchy(collection_id):
    """Get full hierarchy tree for a collection"""
    try:
        collection = Collection.query.filter_by(
            id=collection_id, user_id=current_user.id
        ).first_or_404()

        def build_hierarchy(coll):
            # Get direct children
            children = Collection.query.filter_by(
                parent_id=coll.id, user_id=current_user.id
            ).all()

            # Get snippets in this collection
            snippets = collection.snippets

            return {
                "id": coll.id,
                "name": coll.name,
                "description": coll.description,
                "parent_id": coll.parent_id,
                "snippet_count": len(snippets),
                "children": [build_hierarchy(child) for child in children],
                "snippets": [
                    {
                        "id": s.id,
                        "title": s.title,
                        "language": s.language,
                        "created_at": s.created_at.isoformat(),
                        "order": getattr(s, "order", 0),
                    }
                    for s in snippets
                ],
            }

        hierarchy = build_hierarchy(collection)

        return jsonify(hierarchy)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@collections_bp.route("/drag-drop-positions", methods=["PUT"])
@login_required
def update_drag_drop_positions():
    """Update positions after complex drag-and-drop operations"""
    try:
        data = request.get_json()
        updates = data.get("updates", [])

        if not updates:
            return jsonify({"error": "No position updates provided"}), 400

        # Process each update
        for update in updates:
            item_type = update.get("type")  # 'snippet' or 'collection'
            item_id = update.get("id")
            new_parent_id = update.get("parent_id")
            new_order = update.get("order", 0)

            if item_type == "snippet":
                snippet = Snippet.query.filter_by(
                    id=item_id, user_id=current_user.id
                ).first()
                if snippet:
                    snippet.collection_id = new_parent_id
                    snippet.order = new_order

            elif item_type == "collection":
                collection = Collection.query.filter_by(
                    id=item_id, user_id=current_user.id
                ).first()
                if collection:
                    collection.parent_id = new_parent_id
                    collection.order = new_order

        db.session.commit()

        return jsonify(
            {"message": "Positions updated successfully", "updated_count": len(updates)}
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@collections_bp.route("/<int:collection_id>/export", methods=["GET"])
@login_required
def export_collection(collection_id):
    """Export entire collection with all snippets and subcollections"""
    try:
        collection = Collection.query.filter_by(
            id=collection_id, user_id=current_user.id
        ).first_or_404()

        export_format = request.args.get("format", "json")
        include_nested = request.args.get("nested", "true").lower() == "true"

        def export_collection_data(coll):
            # Get snippets
            snippets = Snippet.query.filter_by(
                collection_id=coll.id, user_id=current_user.id
            ).all()

            data = {
                "id": coll.id,
                "name": coll.name,
                "description": coll.description,
                "created_at": coll.created_at.isoformat(),
                "snippets": [
                    {
                        "title": s.title,
                        "code": s.code,
                        "language": s.language,
                        "description": s.description,
                        "tags": s.tags.split(",") if s.tags else [],
                        "created_at": s.created_at.isoformat(),
                    }
                    for s in snippets
                ],
            }

            # Include nested collections if requested
            if include_nested:
                children = Collection.query.filter_by(
                    parent_id=coll.id, user_id=current_user.id
                ).all()
                data["subcollections"] = [
                    export_collection_data(child) for child in children
                ]

            return data

        export_data = export_collection_data(collection)

        if export_format == "markdown":
            # Convert to markdown format
            from ..services.export_service import ExportService

            export_service = ExportService()
            markdown_content = export_service.collection_to_markdown(export_data)

            return jsonify(
                {
                    "format": "markdown",
                    "content": markdown_content,
                    "filename": f"{collection.name.replace(' ', '_')}.md",
                }
            )

        return jsonify(export_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@collections_bp.route("/statistics", methods=["GET"])
@login_required
def get_collection_statistics():
    """Get collection statistics for current user"""
    try:
        total_collections = Collection.query.filter_by(
            user_id=current_user.id, is_deleted=False
        ).count()

        # Root collections count
        root_collections = Collection.query.filter_by(
            user_id=current_user.id, parent_id=None, is_deleted=False
        ).count()

        # Collections with most snippets
        top_collections = (
            db.session.query(
                Collection.id,
                Collection.name,
                func.count(Snippet.id).label("snippet_count"),
            )
            .join(Snippet, Collection.id == Snippet.collection_id, isouter=True)
            .filter(
                Collection.user_id == current_user.id,
                Collection.is_deleted == False,
                or_(Snippet.is_deleted == False, Snippet.id == None),
            )
            .group_by(Collection.id, Collection.name)
            .order_by(desc("snippet_count"))
            .limit(5)
            .all()
        )

        # Recently created collections
        recent_collections = (
            Collection.query.filter_by(user_id=current_user.id, is_deleted=False)
            .order_by(desc(Collection.created_at))
            .limit(5)
            .all()
        )

        return jsonify(
            {
                "success": True,
                "statistics": {
                    "total_collections": total_collections,
                    "root_collections": root_collections,
                    "max_depth": 5,  # Your configured max depth
                    "top_collections": [
                        {
                            "id": coll.id,
                            "name": coll.name,
                            "snippet_count": coll.snippet_count,
                        }
                        for coll in top_collections
                    ],
                    "recent_collections": [c.to_dict() for c in recent_collections],
                },
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error fetching collection statistics: {str(e)}")
        return jsonify({"success": False, "message": "Failed to fetch statistics"}), 500


@collections_bp.route("/debug-teams", methods=["GET"])
@login_required
def debug_teams():
    """Debug teams loading"""
    try:
        from sqlalchemy import text

        print(f"🔍 DEBUG_TEAMS: User {current_user.id} ({current_user.email})")

        # Check teams directly
        teams_result = db.session.execute(
            text(
                """
                SELECT t.id, t.name, tm.role, tm.is_active, tm.invitation_status
                FROM teams t
                JOIN team_members tm ON t.id = tm.team_id
                WHERE tm.user_id = :user_id
            """
            ),
            {"user_id": str(current_user.id)},
        ).fetchall()

        print(f"🔍 DEBUG_TEAMS: Raw query found {len(teams_result)} team memberships")
        for team in teams_result:
            print(
                f"  - Team: {team.name}, Role: {team.role}, Active: {team.is_active}, Status: {team.invitation_status}"
            )

        # Test collaboration service
        from app.services.collaboration_service import CollaborationService

        collaboration_service = CollaborationService()
        teams_result = collaboration_service.get_user_teams_for_sharing(current_user.id)

        return jsonify(
            {
                "success": True,
                "user_id": current_user.id,
                "raw_teams": len(teams_result),
                "collaboration_result": teams_result,
            }
        )

    except Exception as e:
        print(f"❌ DEBUG_TEAMS ERROR: {str(e)}")
        import traceback

        print(f"❌ TRACEBACK: {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)})


bp = collections_bp
