from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.exc import IntegrityError
from app.models import db
from app.models.snippet_edit import SnippetEdit
from app.models.snippet import Snippet
from app.models.team import Team
from app.models.team_member import TeamMember
from app.models.user import User
import uuid


class EditTrackingService:
    """Service for managing snippet edit tracking and validation"""

    def __init__(self):
        self.db = db

    def create_snippet_edit(
        self,
        original_snippet_id: str,
        team_id: str,
        editor_user_id: str,
        edited_code: str,
        edit_description: str,
        edited_title: Optional[str] = None,
        edited_language: Optional[str] = None,
        edited_tags: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new snippet edit (independent copy)"""
        try:
            # Validate edit description
            if not edit_description or not edit_description.strip():
                return {
                    "success": False,
                    "message": "Edit description is required and cannot be empty",
                    "error_type": "validation_error",
                }

            description_clean = edit_description.strip()
            if len(description_clean) < 3:
                return {
                    "success": False,
                    "message": "Edit description must be at least 3 characters long",
                    "error_type": "validation_error",
                }

            # Validate edited code
            if not edited_code or not edited_code.strip():
                return {
                    "success": False,
                    "message": "Edited code cannot be empty",
                    "error_type": "validation_error",
                }

            # FIXED: Use raw SQL for snippet lookup
            from sqlalchemy import text

            # FIXED: Look in team_snippets table instead of snippets table
            snippet_sql = text(
                """
                SELECT id, title, language, tags, team_id, code FROM team_snippets 
                WHERE id = :snippet_id 
                LIMIT 1
            """
            )

            snippet_result = self.db.session.execute(
                snippet_sql, {"snippet_id": original_snippet_id}
            ).fetchone()

            if not snippet_result:
                return {
                    "success": False,
                    "message": "Original snippet not found",
                    "error_type": "not_found",
                }

            # SECURITY FIX: Verify snippet belongs to the team
            if not snippet_result.team_id or str(snippet_result.team_id) != str(
                team_id
            ):
                return {
                    "success": False,
                    "message": "This snippet does not belong to the specified team",
                    "error_type": "permission_denied",
                }

            # Validate team membership
            validation_result = self._validate_team_membership(team_id, editor_user_id)
            if not validation_result["success"]:
                return validation_result


            # CHECK: User already has an edit for this snippet
            existing_edit_sql = text("""
                SELECT id FROM snippet_edits 
                WHERE original_snippet_id = :snippet_id 
                AND editor_user_id = :user_id 
                AND team_id = :team_id 
                AND is_deleted = false
                LIMIT 1
            """)

            existing_edit = self.db.session.execute(existing_edit_sql, {
                "snippet_id": original_snippet_id,
                "user_id": editor_user_id,
                "team_id": team_id
            }).fetchone()

            if existing_edit:
                return {
                    "success": False,
                    "message": "You have already edited this snippet. Please delete your previous edit to edit again.",
                    "error_type": "duplicate_edit",
                    "existing_edit_id": str(existing_edit.id)
                }    

            # FIXED: Create edit using raw SQL insert
            import uuid

            edit_id = str(uuid.uuid4())

            insert_sql = text(
                """
                INSERT INTO snippet_edits (
                    id, original_snippet_id, team_id, editor_user_id,
                    title, code, language, tags, edit_description,
                    edit_type, created_at, updated_at, is_deleted
                ) VALUES (
                    :id, :original_snippet_id, :team_id, :editor_user_id,
                    :title, :code, :language, :tags, :edit_description,
                    :edit_type, :created_at, :updated_at, :is_deleted
                )
            """
            )

            from datetime import datetime, timezone

            now = datetime.now(timezone.utc)

            self.db.session.execute(
                insert_sql,
                {
                    "id": edit_id,
                    "original_snippet_id": original_snippet_id,
                    "team_id": team_id,
                    "editor_user_id": editor_user_id,
                    "title": edited_title or snippet_result.title,
                    "code": edited_code.strip(),
                    "language": edited_language or snippet_result.language,
                    "tags": edited_tags or snippet_result.tags,
                    "edit_description": description_clean,
                    "edit_type": "content_update",
                    "created_at": now,
                    "updated_at": now,
                    "is_deleted": False,
                },
            )

            self.db.session.commit()

            return {
                "success": True,
                "message": "Snippet edit created successfully",
                "edit_id": edit_id,
                "original_snippet_id": original_snippet_id,
                "team_id": team_id,
                "editor_id": editor_user_id,
            }

        except Exception as e:
            self.db.session.rollback()
            print(f"❌ CREATE EDIT ERROR: {str(e)}")
            import traceback

            print(f"❌ TRACEBACK: {traceback.format_exc()}")
            return {
                "success": False,
                "message": f"Failed to create snippet edit: {str(e)}",
                "error_type": "server_error",
            }

    def get_team_edited_snippets(
        self, team_id: str, include_deleted: bool = False
    ) -> Dict[str, Any]:
        """
        Get all edited snippets for a team, grouped by original snippet

        Args:
            team_id: ID of the team
            include_deleted: Whether to include deleted edits

        Returns:
            Dict with success status and grouped edits data
        """
        try:
            # FIXED: Use raw SQL to avoid model attribute issues
            from sqlalchemy import text

            # Get all edits for the team with user info
            if include_deleted:
                sql = text(
                    """
                    SELECT 
                        se.id, se.original_snippet_id, se.team_id, se.editor_user_id,
                        se.title, se.language, se.tags, se.edit_description, se.edit_type,
                        se.created_at, se.updated_at, se.is_deleted,
                        u.email as editor_email, u.username as editor_username,
                        s.title as original_title
                    FROM snippet_edits se
                    LEFT JOIN users u ON se.editor_user_id = u.id
                    LEFT JOIN snippets s ON se.original_snippet_id = s.id
                    WHERE se.team_id = :team_id
                    ORDER BY se.original_snippet_id, se.created_at DESC
                """
                )
            else:
                sql = text(
                    """
                    SELECT 
                        se.id, se.original_snippet_id, se.team_id, se.editor_user_id,
                        se.title, se.code, se.language, se.tags, se.edit_description, se.edit_type,
                        se.created_at, se.updated_at, se.is_deleted,
                        u.email as editor_email, u.username as editor_username,
                        s.title as original_title
                    FROM snippet_edits se
                    LEFT JOIN users u ON se.editor_user_id = u.id
                    LEFT JOIN snippets s ON se.original_snippet_id = s.id
                    WHERE se.team_id = :team_id AND se.is_deleted = false
                    ORDER BY se.original_snippet_id, se.created_at DESC
                """
                )

            results = self.db.session.execute(sql, {"team_id": team_id}).fetchall()

            # Group by original snippet
            grouped_edits = {}
            for row in results:
                snippet_id = str(row.original_snippet_id)

                if snippet_id not in grouped_edits:
                    grouped_edits[snippet_id] = {
                        "original_snippet_id": snippet_id,
                        "original_title": row.original_title or row.title,
                        "edits": [],
                    }

                # FIXED: Handle user name properly
                editor_name = row.editor_username or row.editor_email or "Unknown User"

                edit_data = {
                    "id": str(row.id),
                    "original_snippet_id": str(row.original_snippet_id),
                    "team_id": str(row.team_id),
                    "editor_user_id": str(row.editor_user_id),
                    "title": row.title,
                    "code": row.code,  # ← ADD THIS LINE
                    "language": row.language,
                    "tags": row.tags.split(",") if row.tags else [],
                    "edit_description": row.edit_description,
                    "edit_type": row.edit_type,
                    "created_at": str(row.created_at) if row.created_at else None,
                    "updated_at": str(row.updated_at) if row.updated_at else None,
                    "is_deleted": row.is_deleted,
                    "editor_name": editor_name,
                    "editor_email": row.editor_email,
                }

                grouped_edits[snippet_id]["edits"].append(edit_data)

            # Convert to list format
            result = list(grouped_edits.values())

            return {
                "success": True,
                "grouped_edits": result,
                "total_groups": len(result),
                "total_edits": sum(len(group["edits"]) for group in result),
            }

        except Exception as e:
            print(f"❌ GET_TEAM_EDITED_SNIPPETS ERROR: {str(e)}")
            import traceback

            print(f"❌ TRACEBACK: {traceback.format_exc()}")
            return {
                "success": False,
                "message": f"Failed to get team edited snippets: {str(e)}",
                "error_type": "server_error",
            }

    def get_snippet_edit(self, edit_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get a specific snippet edit with full content

        Args:
            edit_id: ID of the edit
            user_id: ID of the requesting user

        Returns:
            Dict with success status and edit data
        """
        try:
            # FIXED: Use raw SQL to get edit with user info
            from sqlalchemy import text

            sql = text(
                """
                SELECT 
                    se.id, se.original_snippet_id, se.team_id, se.editor_user_id,
                    se.title, se.code, se.language, se.tags, se.edit_description, 
                    se.edit_type, se.created_at, se.updated_at, se.is_deleted,
                    u.email as editor_email, u.username as editor_username
                FROM snippet_edits se
                LEFT JOIN users u ON se.editor_user_id = u.id
                WHERE se.id = :edit_id AND se.is_deleted = false
                LIMIT 1
            """
            )

            result = self.db.session.execute(sql, {"edit_id": edit_id}).fetchone()

            if not result:
                return {
                    "success": False,
                    "message": "Snippet edit not found",
                    "error_type": "not_found",
                }

            # Validate team membership
            validation_result = self._validate_team_membership(
                str(result.team_id), user_id
            )
            if not validation_result["success"]:
                return validation_result

            # FIXED: Handle user name properly
            editor_name = (
                result.editor_username or result.editor_email or "Unknown User"
            )

            edit_data = {
                "id": str(result.id),
                "original_snippet_id": str(result.original_snippet_id),
                "team_id": str(result.team_id),
                "editor_user_id": str(result.editor_user_id),
                "title": result.title,
                "code": result.code,
                "language": result.language,
                "tags": result.tags.split(",") if result.tags else [],
                "edit_description": result.edit_description,
                "edit_type": result.edit_type,
                "created_at": str(result.created_at) if result.created_at else None,
                "updated_at": str(result.updated_at) if result.updated_at else None,
                "is_deleted": result.is_deleted,
                "editor_name": editor_name,
                "editor_email": result.editor_email,
                "line_count": len(result.code.split("\n")) if result.code else 0,
                "character_count": len(result.code) if result.code else 0,
            }

            return {"success": True, "edit": edit_data}

        except Exception as e:
            print(f"❌ GET_SNIPPET_EDIT ERROR: {str(e)}")
            return {
                "success": False,
                "message": f"Failed to get snippet edit: {str(e)}",
                "error_type": "server_error",
            }

    def delete_snippet_edit(self, edit_id: str, user_id: str) -> Dict[str, Any]:
        """
        Delete a snippet edit (soft delete for independence)

        Args:
            edit_id: ID of the edit to delete
            user_id: ID of the user requesting deletion

        Returns:
            Dict with success status and message
        """
        try:
            edit = SnippetEdit.query.filter_by(id=edit_id, is_deleted=False).first()

            if not edit:
                return {
                    "success": False,
                    "message": "Snippet edit not found",
                    "error_type": "not_found",
                }

            # Check if user can delete this edit (only editor can delete their own edit)
            if not edit.can_user_delete(user_id):
                return {
                    "success": False,
                    "message": "You can only delete your own edits",
                    "error_type": "permission_denied",
                }

            # Soft delete the edit
            edit.soft_delete(user_id)
            self.db.session.commit()

            return {
                "success": True,
                "message": "Snippet edit deleted successfully",
                "edit_id": str(edit.id),
            }

        except Exception as e:
            self.db.session.rollback()
            return {
                "success": False,
                "message": f"Failed to delete snippet edit: {str(e)}",
                "error_type": "server_error",
            }

    def get_user_edits(
        self, user_id: str, team_id: Optional[str] = None, limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get all edits made by a specific user

        Args:
            user_id: ID of the user
            team_id: Optional team ID to filter by
            limit: Maximum number of edits to return

        Returns:
            Dict with success status and user edits
        """
        try:
            query = SnippetEdit.query.filter_by(
                editor_user_id=user_id, is_deleted=False
            )

            if team_id:
                query = query.filter_by(team_id=team_id)

            edits = query.order_by(SnippetEdit.created_at.desc()).limit(limit).all()

            edits_data = [edit.to_dict(include_code=False) for edit in edits]

            return {
                "success": True,
                "edits": edits_data,
                "count": len(edits_data),
                "user_id": user_id,
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to get user edits: {str(e)}",
                "error_type": "server_error",
            }

    def _validate_team_membership(self, team_id: str, user_id: str) -> Dict[str, Any]:
        """Validate that user is a member of the team"""
        try:
            print(f"🔍 TEAM VALIDATION: Looking for team {team_id}")
            print(f"🔍 TEAM VALIDATION: User {user_id}")

            # FIXED: Use raw SQL to avoid UUID conversion issues
            from sqlalchemy import text

            # Method 1: Try direct SQL query
            sql = text("SELECT * FROM teams WHERE id = :team_id LIMIT 1")
            result = self.db.session.execute(sql, {"team_id": team_id}).fetchone()

            if not result:
                print(f"❌ TEAM VALIDATION: Team {team_id} not found")
                return {
                    "success": False,
                    "message": "Team not found",
                    "error_type": "not_found",
                }

            print(f"✅ TEAM VALIDATION: Found team '{result.name}'")

            # Check if user is team owner
            print(f"🔍 TEAM VALIDATION: Team owner_id: {result.owner_id}")
            print(f"🔍 TEAM VALIDATION: User ID: {user_id}")

            if str(result.owner_id) == str(user_id):
                print(f"✅ TEAM VALIDATION: User is team owner")
                return {"success": True, "role": "owner"}

            # Check team membership using raw SQL
            member_sql = text(
                """
                SELECT * FROM team_members 
                WHERE team_id = :team_id 
                AND user_id = :user_id 
                AND is_active = true 
                LIMIT 1
            """
            )

            member_result = self.db.session.execute(
                member_sql, {"team_id": team_id, "user_id": user_id}
            ).fetchone()

            if not member_result:
                print(f"❌ TEAM VALIDATION: User is not a team member")
                return {
                    "success": False,
                    "message": "You are not a member of this team",
                    "error_type": "permission_denied",
                }

            print(f"✅ TEAM VALIDATION: User is a {member_result.role}")
            return {"success": True, "role": member_result.role}

        except Exception as e:
            print(f"❌ TEAM VALIDATION ERROR: {str(e)}")
            import traceback

            print(f"❌ TRACEBACK: {traceback.format_exc()}")
            return {
                "success": False,
                "message": f"Failed to validate team membership: {str(e)}",
                "error_type": "server_error",
            }

    def _validate_team_edit_permission(
        self, team_id: str, user_id: str
    ) -> Dict[str, Any]:
        """Validate that user has permission to create edits in the team"""
        # FIX: Convert string UUIDs to UUID objects
        import uuid

        try:
            team_uuid = uuid.UUID(team_id) if isinstance(team_id, str) else team_id
            user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        except ValueError:
            return {
                "success": False,
                "message": "Invalid UUID format",
                "error_type": "validation_error",
            }

        membership_result = self._validate_team_membership(
            str(team_uuid), str(user_uuid)
        )

        if not membership_result["success"]:
            return membership_result

        # All team members can create edits
        role = membership_result.get("role")
        if role in ["owner", "admin", "editor", "member"]:
            return {"success": True, "role": role}

        return {
            "success": False,
            "message": "Insufficient permissions to create edits",
            "error_type": "permission_denied",
        }

    def validate_edit_description(self, description: str) -> Dict[str, Any]:
        """
        Validate edit description meets requirements

        Args:
            description: The edit description to validate

        Returns:
            Dict with validation result
        """
        if not description:
            return {"valid": False, "message": "Edit description is required"}

        description = description.strip()

        if len(description) == 0:
            return {"valid": False, "message": "Edit description cannot be empty"}

        if len(description) < 3:
            return {
                "valid": False,
                "message": "Edit description must be at least 3 characters long",
            }

        if len(description) > 1000:
            return {
                "valid": False,
                "message": "Edit description cannot exceed 1000 characters",
            }

        return {"valid": True, "message": "Edit description is valid"}

    def get_edit_statistics(self, team_id: str) -> Dict[str, Any]:
        """
        Get statistics about edits in a team

        Args:
            team_id: ID of the team

        Returns:
            Dict with edit statistics
        """
        try:
            from sqlalchemy import func

            # Total edits count
            total_edits = SnippetEdit.query.filter_by(
                team_id=team_id, is_deleted=False
            ).count()

            # Unique editors count
            unique_editors = (
                self.db.session.query(
                    func.count(func.distinct(SnippetEdit.editor_user_id))
                )
                .filter_by(team_id=team_id, is_deleted=False)
                .scalar()
            )

            # Unique original snippets count
            unique_snippets = (
                self.db.session.query(
                    func.count(func.distinct(SnippetEdit.original_snippet_id))
                )
                .filter_by(team_id=team_id, is_deleted=False)
                .scalar()
            )

            # Most active editor
            most_active_editor = (
                self.db.session.query(
                    SnippetEdit.editor_user_id,
                    func.count(SnippetEdit.id).label("edit_count"),
                )
                .filter_by(team_id=team_id, is_deleted=False)
                .group_by(SnippetEdit.editor_user_id)
                .order_by(func.count(SnippetEdit.id).desc())
                .first()
            )

            return {
                "success": True,
                "statistics": {
                    "total_edits": total_edits,
                    "unique_editors": unique_editors,
                    "unique_snippets_edited": unique_snippets,
                    "most_active_editor_id": (
                        str(most_active_editor[0]) if most_active_editor else None
                    ),
                    "most_active_editor_count": (
                        most_active_editor[1] if most_active_editor else 0
                    ),
                },
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to get edit statistics: {str(e)}",
                "error_type": "server_error",
            }


# Create service instance
edit_tracking_service = EditTrackingService()
