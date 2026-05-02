from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime
from app.models import db
from app.services.edit_tracking_service import edit_tracking_service
from app.websocket.events import EventManager, EventType
from app.extensions import socketio
import uuid

# Create blueprint
snippet_edits_bp = Blueprint("snippet_edits", __name__, url_prefix="/api/snippet-edits")


@snippet_edits_bp.route("/teams/<team_id>/snippets/<snippet_id>/edit", methods=["POST"])
@login_required
def create_snippet_edit(team_id, snippet_id):
    """
    Create a new snippet edit (independent copy)
    
    Expected JSON payload:
    {
        "code": "edited code content",
        "edit_description": "description of changes made",
        "title": "optional new title",
        "language": "optional new language",
        "tags": "optional new tags"
    }
    """
    try:
        print(f"🔧 CREATE SNIPPET EDIT - Team: {team_id}, Snippet: {snippet_id}, User: {current_user.id}")
        
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "message": "No data provided",
                "error_type": "validation_error"
            }), 400
        
        # Extract required fields
        edited_code = data.get("code", "").strip()
        edit_description = data.get("edit_description", "").strip()
        
        # Validate required fields
        if not edited_code:
            return jsonify({
                "success": False,
                "message": "Edited code is required",
                "error_type": "validation_error"
            }), 400
        
        if not edit_description:
            return jsonify({
                "success": False,
                "message": "Edit description is required",
                "error_type": "validation_error"
            }), 400
        
        # Validate edit description
        description_validation = edit_tracking_service.validate_edit_description(edit_description)
        if not description_validation["valid"]:
            return jsonify({
                "success": False,
                "message": description_validation["message"],
                "error_type": "validation_error"
            }), 400
        
        # Extract optional fields
        edited_title = data.get("title")
        edited_language = data.get("language")
        edited_tags = data.get("tags")
        
        # Create snippet edit
        result = edit_tracking_service.create_snippet_edit(
            original_snippet_id=snippet_id,
            team_id=team_id,
            editor_user_id=str(current_user.id),
            edited_code=edited_code,
            edit_description=edit_description,
            edited_title=edited_title,
            edited_language=edited_language,
            edited_tags=edited_tags
        )
        
        if not result["success"]:
            status_code = 404 if result.get("error_type") == "not_found" else 403 if result.get("error_type") == "permission_denied" else 400
            return jsonify(result), status_code
        
        # Emit real-time event to team members
        try:
            socketio.emit(
                'edit_created',
                {
                    "type": "snippet_edit_created",
                    "team_id": team_id,
                    "original_snippet_id": snippet_id,
                    "edit_id": result["edit_id"],
                    "editor_name": current_user.name if hasattr(current_user, 'name') else current_user.email,
                    "editor_id": str(current_user.id),
                    "edit_description": edit_description,
                    "timestamp": datetime.now().isoformat()
                },
                room=f"team_{team_id}"
            )
            print(f"✅ WebSocket event emitted for edit creation")
        except Exception as ws_error:
            print(f"⚠️ WebSocket emission failed: {str(ws_error)}")
        
        print(f"✅ Snippet edit created successfully: {result['edit_id']}")
        
        return jsonify(result), 201
        
    except Exception as e:
        print(f"❌ CREATE SNIPPET EDIT ERROR: {str(e)}")
        import traceback
        print(f"❌ TRACEBACK: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "message": "Failed to create snippet edit",
            "error_type": "server_error"
        }), 500


@snippet_edits_bp.route("/teams/<team_id>/edited-snippets", methods=["GET"])
@login_required
def get_team_edited_snippets(team_id):
    """
    Get all edited snippets for a team, grouped by original snippet
    """
    try:
        print(f"📋 GET TEAM EDITED SNIPPETS - Team: {team_id}, User: {current_user.id}")

        # Get include_deleted parameter
        include_deleted = request.args.get("include_deleted", "false").lower() == "true"

        # Get team edited snippets
        result = edit_tracking_service.get_team_edited_snippets(team_id, include_deleted)

        if not result["success"]:
            status_code = 404 if result.get("error_type") == "not_found" else 403 if result.get("error_type") == "permission_denied" else 500
            return jsonify(result), status_code

        print(f"✅ Retrieved {result['total_edits']} edits in {result['total_groups']} groups")

        return jsonify(result), 200

    except Exception as e:
        print(f"❌ GET TEAM EDITED SNIPPETS ERROR: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Failed to get team edited snippets",
            "error_type": "server_error"
        }), 500


@snippet_edits_bp.route("/<edit_id>", methods=["GET"])
@login_required
def get_snippet_edit(edit_id):
    """
    Get a specific snippet edit with full content
    """
    try:
        print(f"🔍 GET SNIPPET EDIT - Edit ID: {edit_id}, User: {current_user.id}")

        # Get snippet edit
        result = edit_tracking_service.get_snippet_edit(edit_id, str(current_user.id))

        if not result["success"]:
            status_code = (
                404
                if result.get("error_type") == "not_found"
                else 403 if result.get("error_type") == "permission_denied" else 500
            )
            return jsonify(result), status_code

        print(f"✅ Retrieved snippet edit: {edit_id}")

        return jsonify(result), 200

    except Exception as e:
        print(f"❌ GET SNIPPET EDIT ERROR: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Failed to get snippet edit",
                    "error_type": "server_error",
                }
            ),
            500,
        )


@snippet_edits_bp.route("/<edit_id>", methods=["DELETE"])
@login_required
def delete_snippet_edit(edit_id):
    """
    Delete a snippet edit (soft delete for independence)
    """
    try:
        print(f"🗑️ DELETE SNIPPET EDIT - Edit ID: {edit_id}, User: {current_user.id}")

        # Delete snippet edit
        result = edit_tracking_service.delete_snippet_edit(
            edit_id, str(current_user.id)
        )

        if not result["success"]:
            status_code = (
                404
                if result.get("error_type") == "not_found"
                else 403 if result.get("error_type") == "permission_denied" else 500
            )
            return jsonify(result), status_code

        # Emit real-time event to team members
        try:
            # Get edit info for WebSocket event (before it's deleted)
            from app.models.snippet_edit import SnippetEdit

            edit = SnippetEdit.query.filter_by(id=edit_id).first()

            if edit:
                socketio.emit(
                    "edit_deleted",
                    {
                        "type": "snippet_edit_deleted",
                        "team_id": str(edit.team_id),
                        "original_snippet_id": str(edit.original_snippet_id),
                        "edit_id": edit_id,
                        "deleted_by": str(current_user.id),
                        "timestamp": datetime.now().isoformat(),
                    },
                    room=f"team_{edit.team_id}",
                )
                print(f"✅ WebSocket event emitted for edit deletion")
        except Exception as ws_error:
            print(f"⚠️ WebSocket emission failed: {str(ws_error)}")

        print(f"✅ Snippet edit deleted successfully: {edit_id}")

        return jsonify(result), 200

    except Exception as e:
        print(f"❌ DELETE SNIPPET EDIT ERROR: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Failed to delete snippet edit",
                    "error_type": "server_error",
                }
            ),
            500,
        )


@snippet_edits_bp.route("/users/<user_id>/edits", methods=["GET"])
@login_required
def get_user_edits(user_id):
    """
    Get all edits made by a specific user
    """
    try:
        print(f"👤 GET USER EDITS - User ID: {user_id}, Requester: {current_user.id}")

        # Users can only view their own edits unless they're admin
        if str(user_id) != str(current_user.id):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "You can only view your own edits",
                        "error_type": "permission_denied",
                    }
                ),
                403,
            )

        # Get query parameters
        team_id = request.args.get("team_id")
        limit = min(int(request.args.get("limit", 50)), 100)  # Max 100

        # Get user edits
        result = edit_tracking_service.get_user_edits(user_id, team_id, limit)

        if not result["success"]:
            return jsonify(result), 500

        print(f"✅ Retrieved {result['count']} edits for user {user_id}")

        return jsonify(result), 200

    except Exception as e:
        print(f"❌ GET USER EDITS ERROR: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Failed to get user edits",
                    "error_type": "server_error",
                }
            ),
            500,
        )


@snippet_edits_bp.route("/teams/<team_id>/statistics", methods=["GET"])
@login_required
def get_team_edit_statistics(team_id):
    """
    Get edit statistics for a team
    """
    try:
        print(f"📊 GET TEAM EDIT STATISTICS - Team: {team_id}, User: {current_user.id}")

        # Get team edit statistics
        result = edit_tracking_service.get_edit_statistics(team_id)

        if not result["success"]:
            return jsonify(result), 500

        print(f"✅ Retrieved edit statistics for team {team_id}")

        return jsonify(result), 200

    except Exception as e:
        print(f"❌ GET TEAM EDIT STATISTICS ERROR: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Failed to get team edit statistics",
                    "error_type": "server_error",
                }
            ),
            500,
        )


@snippet_edits_bp.route("/validate-description", methods=["POST"])
@login_required
def validate_edit_description():
    """
    Validate edit description before submission
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"valid": False, "message": "No data provided"}), 400

        description = data.get("description", "")

        # Validate description
        result = edit_tracking_service.validate_edit_description(description)

        return jsonify(result), 200

    except Exception as e:
        print(f"❌ VALIDATE EDIT DESCRIPTION ERROR: {str(e)}")
        return jsonify({"valid": False, "message": "Validation failed"}), 500


# Error handlers for this blueprint
@snippet_edits_bp.errorhandler(404)
def not_found_error(error):
    return (
        jsonify(
            {
                "success": False,
                "message": "Resource not found",
                "error_type": "not_found",
            }
        ),
        404,
    )


@snippet_edits_bp.errorhandler(403)
def forbidden_error(error):
    return (
        jsonify(
            {
                "success": False,
                "message": "Access forbidden",
                "error_type": "permission_denied",
            }
        ),
        403,
    )


@snippet_edits_bp.route("/debug/team/<team_id>", methods=["GET"])
@login_required
def debug_team_lookup(team_id):
    """Debug team lookup methods"""
    try:
        import uuid
        from app.models.team import Team

        print(f"🔍 DEBUG: Looking for team {team_id}")

        # Try different approaches
        team_uuid = uuid.UUID(team_id)
        print(f"🔍 DEBUG: Converted to UUID object: {team_uuid}")

        # Method 1: filter with UUID object
        team1 = Team.query.filter(Team.id == team_uuid).first()
        print(
            f"🔍 DEBUG: Method 1 (UUID object): {team1.name if team1 else 'NOT FOUND'}"
        )

        # Method 2: filter_by with UUID object
        team2 = Team.query.filter_by(id=team_uuid).first()
        print(
            f"🔍 DEBUG: Method 2 (filter_by UUID): {team2.name if team2 else 'NOT FOUND'}"
        )

        # Method 3: filter with string
        team3 = Team.query.filter(Team.id == team_id).first()
        print(f"🔍 DEBUG: Method 3 (string): {team3.name if team3 else 'NOT FOUND'}")

        # Method 4: filter_by with string
        team4 = Team.query.filter_by(id=team_id).first()
        print(
            f"🔍 DEBUG: Method 4 (filter_by string): {team4.name if team4 else 'NOT FOUND'}"
        )

        # Method 5: Get all teams and check
        all_teams = Team.query.all()
        print(f"🔍 DEBUG: Total teams in database: {len(all_teams)}")

        matching_teams = []
        for team in all_teams:
            if str(team.id) == team_id:
                matching_teams.append(team.name)
                print(f"🔍 DEBUG: Found matching team: {team.name}")

        return jsonify(
            {
                "team_id": team_id,
                "team_uuid": str(team_uuid),
                "method1_filter_uuid": team1.name if team1 else None,
                "method2_filter_by_uuid": team2.name if team2 else None,
                "method3_filter_string": team3.name if team3 else None,
                "method4_filter_by_string": team4.name if team4 else None,
                "total_teams": len(all_teams),
                "matching_teams": matching_teams,
                "all_team_ids": [str(t.id) for t in all_teams[:5]],  # First 5 team IDs
            }
        )

    except Exception as e:
        print(f"❌ DEBUG ERROR: {str(e)}")
        import traceback

        print(f"❌ TRACEBACK: {traceback.format_exc()}")
        return jsonify({"error": str(e)})


@snippet_edits_bp.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return (
        jsonify(
            {
                "success": False,
                "message": "Internal server error",
                "error_type": "server_error",
            }
        ),
        500,
    )


@snippet_edits_bp.route("/debug/tables", methods=["GET"])
@login_required
def debug_tables():
    """Debug database tables"""
    try:
        from sqlalchemy import text
        from app.models import db  # Import db directly

        # Check if team_snippets table exists
        tables_sql = text("SELECT name FROM sqlite_master WHERE type='table';")
        tables = db.session.execute(tables_sql).fetchall()

        # Try to find the team snippet in different possible tables
        results = {}

        # Try team_snippets table
        try:
            team_snippet_sql = text(
                """
                SELECT * FROM team_snippets 
                WHERE id = :snippet_id 
                LIMIT 1
            """
            )

            team_snippet = db.session.execute(
                team_snippet_sql, {"snippet_id": "80399128-fd42-4270-90e1-7be0a3654f08"}
            ).fetchone()

            results["team_snippets"] = dict(team_snippet) if team_snippet else None
        except:
            results["team_snippets"] = "table_not_found"

        # Try snippets table
        try:
            snippet_sql = text(
                """
                SELECT * FROM snippets 
                WHERE id = :snippet_id 
                LIMIT 1
            """
            )

            snippet = db.session.execute(
                snippet_sql, {"snippet_id": "80399128-fd42-4270-90e1-7be0a3654f08"}
            ).fetchone()

            results["snippets"] = dict(snippet) if snippet else None
        except:
            results["snippets"] = "table_not_found"

        return jsonify({"tables": [t.name for t in tables], "search_results": results})

    except Exception as e:
        return jsonify({"error": str(e)})


# Export blueprint
bp = snippet_edits_bp
