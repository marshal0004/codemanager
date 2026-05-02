from flask import Blueprint, request, jsonify, current_app, send_file
from flask_login import login_required, current_user
from sqlalchemy import or_, and_, desc
from datetime import datetime,timedelta
import json
import hashlib
from ..models.snippet import Snippet
from ..models.collection import Collection
from ..models.user import User
from ..services.snippet_analyzer import detect_language, generate_tags
from ..services.search_engine import search_snippets
from ..services.export_service import export_snippets
from ..utils.validators import validate_snippet_data
from .. import db
from ..services.execution_service import ExecutionService
from ..services.export_service import ExportService
from ..services.comparison_service import ComparisonService
import tempfile
import os
import uuid

snippets_bp = Blueprint("snippets", __name__, url_prefix="/api/snippets")


@snippets_bp.route("/", methods=["GET"])
@login_required
def get_snippets():
    """Get all snippets for current user with filtering and pagination"""
    try:
        page = request.args.get("page", 1, type=int)
        per_page = min(request.args.get("per_page", 20, type=int), 100)

        # Filtering parameters
        language = request.args.get("language")
        collection_id = request.args.get("collection_id")
        search_query = request.args.get("search")
        sort_by = request.args.get("sort_by", "created_at")
        sort_order = request.args.get("sort_order", "desc")

        # Base query - exclude deleted snippets
        query = Snippet.query.filter_by(user_id=current_user.id).filter(
            (Snippet.is_deleted == False) | (Snippet.is_deleted.is_(None))
        )

        # Apply filters
        if language:
            query = query.filter(Snippet.language.ilike(f"%{language}%"))

        # FIXED: Only apply collection filter when collection_id is specifically requested
        if collection_id:
            # Handle collection filtering through relationship
            query = query.join(Snippet.collections).filter(
                Collection.id == collection_id
            )
        # If no collection_id filter is requested, show ALL snippets (including those in collections)

        if search_query:
            query = query.filter(
                or_(
                    Snippet.title.contains(search_query),
                    Snippet.code.contains(search_query),
                    Snippet.tags.contains(search_query),
                )
            )

        # Apply sorting
        if sort_by == "title":
            order_column = Snippet.title
        elif sort_by == "language":
            order_column = Snippet.language
        elif sort_by == "updated_at":
            order_column = Snippet.updated_at
        else:
            order_column = Snippet.created_at

        if sort_order == "asc":
            query = query.order_by(order_column.asc())
        else:
            query = query.order_by(order_column.desc())

        # Paginate
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        snippets = []
        for snippet in pagination.items:
            snippet_data = snippet.to_dict()
            snippets.append(snippet_data)

        return jsonify(
            {
                "success": True,
                "snippets": snippets,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": pagination.total,
                    "pages": pagination.pages,
                    "has_next": pagination.has_next,
                    "has_prev": pagination.has_prev,
                },
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error fetching snippets: {str(e)}")
        return jsonify({"success": False, "message": "Failed to fetch snippets"}), 500


@snippets_bp.route("/<snippet_id>/collections", methods=["POST"])
@login_required
def add_snippet_to_collection(snippet_id):
    """Add snippet to a collection"""
    try:
        print(f"📁 ===== ADD SNIPPET TO COLLECTION START =====")
        print(f"📁 Snippet ID: {snippet_id}")

        data = request.get_json()
        collection_id = data.get("collection_id")
        print(f"📁 Collection ID: {collection_id}")

        if not collection_id:
            return jsonify({"success": False, "message": "Collection ID required"}), 400

        # Verify snippet ownership
        snippet = Snippet.query.filter_by(
            id=snippet_id, user_id=current_user.id, is_deleted=False
        ).first()

        if not snippet:
            return jsonify({"success": False, "message": "Snippet not found"}), 404

        # Verify collection ownership
        collection = Collection.query.filter_by(
            id=collection_id, user_id=current_user.id
        ).first()

        if not collection:
            return jsonify({"success": False, "message": "Collection not found"}), 404

        # Check if already in collection
        from sqlalchemy import text

        existing = db.session.execute(
            text(
                "SELECT 1 FROM snippet_collections WHERE snippet_id = :snippet_id AND collection_id = :collection_id"
            ),
            {"snippet_id": str(snippet_id), "collection_id": str(collection_id)},
        ).fetchone()

        if existing:
            return (
                jsonify({"success": False, "message": "Snippet already in collection"}),
                400,
            )

        # Add to collection
        db.session.execute(
            text(
                "INSERT INTO snippet_collections (snippet_id, collection_id) VALUES (:snippet_id, :collection_id)"
            ),
            {"snippet_id": str(snippet_id), "collection_id": str(collection_id)},
        )

        db.session.commit()
        print(f"✅ Successfully added snippet to collection")

        return jsonify(
            {
                "success": True,
                "message": f"Added to collection '{collection.name}'",
                "collection": {"id": collection.id, "name": collection.name},
            }
        )

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error adding snippet to collection: {str(e)}")
        return (
            jsonify({"success": False, "message": "Failed to add to collection"}),
            500,
        )


@snippets_bp.route("/<snippet_id>/collections/<collection_id>", methods=["DELETE"])
@login_required
def remove_snippet_from_collection(snippet_id, collection_id):
    """Remove snippet from a collection"""
    try:
        print(f"📁 ===== REMOVE SNIPPET FROM COLLECTION START =====")
        print(f"📁 Snippet ID: {snippet_id}")
        print(f"📁 Collection ID: {collection_id}")

        # Verify snippet ownership
        snippet = Snippet.query.filter_by(
            id=snippet_id, user_id=current_user.id, is_deleted=False
        ).first()

        if not snippet:
            return jsonify({"success": False, "message": "Snippet not found"}), 404

        # Verify collection ownership
        collection = Collection.query.filter_by(
            id=collection_id, user_id=current_user.id
        ).first()

        if not collection:
            return jsonify({"success": False, "message": "Collection not found"}), 404

        # Remove from collection
        from sqlalchemy import text

        result = db.session.execute(
            text(
                "DELETE FROM snippet_collections WHERE snippet_id = :snippet_id AND collection_id = :collection_id"
            ),
            {"snippet_id": str(snippet_id), "collection_id": str(collection_id)},
        )

        if result.rowcount == 0:
            return (
                jsonify({"success": False, "message": "Snippet not in collection"}),
                400,
            )

        db.session.commit()
        print(f"✅ Successfully removed snippet from collection")

        return jsonify(
            {"success": True, "message": f"Removed from collection '{collection.name}'"}
        )

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error removing snippet from collection: {str(e)}")
        return (
            jsonify({"success": False, "message": "Failed to remove from collection"}),
            500,
        )


@snippets_bp.route("/<snippet_id>/collections", methods=["GET"])
@login_required
def get_snippet_collections(snippet_id):
    """Get all collections that contain this snippet"""
    try:
        print(f"🔍 ===== GET SNIPPET COLLECTIONS START =====")
        print(f"🔍 Snippet ID: {snippet_id}")
        print(f"🔍 User ID: {current_user.id}")

        # Verify snippet ownership
        snippet = Snippet.query.filter_by(
            id=snippet_id, user_id=current_user.id, is_deleted=False
        ).first()

        if not snippet:
            print(f"❌ Snippet not found: {snippet_id}")
            return jsonify({"success": False, "message": "Snippet not found"}), 404

        print(f"✅ Found snippet: {snippet.title}")

        # Get collections for this snippet using raw SQL for reliability
        from sqlalchemy import text

        collections_query = text(
            """
            SELECT c.id, c.name, c.description, c.color 
            FROM collections c
            JOIN snippet_collections sc ON c.id = sc.collection_id
            WHERE sc.snippet_id = :snippet_id 
            AND c.user_id = :user_id
            ORDER BY c.name ASC
        """
        )

        result = db.session.execute(
            collections_query,
            {"snippet_id": str(snippet_id), "user_id": str(current_user.id)},
        )

        collections_data = []
        for row in result.fetchall():
            collection_info = {
                "id": row.id,
                "name": row.name,
                "description": row.description,
                "color": row.color,
            }
            collections_data.append(collection_info)
            print(f"✅ Found collection: {row.name} (ID: {row.id})")

        print(f"🔍 Total collections found: {len(collections_data)}")
        print(f"🔍 ===== GET SNIPPET COLLECTIONS END =====")

        return jsonify(
            {
                "success": True,
                "collections": collections_data,
                "snippet_id": snippet_id,
                "count": len(collections_data),
            }
        )

    except Exception as e:
        print(f"❌ Error getting snippet collections: {str(e)}")
        import traceback

        print(f"❌ Full traceback: {traceback.format_exc()}")
        return jsonify({"success": False, "message": "Failed to get collections"}), 500


@snippets_bp.route("/<snippet_id>", methods=["GET"])
@login_required
def get_snippet(snippet_id):
    """Get a specific snippet by ID"""
    try:
        snippet = (
            Snippet.query.filter_by(id=snippet_id, user_id=current_user.id)
            .filter((Snippet.is_deleted == False) | (Snippet.is_deleted.is_(None)))
            .first()
        )

        if not snippet:
            return jsonify({"success": False, "message": "Snippet not found"}), 404

        # Increment view count
        snippet.view_count += 1
        snippet.last_accessed = datetime.utcnow()
        db.session.commit()
    
        snippet_data = snippet.to_dict()
        # Get collection names from many-to-many relationship
        if snippet.collections:
            snippet_data["collection_names"] = [col.name for col in snippet.collections]
        else:
            snippet_data["collection_names"] = []

        return jsonify({"success": True, "snippet": snippet_data})

    except Exception as e:
        current_app.logger.error(f"Error fetching snippet {snippet_id}: {str(e)}")
        return jsonify({"success": False, "message": "Failed to fetch snippet"}), 500


@snippets_bp.route("/", methods=["POST"])
@login_required
def create_snippet():
    """Create a new snippet"""
    try:
        data = request.get_json()
        print(f"🎯 SNIPPET CREATE - Received data: {data}")

        # Handle both 'code' and 'content' field names
        code_content = data.get("code") or data.get("content")
        title = data.get("title")
        collection_id = data.get("collection_id")  # Extract collection_id

        # Basic validation
        if not title or not code_content:
            return (
                jsonify({"success": False, "message": "Title and code are required"}),
                400,
            )

        # Auto-detect language if not provided
        language = data.get("language", "text")
        if not language or language == "auto":
            # Simple language detection
            if "function" in code_content and "{" in code_content:
                language = "javascript"
            elif "def " in code_content and ":" in code_content:
                language = "python"
            elif "<html" in code_content.lower():
                language = "html"
            elif "SELECT" in code_content.upper() or "INSERT" in code_content.upper():
                language = "sql"
            else:
                language = "text"

        # Validate collection ownership if provided
        if collection_id:
            collection = Collection.query.filter_by(
                id=collection_id, user_id=current_user.id
            ).first()
            if not collection:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Collection not found or access denied",
                        }
                    ),
                    403,
                )
            print(f"✅ Collection validated: {collection.name}")

        # Generate unique snippet ID
        import uuid

        snippet_id = str(uuid.uuid4())

        # Handle tags properly
        tags_str = ""
        if isinstance(data.get("tags"), list):
            tags_str = ",".join([tag.strip() for tag in data["tags"] if tag.strip()])
        elif data.get("tags"):
            tags_str = str(data["tags"]).strip()

        # Insert snippet with ALL required fields
        sql = db.text(
            """
        INSERT INTO snippets (
            id, user_id, title, code, language, source_url, tags, 
            created_at, updated_at, is_deleted, version, is_team_snippet,
            share_permission, is_public, is_collaborative, version_number,
            is_version, execution_count, view_count, copy_count, share_count,
            source_type, "order", status
        ) VALUES (
            :id, :user_id, :title, :code, :language, :source_url, :tags,
            :created_at, :updated_at, :is_deleted, :version, :is_team_snippet,
            :share_permission, :is_public, :is_collaborative, :version_number,
            :is_version, :execution_count, :view_count, :copy_count, :share_count,
            :source_type, :order_val, :status
        )
        """
        )

        from datetime import datetime

        now = datetime.utcnow()

        # Execute snippet creation
        db.session.execute(
            sql,
            {
                "id": snippet_id,
                "user_id": str(current_user.id),
                "title": title.strip(),
                "code": code_content,
                "language": language,
                "source_url": data.get("source_url"),
                "tags": tags_str,
                "created_at": now,
                "updated_at": now,
                "is_deleted": False,
                "version": 1,
                "is_team_snippet": False,
                "share_permission": "READ",
                "is_public": data.get("is_public", False),
                "is_collaborative": False,
                "version_number": 1,
                "is_version": False,
                "execution_count": 0,
                "view_count": 0,
                "copy_count": 0,
                "share_count": 0,
                "source_type": "manual",
                "order_val": 0,
                "status": "ACTIVE",  # Use uppercase to match enum
            },
        )

        # CRITICAL: Link snippet to collection if collection_id is provided
        # CRITICAL: Link snippet to collection if collection_id is provided
        if collection_id:
            relationship_sql = db.text(
                """
            INSERT INTO snippet_collections (snippet_id, collection_id)
            VALUES (:snippet_id, :collection_id)
            """
            )

            db.session.execute(
                relationship_sql,
                {"snippet_id": snippet_id, "collection_id": collection_id},
            )
            print(f"✅ Snippet linked to collection: {collection_id}")

        # NEW: Handle team sharing during creation
        team_ids = data.get("team_ids", [])
        team_permissions = data.get("team_permissions", {})

        if team_ids:
            # Update snippet with team sharing info
            update_sql = db.text(
                """
                UPDATE snippets 
                SET shared_team_ids = :team_ids, team_permissions = :permissions
                WHERE id = :snippet_id
                """
            )

            db.session.execute(
                update_sql,
                {
                    "snippet_id": snippet_id,
                    "team_ids": json.dumps(team_ids),
                    "permissions": json.dumps(team_permissions),
                },
            )
            print(f"✅ Snippet shared with teams during creation: {team_ids}")

        # Commit all changes
        db.session.commit()

        print(
            f"✅ SNIPPET CREATED SUCCESSFULLY - ID: {snippet_id}, Title: {title}, Collection: {collection_id}"
        )

        # Return comprehensive response
        return (
            jsonify(
                {
                    "success": True,
                    "message": "Snippet created successfully",
                    "snippet": {
                        "id": snippet_id,
                        "title": title,
                        "code": code_content,
                        "language": language,
                        "collection_id": collection_id,
                        "tags": tags_str.split(",") if tags_str else [],
                        "created_at": now.isoformat(),
                        "is_public": data.get("is_public", False),
                        "view_count": 0,
                        "line_count": len(code_content.split("\n")),
                        "character_count": len(code_content),
                    },
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        print(f"❌ SNIPPET CREATE ERROR: {str(e)}")
        import traceback

        print(f"❌ FULL TRACEBACK: {traceback.format_exc()}")

        return (
            jsonify(
                {"success": False, "message": f"Failed to create snippet: {str(e)}"}
            ),
            500,
        )


@snippets_bp.route("/<snippet_id>", methods=["PUT"])
@login_required
def update_snippet(snippet_id):
    """Update an existing snippet"""
    try:
        snippet = Snippet.query.filter_by(
            id=snippet_id, user_id=current_user.id, is_deleted=False
        ).first()

        if not snippet:
            return jsonify({"success": False, "message": "Snippet not found"}), 404

        data = request.get_json()
        print(f"🔧 UPDATE SNIPPET - Received data: {data}")
        print(f"🔧 Data keys: {list(data.keys()) if data else 'No data'}")
        print(
            f"🔧 Data types: {[(k, type(v)) for k, v in data.items()] if data else 'No data'}"
        )

        # Validate input data with detailed error logging
        validation_result = validate_snippet_data(data, is_update=True)
        print(f"🔧 Validation result: {validation_result}")

        if not validation_result["valid"]:
            print(f"❌ Validation failed: {validation_result['errors']}")
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Invalid data",
                        "errors": validation_result["errors"],
                        "received_data": data,  # Add this for debugging
                    }
                ),
                400,
            )

        # Rest of your code stays the same...
        print(f"🔧 Updating snippet: {snippet.id}")

        # Update fields
        if "title" in data:
            snippet.title = data["title"]
        if "code" in data:
            snippet.code = data["code"]
            print(f"✅ Updated code for snippet: {snippet.id}")
        if "language" in data:
            snippet.language = data["language"]
        if "description" in data:
            snippet.description = data["description"]
        if "tags" in data:
            snippet.tags = data["tags"]

        snippet.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": "Snippet updated successfully",
                "snippet": {
                    "id": snippet.id,
                    "title": snippet.title,
                    "code": snippet.code,
                    "language": snippet.language,
                    "description": getattr(snippet, "description", ""),
                    "tags": snippet.tags,
                    "updated_at": snippet.updated_at.isoformat(),
                },
            }
        )

    except Exception as e:
        db.session.rollback()
        print(f"❌ ERROR updating snippet {snippet_id}: {str(e)}")
        import traceback

        print(f"❌ FULL TRACEBACK: {traceback.format_exc()}")
        return jsonify({"success": False, "message": "Failed to update snippet"}), 500


@snippets_bp.route("/<snippet_id>", methods=["DELETE"])
@login_required
def delete_snippet(snippet_id):
    """Delete a snippet (soft delete)"""
    try:
        snippet = Snippet.query.filter_by(
            id=snippet_id, user_id=current_user.id, is_deleted=False
        ).first()

        if not snippet:
            return jsonify({"success": False, "message": "Snippet not found"}), 404

        # Soft delete
        snippet.is_deleted = True
        snippet.updated_at = datetime.utcnow()

        # CRITICAL FIX: Remove snippet from all collections when deleted
        # Convert UUIDs to strings for SQLite compatibility
        from sqlalchemy import text

        # Remove from snippet_collections table using string IDs
        db.session.execute(
            text("DELETE FROM snippet_collections WHERE snippet_id = :snippet_id"),
            {"snippet_id": str(snippet_id)},
        )

        db.session.commit()

        print(f"✅ Snippet {snippet_id} marked as deleted and removed from collections")

        return jsonify({"success": True, "message": "Snippet deleted successfully"})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting snippet {snippet_id}: {str(e)}")
        return jsonify({"success": False, "message": "Failed to delete snippet"}), 500


@snippets_bp.route("/<snippet_id>/favorite", methods=["POST"])
@login_required
def toggle_favorite(snippet_id):
    """Toggle favorite status for a snippet"""
    try:
        snippet = Snippet.query.filter_by(
            id=snippet_id, user_id=current_user.id, is_deleted=False
        ).first()

        if not snippet:
            return jsonify({"success": False, "message": "Snippet not found"}), 404

        # Toggle favorite status
        current_favorite = getattr(snippet, "is_favorite", False)
        snippet.is_favorite = not current_favorite
        snippet.updated_at = datetime.utcnow()
        db.session.commit()

        print(f"✅ Toggled favorite for snippet {snippet_id}: {snippet.is_favorite}")

        return jsonify(
            {
                "success": True,
                "is_favorite": snippet.is_favorite,
                "message": "Favorite status updated",
            }
        )

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error toggling favorite {snippet_id}: {str(e)}")
        return jsonify({"success": False, "message": "Failed to update favorite"}), 500


@snippets_bp.route("/bulk", methods=["POST"])
@login_required
def bulk_operations():
    """Handle bulk operations on snippets"""
    try:
        data = request.get_json()
        operation = data.get("operation")
        snippet_ids = data.get("snippet_ids", [])

        if not operation or not snippet_ids:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Operation and snippet_ids are required",
                    }
                ),
                400,
            )

        # Verify all snippets belong to current user
        snippets = Snippet.query.filter(
            Snippet.id.in_(snippet_ids),
            Snippet.user_id == current_user.id,
            Snippet.is_deleted == False,
        ).all()

        if len(snippets) != len(snippet_ids):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Some snippets not found or access denied",
                    }
                ),
                403,
            )

        if operation == "delete":
            for snippet in snippets:
                snippet.is_deleted = True
                snippet.deleted_at = datetime.utcnow()
            message = f"{len(snippets)} snippets deleted successfully"

        elif operation == "move_to_collection":
            collection_id = data.get("collection_id")
            if collection_id:
                collection = Collection.query.filter_by(
                    id=collection_id, user_id=current_user.id, is_deleted=False
                ).first()
                if not collection:
                    return (
                        jsonify({"success": False, "message": "Collection not found"}),
                        404,
                    )

            for snippet in snippets:
                snippet.collection_id = collection_id
            message = f"{len(snippets)} snippets moved successfully"

        elif operation == "update_tags":
            new_tags = data.get("tags", [])
            for snippet in snippets:
                snippet.tags = new_tags
            message = f"{len(snippets)} snippets tagged successfully"

        elif operation == "export":
            format_type = data.get("format", "json")
            export_data = export_snippets(snippets, format_type)
            return jsonify(
                {"success": True, "export_data": export_data, "format": format_type}
            )

        else:
            return jsonify({"success": False, "message": "Invalid operation"}), 400

        db.session.commit()

        return jsonify(
            {"success": True, "message": message, "affected_count": len(snippets)}
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in bulk operation: {str(e)}")
        return (
            jsonify({"success": False, "message": "Failed to perform bulk operation"}),
            500,
        )


@snippets_bp.route("/<int:snippet_id>/versions", methods=["GET"])
@login_required
def get_snippet_versions(snippet_id):
    """Get version history for a snippet"""
    try:
        snippet = Snippet.query.filter_by(
            id=snippet_id, user_id=current_user.id, is_deleted=False
        ).first()

        if not snippet:
            return jsonify({"success": False, "message": "Snippet not found"}), 404

        versions = snippet.get_versions()

        return jsonify({"success": True, "versions": versions})

    except Exception as e:
        current_app.logger.error(
            f"Error fetching versions for snippet {snippet_id}: {str(e)}"
        )
        return jsonify({"success": False, "message": "Failed to fetch versions"}), 500


@snippets_bp.route("/search", methods=["GET"])
@login_required
def search_user_snippets():
    """Advanced search for snippets"""
    try:
        query = request.args.get("q", "")
        if not query:
            return jsonify({"success": False, "message": "Search query required"}), 400

        results = search_snippets(query, current_user.id)

        return jsonify({"success": True, "results": results, "query": query})

    except Exception as e:
        current_app.logger.error(f"Error searching snippets: {str(e)}")
        return jsonify({"success": False, "message": "Search failed"}), 500


@snippets_bp.route("/bulk-delete", methods=["DELETE"])
@login_required
def bulk_delete_snippets():
    """Delete multiple snippets at once"""
    try:
        data = request.get_json()
        snippet_ids = data.get("snippet_ids", [])

        if not snippet_ids:
            return jsonify({"error": "No snippet IDs provided"}), 400

        # Verify all snippets belong to current user
        snippets = Snippet.query.filter(
            Snippet.id.in_(snippet_ids), Snippet.user_id == current_user.id
        ).all()

        if len(snippets) != len(snippet_ids):
            return jsonify({"error": "Some snippets not found or unauthorized"}), 403

        # Delete snippets
        for snippet in snippets:
            db.session.delete(snippet)

        db.session.commit()

        return jsonify(
            {
                "message": f"Successfully deleted {len(snippets)} snippets",
                "deleted_count": len(snippets),
            }
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@snippets_bp.route("/bulk-export", methods=["POST"])
@login_required
def bulk_export_snippets():
    """Export multiple snippets to various formats"""
    try:
        data = request.get_json()
        snippet_ids = data.get("snippet_ids", [])
        export_format = data.get("format", "json")  # json, markdown, zip

        if not snippet_ids:
            return jsonify({"error": "No snippet IDs provided"}), 400

        # Get snippets
        snippets = Snippet.query.filter(
            Snippet.id.in_(snippet_ids), Snippet.user_id == current_user.id
        ).all()

        if not snippets:
            return jsonify({"error": "No snippets found"}), 404

        # Export snippets
        export_service = ExportService()
        export_data = export_service.export_snippets(snippets, export_format)

        if export_format == "file":
            # Return file download
            return send_file(
                export_data["file_path"],
                as_attachment=True,
                download_name=export_data["filename"],
            )
        else:
            # Return data directly
            return jsonify(export_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@snippets_bp.route("/bulk-update", methods=["PUT"])
@login_required
def bulk_update_snippets():
    """Update multiple snippets with common properties"""
    try:
        data = request.get_json()
        snippet_ids = data.get("snippet_ids", [])
        updates = data.get("updates", {})

        if not snippet_ids or not updates:
            return jsonify({"error": "Invalid request data"}), 400

        # Get snippets
        snippets = Snippet.query.filter(
            Snippet.id.in_(snippet_ids), Snippet.user_id == current_user.id
        ).all()

        # Update allowed fields
        allowed_fields = ["collection_id", "tags", "is_private", "description"]
        updated_count = 0

        for snippet in snippets:
            for field, value in updates.items():
                if field in allowed_fields:
                    if field == "tags" and isinstance(value, list):
                        snippet.tags = ",".join(value) if value else ""
                    else:
                        setattr(snippet, field, value)
                    updated_count += 1

        db.session.commit()

        return jsonify(
            {
                "message": f"Successfully updated {len(snippets)} snippets",
                "updated_count": len(snippets),
            }
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@snippets_bp.route("/<int:snippet_id>/execute", methods=["POST"])
@login_required
def execute_snippet(snippet_id):
    """Execute a code snippet in a safe sandboxed environment"""
    try:
        snippet = Snippet.query.filter_by(
            id=snippet_id, user_id=current_user.id
        ).first_or_404()

        execution_service = ExecutionService()

        # Check if language is supported for execution
        if not execution_service.is_language_supported(snippet.language):
            return (
                jsonify({"error": f"Execution not supported for {snippet.language}"}),
                400,
            )

        # Execute code
        result = execution_service.execute_code(
            code=snippet.code,
            language=snippet.language,
            input_data=request.json.get("input", ""),
        )

        # Update snippet analytics
        snippet.execution_count = (snippet.execution_count or 0) + 1
        snippet.last_executed = datetime.utcnow()
        db.session.commit()

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@snippets_bp.route("/<int:snippet_id>/compare/<int:other_snippet_id>", methods=["GET"])
@login_required
def compare_snippets(snippet_id, other_snippet_id):
    """Compare two snippets and return diff"""
    try:
        # Get both snippets
        snippet1 = Snippet.query.filter_by(
            id=snippet_id, user_id=current_user.id
        ).first_or_404()

        snippet2 = Snippet.query.filter_by(
            id=other_snippet_id, user_id=current_user.id
        ).first_or_404()

        comparison_service = ComparisonService()
        diff_result = comparison_service.compare_snippets(snippet1, snippet2)

        return jsonify(diff_result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@snippets_bp.route("/<int:snippet_id>/duplicate", methods=["POST"])
@login_required
def duplicate_snippet(snippet_id):
    """Create a duplicate of an existing snippet"""
    try:
        original = Snippet.query.filter_by(
            id=snippet_id, user_id=current_user.id
        ).first_or_404()

        # Create duplicate
        duplicate = Snippet(
            title=f"{original.title} (Copy)",
            code=original.code,
            language=original.language,
            description=original.description,
            tags=original.tags,
            user_id=current_user.id,
            collection_id=original.collection_id,
            is_private=original.is_private,
        )

        db.session.add(duplicate)
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Snippet duplicated successfully",
                    "snippet": {
                        "id": duplicate.id,
                        "title": duplicate.title,
                        "created_at": duplicate.created_at.isoformat(),
                    },
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@snippets_bp.route("/analytics", methods=["GET"])
@login_required
def get_snippets_analytics():
    """Get user's snippet analytics and statistics"""
    try:
        # Get date range from query params
        days = request.args.get("days", 30, type=int)
        start_date = datetime.utcnow() - timedelta(days=days)

        # Basic counts
        total_snippets = Snippet.query.filter_by(user_id=current_user.id).count()
        public_snippets = Snippet.query.filter_by(
            user_id=current_user.id, is_private=False
        ).count()

        # Language distribution
        language_stats = (
            db.session.query(Snippet.language, db.func.count(Snippet.id).label("count"))
            .filter_by(user_id=current_user.id)
            .group_by(Snippet.language)
            .all()
        )

        # Recent activity
        recent_snippets = Snippet.query.filter(
            Snippet.user_id == current_user.id, Snippet.created_at >= start_date
        ).count()

        # Most used tags
        all_tags = []
        snippets_with_tags = Snippet.query.filter(
            Snippet.user_id == current_user.id,
            Snippet.tags.isnot(None),
            Snippet.tags != "",
        ).all()

        for snippet in snippets_with_tags:
            if snippet.tags:
                all_tags.extend([tag.strip() for tag in snippet.tags.split(",")])

        from collections import Counter

        tag_counts = Counter(all_tags).most_common(10)

        return jsonify(
            {
                "total_snippets": total_snippets,
                "public_snippets": public_snippets,
                "private_snippets": total_snippets - public_snippets,
                "recent_snippets": recent_snippets,
                "language_distribution": [
                    {"language": lang, "count": count} for lang, count in language_stats
                ],
                "popular_tags": [
                    {"tag": tag, "count": count} for tag, count in tag_counts
                ],
                "period_days": days,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@snippets_bp.route("/statistics", methods=["GET"])
@login_required
def get_snippet_statistics():
    """Get user's snippet statistics"""
    try:
        total_snippets = Snippet.query.filter_by(
            user_id=current_user.id, is_deleted=False
        ).count()

        # Language distribution
        language_stats = (
            db.session.query(Snippet.language, db.func.count(Snippet.id).label("count"))
            .filter_by(user_id=current_user.id, is_deleted=False)
            .group_by(Snippet.language)
            .all()
        )

        # Recent activity
        recent_snippets = (
            Snippet.query.filter_by(user_id=current_user.id, is_deleted=False)
            .order_by(desc(Snippet.created_at))
            .limit(5)
            .all()
        )

        # Most viewed snippets
        popular_snippets = (
            Snippet.query.filter_by(user_id=current_user.id, is_deleted=False)
            .order_by(desc(Snippet.view_count))
            .limit(5)
            .all()
        )

        return jsonify(
            {
                "success": True,
                "statistics": {
                    "total_snippets": total_snippets,
                    "language_distribution": [
                        {"language": lang, "count": count}
                        for lang, count in language_stats
                    ],
                    "recent_snippets": [s.to_dict() for s in recent_snippets],
                    "popular_snippets": [s.to_dict() for s in popular_snippets],
                },
            }
        )

    except Exception as e:
        current_app.logger.error(f"Error fetching statistics: {str(e)}")
        return jsonify({"success": False, "message": "Failed to fetch statistics"}), 500


@snippets_bp.route("/<snippet_id>/share", methods=["POST"])
@login_required
def share_snippet_with_teams(snippet_id):
    """Share snippet with teams"""
    try:
        from ..services.collaboration_service import collaboration_service

        print(f"🔗 SHARING SNIPPET: {snippet_id} by user {current_user.id}")

        data = request.get_json()
        team_ids = data.get("team_ids", [])
        sharing_type = "copy"

        if not team_ids:
            return jsonify({"success": False, "message": "No teams selected"}), 400

        shared_count = 0
        already_shared_count = 0  # ✅ NEW: Track already shared
        already_shared_teams = []  # ✅ NEW: Track team names
        errors = []

        for team_id in team_ids:
            try:
                result = collaboration_service.share_snippet_with_team_copy(
                    snippet_id, str(team_id), current_user.id
                )

                if result.get("success"):
                    shared_count += 1
                    print(f"✅ SNIPPET SHARED with team {team_id}")
                else:
                    # ✅ DETECT "ALREADY SHARED" SPECIFICALLY
                    if "already shared" in result.get("message", "").lower():
                        already_shared_count += 1
                        already_shared_teams.append(team_id)  # ✅ Track team
                        print(f"ℹ️ SNIPPET ALREADY SHARED with team {team_id}")
                    else:
                        error_msg = result.get("message", "Unknown error")
                        errors.append(f"Team {team_id}: {error_msg}")

            except Exception as team_error:
                errors.append(f"Team {team_id}: {str(team_error)}")
                continue

        # ✅ RETURN SPECIFIC RESPONSES WITH 409 FOR ALREADY SHARED
        total_teams = len(team_ids)

        if already_shared_count == total_teams:
            # All teams already have this snippet - 409 CONFLICT
            return (
                jsonify(
                    {
                        "success": False,  # ✅ False to trigger frontend handling
                        "error_type": "already_shared",
                        "message": "Snippet already shared with selected team(s)",
                        "already_shared_teams": already_shared_teams,
                        "shared_count": 0,
                        "already_shared_count": already_shared_count,
                    }
                ),
                409,
            )  # ✅ 409 CONFLICT as requested

        elif shared_count > 0 and already_shared_count > 0:
            # Mixed results - 200 SUCCESS
            return jsonify(
                {
                    "success": True,
                    "message": f"Snippet shared with {shared_count} team(s), {already_shared_count} already had it",
                    "shared_count": shared_count,
                    "already_shared_count": already_shared_count,
                    "already_shared_teams": already_shared_teams,
                }
            )

        elif shared_count > 0:
            # All new shares - 200 SUCCESS
            return jsonify(
                {
                    "success": True,
                    "message": f"Snippet shared with {shared_count} team(s) successfully",
                    "shared_count": shared_count,
                    "already_shared_count": 0,
                }
            )
        else:
            # All failed - 500 ERROR
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
        db.session.rollback()
        print(f"❌ SHARE ERROR: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


@snippets_bp.route("/<snippet_id>/shared-teams", methods=["GET"])
@login_required
def get_snippet_shared_teams(snippet_id):
    """Get teams snippet is shared with"""
    try:
        snippet = Snippet.query.filter_by(
            id=snippet_id, user_id=current_user.id, is_deleted=False
        ).first()

        if not snippet:
            return jsonify({"success": False, "message": "Snippet not found"}), 404

        shared_teams = snippet.get_shared_teams()

        return jsonify(
            {
                "success": True,
                "shared_teams": shared_teams,
                "permissions": snippet.team_permissions or {},
            }
        )

    except Exception as e:
        print(f"❌ GET_SNIPPET_SHARED_TEAMS ERROR: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


@snippets_bp.route("/user-teams", methods=["GET"])
@login_required
def get_user_teams_for_snippet_sharing():
    """Get user's teams for snippet sharing - FIXED VERSION"""
    try:
        from ..services.collaboration_service import collaboration_service

        result = collaboration_service.get_user_teams_for_sharing(current_user.id)

        if result.get("success"):
            teams = result.get("teams", [])

            # 🔥 FIXED: Use the same logic as working teams page
            created_teams = []
            joined_teams = []

            for team in teams:
                # 🔥 BULLETPROOF OWNERSHIP CHECK (same as teams page)
                user_id_str = str(current_user.id)

                # Check multiple ownership indicators
                is_owner = team.get("is_owner", False)
                is_creator = team.get("is_creator", False)
                is_team_creator = team.get("is_team_creator", False)
                team_type = team.get("team_type", "")

                # Role-based check (handle case variations)
                role_str = str(team.get("role", "")).upper().strip()
                is_admin_or_owner = role_str in ["OWNER", "ADMIN"]

                # Owner ID check
                owner_id = str(team.get("owner_id", "")) if team.get("owner_id") else ""
                created_by = (
                    str(team.get("created_by", "")) if team.get("created_by") else ""
                )

                # 🔥 COMPREHENSIVE OWNERSHIP DETERMINATION
                is_team_owner = (
                    is_owner
                    or is_creator
                    or is_team_creator
                    or team_type == "created"
                    or is_admin_or_owner
                    or owner_id == user_id_str
                    or created_by == user_id_str
                )

                # Debug logging
                print(f"🔍 SNIPPET TEAMS: {team.get('name')}")
                print(f"  - is_owner: {is_owner}")
                print(f"  - is_creator: {is_creator}")
                print(f"  - team_type: {team_type}")
                print(f"  - role: {role_str}")
                print(f"  - owner_id: {owner_id} vs user: {user_id_str}")
                print(f"  - FINAL: {'CREATED' if is_team_owner else 'JOINED'}")

                if is_team_owner:
                    created_teams.append(team)
                else:
                    joined_teams.append(team)

            print(
                f"✅ SNIPPET TEAMS RESULT: Created={len(created_teams)}, Joined={len(joined_teams)}"
            )

            return jsonify(
                {
                    "success": True,
                    "created_teams": created_teams,
                    "joined_teams": joined_teams,
                    "all_teams": teams,
                }
            )
        else:
            return jsonify(result), 500

    except Exception as e:
        print(f"❌ GET_USER_TEAMS_SNIPPET ERROR: {str(e)}")
        import traceback

        print(f"❌ TRACEBACK: {traceback.format_exc()}")
        return jsonify({"success": False, "message": str(e)}), 500


bp = snippets_bp  # Alias for import compatibility
