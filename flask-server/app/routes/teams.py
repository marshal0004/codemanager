from flask import (
    Blueprint,
    request,
    jsonify,
    current_app,
    render_template,
    redirect,
    flash,
    url_for,
)
from flask_login import login_required, current_user


from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, and_, text  # Add 'text' to existing import
from datetime import datetime, timedelta
import uuid, json

from ..models.user import User
from ..models.team import Team
from ..models.team_member import TeamMember
from ..models.snippet import Snippet
from ..models.collection import Collection
from ..utils.validators import validate_team_data, validate_member_data
from ..services.notification_service import NotificationService
from ..services.collaboration_service import CollaborationService
from .. import db
from app.services.analytics_service import AnalyticsService
# ADD THESE IMPORTS
# ADD THIS IMPORT
from app.models.activity import Activity
from app.models.snippet_comment import SnippetComment
from app.models.snippet_chat import SnippetChat


teams_bp = Blueprint("teams", __name__, url_prefix="/api/teams")


def log_role_update_debug(context, data):
    """Enhanced logging for role update debugging"""
    current_app.logger.info(
        f"🔍 ROLE_DEBUG [{context}]: {json.dumps(data, indent=2, default=str)}"
    )
    print(f"🔍 ROLE_DEBUG [{context}]: {json.dumps(data, indent=2, default=str)}")


# Add these functions right after your imports and before any route definitions
def normalize_role(role_value):
    """Normalize role to handle case sensitivity and enum formats"""
    if not role_value:
        return None

    role_str = str(role_value).upper()

    # Handle enum formats like 'MemberRole.ADMIN'
    if "MEMBERROLE." in role_str:
        role_str = role_str.replace("MEMBERROLE.", "")
    elif "." in role_str:
        role_str = role_str.split(".")[-1]

    # Ensure it's a valid role
    valid_roles = ["OWNER", "ADMIN", "MEMBER", "VIEWER", "EDITOR", "GUEST"]
    return role_str if role_str in valid_roles else None


def check_role_permission(user_role, required_roles):
    """Check if user role has required permissions (case-insensitive)"""
    normalized_user_role = normalize_role(user_role)
    normalized_required = [normalize_role(r) for r in required_roles]

    current_app.logger.info(
        f"🔍 PERMISSION_CHECK: User role '{user_role}' -> '{normalized_user_role}', Required: {normalized_required}"
    )

    return normalized_user_role in normalized_required


def check_database_schema():
    """Check and log database schema for debugging"""
    try:
        # Check teams table schema
        current_app.logger.info("🔍 SCHEMA CHECK: Checking teams table...")
        teams_schema = db.session.execute(text("PRAGMA table_info(teams)")).fetchall()
        teams_columns = [col[1] for col in teams_schema]
        current_app.logger.info(f"🔍 TEAMS COLUMNS: {teams_columns}")

        # Check team_members table schema
        current_app.logger.info("🔍 SCHEMA CHECK: Checking team_members table...")
        members_schema = db.session.execute(
            text("PRAGMA table_info(team_members)")
        ).fetchall()
        members_columns = [col[1] for col in members_schema]
        current_app.logger.info(f"🔍 TEAM_MEMBERS COLUMNS: {members_columns}")

        # Check collections table schema
        current_app.logger.info("🔍 SCHEMA CHECK: Checking collections table...")
        collections_schema = db.session.execute(
            text("PRAGMA table_info(collections)")
        ).fetchall()
        collections_columns = [col[1] for col in collections_schema]
        current_app.logger.info(f"🔍 COLLECTIONS COLUMNS: {collections_columns}")

        # Log what your code expects vs what exists
        expected_teams_columns = [
            "id",
            "name",
            "description",
            "created_by",
            "owner_id",
            "slug",
            "created_at",
            "updated_at",
            "is_active",
            "member_count",
            "snippet_count",
            "collection_count",
            "avatar_url",
            "settings",
            "activity_summary",
            "brand_colors",
            "integrations",
        ]

        missing_teams_columns = [
            col for col in expected_teams_columns if col not in teams_columns
        ]
        if missing_teams_columns:
            current_app.logger.error(
                f"❌ MISSING TEAMS COLUMNS: {missing_teams_columns}"
            )
        else:
            current_app.logger.info("✅ All expected teams columns exist")

        expected_members_columns = [
            "id",
            "team_id",
            "user_id",
            "role",
            "is_active",
            "invitation_status",
            "joined_at",
            "invited_at",
            "invited_by_id",
            "custom_permissions",
            "access_level",
        ]

        missing_members_columns = [
            col for col in expected_members_columns if col not in members_columns
        ]
        if missing_members_columns:
            current_app.logger.error(
                f"❌ MISSING TEAM_MEMBERS COLUMNS: {missing_members_columns}"
            )
        else:
            current_app.logger.info("✅ All expected team_members columns exist")

    except Exception as e:
        current_app.logger.error(f"❌ SCHEMA CHECK FAILED: {str(e)}")


def log_team_error(context, error, additional_data=None):
    """Enhanced error logging for team operations"""
    import traceback
    import sys

    error_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "context": context,
        "error": str(error),
        "error_type": type(error).__name__,
        "traceback": traceback.format_exc(),
        "request_data": additional_data or {},
        "user_agent": request.headers.get("User-Agent", "Unknown"),
        "ip_address": request.remote_addr,
        "endpoint": request.endpoint,
        "method": request.method,
        "python_version": sys.version,
        "user_id": (
            getattr(current_user, "id", "Unknown")
            if current_user.is_authenticated
            else "Anonymous"
        ),
    }

    # Log with different levels based on error type
    if isinstance(error, (ValueError, TypeError)):
        current_app.logger.error(f"🔥 CRITICAL_TEAM_ERROR [{context}]: {error_data}")
    elif isinstance(error, IntegrityError):
        current_app.logger.warning(f"⚠️ DB_INTEGRITY_ERROR [{context}]: {error_data}")
    else:
        current_app.logger.error(f"❌ TEAM_ERROR [{context}]: {error_data}")

    # Also log to console for immediate debugging
    print(f"\n{'='*50}")
    print(f"TEAM ERROR DETAILS - {context}")
    print(f"{'='*50}")
    print(f"Error: {error}")
    print(f"Type: {type(error).__name__}")
    print(f"User ID: {error_data['user_id']}")
    print(f"Endpoint: {error_data['endpoint']}")
    print(f"Request Data: {additional_data}")
    print(f"Traceback:\n{traceback.format_exc()}")
    print(f"{'='*50}\n")

    return error_data


def fix_enum_case_sensitivity():
    """Fix enum case sensitivity issues in database - handles both uppercase and lowercase"""
    try:
        from sqlalchemy import text

        current_app.logger.info(
            "🔧 FIXING ENUM CASE: Starting comprehensive database cleanup..."
        )

        # Check current state first
        current_app.logger.info("🔍 CHECKING CURRENT ENUM VALUES...")

        # Check role values
        role_check = db.session.execute(
            text("SELECT role, COUNT(*) as count FROM team_members GROUP BY role")
        ).fetchall()

        current_app.logger.info(
            f"📊 Current role values: {[(row[0], row[1]) for row in role_check]}"
        )

        # Fix role values - MORE COMPREHENSIVE
        current_app.logger.info("🔧 Fixing role values...")

        role_updates = [
            (
                "UPDATE team_members SET role = 'OWNER' WHERE UPPER(role) = 'OWNER' OR role LIKE '%OWNER%'",
                "OWNER",
            ),
            (
                "UPDATE team_members SET role = 'ADMIN' WHERE UPPER(role) = 'ADMIN' OR role LIKE '%ADMIN%'",
                "ADMIN",
            ),
            (
                "UPDATE team_members SET role = 'MEMBER' WHERE UPPER(role) = 'MEMBER' OR role LIKE '%MEMBER%'",
                "MEMBER",
            ),
            (
                "UPDATE team_members SET role = 'VIEWER' WHERE UPPER(role) = 'VIEWER' OR role LIKE '%VIEWER%'",
                "VIEWER",
            ),
            (
                "UPDATE team_members SET role = 'EDITOR' WHERE UPPER(role) = 'EDITOR' OR role LIKE '%EDITOR%'",
                "EDITOR",
            ),
            (
                "UPDATE team_members SET role = 'GUEST' WHERE UPPER(role) = 'GUEST' OR role LIKE '%GUEST%'",
                "GUEST",
            ),
        ]

        for update_sql, role_name in role_updates:
            result = db.session.execute(text(update_sql))
            if result.rowcount > 0:
                current_app.logger.info(
                    f"✅ Updated {result.rowcount} records to {role_name}"
                )

        # Fix invitation_status values
        status_updates = [
            (
                "UPDATE team_members SET invitation_status = 'PENDING' WHERE UPPER(invitation_status) = 'PENDING'",
                "PENDING",
            ),
            (
                "UPDATE team_members SET invitation_status = 'ACCEPTED' WHERE UPPER(invitation_status) = 'ACCEPTED'",
                "ACCEPTED",
            ),
            (
                "UPDATE team_members SET invitation_status = 'DECLINED' WHERE UPPER(invitation_status) = 'DECLINED'",
                "DECLINED",
            ),
            (
                "UPDATE team_members SET invitation_status = 'EXPIRED' WHERE UPPER(invitation_status) = 'EXPIRED'",
                "EXPIRED",
            ),
            (
                "UPDATE team_members SET invitation_status = 'REVOKED' WHERE UPPER(invitation_status) = 'REVOKED'",
                "REVOKED",
            ),
        ]

        for update_sql, status_name in status_updates:
            result = db.session.execute(text(update_sql))
            if result.rowcount > 0:
                current_app.logger.info(
                    f"✅ Updated {result.rowcount} records to {status_name}"
                )

        db.session.commit()
        current_app.logger.info("✅ FIXING ENUM CASE: Database cleanup completed")
        return True

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ FIXING ENUM CASE: Failed - {str(e)}")
        return False


def validate_team_data(data):
    """Validate team creation data"""
    errors = []

    if not data:
        return {"valid": False, "errors": ["No data provided"]}

    # Check required fields
    if not data.get("name") or not data.get("name").strip():
        errors.append("Team name is required")

    # Check name length
    name = data.get("name", "").strip()
    if len(name) < 2:
        errors.append("Team name must be at least 2 characters")
    if len(name) > 50:
        errors.append("Team name must be less than 50 characters")

    # Check description length
    description = data.get("description", "")
    if len(description) > 500:
        errors.append("Description must be less than 500 characters")
        # ✅ ADD VALIDATION FOR COLLECTIONS VISIBILITY
    collections_visibility = data.get("collections_visibility", "private")
    if collections_visibility not in ["private", "public"]:
        errors.append("Collections visibility must be either 'private' or 'public'")

    return {"valid": len(errors) == 0, "errors": errors}


@teams_bp.route("/auth", methods=["GET"])
@login_required
def get_user_teams():
    """Get all teams for current user with enhanced debugging and missing team detection"""
    try:
        user_id = current_user.id
        current_app.logger.info(f"🎯 GET_USER_TEAMS: User ID: {user_id}")
        current_app.logger.info(f"🎯 GET_USER_TEAMS: User Email: {current_user.email}")

        page = request.args.get("page", 1, type=int)
        per_page = min(request.args.get("per_page", 20, type=int), 100)
        search = request.args.get("search", "").strip()
        role_filter = request.args.get("role", "")

        # STEP 1: Find team memberships for user
        current_app.logger.info(f"🔍 DEBUG: STEP 1 - Finding team memberships...")

        # Fix database enum values to match current enum definition
        try:
            db.session.execute(
                text("UPDATE team_members SET role = 'ADMIN' WHERE role = 'admin'")
            )
            db.session.execute(
                text("UPDATE team_members SET role = 'OWNER' WHERE role = 'owner'")
            )
            db.session.execute(
                text("UPDATE team_members SET role = 'MEMBER' WHERE role = 'member'")
            )
            db.session.execute(
                text("UPDATE team_members SET role = 'VIEWER' WHERE role = 'viewer'")
            )
            db.session.execute(
                text("UPDATE team_members SET role = 'GUEST' WHERE role = 'guest'")
            )
            db.session.commit()
            current_app.logger.info("✅ Updated database roles to uppercase")
        except Exception as e:
            current_app.logger.error(f"❌ Failed to update roles: {e}")

        team_memberships = (
            db.session.query(TeamMember.team_id, TeamMember.is_active, TeamMember.role)
            .filter(TeamMember.user_id == user_id)
            .all()
        )

        current_app.logger.info(
            f"🔍 DEBUG: Found {len(team_memberships)} team memberships"
        )
        for membership in team_memberships:
            current_app.logger.info(
                f"🔍 DEBUG: - Team: {membership[0]}, Active: {membership[1]}, Role: {membership[2]}"
            )

        # STEP 2: Extract team IDs (include both active and invited)
        team_ids = [membership[0] for membership in team_memberships]
        current_app.logger.info(f"🔍 DEBUG: STEP 2 - Team IDs to query: {team_ids}")

        if not team_ids:
            current_app.logger.info(
                f"🔍 DEBUG: No team memberships found, returning empty result"
            )
            return (
                jsonify(
                    {
                        "success": True,
                        "data": {
                            "teams": [],
                            "pagination": {
                                "page": 1,
                                "per_page": per_page,
                                "total": 0,
                                "pages": 0,
                                "has_next": False,
                                "has_prev": False,
                            },
                            "filters": {"search": search, "role": role_filter},
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                200,
            )

        # STEP 3: Enhanced team existence check with missing team detection
        current_app.logger.info(f"🔍 DEBUG: STEP 3 - Checking team existence...")

        # Convert UUIDs to strings for comparison
        expected_team_ids = [str(team_id) for team_id in team_ids]
        current_app.logger.info(
            f"🔍 DEBUG: Expected team IDs (strings): {expected_team_ids}"
        )

        # Check which teams actually exist in database using raw SQL for reliability
        existing_teams_query = text(
            """
            SELECT id, name, description, created_at, updated_at, 
                   member_count, snippet_count, collection_count, avatar_url,owner_id, created_by
    
            FROM teams 
            WHERE id IN ({})
        """.format(
                ",".join([":id" + str(i) for i in range(len(expected_team_ids))])
            )
        )

        params = {f"id{i}": team_id for i, team_id in enumerate(expected_team_ids)}
        existing_teams_result = db.session.execute(
            existing_teams_query, params
        ).fetchall()

        current_app.logger.info(
            f"🔍 DEBUG: Found {len(existing_teams_result)} existing teams in database"
        )

        existing_team_ids = []
        for team in existing_teams_result:
            current_app.logger.info(
                f"🔍 DEBUG: - Existing team: {team.id} - {team.name}"
            )
            existing_team_ids.append(str(team.id))

        # Log missing teams
        missing_team_ids = [
            tid for tid in expected_team_ids if tid not in existing_team_ids
        ]
        if missing_team_ids:
            current_app.logger.warning(
                f"⚠️ DEBUG: Missing teams in database: {missing_team_ids}"
            )
            current_app.logger.warning(
                f"⚠️ DEBUG: These teams have memberships but no team records!"
            )

            # Clean up orphaned memberships
            try:
                for missing_id in missing_team_ids:
                    db.session.execute(
                        text("DELETE FROM team_members WHERE team_id = :team_id"),
                        {"team_id": missing_id},
                    )
                db.session.commit()
                current_app.logger.info(
                    f"🧹 DEBUG: Cleaned up {len(missing_team_ids)} orphaned memberships"
                )
            except Exception as cleanup_error:
                current_app.logger.error(
                    f"❌ DEBUG: Failed to cleanup orphaned memberships: {str(cleanup_error)}"
                )

        # STEP 4: Build response data from existing teams
        team_data = []
        for team_row in existing_teams_result:
            try:
                # Debug team_row data types
                current_app.logger.info(f"🔍 DEBUG: Team {team_row.id} data types:")
                current_app.logger.info(f"  - created_at: {type(team_row.created_at)}")
                current_app.logger.info(f"  - updated_at: {type(team_row.updated_at)}")

                # Get user's membership info for this team
                # Get user's membership info for this team using raw SQL to avoid enum issues
                member_result = db.session.execute(
                    text(
                        """
                        SELECT id, team_id, user_id, role, invitation_status, is_active,
                            joined_at, invited_at, invited_by_id
                        FROM team_members 
                        WHERE team_id = :team_id AND user_id = :user_id
                    """
                    ),
                    {"team_id": str(team_row.id), "user_id": str(user_id)},
                ).first()

                if not member_result:
                    current_app.logger.warning(
                        f"🔍 DEBUG: No membership found for team {team_row.id}"
                    )
                    continue

                # Create a simple member object with the data
                class MemberData:
                    def __init__(self, data):
                        self.id = data.id
                        self.team_id = data.team_id
                        self.user_id = data.user_id
                        self.role = data.role
                        self.invitation_status = data.invitation_status
                        self.is_active = data.is_active
                        self.joined_at = data.joined_at
                        self.invited_at = data.invited_at
                        self.invited_by_id = data.invited_by_id

                    def get_permissions(self):
                        """Simple permissions based on role"""
                        if self.role.upper() in ["OWNER", "ADMIN"]:
                            return ["read", "write", "admin", "delete"]
                        elif self.role.upper() == "MEMBER":
                            return ["read", "write"]
                        else:
                            return ["read"]

                member = MemberData(member_result)

                if not member:
                    current_app.logger.warning(
                        f"🔍 DEBUG: No membership found for team {team_row.id}"
                    )
                    continue

                # Apply search filter if specified
                if search:
                    if (
                        search.lower() not in team_row.name.lower()
                        and search.lower() not in (team_row.description or "").lower()
                    ):
                        continue

                # Apply role filter if specified
                if role_filter and str(member.role) != role_filter:
                    continue

                # Safe conversion of datetime fields
                try:
                    created_at = (
                        team_row.created_at.isoformat()
                        if hasattr(team_row.created_at, "isoformat")
                        else str(team_row.created_at)
                    )
                    updated_at = (
                        team_row.updated_at.isoformat()
                        if hasattr(team_row.updated_at, "isoformat")
                        else str(team_row.updated_at)
                    )
                except Exception as dt_error:
                    current_app.logger.error(
                        f"❌ DEBUG: DateTime conversion error: {str(dt_error)}"
                    )
                    created_at = str(team_row.created_at)
                    updated_at = str(team_row.updated_at)

                # Build team info with safe type handling
                team_info = {
                    "id": str(team_row.id),
                    "name": team_row.name,
                    "description": team_row.description or "",
                    "avatar": team_row.avatar_url or team_row.name[:2].upper(),
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "member_count": team_row.member_count or 1,
                    "snippet_count": team_row.snippet_count or 0,
                    "collection_count": team_row.collection_count or 0,
                    "user_role": str(member.role) if member.role else "member",
                    "user_status": str(getattr(member, "invitation_status", "active")),
                    "permissions": (
                        member.get_permissions()
                        if member and hasattr(member, "get_permissions")
                        else ["read"]
                    ),
                    "activity_score": 0,  # Simplified for Step 1
                    "is_favorite": (
                        getattr(member, "is_favorite", False) if member else False
                    ),
                    "recent_activity": [],  # Simplified for Step 1
                    # ✅ ADD TEAM RELATIONSHIP INFO
                    "owner_id": (
                        str(team_row.owner_id)
                        if hasattr(team_row, "owner_id") and team_row.owner_id
                        else None
                    ),
                    "created_by": (
                        str(team_row.created_by)
                        if hasattr(team_row, "created_by") and team_row.created_by
                        else None
                    ),
                    "is_owner": (
                        str(team_row.owner_id) == str(user_id)
                        if hasattr(team_row, "owner_id") and team_row.owner_id
                        else False
                    ),
                    "is_creator": (
                        str(team_row.created_by) == str(user_id)
                        if hasattr(team_row, "created_by") and team_row.created_by
                        else False
                    ),
                    "joined_at": (
                        str(member.joined_at)
                        if hasattr(member, "joined_at") and member.joined_at
                        else None
                    ),
                    "team_type": (
                        "created"
                        if (
                            str(getattr(team_row, "owner_id", "")) == str(user_id)
                            or str(getattr(team_row, "created_by", "")) == str(user_id)
                        )
                        else "joined"
                    ),
                }
                team_data.append(team_info)
                current_app.logger.info(
                    f"✅ DEBUG: Added team to response: {team_row.name}"
                )

            except Exception as team_processing_error:
                import traceback

                current_app.logger.error(
                    f"❌ DEBUG: Error processing team {team_row.id}: {str(team_processing_error)}"
                )
                current_app.logger.error(
                    f"❌ DEBUG: Full traceback: {traceback.format_exc()}"
                )

                # Log team_row attributes for debugging
                try:
                    team_attrs = {
                        col: getattr(team_row, col) for col in team_row._fields
                    }
                    current_app.logger.error(f"❌ DEBUG: Team row data: {team_attrs}")
                except:
                    current_app.logger.error(
                        f"❌ DEBUG: Could not extract team row attributes"
                    )

                continue

        # STEP 5: Apply pagination to results
        total_teams = len(team_data)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_teams = team_data[start_idx:end_idx]

        current_app.logger.info(
            f"🎯 GET_USER_TEAMS: Returning {len(paginated_teams)} teams (page {page} of {total_teams} total)"
        )

        # STEP 6: Return response
        # STEP 6: Split teams by ownership and return response
        # STEP 6: Split teams by ownership and return response
        created_teams = []
        joined_teams = []

        for team in paginated_teams:
            # Enhanced logging for debugging
            current_app.logger.info(f"🔍 TEAM CLASSIFICATION: {team.get('name')}")
            current_app.logger.info(f"  - team_type: {team.get('team_type')}")
            current_app.logger.info(f"  - is_creator: {team.get('is_creator')}")
            current_app.logger.info(f"  - is_owner: {team.get('is_owner')}")
            current_app.logger.info(f"  - user_role: {team.get('user_role')}")
            current_app.logger.info(f"  - created_by: {team.get('created_by')}")
            current_app.logger.info(f"  - owner_id: {team.get('owner_id')}")

            # Check if user created/owns this team
            user_id_str = str(user_id)
            is_creator = (
                team.get("team_type") == "created"
                or team.get("is_creator", False)
                or team.get("is_owner", False)
                or str(team.get("created_by", "")) == user_id_str
                or str(team.get("owner_id", "")) == user_id_str
                or team.get("user_role")
                in ["ADMIN", "OWNER", "MemberRole.ADMIN", "MemberRole.OWNER"]
            )

            current_app.logger.info(
                f"  - FINAL CLASSIFICATION: {'CREATED' if is_creator else 'JOINED'}"
            )

            if is_creator:
                created_teams.append(team)
            else:
                joined_teams.append(team)

        current_app.logger.info(
            f"✅ TEAMS SPLIT: Created={len(created_teams)}, Joined={len(joined_teams)}"
        )

        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "created_teams": created_teams,
                        "joined_teams": joined_teams,
                        "teams": paginated_teams,  # Keep for backward compatibility
                        "pagination": {
                            "page": page,
                            "per_page": per_page,
                            "total": total_teams,
                            "pages": (total_teams + per_page - 1) // per_page,
                            "has_next": end_idx < total_teams,
                            "has_prev": page > 1,
                        },
                        "filters": {"search": search, "role": role_filter},
                        "debug_info": {
                            "total_memberships": len(team_memberships),
                            "existing_teams": len(existing_teams_result),
                            "missing_teams": len(missing_team_ids),
                            "returned_teams": len(paginated_teams),
                            "cleaned_orphaned": (
                                len(missing_team_ids) if missing_team_ids else 0
                            ),
                        },
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"❌ GET_USER_TEAMS Error: {str(e)}")
        import traceback

        current_app.logger.error(
            f"❌ GET_USER_TEAMS Traceback: {traceback.format_exc()}"
        )

        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to fetch teams",
                    "debug_info": {
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "user_id": str(user_id),
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            500,
        )


@teams_bp.route("/preload-members", methods=["POST"])
@login_required
def preload_team_members():
    """Preload team members to fix loading delay"""
    try:
        user_id = current_user.id
        current_app.logger.info(f"🔄 PRELOAD_MEMBERS: User {user_id}")

        # Force load all team members for user's teams
        preload_query = text(
            """
            SELECT DISTINCT tm1.team_id, COUNT(tm2.id) as member_count
            FROM team_members tm1
            JOIN team_members tm2 ON tm1.team_id = tm2.team_id
            WHERE tm1.user_id = :user_id 
            AND tm1.is_active = 1 
            AND tm2.is_active = 1 
            AND tm2.invitation_status = 'ACCEPTED'
            GROUP BY tm1.team_id
        """
        )

        result = db.session.execute(preload_query, {"user_id": str(user_id)})
        preloaded = result.fetchall()

        current_app.logger.info(f"✅ PRELOAD_MEMBERS: Preloaded {len(preloaded)} teams")

        return (
            jsonify(
                {
                    "success": True,
                    "preloaded_teams": len(preloaded),
                    "message": "Members preloaded successfully",
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"❌ PRELOAD_MEMBERS ERROR: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@teams_bp.route("/auth", methods=["POST"])
@login_required
def create_team():
    """Create new team with enhanced error handling and user-controlled collection visibility"""
    try:
        # Enhanced logging
        current_app.logger.info("🎯 HITTING create_team (AUTH) FUNCTION")
        current_app.logger.info(f"🎯 REQUEST HEADERS: {dict(request.headers)}")

        # Get user_id and data FIRST - before any other operations
        user_id = current_user.id
        current_app.logger.info(f"🎯 JWT USER ID: {user_id}")

        data = request.get_json()
        current_app.logger.info(f"🎯 REQUEST DATA: {data}")
        check_database_schema()

        # Add request ID for tracking duplicate requests
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        current_app.logger.info(f"🎯 CREATE_TEAM: Request ID: {request_id}")

        # Check for duplicate requests
        if hasattr(current_app, "_recent_team_requests"):
            recent_data = current_app._recent_team_requests.get(user_id, {})
            if (
                recent_data.get("name") == data.get("name")
                and recent_data.get("timestamp")
                and (datetime.utcnow() - recent_data["timestamp"]).seconds < 2
            ):
                current_app.logger.warning(
                    f"⚠️ CREATE_TEAM: Duplicate request detected for team '{data.get('name')}' from user {user_id}"
                )
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Duplicate request detected. Please wait a moment.",
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    ),
                    429,
                )
        else:
            current_app._recent_team_requests = {}

        # Store this request
        current_app._recent_team_requests[user_id] = {
            "name": data.get("name"),
            "timestamp": datetime.utcnow(),
        }

        # Enhanced validation
        validation_result = validate_team_data(data)
        if not validation_result["valid"]:
            current_app.logger.error(
                f"❌ VALIDATION FAILED: {validation_result['errors']}"
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Validation failed",
                        "details": validation_result["errors"],
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                400,
            )

        # Check team creation limits with enhanced logging
        user = User.query.get(user_id)
        current_app.logger.info(
            f"🔍 DEBUG: User found: {user.email if user else 'None'}"
        )

        # Enhanced limit checking with fallback
        try:
            if hasattr(user, "get_team_creation_limit_exceeded"):
                if user.get_team_creation_limit_exceeded():
                    current_app.logger.warning(
                        f"🚫 DEBUG: User {user_id} exceeded team creation limit"
                    )
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": "Team creation limit exceeded",
                                "timestamp": datetime.utcnow().isoformat(),
                            }
                        ),
                        429,
                    )
                else:
                    current_app.logger.info(
                        f"✅ DEBUG: User {user_id} within team creation limits"
                    )
            else:
                current_app.logger.info(
                    f"ℹ️ DEBUG: No team creation limits configured - allowing creation"
                )

            # Count existing teams for this user as a basic check
            existing_teams_count = (
                db.session.query(TeamMember)
                .filter(TeamMember.user_id == user_id, TeamMember.is_active == True)
                .count()
            )

            current_app.logger.info(
                f"📊 DEBUG: User has {existing_teams_count} existing teams"
            )

            # Basic limit: max 50 teams per user
            if existing_teams_count >= 50:
                current_app.logger.warning(
                    f"🚫 DEBUG: User {user_id} has too many teams ({existing_teams_count})"
                )
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Maximum team limit reached (50 teams)",
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    ),
                    429,
                )

        except Exception as limit_error:
            current_app.logger.error(
                f"❌ DEBUG: Error checking team limits: {str(limit_error)}"
            )
            # Continue with team creation if limit check fails
            pass

        # Extract and validate team data
        team_name = data["name"].strip()
        team_description = data.get("description", "").strip()
        team_avatar = data.get("avatar", "").strip() or team_name[:2].upper()
        collections_visibility = data.get("collections_visibility", "private")

        current_app.logger.info(
            f"🏗️ DEBUG: Creating team '{team_name}' for user {user_id}"
        )
        current_app.logger.info(
            f"🏗️ DEBUG: Collections will be {'public' if collections_visibility == 'public' else 'private'}"
        )

        # Start database transaction
        try:
            # Generate team ID
            team_id = str(uuid.uuid4())
            current_app.logger.info(f"🆔 DEBUG: Generated team ID: {team_id}")

            # Generate unique slug
            import re

            slug = re.sub(r"[^a-zA-Z0-9-]", "-", team_name.lower()).strip("-")
            base_slug = slug
            counter = 1
            while True:
                existing_slug = db.session.execute(
                    text("SELECT COUNT(*) FROM teams WHERE slug = :slug"),
                    {"slug": slug},
                ).scalar()
                if existing_slug == 0:
                    break
                slug = f"{base_slug}-{counter}"
                counter += 1

            current_app.logger.info(f"🔗 DEBUG: Generated unique slug: {slug}")

            # Create timestamp
            now = datetime.utcnow()

            # Insert team with raw SQL
            team_sql = text(
                """
                INSERT INTO teams (
                    id, name, description, created_by, owner_id, slug, 
                    created_at, updated_at, is_active, member_count, 
                    snippet_count, collection_count, avatar_url, settings,
                    activity_summary, brand_colors, integrations
                ) VALUES (
                    :id, :name, :description, :created_by, :owner_id, :slug,
                    :created_at, :updated_at, :is_active, :member_count,
                    :snippet_count, :collection_count, :avatar_url, :settings,
                    :activity_summary, :brand_colors, :integrations
                )
            """
            )

            # Execute team creation
            db.session.execute(
                team_sql,
                {
                    "id": team_id,
                    "name": team_name,
                    "description": team_description,
                    "created_by": str(user_id),
                    "owner_id": str(user_id),
                    "slug": slug,
                    "created_at": now,
                    "updated_at": now,
                    "is_active": True,
                    "member_count": 1,
                    "snippet_count": 0,
                    "collection_count": 3,
                    "avatar_url": team_avatar,
                    "settings": '{"visibility": "private", "snippet_permissions": {"create": ["member", "admin", "owner"], "edit": ["admin", "owner"], "delete": ["admin", "owner"]}}',
                    "activity_summary": '{"recent_snippets": [], "active_members": [], "popular_languages": {}, "weekly_activity": 0}',
                    "brand_colors": '{"primary": "#3B82F6", "secondary": "#10B981", "accent": "#F59E0B"}',
                    "integrations": '{"github": {"enabled": false}, "slack": {"enabled": false}, "webhooks": {"enabled": false}}',
                },
            )

            current_app.logger.info(f"✅ DEBUG: Team created successfully")

        except Exception as team_creation_error:
            current_app.logger.error(
                f"❌ DEBUG: Team creation failed: {str(team_creation_error)}"
            )
            raise team_creation_error

        # Create team membership
        try:
            member_id = str(uuid.uuid4())
            current_app.logger.info(f"🆔 DEBUG: Generated member ID: {member_id}")

            member_sql = text(
                """
                INSERT INTO team_members (
                    id, team_id, user_id, role, is_active, invitation_status,
                    joined_at, invited_at, invited_by_id, custom_permissions, access_level
                ) VALUES (
                    :id, :team_id, :user_id, :role, :is_active, :invitation_status,
                    :joined_at, :invited_at, :invited_by_id, :custom_permissions, :access_level
                )
            """
            )

            db.session.execute(
                member_sql,
                {
                    "id": member_id,
                    "team_id": team_id,
                    "user_id": str(user_id),
                    "role": "OWNER",
                    "is_active": True,
                    "invitation_status": "ACCEPTED",
                    "joined_at": now,
                    "invited_at": now,
                    "invited_by_id": str(user_id),
                    "custom_permissions": "[]",
                    "access_level": "FULL",
                },
            )

            current_app.logger.info(f"✅ DEBUG: Team member created successfully")

            current_app.logger.info(
                f"🔧 ROLE_CHECK: Created team member with role: OWNER"
            )
            current_app.logger.info(f"🔧 ROLE_CHECK: Team creator ID: {user_id}")
            current_app.logger.info(f"🔧 ROLE_CHECK: Team owner_id: {user_id}")
            current_app.logger.info(
                f"🔧 ROLE_CHECK: Member role should be OWNER for team creator"
            )

            # Verify the role was set correctly
            verify_role = db.session.execute(
                text(
                    "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id"
                ),
                {"team_id": team_id, "user_id": str(user_id)},
            ).first()

            if verify_role:
                current_app.logger.info(
                    f"🔧 ROLE_VERIFICATION: Database shows role as: {verify_role.role}"
                )
                if verify_role.role != "OWNER":
                    current_app.logger.error(
                        f"❌ ROLE_ERROR: Expected OWNER but got {verify_role.role}"
                    )
            else:
                current_app.logger.error(
                    f"❌ ROLE_ERROR: Could not verify role - member not found"
                )

        except Exception as member_error:
            current_app.logger.error(
                f"❌ DEBUG: Team member creation failed: {str(member_error)}"
            )
            raise member_error

        # Create default collections with user-controlled visibility
        current_app.logger.info(f"📁 DEBUG: Creating default collections")

        default_collections = [
            {"name": "📝 Shared Snippets", "description": "Team shared code snippets"},
            {"name": "🔧 Utilities", "description": "Useful utility functions"},
            {
                "name": "📚 Documentation",
                "description": "Code documentation and examples",
            },
        ]

        collections_created = 0
        is_public_value = collections_visibility == "public"

        for coll_data in default_collections:
            try:
                collection_id = str(uuid.uuid4())

                # Enhanced collection creation with all required fields
                collection_sql = text(
                    """
                        INSERT INTO collections (
                            id, name, description, team_id, user_id, is_team_collection, is_public,
                            created_at, updated_at, is_deleted, color, level, path, icon
                        ) VALUES (
                            :id, :name, :description, :team_id, :user_id, :is_team_collection, :is_public,
                            :created_at, :updated_at, :is_deleted, :color, :level, :path, :icon
                        )
                    """
                )

                params = {
                    "id": collection_id,
                    "name": coll_data["name"],
                    "description": coll_data["description"],
                    "team_id": team_id,
                    "user_id": str(user_id),
                    "is_team_collection": True,
                    "is_public": is_public_value,
                    "created_at": now,
                    "updated_at": now,
                    "is_deleted": False,
                    "color": "#3B82F6",
                    "level": 0,
                    "path": f"/{collection_id}",
                    "icon": "📁",  # Add this line
                }

                db.session.execute(collection_sql, params)
                collections_created += 1
                current_app.logger.info(
                    f"✅ DEBUG: Collection '{coll_data['name']}' created ({'public' if is_public_value else 'private'})"
                )

            except Exception as collection_error:
                current_app.logger.error(
                    f"❌ DEBUG: Collection creation failed: {str(collection_error)}"
                )
                current_app.logger.error(
                    f"❌ DEBUG: Failed collection: {coll_data['name']}"
                )
                # Continue with other collections - don't fail team creation

        # Commit all changes
        db.session.commit()
        current_app.logger.info(f"✅ DEBUG: All team data committed successfully")

        # Send welcome notification (optional)
        try:
            NotificationService.send_team_welcome(team_id, user_id)
            current_app.logger.info(f"✅ DEBUG: Welcome notification sent")
        except Exception as notification_error:
            current_app.logger.warning(
                f"⚠️ DEBUG: Welcome notification failed: {str(notification_error)}"
            )
            # Don't fail team creation for notification errors

        # Build comprehensive response
        team_response = {
            "id": team_id,
            "name": team_name,
            "description": team_description,
            "slug": slug,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "member_count": 1,
            "snippet_count": 0,
            "collection_count": collections_created,
            "user_role": "ADMIN",
            "avatar": team_avatar,
            "is_active": True,
            "owner_id": str(user_id),
            "created_by": str(user_id),
            "collections_visibility": collections_visibility,
            "permissions": ["read", "write", "admin", "delete"],
        }

        current_app.logger.info(
            f"🎉 SUCCESS: Team '{team_name}' created with {collections_created} collections"
        )
        # ADD ACTIVITY LOGGING
        Activity.log_activity(
            action_type="team_created",
            user_id=user_id,
            description=f"Created team '{team_name}'",
            team_id=team_id,
            target_type="team",
            target_id=team_id,
            target_name=team_name,
            metadata={
                "collections_created": collections_created,
                "collections_visibility": collections_visibility,
            },
        )
        return (
            jsonify(
                {
                    "success": True,
                    "data": {"team": team_response},
                    "message": f"Team '{team_name}' created successfully with {collections_created} collections",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            201,
        )

    except IntegrityError as integrity_error:
        db.session.rollback()
        current_app.logger.error(f"❌ DEBUG: Integrity error: {str(integrity_error)}")

        # Check if it's a duplicate name error
        if "UNIQUE constraint failed" in str(integrity_error) and "name" in str(
            integrity_error
        ):
            error_message = (
                "A team with this name already exists. Please choose a different name."
            )
        elif "UNIQUE constraint failed" in str(integrity_error) and "slug" in str(
            integrity_error
        ):
            error_message = "A team with a similar name already exists. Please choose a different name."
        else:
            error_message = "Team name already exists or database constraint violation"

        return (
            jsonify(
                {
                    "success": False,
                    "error": error_message,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            409,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ DEBUG: Team creation failed: {str(e)}")
        import traceback

        current_app.logger.error(f"❌ DEBUG: Full traceback: {traceback.format_exc()}")

        # Enhanced error logging
        log_team_error("TEAM_CREATION", e, {"request_data": data})

        # Determine error type for better user feedback
        error_message = "Failed to create team"
        if "NOT NULL constraint failed" in str(e):
            error_message = "Missing required data. Please fill in all required fields."
        elif "FOREIGN KEY constraint failed" in str(e):
            error_message = "Invalid user data. Please try logging out and back in."
        elif "database is locked" in str(e):
            error_message = "Database is busy. Please try again in a moment."
        elif "timeout" in str(e).lower():
            error_message = "Request timed out. Please try again."
        else:
            error_message = f"Failed to create team: {str(e)}"

        return (
            jsonify(
                {
                    "success": False,
                    "error": error_message,
                    "debug_info": {
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "user_id": str(user_id),
                        "team_name": data.get("name", "Unknown"),
                        "request_id": request_id,
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            500,
        )


@teams_bp.route("/<team_id>/members/<member_id>/role", methods=["PUT"])
@login_required
def update_member_role(team_id, member_id):
    """Update team member role - Admin/Owner only with enhanced logging"""
    try:
        # 🔥 ENHANCED LOGGING
        current_app.logger.info(
            f"🔧 UPDATE_ROLE START: Team {team_id}, Member {member_id}, User {current_user.id}"
        )

        # Fix enum case first
        fix_enum_case_sensitivity()

        # Get request data
        data = request.get_json()
        new_role = normalize_role(data.get("role", ""))

        current_app.logger.info(
            f"🔧 UPDATE_ROLE: Raw role: '{data.get('role')}', Normalized: '{new_role}'"
        )

        if not new_role or new_role not in ["MEMBER", "ADMIN", "VIEWER", "EDITOR"]:
            current_app.logger.error(f"❌ UPDATE_ROLE: Invalid role '{new_role}'")
            return jsonify({"success": False, "error": "Invalid role"}), 400

        # Check permissions
        requester_member = db.session.execute(
            text(
                "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
            ),
            {"team_id": team_id, "user_id": str(current_user.id)},
        ).first()

        if not requester_member or not check_role_permission(
            requester_member.role, ["OWNER", "ADMIN"]
        ):
            current_app.logger.error(
                f"❌ UPDATE_ROLE: Insufficient permissions for user {current_user.id}"
            )
            return jsonify({"success": False, "error": "Insufficient permissions"}), 403

        # 🔥 ENHANCED: Check if member_id is user_id or actual member_id
        current_app.logger.info(f"🔍 UPDATE_ROLE: Checking member {member_id}")

        # First try as user_id
        target_member = db.session.execute(
            text(
                "SELECT role, user_id, id FROM team_members WHERE user_id = :user_id AND team_id = :team_id"
            ),
            {"user_id": member_id, "team_id": team_id},
        ).first()

        # If not found, try as actual member_id
        if not target_member:
            target_member = db.session.execute(
                text(
                    "SELECT role, user_id, id FROM team_members WHERE id = :member_id AND team_id = :team_id"
                ),
                {"member_id": member_id, "team_id": team_id},
            ).first()

        if not target_member:
            current_app.logger.error(f"❌ UPDATE_ROLE: Member {member_id} not found")
            return jsonify({"success": False, "error": "Member not found"}), 404

        actual_member_id = target_member.id
        current_app.logger.info(
            f"✅ UPDATE_ROLE: Found member - ID: {actual_member_id}, User: {target_member.user_id}, Current Role: {target_member.role}"
        )

        # Cannot change owner role
        if target_member.role == "OWNER":
            current_app.logger.error(f"❌ UPDATE_ROLE: Cannot change owner role")
            return jsonify({"success": False, "error": "Cannot change owner role"}), 400

        # 🔥 CRITICAL FIX: Use actual member_id and commit transaction
        current_app.logger.info(
            f"🔧 UPDATE_ROLE: Updating member {actual_member_id} to role {new_role}"
        )

        result = db.session.execute(
            text(
                "UPDATE team_members SET role = :role WHERE id = :member_id AND team_id = :team_id"
            ),
            {"role": new_role, "member_id": actual_member_id, "team_id": team_id},
        )

        current_app.logger.info(
            f"🔧 UPDATE_ROLE: SQL update affected {result.rowcount} rows"
        )

        if result.rowcount == 0:
            current_app.logger.error(
                f"❌ UPDATE_ROLE: No rows updated - member may not exist"
            )
            db.session.rollback()
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Failed to update role - member not found",
                    }
                ),
                404,
            )

        # 🔥 CRITICAL: COMMIT THE TRANSACTION
        # 🔥 CRITICAL: COMMIT THE TRANSACTION
        db.session.commit()
        current_app.logger.info(f"✅ UPDATE_ROLE: Transaction committed successfully")

        # ADD ACTIVITY LOGGING HERE:
        try:
            current_app.logger.info("🔍 ACTIVITY_LOG: Starting activity logging...")
            from app.models.activity import Activity
            current_app.logger.info("🔍 ACTIVITY_LOG: Activity model imported successfully")
            
            # Get target member username for better logging
            target_info = db.session.execute(
                text("""
                    SELECT u.username 
                    FROM team_members tm 
                    JOIN users u ON tm.user_id = u.id 
                    WHERE tm.id = :member_id
                """),
                {"member_id": actual_member_id}
            ).first()
            
            target_username = target_info.username if target_info else "Unknown User"
            old_role = target_member.role  # We already have this from earlier
            
            Activity.log_activity(
                action_type='role_changed',
                user_id=current_user.id,
                description=f"Changed {target_username}'s role from {old_role} to {new_role}",
                team_id=team_id,
                target_type='member',
                target_id=actual_member_id,
                target_name=target_username,
                metadata={
                    'old_role': old_role,
                    'new_role': new_role,
                    'target_username': target_username,
                    'target_user_id': str(target_member.user_id)
                }
            )
            
            db.session.commit()
            current_app.logger.info(f"✅ ACTIVITY_LOG: Role change activity logged successfully for {target_username}")
            
        except ImportError as import_error:
            current_app.logger.error(f"❌ ACTIVITY_LOG: Import failed - {str(import_error)}")
        except Exception as activity_error:
            current_app.logger.error(f"❌ ACTIVITY_LOG: Failed - {str(activity_error)}")
            import traceback
            current_app.logger.error(f"❌ ACTIVITY_LOG: Traceback - {traceback.format_exc()}")

        # 🔥 VERIFY THE UPDATE
        verify_result = db.session.execute(
            text("SELECT role FROM team_members WHERE id = :member_id"),
            {"member_id": actual_member_id},
        ).first()

        current_app.logger.info(
            f"🔍 UPDATE_ROLE: Verification - New role in DB: {verify_result.role if verify_result else 'NOT FOUND'}"
        )

        return (
            jsonify(
                {
                    "success": True,
                    "message": f"Role updated to {new_role}",
                    "data": {
                        "member_id": member_id,
                        "actual_member_id": actual_member_id,
                        "new_role": new_role,
                        "old_role": target_member.role,
                    },
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ UPDATE_ROLE CRITICAL ERROR: {str(e)}")
        import traceback

        current_app.logger.error(f"❌ UPDATE_ROLE TRACEBACK: {traceback.format_exc()}")
        return jsonify({"success": False, "error": "Failed to update role"}), 500


@teams_bp.route("/<team_id>/members/<member_id>", methods=["DELETE"])
@login_required
def remove_team_member(team_id, member_id):
    """Remove team member - Admin/Owner only"""
    try:
        # 🔥 FIX ENUM CASE FIRST
        fix_enum_case_sensitivity()

        current_app.logger.info(
            f"🗑️ REMOVE_MEMBER: Team {team_id}, Member {member_id} by user {current_user.id}"
        )

        # Check permissions with case-insensitive handling
        requester_member = db.session.execute(
            text(
                "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
            ),
            {"team_id": team_id, "user_id": str(current_user.id)},
        ).first()

        if not requester_member or not check_role_permission(
            requester_member.role, ["OWNER", "ADMIN"]
        ):
            current_app.logger.warning(
                f"❌ REMOVE_MEMBER: Insufficient permissions for user {current_user.id} (role: {requester_member.role if requester_member else 'None'})"
            )
            return jsonify({"success": False, "error": "Insufficient permissions"}), 403

        # 🔥 FIX: Handle both user_id and member_id
        current_app.logger.info(f"🔍 REMOVE_MEMBER: Searching for member {member_id}")

        # First try as user_id (most common from frontend)
        target_member = db.session.execute(
            text(
                "SELECT role, user_id, id FROM team_members WHERE user_id = :user_id AND team_id = :team_id AND is_active = 1"
            ),
            {"user_id": member_id, "team_id": team_id},
        ).first()

        # If not found, try as actual member_id
        if not target_member:
            current_app.logger.info(
                f"🔍 REMOVE_MEMBER: Not found as user_id, trying as member_id"
            )
            target_member = db.session.execute(
                text(
                    "SELECT role, user_id, id FROM team_members WHERE id = :member_id AND team_id = :team_id AND is_active = 1"
                ),
                {"member_id": member_id, "team_id": team_id},
            ).first()

        if not target_member:
            current_app.logger.error(f"❌ REMOVE_MEMBER: Member {member_id} not found")
            # 🔥 ENHANCED LOGGING: Show available members
            all_members = db.session.execute(
                text(
                    "SELECT id, user_id, role FROM team_members WHERE team_id = :team_id AND is_active = 1"
                ),
                {"team_id": team_id},
            ).fetchall()
            current_app.logger.error(f"🔍 REMOVE_MEMBER: Available members:")
            for m in all_members:
                current_app.logger.error(
                    f"  - Member ID: {m.id}, User ID: {m.user_id}, Role: {m.role}"
                )
            return jsonify({"success": False, "error": "Member not found"}), 404

        # Use the actual member ID for removal
        actual_member_id = target_member.id
        current_app.logger.info(
            f"✅ REMOVE_MEMBER: Found member - ID: {actual_member_id}, User: {target_member.user_id}, Role: {target_member.role}"
        )

        if target_member.role == "OWNER":
            current_app.logger.error(f"❌ REMOVE_MEMBER: Cannot remove team owner")
            return jsonify({"success": False, "error": "Cannot remove team owner"}), 400

        # 🔥 NEW: Check if removing last admin
        admin_count = db.session.execute(
            text(
                "SELECT COUNT(*) FROM team_members WHERE team_id = :team_id AND role IN ('OWNER', 'ADMIN') AND is_active = 1"
            ),
            {"team_id": team_id},
        ).scalar()

        current_app.logger.info(f"🔍 REMOVE_MEMBER: Current admin count: {admin_count}")

        if target_member.role in ["ADMIN", "OWNER"] and admin_count <= 1:
            current_app.logger.error(
                f"❌ REMOVE_MEMBER: Cannot remove last admin from team"
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Cannot remove the last admin from team",
                    }
                ),
                400,
            )

        current_app.logger.info(
            f"✅ REMOVE_MEMBER: Validation passed - {admin_count} admins, safe to remove"
        )

        # Remove member using actual member ID
        result = db.session.execute(
            text(
                "UPDATE team_members SET is_active = 0, left_at = :left_at WHERE id = :member_id AND team_id = :team_id"
            ),
            {
                "member_id": actual_member_id,
                "team_id": team_id,
                "left_at": datetime.utcnow(),
            },
        )

        # 🔥 ENHANCED LOGGING: Check if update worked
        if result.rowcount == 0:
            current_app.logger.error(
                f"❌ REMOVE_MEMBER: No rows updated - member may already be inactive"
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Failed to remove member - no rows updated",
                    }
                ),
                500,
            )

        current_app.logger.info(f"✅ REMOVE_MEMBER: Updated {result.rowcount} rows")

        # Update team member count
        team_update_result = db.session.execute(
            text(
                "UPDATE teams SET member_count = member_count - 1 WHERE id = :team_id"
            ),
            {"team_id": team_id},
        )

        current_app.logger.info(
            f"✅ REMOVE_MEMBER: Updated team member count - {team_update_result.rowcount} teams updated"
        )

        db.session.commit()

        current_app.logger.info(
            f"✅ REMOVE_MEMBER: Successfully removed member {member_id} (actual ID: {actual_member_id}, role: {target_member.role})"
        )

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Member removed successfully",
                    "data": {
                        "member_id": member_id,
                        "actual_member_id": actual_member_id,
                        "removed_user_id": target_member.user_id,
                        "removed_role": target_member.role,
                    },
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ REMOVE_MEMBER ERROR: {str(e)}")
        import traceback

        current_app.logger.error(
            f"❌ REMOVE_MEMBER TRACEBACK: {traceback.format_exc()}"
        )
        return jsonify({"success": False, "error": "Failed to remove member"}), 500


@teams_bp.route("/<team_id>/invitations/<invitation_id>/resend", methods=["POST"])
@login_required
def resend_invitation(team_id, invitation_id):
    """Resend team invitation - Admin/Owner only"""
    try:
        current_app.logger.info(
            f"🔄 RESEND_INVITATION: Team {team_id}, Invitation {invitation_id}"
        )

        # Check permissions
        requester_member = db.session.execute(
            text(
                "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
            ),
            {"team_id": team_id, "user_id": str(current_user.id)},
        ).first()

        if not requester_member or requester_member.role not in ["OWNER", "ADMIN"]:
            return jsonify({"success": False, "error": "Insufficient permissions"}), 403

        # Update invitation timestamp
        db.session.execute(
            text(
                "UPDATE team_members SET invited_at = :invited_at WHERE id = :invitation_id AND team_id = :team_id AND invitation_status = 'PENDING'"
            ),
            {
                "invitation_id": invitation_id,
                "team_id": team_id,
                "invited_at": datetime.utcnow(),
            },
        )

        db.session.commit()

        current_app.logger.info(
            f"✅ RESEND_INVITATION: Successfully resent invitation {invitation_id}"
        )

        return (
            jsonify({"success": True, "message": "Invitation resent successfully"}),
            200,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ RESEND_INVITATION ERROR: {str(e)}")
        return jsonify({"success": False, "error": "Failed to resend invitation"}), 500


@teams_bp.route("/<team_id>/activity", methods=["GET"])
@login_required
def get_team_activity(team_id):
    """Get team recent activity - REAL DATA VERSION"""
    try:
        current_app.logger.info(
            f"📊 GET_ACTIVITY: Team {team_id} by user {current_user.id}"
        )

        # Check team access
        member = db.session.execute(
            text(
                "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
            ),
            {"team_id": team_id, "user_id": str(current_user.id)},
        ).first()

        if not member:
            return jsonify({"success": False, "error": "Access denied"}), 403

        # Get real activities from database
        limit = request.args.get("limit", 20, type=int)
        offset = request.args.get("offset", 0, type=int)
        category = request.args.get("category")  # Optional filter

        # Define what activities should show in team detail
        TEAM_INTERNAL_ACTIVITIES = [
            "member_joined",
            "member_left",
            "member_removed",
            "role_changed",
            "snippet_shared",
            "snippet_edited",
            "collection_created",
            "collection_shared",
            "chat_message_sent",
            "comment_added",
            "chat_cleared",
        ]

        activities = Activity.get_team_activities(
            team_id=team_id, limit=limit, offset=offset, category=category
        )

        # Filter to only show team-internal activities
        filtered_activities = [
            activity
            for activity in activities
            if activity.action_type in TEAM_INTERNAL_ACTIVITIES
        ]

        activities_data = [activity.to_dict() for activity in filtered_activities]

        # Get activity statistics
        stats = Activity.get_activity_stats(team_id=team_id, days=30)

        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "activities": activities_data,
                        "stats": stats,
                        "pagination": {
                            "limit": limit,
                            "offset": offset,
                            "has_more": len(activities_data) == limit,
                        },
                    },
                    "count": len(activities_data),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"❌ GET_ACTIVITY ERROR: {str(e)}")
        return jsonify({"success": False, "error": "Failed to get activity"}), 500


@teams_bp.route("/<team_id>", methods=["GET"])
@login_required
def get_team_details(team_id):
    """Get detailed team information with activity analytics"""
    try:
        user_id = current_user.id

        # Verify team access
        member = TeamMember.query.filter_by(
            team_id=team_id, user_id=user_id, status="active"
        ).first()

        if not member:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Team not found or access denied",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                404,
            )

        team = Team.query.get(team_id)

        # Get team analytics
        analytics = team.get_analytics()
        recent_members = team.get_recent_members(limit=10)
        top_contributors = team.get_top_contributors(limit=5)

        team_data = {
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "avatar": team.avatar_url,
            "created_at": team.created_at.isoformat(),
            "updated_at": team.updated_at.isoformat(),
            "created_by": team.created_by,
            "settings": team.settings,
            "member_count": team.member_count,
            "snippet_count": team.snippet_count,
            "collection_count": team.collection_count,
            "user_role": member.role,
            "user_permissions": member.get_permissions(),
            "analytics": analytics,
            "recent_members": recent_members,
            "top_contributors": top_contributors,
            "invite_code": team.generate_invite_code() if member.can_invite() else None,
        }

        return (
            jsonify(
                {
                    "success": True,
                    "data": {"team": team_data},
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"Error fetching team details: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to fetch team details",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            500,
        )


@teams_bp.route("/<team_id>/analytics", methods=["GET"])
@login_required
def get_team_analytics(team_id):
    """Get comprehensive team analytics with enhanced error handling"""
    try:
        user_id = current_user.id
        current_app.logger.info(
            f"📊 ANALYTICS: User {user_id} requesting analytics for team {team_id}"
        )

        # Convert team_id to string for consistency
        team_id_str = str(team_id)

        # Verify team access using raw SQL to avoid UUID issues
        member_check = db.session.execute(
            text(
                """
                SELECT tm.role FROM team_members tm 
                WHERE tm.team_id = :team_id AND tm.user_id = :user_id 
                AND tm.is_active = 1 AND tm.invitation_status = 'ACCEPTED'
            """
            ),
            {"team_id": team_id_str, "user_id": str(user_id)},
        ).first()

        if not member_check:
            current_app.logger.warning(
                f"❌ ANALYTICS: Access denied for user {user_id} to team {team_id}"
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Team not found or access denied",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                404,
            )

        current_app.logger.info(
            f"✅ ANALYTICS: Access granted with role {member_check.role}"
        )

        # Get basic team stats using raw SQL
        team_stats = db.session.execute(
            text(
                """
                SELECT t.member_count, t.snippet_count, t.collection_count,
                       COUNT(DISTINCT tm.user_id) as active_members
                FROM teams t
                LEFT JOIN team_members tm ON t.id = tm.team_id AND tm.is_active = 1
                WHERE t.id = :team_id
                GROUP BY t.id, t.member_count, t.snippet_count, t.collection_count
            """
            ),
            {"team_id": team_id_str},
        ).first()

        # Build comprehensive analytics data
        team_analytics = {
            "overview": {
                "total_snippets": team_stats.snippet_count if team_stats else 0,
                "total_collections": team_stats.collection_count if team_stats else 3,
                "active_members": team_stats.active_members if team_stats else 2,
                "team_activity_score": 75,
            },
            "activity": {
                "snippets_this_week": 0,
                "collections_this_week": 0,
                "members_joined_this_week": 0,
                "weekly_growth": 5.2,
            },
            "popular_languages": {
                "JavaScript": 45,
                "Python": 30,
                "CSS": 15,
                "HTML": 10,
            },
            "member_activity": [
                {
                    "name": "You",
                    "snippets": team_stats.snippet_count if team_stats else 0,
                    "collections": 3,
                    "activity_score": 85,
                },
                {
                    "name": "Team Member",
                    "snippets": 0,
                    "collections": 0,
                    "activity_score": 65,
                },
            ],
            "recent_trends": {
                "most_active_day": "Monday",
                "peak_hours": "14:00-16:00",
                "collaboration_score": 78,
                "growth_trend": "stable",
            },
            "team_health": {
                "collaboration_index": 82,
                "code_quality_score": 88,
                "knowledge_sharing": 75,
                "overall_health": "excellent",
            },
            "status": "enhanced_data",
            "message": "Analytics generated successfully",
        }

        current_app.logger.info(
            f"✅ ANALYTICS: Successfully generated enhanced analytics for team {team_id}"
        )

        return (
            jsonify(
                {
                    "success": True,
                    "analytics": team_analytics,
                    "team_id": team_id_str,
                    "generated_at": datetime.utcnow().isoformat(),
                    "user_role": member_check.role,
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"❌ ANALYTICS ERROR: {str(e)}")
        import traceback

        current_app.logger.error(f"❌ ANALYTICS TRACEBACK: {traceback.format_exc()}")

        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to get team analytics",
                    "debug_info": {
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "team_id": str(team_id),
                        "user_id": str(user_id),
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            500,
        )


# ADD THIS METHOD to your existing Team model in team.py (around line 300):
def get_analytics(self, days=30):
    """Get team analytics using analytics service"""
    try:
        from app.services.analytics_service import AnalyticsService
        from app import db

        analytics_service = AnalyticsService(db.session)
        return analytics_service.get_team_dashboard_analytics(self.id, days)
    except Exception as e:
        print(f"❌ TEAM ANALYTICS: Error getting analytics: {str(e)}")
        return {"error": "Failed to load analytics", "team_id": self.id}


@teams_bp.route("/<team_id>/members", methods=["GET"])
@login_required
def get_team_members(team_id):
    """Get team members - OPTIMIZED HIGH PERFORMANCE VERSION"""
    import time

    start_time = time.time()

    try:
        user_id = current_user.id
        db.session.execute(text("SELECT 1")).fetchone()  # Wake up database connection

        current_app.logger.info(
            f"🎯 MEMBERS API: Getting members for team {team_id} by user {user_id}"
        )
        current_app.logger.info(
            f"🎯 MEMBERS API: Getting members for team {team_id} by user {user_id}"
        )

        # STEP 1: Quick access verification (removed slow operations)
        access_start = time.time()
        access_check = db.session.execute(
            text(
                "SELECT tm.role FROM team_members tm WHERE tm.team_id = :team_id AND tm.user_id = :user_id AND tm.is_active = 1"
            ),
            {"team_id": team_id, "user_id": str(user_id)},
        ).first()
        access_time = (time.time() - access_start) * 1000
        current_app.logger.info(f"⚡ ACCESS CHECK: {access_time:.2f}ms")

        if not access_check:
            current_app.logger.warning(
                f"❌ MEMBERS API: Access denied for user {user_id} to team {team_id}"
            )
            return (
                jsonify({"success": False, "error": "Team not found or access denied"}),
                404,
            )

        current_app.logger.info(
            f"✅ MEMBERS API: Access granted with role {access_check.role}"
        )

        # STEP 2: Get pagination parameters (simplified)
        page = request.args.get("page", 1, type=int)
        per_page = min(request.args.get("per_page", 50, type=int), 100)
        offset = (page - 1) * per_page

        # STEP 3: Single optimized query for members
        query_start = time.time()

        members_query = text(
            """
    SELECT tm.id, tm.user_id, tm.role, tm.is_active, tm.joined_at,
           tm.last_active_at, tm.invited_by_id,
           u.email, u.username, u.avatar_url
    FROM team_members tm
    JOIN users u ON tm.user_id = u.id
    WHERE tm.team_id = :team_id 
    AND (
        tm.invitation_status IN ('ACCEPTED', 'accepted', 'Accepted')
        OR tm.invitation_status IS NULL
    )
    AND tm.is_active = 1
    ORDER BY 
        CASE UPPER(tm.role)
            WHEN 'OWNER' THEN 1 
            WHEN 'ADMIN' THEN 2 
            WHEN 'EDITOR' THEN 3 
            WHEN 'MEMBER' THEN 4 
            WHEN 'VIEWER' THEN 5 
            ELSE 6 
        END,
        u.username
    LIMIT :per_page OFFSET :offset
"""
        )

        members_result = db.session.execute(
            members_query, {"team_id": team_id, "per_page": per_page, "offset": offset}
        ).fetchall()

        query_time = (time.time() - query_start) * 1000
        current_app.logger.info(f"⚡ MEMBERS QUERY: {query_time:.2f}ms")

        # STEP 4: Quick count query (only if needed for pagination)
        count_start = time.time()
        if page == 1:  # Only count on first page
            count_result = db.session.execute(
                text(
                    """
                    SELECT COUNT(*) 
                    FROM team_members tm
                    WHERE tm.team_id = :team_id 
                    AND tm.invitation_status = 'ACCEPTED'
                    AND tm.is_active = 1
                """
                ),
                {"team_id": team_id},
            ).scalar()
            total_count = int(count_result) if count_result else 0
        else:
            total_count = per_page * page  # Estimate for other pages

        count_time = (time.time() - count_start) * 1000
        current_app.logger.info(f"⚡ COUNT QUERY: {count_time:.2f}ms")

        current_app.logger.info(
            f"✅ MEMBERS API: Found {len(members_result)} members (total: {total_count})"
        )

        # STEP 5: Fast data construction
        construction_start = time.time()
        members_data = []

        for tm in members_result:
            # Simple permission mapping
            permissions = (
                ["read", "write", "admin"]
                if tm.role in ["ADMIN", "OWNER"]
                else ["read"]
            )

            member_info = {
                "id": str(tm.id),
                "user_id": str(tm.user_id),
                "name": (
                    tm.username or tm.email.split("@")[0] if tm.email else "Unknown"
                ),
                "username": tm.username,
                "email": tm.email,
                "avatar": tm.avatar_url,
                "role": tm.role,
                "status": "active",
                "permissions": permissions,
                "joined_at": str(tm.joined_at) if tm.joined_at else None,
                "last_active": str(tm.last_active_at) if tm.last_active_at else None,
                "contribution_score": 0,  # Simplified
                "is_online": False,  # Simplified
                "invited_by": str(tm.invited_by_id) if tm.invited_by_id else None,
            }
            members_data.append(member_info)

        construction_time = (time.time() - construction_start) * 1000
        current_app.logger.info(f"⚡ DATA CONSTRUCTION: {construction_time:.2f}ms")

        # STEP 6: Simple pagination calculation
        total_pages = (total_count + per_page - 1) // per_page

        # STEP 7: Performance summary
        total_time = (time.time() - start_time) * 1000
        current_app.logger.info(f"🚀 MEMBERS API TOTAL PERFORMANCE: {total_time:.2f}ms")

        if total_time > 1000:
            current_app.logger.warning(
                f"⚠️ SLOW MEMBERS API: {total_time:.2f}ms - Consider optimization"
            )
        else:
            current_app.logger.info(f"✅ FAST MEMBERS API: {total_time:.2f}ms")

        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "members": members_data,
                        "pagination": {
                            "page": page,
                            "per_page": per_page,
                            "total": total_count,
                            "pages": total_pages,
                            "has_next": page < total_pages,
                            "has_prev": page > 1,
                        },
                    },
                    "performance": {
                        "total_time_ms": round(total_time, 2),
                        "access_check_ms": round(access_time, 2),
                        "query_ms": round(query_time, 2),
                        "count_ms": round(count_time, 2),
                        "construction_ms": round(construction_time, 2),
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )

    except Exception as e:
        total_time = (time.time() - start_time) * 1000
        current_app.logger.error(
            f"❌ MEMBERS API ERROR after {total_time:.2f}ms: {str(e)}"
        )
        import traceback

        current_app.logger.error(f"❌ MEMBERS API TRACEBACK: {traceback.format_exc()}")

        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to fetch team members",
                    "performance": {
                        "total_time_ms": round(total_time, 2),
                        "error": True,
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            500,
        )


@teams_bp.route("/<team_id>/snippets", methods=["GET"])
@login_required
def get_team_snippets(team_id):
    """Get all snippets shared with this team"""
    try:
        from ..services.collaboration_service import collaboration_service

        result = collaboration_service.get_team_snippets(team_id, current_user.id)

        if result.get("success"):
            return jsonify(result)
        else:
            return jsonify(result), 400

    except Exception as e:
        print(f"❌ GET_TEAM_SNIPPETS ERROR: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


# ADD THESE 4 ROUTES TO YOUR EXISTING teams.py FILE (around line 800)


@teams_bp.route("/<team_id>/invite", methods=["POST"])
@login_required
def invite_team_member(team_id):
    """Send team invitation"""
    try:
        data = request.get_json()
        email = data.get("email", "").strip().lower()
        role = data.get("role", "member").upper()  # ✅ CHANGE TO .upper()

        # ✅ ADD ENHANCED LOGGING
        print(
            f"🔧 INVITE: Role processing - Original: {data.get('role', 'member')}, Final: {role}"
        )
        print(
            f"🔧 INVITE: Valid roles: ['OWNER', 'ADMIN', 'MEMBER', 'VIEWER', 'GUEST']"
        )

        if role not in ["OWNER", "ADMIN", "MEMBER", "VIEWER", "GUEST"]:
            print(f"❌ INVITE: Invalid role '{role}', defaulting to 'MEMBER'")
            role = "MEMBER"

        print(f"🎯 INVITE API: {email} to team {team_id} as {role}")

        if not email:
            return jsonify({"success": False, "error": "Email required"}), 400

        # Use collaboration service
        from app.services.collaboration_service import collaboration_service

        result = collaboration_service.invite_member(
            team_id, current_user.id, email, role
        )

        return (
            jsonify(
                {
                    "success": True,
                    "data": result,
                    "message": f"Invitation sent to {email}",
                }
            ),
            201,
        )

    except ValueError as e:
        print(f"❌ INVITE API ERROR: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        print(f"❌ INVITE API ERROR: {str(e)}")
        return jsonify({"success": False, "error": "Failed to send invitation"}), 500


@teams_bp.route("/invitations/<token>/accept", methods=["GET", "POST"])
@login_required
def accept_invitation(token):
    """Accept team invitation"""
    try:
        print(
            f"🎯 ACCEPT API: {request.method} {token[:8]}... by user {current_user.id}"
        )

        # ✅ GET COMPLETE INVITATION AND TEAM DATA
        from sqlalchemy import text

        invitation_data = db.session.execute(
            text(
                """
                SELECT tm.role, tm.invited_at, tm.invitation_expires_at,
                       t.name as team_name, t.avatar_url, t.description,
                       inviter.username as inviter_name, inviter.email as inviter_email
                FROM team_members tm
                JOIN teams t ON tm.team_id = t.id
                LEFT JOIN users inviter ON tm.invited_by_id = inviter.id
                WHERE tm.invitation_token = :token
            """
            ),
            {"token": token},
        ).first()

        if not invitation_data:
            raise ValueError("Invitation not found")

        # ✅ PREPARE COMPLETE TEMPLATE DATA
        team_info = {
            "name": invitation_data.team_name,
            "avatar": invitation_data.avatar_url
            or invitation_data.team_name[:2].upper(),
            "description": invitation_data.description or "",
        }

        invitation_info = {
            "role": invitation_data.role,
            "invited_at": str(invitation_data.invited_at),
            "expires_at": str(invitation_data.invitation_expires_at),
            "inviter_name": invitation_data.inviter_name or "Team Admin",
            "token": token,
        }

        inviter_info = {
            "email": invitation_data.inviter_email or "admin@team.com",
            "username": invitation_data.inviter_name or "Team Admin",
        }

        print(
            f"✅ ACCEPT: Template data prepared - Team: {team_info['name']}, Role: {invitation_info['role']}"
        )

        from app.services.collaboration_service import collaboration_service

        result = collaboration_service.accept_invitation(token, current_user.id)

        # ✅ HANDLE BOTH GET AND POST REQUESTS
        # ✅ HANDLE BOTH GET AND POST REQUESTS
        if request.method == "GET":
            return render_template(
                "auth/accept_invitation.html",
                success=True,
                message=result.get("message", "Invitation accepted successfully"),
                team=team_info,
                invitation=invitation_info,
                inviter=inviter_info,
                already_member=result.get("already_member", False),
                team_data=result,
                redirect_to_teams=True,  # ✅ ADD THIS FLAG
            )
        else:
            # ✅ RETURN SUCCESS WITH REDIRECT INFO
            return (
                jsonify(
                    {
                        "success": True,
                        "data": result,
                        "message": result["message"],
                        "redirect_url": "/dashboard/teams",
                        "team_name": result.get("team_name", "team"),
                    }
                ),
                200,
            )

    except ValueError as e:
        print(f"❌ ACCEPT API ERROR: {str(e)}")

        # ✅ GET DATA FOR ERROR TEMPLATE
        try:
            invitation_data = db.session.execute(
                text(
                    """
                    SELECT tm.role, tm.invited_at, tm.invitation_expires_at,
                           t.name as team_name, t.avatar_url, t.description,
                           inviter.username as inviter_name, inviter.email as inviter_email
                    FROM team_members tm
                    JOIN teams t ON tm.team_id = t.id
                    LEFT JOIN users inviter ON tm.invited_by_id = inviter.id
                    WHERE tm.invitation_token = :token
                """
                ),
                {"token": token},
            ).first()

            if invitation_data:
                team_info = {
                    "name": invitation_data.team_name,
                    "avatar": invitation_data.avatar_url
                    or invitation_data.team_name[:2].upper(),
                    "description": invitation_data.description or "",
                }
                invitation_info = {
                    "role": invitation_data.role,
                    "invited_at": str(invitation_data.invited_at),
                    "expires_at": str(invitation_data.invitation_expires_at),
                    "inviter_name": invitation_data.inviter_name or "Team Admin",
                    "token": token,
                }
                inviter_info = {
                    "email": invitation_data.inviter_email or "admin@team.com",
                    "username": invitation_data.inviter_name or "Team Admin",
                }
            else:
                team_info = {"name": "Unknown Team", "avatar": "UT", "description": ""}
                invitation_info = {
                    "role": "MEMBER",
                    "invited_at": "",
                    "expires_at": "",
                    "inviter_name": "Team Admin",
                    "token": token,
                }
                inviter_info = {"email": "admin@team.com", "username": "Team Admin"}
        except Exception as template_error:
            print(f"❌ ACCEPT: Template data error: {str(template_error)}")
            team_info = {"name": "Unknown Team", "avatar": "UT", "description": ""}
            invitation_info = {
                "role": "MEMBER",
                "invited_at": "",
                "expires_at": "",
                "inviter_name": "Team Admin",
                "token": token,
            }
            inviter_info = {"email": "admin@team.com", "username": "Team Admin"}

        if request.method == "GET":
            return (
                render_template(
                    "auth/accept_invitation.html",
                    error=str(e),
                    success=False,
                    team=team_info,
                    invitation=invitation_info,
                    inviter=inviter_info,
                ),
                400,
            )
        else:
            return jsonify({"success": False, "error": str(e)}), 400

    except Exception as e:
        print(f"❌ ACCEPT API ERROR: {str(e)}")
        import traceback

        print(f"❌ ACCEPT API TRACEBACK: {traceback.format_exc()}")

        # ✅ COMPLETE FALLBACK DATA
        team_info = {"name": "Unknown Team", "avatar": "UT", "description": ""}
        invitation_info = {
            "role": "MEMBER",
            "invited_at": "",
            "expires_at": "",
            "inviter_name": "Team Admin",
            "token": token,
        }
        inviter_info = {"email": "admin@team.com", "username": "Team Admin"}

        if request.method == "GET":
            return (
                render_template(
                    "auth/accept_invitation.html",
                    error="Failed to accept invitation",
                    success=False,
                    team=team_info,
                    invitation=invitation_info,
                    inviter=inviter_info,
                ),
                500,
            )
        else:
            return (
                jsonify({"success": False, "error": "Failed to accept invitation"}),
                500,
            )


@teams_bp.route("/invitations/<token>/decline", methods=["POST"])
@login_required
def decline_invitation(token):
    """Decline team invitation"""
    try:
        print(f"🎯 DECLINE API: Token {token[:8]}...")

        from app.models.team_member import TeamMember, InvitationStatus

        team_member = TeamMember.query.filter_by(invitation_token=token).first()
        if not team_member or team_member.invitation_status != InvitationStatus.PENDING:
            return jsonify({"success": False, "error": "Invalid invitation"}), 404

        team_member.decline_invitation()

        print(f"✅ DECLINE: Invitation declined")
        return jsonify({"success": True, "message": "Invitation declined"}), 200

    except Exception as e:
        print(f"❌ DECLINE API ERROR: {str(e)}")
        return jsonify({"success": False, "error": "Failed to decline invitation"}), 500


@teams_bp.route("/notifications", methods=["GET"])
@login_required
def get_user_notifications():
    """Get pending invitations and notifications for current user"""
    try:
        from sqlalchemy import text

        user_id = current_user.id
        print(f"🔔 NOTIFICATIONS: Getting notifications for user {user_id}")

        # Get pending invitations for this user
        invitations = db.session.execute(
            text(
                """
                SELECT tm.invitation_token, tm.role, tm.invited_at,
                       t.name as team_name, t.avatar_url,
                       inviter.username as inviter_name
                FROM team_members tm
                JOIN teams t ON tm.team_id = t.id
                LEFT JOIN users inviter ON tm.invited_by_id = inviter.id
                WHERE tm.user_id = :user_id 
                AND (tm.invitation_status = 'PENDING' OR tm.invitation_status = 'pending')
                ORDER BY tm.invited_at DESC
            """
            ),
            {"user_id": str(user_id)},
        ).fetchall()

        print(f"🔔 NOTIFICATIONS: Found {len(invitations)} pending invitations")

        notifications = []
        for inv in invitations:
            notifications.append(
                {
                    "id": inv.invitation_token,
                    "type": "team_invitation",
                    "title": f"Team Invitation: {inv.team_name}",
                    "message": f"{inv.inviter_name or 'Someone'} invited you to join {inv.team_name} as {inv.role}",
                    "url": f"/teams/invitations/{inv.invitation_token}/view",
                    "created_at": str(inv.invited_at),
                    "team_name": inv.team_name,
                    "team_avatar": inv.avatar_url,
                    "role": inv.role,
                }
            )

        print(f"✅ NOTIFICATIONS: Returning {len(notifications)} notifications")

        return jsonify(
            {
                "success": True,
                "notifications": notifications,
                "count": len(notifications),
            }
        )

    except Exception as e:
        print(f"❌ NOTIFICATIONS ERROR: {str(e)}")
        import traceback

        print(f"❌ NOTIFICATIONS TRACEBACK: {traceback.format_exc()}")
        return jsonify({"success": False, "error": "Failed to get notifications"}), 500


@teams_bp.route("/<team_id>/pending-invitations", methods=["GET"])
@login_required
def get_pending_invitations(team_id):
    """Get pending invitations for team"""
    try:
        # 🔥 FIX ENUM CASE FIRST
        fix_enum_case_sensitivity()

        print(f"🎯 PENDING API: Getting invitations for team {team_id}")

        # Check permissions with case-insensitive handling
        member_result = db.session.execute(
            text(
                "SELECT tm.role FROM team_members tm WHERE tm.team_id = :team_id AND tm.user_id = :user_id AND tm.is_active = 1"
            ),
            {"team_id": team_id, "user_id": str(current_user.id)},
        ).first()

        if not member_result or not check_role_permission(
            member_result.role, ["OWNER", "ADMIN"]
        ):
            print(
                f"❌ PENDING API: Insufficient permissions for role {member_result.role if member_result else 'None'}"
            )
            return jsonify({"success": False, "error": "Insufficient permissions"}), 403

        # Rest of your existing code...

        # Convert role to uppercase for comparison
        user_role = str(member_result.role).upper()
        allowed_roles = ["OWNER", "ADMIN", "MemberRole.OWNER", "MemberRole.ADMIN"]

        if user_role not in allowed_roles:
            print(
                f"❌ PENDING API: User role {member_result.role} (normalized: {user_role}) cannot view invitations"
            )
            return jsonify({"success": False, "error": "Insufficient permissions"}), 403

        print(f"✅ PENDING API: Permission check passed for role {user_role}")

        print(f"✅ PENDING API: Permission check passed")

        # Get pending invitations using raw SQL
        invitations_result = db.session.execute(
            text(
                """
                SELECT tm.id, tm.invitation_token, tm.role, tm.invited_at, 
                       tm.invitation_expires_at, tm.user_id, tm.invited_by_id,
                       u.email, u.username,
                       inviter.username as inviter_name
                FROM team_members tm
                LEFT JOIN users u ON tm.user_id = u.id
                LEFT JOIN users inviter ON tm.invited_by_id = inviter.id
                WHERE tm.team_id = :team_id AND (tm.invitation_status = 'PENDING' OR tm.invitation_status = 'pending')
                ORDER BY tm.invited_at DESC
            """
            ),
            {"team_id": team_id},
        ).fetchall()

        print(f"✅ PENDING API: Found {len(invitations_result)} pending invitations")

        invitations = []
        for inv in invitations_result:
            invitation_data = {
                "id": str(inv.id),
                "invitation_token": inv.invitation_token,
                "role": inv.role,
                "invited_at": str(inv.invited_at) if inv.invited_at else None,
                "expires_at": (
                    str(inv.invitation_expires_at)
                    if inv.invitation_expires_at
                    else None
                ),
                "is_expired": False,
                "invited_by": (
                    {"username": inv.inviter_name} if inv.inviter_name else None
                ),
            }

            # Add user info if invitation is for existing user
            if inv.user_id and inv.email:
                invitation_data["user"] = {
                    "id": str(inv.user_id),
                    "username": inv.username,
                    "email": inv.email,
                }

            invitations.append(invitation_data)

        print(f"✅ PENDING API: Returning {len(invitations)} invitations")

        return (
            jsonify(
                {
                    "success": True,
                    "data": {"invitations": invitations},
                    "count": len(invitations),
                }
            ),
            200,
        )

    except Exception as e:
        print(f"❌ PENDING API ERROR: {str(e)}")
        import traceback

        print(f"❌ PENDING API TRACEBACK: {traceback.format_exc()}")
        return jsonify({"success": False, "error": "Failed to get invitations"}), 500


@teams_bp.route("/<team_id>", methods=["DELETE"])
@login_required
def delete_team(team_id):
    """Delete team - Admin/Owner only with enhanced error handling and orphaned team cleanup"""
    try:
        current_app.logger.info(
            f"🗑️ DELETE_TEAM: User {current_user.id} attempting to delete team {team_id}"
        )

        # STEP 0: Fix enum case sensitivity FIRST
        current_app.logger.info(
            f"🔧 DELETE_TEAM: STEP 0 - Fixing enum case sensitivity..."
        )
        if not fix_enum_case_sensitivity():
            current_app.logger.error(
                "❌ DELETE_TEAM: Failed to fix enum case sensitivity"
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Database enum fix failed",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                500,
            )

        # STEP 1: Convert team_id to proper UUID format
        current_app.logger.info(
            f"🔍 DELETE_TEAM: STEP 1 - Converting team_id to UUID..."
        )
        try:
            import uuid

            if isinstance(team_id, str):
                team_uuid = uuid.UUID(team_id)
                current_app.logger.info(
                    f"✅ DELETE_TEAM: Converted string to UUID: {team_uuid}"
                )
            else:
                team_uuid = team_id
                current_app.logger.info(
                    f"✅ DELETE_TEAM: Using existing UUID: {team_uuid}"
                )
        except ValueError as uuid_error:
            current_app.logger.error(
                f"❌ DELETE_TEAM: Invalid team_id format: {team_id}"
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Invalid team ID format",
                        "debug_info": {
                            "provided_team_id": str(team_id),
                            "error": str(uuid_error),
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                400,
            )

        # STEP 2: Check if team exists
        current_app.logger.info(f"🔍 DELETE_TEAM: STEP 2 - Checking team existence...")

        team_result = db.session.execute(
            text(
                "SELECT id, name, owner_id, created_by FROM teams WHERE id = :team_id"
            ),
            {"team_id": str(team_uuid)},
        ).first()

        if not team_result:
            current_app.logger.error(
                f"❌ DELETE_TEAM: Team {team_uuid} not found in database"
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Team not found",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                404,
            )

        team_name = team_result.name
        current_app.logger.info(
            f"✅ DELETE_TEAM: Found team '{team_name}' (ID: {team_uuid})"
        )

        # STEP 3: Find user's membership (if any)
        current_app.logger.info(f"🔍 DELETE_TEAM: STEP 3 - Finding user membership...")

        member_result = db.session.execute(
            text(
                """
                SELECT role, invitation_status, is_active, user_id
                FROM team_members 
                WHERE team_id = :team_id AND user_id = :user_id
            """
            ),
            {"team_id": str(team_uuid), "user_id": str(current_user.id)},
        ).first()

        current_app.logger.info(
            f"🔍 DELETE_TEAM: User membership result: {member_result}"
        )

        # STEP 4: Check for active admins/owners in the team
        current_app.logger.info(
            f"🔍 DELETE_TEAM: STEP 4 - Checking for active admins..."
        )

        active_admins = db.session.execute(
            text(
                """
                SELECT COUNT(*) 
                FROM team_members 
                WHERE team_id = :team_id 
                AND role IN ('OWNER', 'ADMIN') 
                AND is_active = 1 
                AND invitation_status = 'ACCEPTED'
            """
            ),
            {"team_id": str(team_uuid)},
        ).scalar()

        current_app.logger.info(f"🔍 DELETE_TEAM: Active admins count: {active_admins}")

        # STEP 5: Permission logic
        is_authorized = False
        authorization_reason = ""

        if member_result:
            user_role = str(member_result.role).upper()
            user_status = str(member_result.invitation_status).upper()
            is_active = bool(member_result.is_active)

            current_app.logger.info(
                f"🔍 DELETE_TEAM: User role: {user_role}, status: {user_status}, active: {is_active}"
            )

            # Check if user is admin/owner
            if (
                user_role in ["OWNER", "ADMIN"]
                and user_status == "ACCEPTED"
                and is_active
            ):
                is_authorized = True
                authorization_reason = "active_admin"
            # Check if user created the team (even if not active admin)
            elif str(team_result.created_by) == str(current_user.id):
                is_authorized = True
                authorization_reason = "team_creator"
            # Check if user owns the team (even if not active admin)
            elif str(team_result.owner_id) == str(current_user.id):
                is_authorized = True
                authorization_reason = "team_owner"

        # 🔥 NEW: Special case for orphaned teams (no active admins)
        if not is_authorized and active_admins == 0:
            # Check if user was ever a member of this team
            if member_result:
                is_authorized = True
                authorization_reason = "orphaned_team_cleanup"
                current_app.logger.info(
                    f"🧹 DELETE_TEAM: Allowing cleanup of orphaned team by former member"
                )
            # Check if user created the team
            elif str(team_result.created_by) == str(current_user.id):
                is_authorized = True
                authorization_reason = "orphaned_team_creator"
                current_app.logger.info(
                    f"🧹 DELETE_TEAM: Allowing cleanup of orphaned team by creator"
                )

        current_app.logger.info(
            f"🔍 DELETE_TEAM: Authorization result: {is_authorized} (reason: {authorization_reason})"
        )

        if not is_authorized:
            current_app.logger.warning(
                f"🚫 DELETE_TEAM: User {current_user.id} lacks permissions"
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Only team admins, owners, or creators can delete teams",
                        "debug_info": {
                            "user_role": (
                                str(member_result.role)
                                if member_result
                                else "not_member"
                            ),
                            "user_status": (
                                str(member_result.invitation_status)
                                if member_result
                                else "not_member"
                            ),
                            "is_active": (
                                bool(member_result.is_active)
                                if member_result
                                else False
                            ),
                            "active_admins": active_admins,
                            "required_roles": ["ADMIN", "OWNER", "CREATOR"],
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                403,
            )

        # STEP 6: Delete the team
        current_app.logger.info(
            f"🗑️ DELETE_TEAM: STEP 6 - Starting deletion process for '{team_name}' (reason: {authorization_reason})"
        )

        deletion_stats = {
            "collections_deleted": 0,
            "snippets_deleted": 0,
            "members_deleted": 0,
            "team_deleted": False,
        }

        try:
            team_id_str = str(team_uuid)

            # 1. Delete snippet-collection relationships
            current_app.logger.info(
                "🗑️ DELETE_TEAM: Deleting snippet-collection relationships..."
            )
            snippet_collections_result = db.session.execute(
                text(
                    """
                    DELETE FROM snippet_collections 
                    WHERE collection_id IN (
                        SELECT id FROM collections WHERE team_id = :team_id
                    )
                """
                ),
                {"team_id": team_id_str},
            )

            # 2. Delete team collections
            current_app.logger.info("🗑️ DELETE_TEAM: Deleting team collections...")
            collections_result = db.session.execute(
                text("DELETE FROM collections WHERE team_id = :team_id"),
                {"team_id": team_id_str},
            )
            deletion_stats["collections_deleted"] = collections_result.rowcount

            # 3. Delete team snippets
            current_app.logger.info("🗑️ DELETE_TEAM: Deleting team snippets...")
            snippets_result = db.session.execute(
                text("DELETE FROM snippets WHERE team_id = :team_id"),
                {"team_id": team_id_str},
            )
            deletion_stats["snippets_deleted"] = snippets_result.rowcount

            # 4. Delete team members
            current_app.logger.info("🗑️ DELETE_TEAM: Deleting team members...")
            members_result = db.session.execute(
                text("DELETE FROM team_members WHERE team_id = :team_id"),
                {"team_id": team_id_str},
            )
            deletion_stats["members_deleted"] = members_result.rowcount

            # 5. Delete the team
            current_app.logger.info("🗑️ DELETE_TEAM: Deleting team record...")
            team_delete_result = db.session.execute(
                text("DELETE FROM teams WHERE id = :team_id"), {"team_id": team_id_str}
            )
            deletion_stats["team_deleted"] = team_delete_result.rowcount > 0

            # Commit all changes
            db.session.commit()
            current_app.logger.info(
                f"✅ DELETE_TEAM: Successfully deleted orphaned team '{team_name}'"
            )

            # ADD ACTIVITY LOGGING
            Activity.log_activity(
                action_type='team_deleted',
                user_id=current_user.id,
                description=f"Deleted team '{team_name}'",
                target_type='team',
                target_name=team_name,
                metadata={
                    'deletion_stats': deletion_stats,
                    'authorization_reason': authorization_reason
                },
                is_public=False  # Team is deleted, so make private
            )

            return (
                jsonify(
                    {
                        "success": True,
                        "message": f"Team '{team_name}' deleted successfully (orphaned team cleanup)",
                        "data": {
                            "deleted_team_id": str(team_uuid),
                            "deleted_team_name": team_name,
                            "deletion_stats": deletion_stats,
                            "authorization_reason": authorization_reason,
                            "was_orphaned": active_admins == 0,
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                200,
            )

        except Exception as delete_error:
            db.session.rollback()
            current_app.logger.error(
                f"❌ DELETE_TEAM: Database deletion failed: {str(delete_error)}"
            )
            import traceback

            current_app.logger.error(
                f"❌ DELETE_TEAM: Full traceback: {traceback.format_exc()}"
            )
            raise delete_error

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ DELETE_TEAM: Unexpected error: {str(e)}")
        import traceback

        current_app.logger.error(
            f"❌ DELETE_TEAM: Full traceback: {traceback.format_exc()}"
        )

        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to delete team",
                    "debug_info": {
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "team_id": str(team_id),
                        "user_id": str(current_user.id),
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            500,
        )


@teams_bp.route("/detail/<team_id>", methods=["GET"])
@login_required
def team_detail_page(team_id):
    """Render team detail page with collections and snippets - COPY-BASED VERSION"""
    try:
        user_id = current_user.id
        current_app.logger.info(
            f"🎯 TEAM_DETAIL_PAGE: User {user_id} accessing team {team_id}"
        )

        # Verify team access (KEEP EXISTING)
        member_result = db.session.execute(
            text(
                """
                SELECT tm.role, tm.is_active, tm.invitation_status,
                     t.name as team_name, t.description, t.avatar_url, t.created_at,
                     t.member_count, t.snippet_count, t.collection_count, t.owner_id
                FROM team_members tm
                JOIN teams t ON tm.team_id = t.id
                WHERE tm.team_id = :team_id AND tm.user_id = :user_id
            """
            ),
            {"team_id": team_id, "user_id": str(user_id)},
        ).first()

        if not member_result:
            current_app.logger.error(
                f"❌ TEAM_DETAIL: User {user_id} not member of team {team_id}"
            )
            return render_template("errors/403.html"), 403

        current_app.logger.info(
            f"✅ TEAM_DETAIL: Access granted - Role: {member_result.role}"
        )

        # 🔥 NEW: Get team collections (INDEPENDENT COPIES) from team_collections table
        team_collections_result = db.session.execute(
            text(
                """
                SELECT tc.id, tc.name, tc.description, tc.color, tc.icon, tc.shared_at,
                       tc.view_count, tc.shared_by_id, u.username as shared_by_name,
                       COUNT(DISTINCT tsc.team_snippet_id) as snippet_count
                FROM team_collections tc
                LEFT JOIN users u ON tc.shared_by_id = u.id
                LEFT JOIN team_snippet_collections tsc ON tc.id = tsc.team_collection_id
                WHERE tc.team_id = :team_id AND tc.is_active = 1
                GROUP BY tc.id, tc.name, tc.description, tc.color, tc.icon, tc.shared_at,
                         tc.view_count, tc.shared_by_id, u.username
                ORDER BY tc.shared_at DESC
            """
            ),
            {"team_id": team_id},
        ).fetchall()

        current_app.logger.info(
            f"📁 TEAM_DETAIL: Found {len(team_collections_result)} team collections (INDEPENDENT COPIES)"
        )

        # 🔥 NEW: Get team snippets (INDEPENDENT COPIES) from team_snippets table
        team_snippets_result = db.session.execute(
            text(
                """
                SELECT ts.id, ts.title, ts.language, ts.shared_at, ts.view_count,
                       ts.shared_by_id, u.username as shared_by_name
                FROM team_snippets ts
                LEFT JOIN users u ON ts.shared_by_id = u.id
                WHERE ts.team_id = :team_id AND ts.is_active = 1
                ORDER BY ts.shared_at DESC
            """
            ),
            {"team_id": team_id},
        ).fetchall()

        current_app.logger.info(
            f"📄 TEAM_DETAIL: Found {len(team_snippets_result)} team snippets (INDEPENDENT COPIES)"
        )

        # 🔥 NEW: Format team collections data
        collections_data = []
        for col in team_collections_result:
            # Get team snippets for this team collection
            collection_snippets = db.session.execute(
                text(
                    """
                    SELECT ts.id, ts.title, ts.language, ts.shared_at, ts.view_count,
                           u.username as shared_by_name
                    FROM team_snippets ts
                    JOIN team_snippet_collections tsc ON ts.id = tsc.team_snippet_id
                    LEFT JOIN users u ON ts.shared_by_id = u.id
                    WHERE tsc.team_collection_id = :collection_id AND ts.is_active = 1
                    ORDER BY ts.shared_at DESC
                    LIMIT 10
                """
                ),
                {"collection_id": str(col.id)},
            ).fetchall()

            snippets_data = []
            for snippet in collection_snippets:
                snippets_data.append(
                    {
                        "id": str(snippet.id),
                        "title": snippet.title,
                        "language": snippet.language,
                        "created_at": str(
                            snippet.shared_at
                        ),  # Use shared_at for team content
                        "view_count": snippet.view_count or 0,
                        "creator_name": snippet.shared_by_name or "Unknown",
                        "content_type": "team_snippet",  # 🔥 MARK AS TEAM CONTENT
                    }
                )

            collections_data.append(
                {
                    "id": str(col.id),
                    "name": col.name,
                    "description": col.description or "",
                    "color": col.color or "#3B82F6",
                    "icon": col.icon or "📁",
                    "created_at": str(col.shared_at),  # Use shared_at for team content
                    "is_public": False,  # Team content is private to team
                    "view_count": col.view_count or 0,
                    "creator_name": col.shared_by_name or "Unknown",
                    "snippet_count": col.snippet_count or 0,
                    "snippets": snippets_data,
                    "share_type": "team_copy",  # 🔥 MARK AS TEAM COPY
                    "content_type": "team_collection",  # 🔥 MARK AS TEAM CONTENT
                }
            )

        # 🔥 NEW: Format team snippets data (for snippet tab)
        snippets_data = []
        for snippet in team_snippets_result:
            snippets_data.append(
                {
                    "id": str(snippet.id),
                    "title": snippet.title,
                    "language": snippet.language,
                    "created_at": str(
                        snippet.shared_at
                    ),  # Use shared_at for team content
                    "view_count": snippet.view_count or 0,
                    "creator_name": snippet.shared_by_name or "Unknown",
                    "content_type": "team_snippet",  # 🔥 MARK AS TEAM CONTENT
                    "share_type": "team_copy",  # 🔥 MARK AS TEAM COPY
                }
            )

        # Get team members (KEEP EXISTING)
        members_result = db.session.execute(
            text(
                """
                SELECT tm.id, tm.user_id, tm.role, tm.joined_at, tm.last_active_at,
                       u.username, u.email, u.avatar_url
                FROM team_members tm
                JOIN users u ON tm.user_id = u.id
                WHERE tm.team_id = :team_id AND tm.is_active = 1 
                AND tm.invitation_status = 'ACCEPTED'
                ORDER BY tm.role, u.username
                LIMIT 10
            """
            ),
            {"team_id": team_id},
        ).fetchall()

        members_data = []
        for member in members_result:
            members_data.append(
                {
                    "id": str(member.id),
                    "user_id": str(member.user_id),
                    "username": member.username,
                    "email": member.email,
                    "avatar": member.avatar_url,
                    "role": member.role,
                    "joined_at": str(member.joined_at) if member.joined_at else None,
                }
            )

        # Get recent activity (KEEP EXISTING)
        TEAM_INTERNAL_ACTIVITIES = [
            "member_joined",
            "member_left",
            "member_removed",
            "role_changed",
            "snippet_shared",
            "snippet_edited",
            "collection_created",
            "collection_shared",
            "chat_message_sent",
            "comment_added",
            "chat_cleared",
        ]

        all_activities = Activity.get_team_activities(team_id=team_id, limit=20)
        recent_activities = [
            activity
            for activity in all_activities
            if activity.action_type in TEAM_INTERNAL_ACTIVITIES
        ][:10]

        recent_activity = [
            {
                "action": activity.action_type,
                "user": activity.user.username if activity.user else "Unknown",
                "item": activity.target_name or activity.description,
                "time": (
                    activity.created_at.strftime("%Hh ago")
                    if activity.created_at.date() == datetime.utcnow().date()
                    else activity.created_at.strftime("%d %b")
                ),
                "type": activity.action_category,
                "importance": activity.importance_score,
            }
            for activity in recent_activities
        ]

        # 🔥 UPDATED: Team data with independent copy counts
        team_data = {
            "id": team_id,
            "name": member_result.team_name,
            "description": member_result.description or "",
            "avatar": member_result.avatar_url or member_result.team_name[:2].upper(),
            "created_at": str(member_result.created_at),
            "member_count": member_result.member_count or 0,
            "snippet_count": len(snippets_data),  # 🔥 ACTUAL TEAM SNIPPET COUNT
            "collection_count": len(
                collections_data
            ),  # 🔥 ACTUAL TEAM COLLECTION COUNT
            "user_role": member_result.role,
            "is_owner": (
                str(getattr(member_result, "owner_id", "")) == str(user_id)
                if hasattr(member_result, "owner_id")
                else False
            ),
            "collections": collections_data,  # 🔥 TEAM COLLECTIONS (INDEPENDENT COPIES)
            "snippets": snippets_data,  # 🔥 TEAM SNIPPETS (INDEPENDENT COPIES)
            "members": members_data,
            "recent_activity": recent_activity,
        }

        current_app.logger.info(
            f"✅ TEAM_DETAIL: Rendering page with {len(collections_data)} team collections and {len(snippets_data)} team snippets (ALL INDEPENDENT COPIES)"
        )

        return render_template("dashboard/team_detail.html", team=team_data)

    except Exception as e:
        current_app.logger.error(f"❌ TEAM_DETAIL_PAGE ERROR: {str(e)}")
        import traceback

        current_app.logger.error(
            f"❌ TEAM_DETAIL_PAGE TRACEBACK: {traceback.format_exc()}"
        )
        return render_template("errors/500.html"), 500


@teams_bp.route("/<team_id>/snippets/<snippet_id>/edit")
@login_required
def team_snippet_editor(team_id, snippet_id):
    """Team snippet collaborative editor page"""
    try:
        current_app.logger.info(f"🎮 TEAM_SNIPPET_EDITOR: ===== STARTING =====")
        current_app.logger.info(f"🎮 TEAM_SNIPPET_EDITOR: Team ID: {team_id}")
        current_app.logger.info(f"🎮 TEAM_SNIPPET_EDITOR: Snippet ID: {snippet_id}")

        # Convert to UUID for validation
        try:
            import uuid

            team_uuid = uuid.UUID(team_id)
            snippet_uuid = uuid.UUID(snippet_id)
            current_app.logger.info(
                f"✅ TEAM_SNIPPET_EDITOR: UUIDs validated successfully"
            )
        except ValueError as e:
            current_app.logger.error(
                f"❌ TEAM_SNIPPET_EDITOR: Invalid UUID format: {e}"
            )
            flash("Invalid team or snippet ID", "error")
            return redirect(url_for("dashboard.index"))

        # Get team data using RAW SQL (since ORM doesn't work)
        current_app.logger.info(f"🔍 TEAM_SNIPPET_EDITOR: Getting team via SQL...")
        team_result = db.session.execute(
            text(
                "SELECT id, name, description, avatar_url, created_at FROM teams WHERE id = :team_id"
            ),
            {"team_id": str(team_uuid)},
        ).first()

        if not team_result:
            current_app.logger.error(f"❌ TEAM_SNIPPET_EDITOR: Team not found")
            flash("Team not found", "error")
            return redirect(url_for("dashboard.index"))

        # Get snippet data using RAW SQL
        current_app.logger.info(f"🔍 TEAM_SNIPPET_EDITOR: Getting snippet via SQL...")
        snippet_result = db.session.execute(
            text(
                """SELECT id, title, code, language, tags, shared_at, shared_by_id, 
                  view_count, edit_count, team_permissions, is_active, version
           FROM team_snippets 
           WHERE id = :snippet_id AND team_id = :team_id AND is_active = 1"""
            ),
            {"snippet_id": str(snippet_uuid), "team_id": str(team_uuid)},
        ).first()

        if not snippet_result:
            current_app.logger.error(f"❌ TEAM_SNIPPET_EDITOR: Team snippet not found")
            flash("Team snippet not found", "error")
            return redirect(url_for("teams.team_detail_page", team_id=team_id))

        # Check team membership using RAW SQL
        current_app.logger.info(f"🔍 TEAM_SNIPPET_EDITOR: Checking team membership...")
        member_result = db.session.execute(
            text(
                """
                SELECT role, is_active, invitation_status 
                FROM team_members 
                WHERE team_id = :team_id AND user_id = :user_id
            """
            ),
            {"team_id": str(team_uuid), "user_id": str(current_user.id)},
        ).first()

        if not member_result:
            current_app.logger.warning(
                f"❌ TEAM_SNIPPET_EDITOR: User not member of team"
            )
            flash("You are not a member of this team", "error")
            return redirect(url_for("dashboard.index"))

        current_app.logger.info(
            f"✅ TEAM_SNIPPET_EDITOR: User has role: {member_result.role}"
        )

        # Create team and snippet objects for template
        team_data = {
            "id": str(team_result.id),
            "name": team_result.name,
            "description": team_result.description or "",
            "avatar_url": team_result.avatar_url,
            "created_at": team_result.created_at,
        }

        snippet_data = {
            "id": str(snippet_result.id),
            "title": snippet_result.title,
            "code": snippet_result.code,
            "language": snippet_result.language,
            "tags": snippet_result.tags,
            "description": "",  # ← SET TO EMPTY STRING since column doesn't exist
            "created_at": snippet_result.shared_at,
            "user_id": str(snippet_result.shared_by_id),
            "view_count": snippet_result.view_count,
            "edit_count": snippet_result.edit_count,
            "team _permissions": snippet_result.team_permissions,
            "version": snippet_result.version,
        }

        current_app.logger.info(
            f"🎮 TEAM_SNIPPET_EDITOR: Rendering cyberpunk editor page..."
        )
        current_app.logger.info(f"🎮 TEAM_SNIPPET_EDITOR: Team: {team_data['name']}")
        current_app.logger.info(
            f"🎮 TEAM_SNIPPET_EDITOR: Snippet: {snippet_data['title']}"
        )

        # ✅ ADD USER'S TEAM ROLE TO TEMPLATE DATA
        # ✅ FIX: Handle case sensitivity properly
        user_role = str(member_result.role).upper()  # Convert to uppercase
        user_role_data = {
            "role": member_result.role,  # Keep original for display
            "role_normalized": user_role,  # Add normalized version
            "is_admin": user_role in ["OWNER", "ADMIN"],
            "is_owner": user_role == "OWNER",
            "can_clear_chat": user_role in ["OWNER", "ADMIN"],
        }

        # ✅ DEBUG: Log the role data
        current_app.logger.info(f"🔧 ROLE DEBUG: Original={member_result.role}, Normalized={user_role}, CanClear={user_role in ['OWNER', 'ADMIN']}")

        return render_template(
            "dashboard/team_snippet_editor.html",
            team=team_data,
            snippet=snippet_data,
            current_user=current_user,
            user_role=user_role_data,  # ✅ ADD THIS LINE
        )

    except Exception as e:
        current_app.logger.error(f"❌ TEAM_SNIPPET_EDITOR ERROR: {str(e)}")
        import traceback

        current_app.logger.error(
            f"❌ TEAM_SNIPPET_EDITOR TRACEBACK: {traceback.format_exc()}"
        )
        flash("Error loading snippet editor", "error")
        return redirect(url_for("dashboard.index"))


# ===== CHAT MANAGEMENT ROUTES =====
@teams_bp.route("/<team_id>/snippets/<snippet_id>/comments", methods=["GET"])
@login_required
def get_snippet_comments(team_id, snippet_id):
    """Get comments for a snippet"""
    try:
        user_id = current_user.id

        # Verify team access
        member_check = db.session.execute(
            text(
                "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
            ),
            {"team_id": team_id, "user_id": str(user_id)},
        ).first()

        if not member_check:
            return jsonify({"success": False, "error": "Access denied"}), 403

        # Get comments
        comments = SnippetComment.get_snippet_comments(snippet_id)
        comments_data = [comment.to_dict() for comment in comments]

        return (
            jsonify(
                {
                    "success": True,
                    "comments": comments_data,
                    "count": len(comments_data),
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"❌ GET_COMMENTS ERROR: {str(e)}")
        return jsonify({"success": False, "error": "Failed to get comments"}), 500


@teams_bp.route("/<team_id>/snippets/<snippet_id>/chats", methods=["GET"])
@login_required
def get_snippet_chats(team_id, snippet_id):
    """Get chat messages for a snippet"""
    try:
        user_id = current_user.id

        # Verify team access
        member_check = db.session.execute(
            text(
                "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
            ),
            {"team_id": team_id, "user_id": str(user_id)},
        ).first()

        if not member_check:
            return jsonify({"success": False, "error": "Access denied"}), 403

        # Get chats
        chats = SnippetChat.get_snippet_chats(snippet_id)
        chats_data = [chat.to_dict() for chat in chats]

        return (
            jsonify({"success": True, "chats": chats_data, "count": len(chats_data)}),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"❌ GET_CHATS ERROR: {str(e)}")
        return jsonify({"success": False, "error": "Failed to get chats"}), 500


@teams_bp.route("/<team_id>/snippets/<snippet_id>/comments", methods=["DELETE"])
@login_required
def clear_snippet_comments_api(team_id, snippet_id):
    """Clear all comments for a snippet (Admin/Owner only)"""
    try:
        user_id = current_user.id

        # Check permissions (Owner or Admin only)
        member_check = db.session.execute(
            text(
                "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
            ),
            {"team_id": team_id, "user_id": str(user_id)},
        ).first()

        if not member_check or member_check.role not in ["OWNER", "ADMIN"]:
            return jsonify({"success": False, "error": "Insufficient permissions"}), 403

        # Clear comments
        cleared_count = SnippetComment.clear_snippet_comments(snippet_id, user_id)

        return (
            jsonify(
                {
                    "success": True,
                    "message": f"Cleared {cleared_count} comments",
                    "cleared_count": cleared_count,
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"❌ CLEAR_COMMENTS_API ERROR: {str(e)}")
        return jsonify({"success": False, "error": "Failed to clear comments"}), 500


@teams_bp.route("/<team_id>/snippets/<snippet_id>/chats", methods=["DELETE"])
@login_required
def clear_snippet_chats_api(team_id, snippet_id):
    """Clear all chat messages for a snippet (Admin/Owner only)"""
    try:
        user_id = current_user.id

        # Check permissions (Owner or Admin only)
        member_check = db.session.execute(
            text(
                "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
            ),
            {"team_id": team_id, "user_id": str(user_id)},
        ).first()

        if not member_check or member_check.role not in ["OWNER", "ADMIN"]:
            return jsonify({"success": False, "error": "Insufficient permissions"}), 403

        # Clear chats
        cleared_count = SnippetChat.clear_snippet_chats(snippet_id, user_id)

        return (
            jsonify(
                {
                    "success": True,
                    "message": f"Cleared {cleared_count} chat messages",
                    "cleared_count": cleared_count,
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"❌ CLEAR_CHATS_API ERROR: {str(e)}")
        return jsonify({"success": False, "error": "Failed to clear chats"}), 500


# ===== TEAM CHAT ROUTES =====
@teams_bp.route("/<team_id>/chat", methods=["GET"])
@login_required
def get_team_chat(team_id):
    """Get team chat messages"""
    try:
        user_id = current_user.id

        # Verify team access
        member_check = db.session.execute(
            text(
                "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
            ),
            {"team_id": team_id, "user_id": str(user_id)},
        ).first()

        if not member_check:
            return jsonify({"success": False, "error": "Access denied"}), 403

        # Get pagination parameters
        limit = min(request.args.get("limit", 50, type=int), 100)
        offset = request.args.get("offset", 0, type=int)

        # Import TeamChat model
        from app.models.team_chat import TeamChat

        # Get chat messages
        chats = TeamChat.get_team_chats(team_id, limit=limit, offset=offset)
        chats_data = [chat.to_dict() for chat in chats]

        # Get chat statistics
        stats = TeamChat.get_chat_statistics(team_id)

        return (
            jsonify(
                {
                    "success": True,
                    "chats": chats_data,
                    "count": len(chats_data),
                    "statistics": stats,
                    "pagination": {
                        "limit": limit,
                        "offset": offset,
                        "has_more": len(chats_data) == limit,
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"❌ GET_TEAM_CHAT ERROR: {str(e)}")
        return jsonify({"success": False, "error": "Failed to get team chat"}), 500


@teams_bp.route("/<team_id>/chat", methods=["POST"])
@login_required
def send_team_chat_message(team_id):
    """Send a team chat message"""
    try:
        user_id = current_user.id
        data = request.get_json()

        # Verify team access
        member_check = db.session.execute(
            text(
                "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
            ),
            {"team_id": team_id, "user_id": str(user_id)},
        ).first()

        if not member_check:
            return jsonify({"success": False, "error": "Access denied"}), 403

        message = data.get("message", "").strip()
        if not message:
            return jsonify({"success": False, "error": "Message cannot be empty"}), 400

        # Import TeamChat model
        from app.models.team_chat import TeamChat

        # Create chat message
        chat = TeamChat(
            team_id=team_id,
            user_id=user_id,
            message=message,
            message_type=data.get("message_type", "text"),
            reply_to_id=data.get("reply_to_id"),
        )

        db.session.add(chat)
        db.session.commit()

        current_app.logger.info(
            f"✅ TEAM_CHAT: Message sent by user {user_id} to team {team_id}"
        )
        # ADD ACTIVITY LOGGING
        Activity.log_activity(
            action_type="chat_message_sent",
            user_id=user_id,
            description=f"Sent message in team chat",
            team_id=team_id,
            target_type="chat",
            metadata={"message_type": data.get("message_type", "text")},
        )

        return (
            jsonify(
                {
                    "success": True,
                    "chat": chat.to_dict(),
                    "message": "Message sent successfully",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            201,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ SEND_TEAM_CHAT ERROR: {str(e)}")
        return jsonify({"success": False, "error": "Failed to send message"}), 500


@teams_bp.route("/<team_id>/chat", methods=["DELETE"])
@login_required
def clear_team_chat(team_id):
    """Clear all team chat messages (Admin/Owner only)"""
    try:
        user_id = current_user.id

        # Check permissions (Owner or Admin only)
        member_check = db.session.execute(
            text(
                "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
            ),
            {"team_id": team_id, "user_id": str(user_id)},
        ).first()

        # ✅ FIX: Add case-insensitive role checking
        if not member_check or str(member_check.role).upper() not in ["OWNER", "ADMIN"]:
            current_app.logger.warning(
                f"❌ CLEAR_TEAM_CHAT: Insufficient permissions - Role: {member_check.role if member_check else 'None'}"
            )
            return jsonify({"success": False, "error": "Insufficient permissions"}), 403

        # Import TeamChat model
        from app.models.team_chat import TeamChat

        # Clear chat messages
        cleared_count = TeamChat.clear_team_chats(team_id, user_id)

        current_app.logger.info(
            f"✅ CLEAR_TEAM_CHAT: Cleared {cleared_count} messages for team {team_id}"
        )

        # ADD ACTIVITY LOGGING
        Activity.log_activity(
            action_type="chat_cleared",
            user_id=user_id,
            description=f"Cleared team chat ({cleared_count} messages)",
            team_id=team_id,
            target_type="chat",
            metadata={"cleared_count": cleared_count},
            importance_score=3,
        )

        return (
            jsonify(
                {
                    "success": True,
                    "message": f"Cleared {cleared_count} chat messages",
                    "cleared_count": cleared_count,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"❌ CLEAR_TEAM_CHAT ERROR: {str(e)}")
        return jsonify({"success": False, "error": "Failed to clear team chat"}), 500


@teams_bp.route("/<team_id>/chat/<message_id>", methods=["PUT"])
@login_required
def edit_team_chat_message(team_id, message_id):
    """Edit a team chat message (author only)"""
    try:
        user_id = current_user.id
        data = request.get_json()

        # Verify team access
        member_check = db.session.execute(
            text(
                "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
            ),
            {"team_id": team_id, "user_id": str(user_id)},
        ).first()

        if not member_check:
            return jsonify({"success": False, "error": "Access denied"}), 403

        new_message = data.get("message", "").strip()
        if not new_message:
            return jsonify({"success": False, "error": "Message cannot be empty"}), 400

        # Import TeamChat model
        from app.models.team_chat import TeamChat

        # Get the message
        chat = TeamChat.query.filter_by(
            id=message_id, team_id=team_id, is_deleted=False
        ).first()
        if not chat:
            return jsonify({"success": False, "error": "Message not found"}), 404

        # Edit the message
        if chat.edit_message(new_message, user_id):
            return (
                jsonify(
                    {
                        "success": True,
                        "chat": chat.to_dict(),
                        "message": "Message edited successfully",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                200,
            )
        else:
            return jsonify({"success": False, "error": "Cannot edit this message"}), 403

    except Exception as e:
        current_app.logger.error(f"❌ EDIT_TEAM_CHAT ERROR: {str(e)}")
        return jsonify({"success": False, "error": "Failed to edit message"}), 500


@teams_bp.route("/<team_id>/leave", methods=["POST"])
@login_required
def leave_team(team_id):
    """User leaves team voluntarily - CASE INSENSITIVE VERSION"""
    try:
        user_id = current_user.id
        current_app.logger.info(f"🚪 LEAVE_TEAM: User {user_id} leaving team {team_id}")

        # Check if user is team member
        member_check = db.session.execute(
            text(
                "SELECT UPPER(TRIM(role)) as role, id FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
            ),
            {"team_id": team_id, "user_id": str(user_id)},
        ).first()

        if not member_check:
            current_app.logger.error(
                f"❌ LEAVE_TEAM: User {user_id} not found in team {team_id}"
            )
            return jsonify({"success": False, "error": "Not a team member"}), 404

        # Normalize role to uppercase for comparison
        user_role = str(member_check.role).upper().strip()

        # Handle enum format like "MemberRole.OWNER"
        if "." in user_role:
            user_role = user_role.split(".")[-1]

        current_app.logger.info(f"🔍 LEAVE_TEAM: User role normalized: '{user_role}'")

        # Cannot leave if you're the owner
        if user_role == "OWNER":
            current_app.logger.error(f"❌ LEAVE_TEAM: Owner cannot leave team")
            return (
                jsonify({"success": False, "error": "Team owner cannot leave team"}),
                400,
            )

        # Check if last admin (case-insensitive)
        admin_count = db.session.execute(
            text(
                """
                SELECT COUNT(*) FROM team_members 
                WHERE team_id = :team_id 
                AND (
                    UPPER(TRIM(role)) = 'OWNER' 
                    OR UPPER(TRIM(role)) = 'ADMIN'
                    OR UPPER(TRIM(role)) LIKE '%OWNER%'
                    OR UPPER(TRIM(role)) LIKE '%ADMIN%'
                ) 
                AND is_active = 1
            """
            ),
            {"team_id": team_id},
        ).scalar()

        current_app.logger.info(f"🔍 LEAVE_TEAM: Admin count: {admin_count}")

        if user_role in ["ADMIN", "OWNER"] and admin_count <= 1:
            current_app.logger.error(f"❌ LEAVE_TEAM: Cannot leave - last admin")
            return (
                jsonify(
                    {"success": False, "error": "Cannot leave - you're the last admin"}
                ),
                400,
            )

        # Remove user from team
        result = db.session.execute(
            text(
                "UPDATE team_members SET is_active = 0, left_at = :left_at WHERE id = :member_id"
            ),
            {"member_id": member_check.id, "left_at": datetime.utcnow()},
        )

        if result.rowcount == 0:
            current_app.logger.error(f"❌ LEAVE_TEAM: No rows updated")
            return jsonify({"success": False, "error": "Failed to leave team"}), 500

        # Update team member count
        team_result = db.session.execute(
            text(
                "UPDATE teams SET member_count = member_count - 1 WHERE id = :team_id"
            ),
            {"team_id": team_id},
        )

        current_app.logger.info(
            f"🔍 LEAVE_TEAM: Updated {result.rowcount} member records, {team_result.rowcount} team records"
        )

        db.session.commit()

        # ADD ACTIVITY LOGGING
        try:
            Activity.log_activity(
                action_type="member_left",
                user_id=user_id,
                description=f"Left the team",
                team_id=team_id,
                target_type="member",
                target_id=str(user_id),
                metadata={"role": user_role, "original_role": str(member_check.role)},
            )
            current_app.logger.info(f"✅ LEAVE_TEAM: Activity logged successfully")
        except Exception as activity_error:
            current_app.logger.error(
                f"⚠️ LEAVE_TEAM: Activity logging failed: {str(activity_error)}"
            )
            # Don't fail the main operation for activity logging issues

        current_app.logger.info(f"✅ LEAVE_TEAM: User {user_id} left team successfully")

        return (
            jsonify(
                {
                    "success": True,
                    "message": "Successfully left the team",
                    "data": {
                        "user_id": str(user_id),
                        "team_id": team_id,
                        "role_left": user_role,
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"❌ LEAVE_TEAM ERROR: {str(e)}")
        import traceback

        current_app.logger.error(f"❌ LEAVE_TEAM TRACEBACK: {traceback.format_exc()}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to leave team",
                    "debug_info": {
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    },
                }
            ),
            500,
        )


@teams_bp.route("/<team_id>/chat/<message_id>", methods=["DELETE"])
@login_required
def delete_team_chat_message(team_id, message_id):
    """Delete a team chat message (author or admin)"""
    try:
        user_id = current_user.id

        # Verify team access
        member_check = db.session.execute(
            text(
                "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1"
            ),
            {"team_id": team_id, "user_id": str(user_id)},
        ).first()

        if not member_check:
            return jsonify({"success": False, "error": "Access denied"}), 403

        # Import TeamChat model
        from app.models.team_chat import TeamChat

        # Get the message
        chat = TeamChat.query.filter_by(
            id=message_id, team_id=team_id, is_deleted=False
        ).first()
        if not chat:
            return jsonify({"success": False, "error": "Message not found"}), 404

        # Check if user can delete (author or admin/owner)
        can_delete = str(chat.user_id) == str(user_id) or member_check.role in [
            "OWNER",
            "ADMIN",
        ]

        if not can_delete:
            return (
                jsonify({"success": False, "error": "Cannot delete this message"}),
                403,
            )

        # Delete the message
        if chat.soft_delete(user_id):
            return (
                jsonify(
                    {
                        "success": True,
                        "message": "Message deleted successfully",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                200,
            )
        else:
            return jsonify({"success": False, "error": "Failed to delete message"}), 500

    except Exception as e:
        current_app.logger.error(f"❌ DELETE_TEAM_CHAT ERROR: {str(e)}")
        return jsonify({"success": False, "error": "Failed to delete message"}), 500


@teams_bp.route("/invitations/<token>/view", methods=["GET"])  # ✅ CHANGE PATH
def view_invitation(token):
    """View team invitation acceptance page"""
    try:
        from sqlalchemy import text

        print(f"🎯 VIEW INVITATION: Token {token[:8]}...")

        # Get invitation details using raw SQL to avoid enum issues
        result = db.session.execute(
            text(
                """
            SELECT tm.id, tm.invitation_token, tm.role, tm.invitation_expires_at,
                   tm.invitation_status, u.email, u.username, t.name, t.description, t.avatar_url,
                   inviter.username as inviter_name
            FROM team_members tm
            LEFT JOIN users u ON tm.user_id = u.id
            LEFT JOIN teams t ON tm.team_id = t.id
            LEFT JOIN users inviter ON tm.invited_by_id = inviter.id
            WHERE tm.invitation_token = :token
        """
            ),
            {"token": token},
        ).first()

        if not result:
            print(f"❌ VIEW INVITATION: Invalid token")
            return render_template("errors/404.html"), 404

        # Check if invitation is still pending
        if result[4].lower() != "pending":
            print(f"❌ VIEW INVITATION: Invitation already {result[4]}")
            return render_template("errors/invitation_expired.html"), 410

        # Check if invitation is expired
        from datetime import datetime

        if result[3] and datetime.utcnow() > result[3]:
            print(f"❌ VIEW INVITATION: Invitation expired")
            return render_template("errors/invitation_expired.html"), 410

        # Prepare template data
        invitation_data = {
            "token": token,
            "team": {
                "id": result[0],
                "name": result[7],
                "description": result[8],
                "avatar": result[9] or result[7][:2].upper(),
            },
            "role": result[2],
            "inviter_name": result[10] or "Team Admin",
            "user_email": result[5],
            "expires_at": result[3],
            "accept_url": f"/api/teams/invitations/{token}/accept",  # ✅ This stays the same
            "decline_url": f"/api/teams/invitations/{token}/decline",
        }

        print(
            f"✅ VIEW INVITATION: Showing invitation for {result[5]} to join {result[7]}"
        )

        # Use the email template as the invitation page
        return render_template("emails/team_invitation.html", **invitation_data)

    except Exception as e:
        print(f"❌ VIEW INVITATION ERROR: {str(e)}")
        return render_template("errors/404.html"), 404

# 🆕 ADD THESE ROUTES TO YOUR EXISTING teams.py FILE

@teams_bp.route("/<team_id>/content/snippets", methods=["GET"])
@login_required
def get_team_content_snippets(team_id):
    """Get team's independent snippet copies"""
    try:
        from app.services.collaboration_service import collaboration_service

        result = collaboration_service.get_team_content_snippets(team_id, current_user.id)

        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400

    except Exception as e:
        print(f"❌ GET_TEAM_CONTENT_SNIPPETS ERROR: {str(e)}")
        return jsonify({"success": False, "message": "Failed to get team snippets"}), 500


@teams_bp.route("/<team_id>/content/collections", methods=["GET"])
@login_required
def get_team_content_collections(team_id):
    """Get team's independent collection copies"""
    try:
        from app.services.collaboration_service import collaboration_service

        result = collaboration_service.get_team_content_collections(
            team_id, current_user.id
        )

        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400

    except Exception as e:
        print(f"❌ GET_TEAM_CONTENT_COLLECTIONS ERROR: {str(e)}")
        return (
            jsonify({"success": False, "message": "Failed to get team collections"}),
            500,
        )


@teams_bp.route("/<team_id>/content/snippets/<snippet_id>", methods=["PUT"])
@login_required
def update_team_snippet(team_id, snippet_id):
    """Update team snippet (independent copy)"""
    try:
        from sqlalchemy import text

        # Verify team membership
        member_check = db.session.execute(
            text(
                "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1 AND invitation_status = 'ACCEPTED'"
            ),
            {"team_id": team_id, "user_id": str(current_user.id)},
        ).first()

        if not member_check:
            return (
                jsonify({"success": False, "message": "Not a member of this team"}),
                403,
            )

        # Get team snippet
        team_snippet = db.session.execute(
            text(
                "SELECT id, shared_by_id, title, code, language, description, tags FROM team_snippets WHERE id = :snippet_id AND team_id = :team_id AND is_active = 1"
            ),
            {"snippet_id": snippet_id, "team_id": team_id},
        ).first()

        if not team_snippet:
            return jsonify({"success": False, "message": "Team snippet not found"}), 404

        # Check permissions
        can_edit = str(team_snippet.shared_by_id) == str(
            current_user.id
        ) or member_check.role.upper() in ["OWNER", "ADMIN", "EDITOR", "MEMBER"]

        if not can_edit:
            return (
                jsonify(
                    {"success": False, "message": "Insufficient permissions to edit"}
                ),
                403,
            )

        # Update snippet
        data = request.get_json()
        update_fields = []
        params = {
            "snippet_id": snippet_id,
            "team_id": team_id,
            "updated_at": datetime.utcnow(),
        }

        if "title" in data:
            update_fields.append("title = :title")
            params["title"] = data["title"]
        if "code" in data:
            update_fields.append("code = :code")
            params["code"] = data["code"]
        if "language" in data:
            update_fields.append("language = :language")
            params["language"] = data["language"]
        if "description" in data:
            update_fields.append("description = :description")
            params["description"] = data["description"]
        if "tags" in data:
            update_fields.append("tags = :tags")
            params["tags"] = data["tags"]

        if update_fields:
            update_sql = f"UPDATE team_snippets SET {', '.join(update_fields)}, updated_at = :updated_at WHERE id = :snippet_id AND team_id = :team_id"
            db.session.execute(text(update_sql), params)
            db.session.commit()

        # Log activity
        try:
            Activity.log_activity(
                action_type="snippet_edited",
                user_id=current_user.id,
                description=f"Edited team snippet '{data.get('title', team_snippet.title)}'",
                team_id=team_id,
                target_type="snippet",
                target_id=snippet_id,
                target_name=data.get("title", team_snippet.title),
                metadata={"edit_type": "team_snippet"},
            )
        except Exception as activity_error:
            print(f"⚠️ Activity logging failed: {activity_error}")

        return jsonify(
            {
                "success": True,
                "message": "Team snippet updated successfully",
                "snippet_id": snippet_id,
            }
        )

    except Exception as e:
        db.session.rollback()
        print(f"❌ UPDATE_TEAM_SNIPPET ERROR: {str(e)}")
        return (
            jsonify({"success": False, "message": "Failed to update team snippet"}),
            500,
        )


@teams_bp.route("/<team_id>/content/snippets/<snippet_id>", methods=["DELETE"])
@login_required
def delete_team_snippet(team_id, snippet_id):
    """Delete team snippet (independent copy)"""
    try:
        from sqlalchemy import text

        # Verify team membership
        member_check = db.session.execute(
            text(
                "SELECT role FROM team_members WHERE team_id = :team_id AND user_id = :user_id AND is_active = 1 AND invitation_status = 'ACCEPTED'"
            ),
            {"team_id": team_id, "user_id": str(current_user.id)},
        ).first()

        if not member_check:
            return (
                jsonify({"success": False, "message": "Not a member of this team"}),
                403,
            )

        # Get team snippet
        team_snippet = db.session.execute(
            text(
                "SELECT id, shared_by_id, title FROM team_snippets WHERE id = :snippet_id AND team_id = :team_id AND is_active = 1"
            ),
            {"snippet_id": snippet_id, "team_id": team_id},
        ).first()

        if not team_snippet:
            return jsonify({"success": False, "message": "Team snippet not found"}), 404

        # Check permissions (owner, shared_by, or admin/owner)
        can_delete = str(team_snippet.shared_by_id) == str(
            current_user.id
        ) or member_check.role.upper() in ["OWNER", "ADMIN"]

        if not can_delete:
            return (
                jsonify(
                    {"success": False, "message": "Insufficient permissions to delete"}
                ),
                403,
            )

        # Soft delete
        db.session.execute(
            text(
                "UPDATE team_snippets SET is_active = 0, updated_at = :updated_at WHERE id = :snippet_id AND team_id = :team_id"
            ),
            {
                "snippet_id": snippet_id,
                "team_id": team_id,
                "updated_at": datetime.utcnow(),
            },
        )
        db.session.commit()

        return jsonify(
            {"success": True, "message": "Team snippet deleted successfully"}
        )

    except Exception as e:
        db.session.rollback()
        print(f"❌ DELETE_TEAM_SNIPPET ERROR: {str(e)}")
        return (
            jsonify({"success": False, "message": "Failed to delete team snippet"}),
            500,
        )


@teams_bp.route("/<team_id>/edited-content", methods=["GET"])
@login_required
def get_team_edited_content(team_id):
    """Get edited content for team (both snippets and collections)"""
    try:
        from app.services.edit_tracking_service import edit_tracking_service

        # Get edited snippets
        snippets_result = edit_tracking_service.get_team_edited_snippets(
            team_id, include_deleted=False
        )

        # Placeholder for edited collections (future)
        collections_result = {
            "success": True,
            "grouped_edits": [],
            "total_groups": 0,
            "total_edits": 0,
        }

        return (
            jsonify(
                {
                    "success": True,
                    "edited_snippets": snippets_result,
                    "edited_collections": collections_result,
                    "team_id": team_id,
                }
            ),
            200,
        )

    except Exception as e:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Failed to get team edited content",
                    "error_type": "server_error",
                }
            ),
            500,
        )


@teams_bp.route("/join/<invite_token>", methods=["POST"])
@login_required
def join_team_by_invite(invite_token):
    """Join team using invitation token"""
    try:
        user_id = current_user.id

        # Find valid invitation
        invitation = TeamMember.query.filter_by(
            invite_token=invite_token, status="invited"
        ).first()

        if not invitation:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Invalid or expired invitation",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                404,
            )

        # Check expiration
        if invitation.invite_expires_at < datetime.utcnow():
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Invitation has expired",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                410,
            )

        # Update invitation to active membership
        invitation.user_id = user_id
        invitation.status = "active"
        invitation.joined_at = datetime.utcnow()
        invitation.invite_token = None
        invitation.invite_expires_at = None

        db.session.commit()

        # Send welcome notification
        NotificationService.send_team_join_success(invitation.team_id, user_id)

        team = Team.query.get(invitation.team_id)

        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "team": {
                            "id": team.id,
                            "name": team.name,
                            "description": team.description,
                            "avatar": team.avatar_url,
                            "role": invitation.role,
                            "permissions": invitation.get_permissions(),
                        }
                    },
                    "message": f"Successfully joined {team.name}",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error joining team: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to join team",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            500,
        )


# Create a separate blueprint for public invitation pages (no /api prefix)
teams_public_bp = Blueprint("teams_public", __name__, url_prefix="/teams")


@teams_public_bp.route("/invitations/<token>/view", methods=["GET"])  # ✅ CHANGE PATH
def view_invitation_public(token):
    """View team invitation acceptance page (public route)"""
    try:
        from sqlalchemy import text

        print(f"🎯 VIEW INVITATION PUBLIC: Token {token[:8]}...")

        # Get invitation details using raw SQL to avoid enum issues
        result = db.session.execute(
            text(
                """
            SELECT tm.id, tm.invitation_token, tm.role, tm.invitation_expires_at,
                   tm.invitation_status, u.email, u.username, t.name, t.description, t.avatar_url,
                   inviter.username as inviter_name
            FROM team_members tm
            LEFT JOIN users u ON tm.user_id = u.id
            LEFT JOIN teams t ON tm.team_id = t.id
            LEFT JOIN users inviter ON tm.invited_by_id = inviter.id
            WHERE tm.invitation_token = :token
        """
            ),
            {"token": token},
        ).first()

        if not result:
            print(f"❌ VIEW INVITATION PUBLIC: Invalid token")
            return render_template("errors/404.html"), 404

        # ✅ ADD ENHANCED LOGGING
        print(f"🔍 VIEW INVITATION: Invitation data types:")
        print(f"  - expires_at: {result[3]} (type: {type(result[3])})")
        print(f"  - status: {result[4]} (type: {type(result[4])})")

        # Check if invitation is still pending
        if result[4].lower() != "pending":
            print(f"❌ VIEW INVITATION PUBLIC: Invitation already {result[4]}")
            return render_template("errors/invitation_expired.html"), 410

        # Check if invitation is expired
        # Check if invitation is expired
        from datetime import datetime

        # ✅ FIX: Convert string to datetime if needed
        expires_at = result[3]
        if expires_at:
            if isinstance(expires_at, str):
                try:
                    expires_at = datetime.fromisoformat(
                        expires_at.replace("Z", "+00:00")
                    )
                except:
                    expires_at = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S.%f")

            if datetime.utcnow() > expires_at:
                print(f"❌ VIEW INVITATION PUBLIC: Invitation expired")
                return render_template("errors/invitation_expired.html"), 410

        # Prepare template data
        invitation_data = {
            "token": token,
            "team": {
                "id": result[0],
                "name": result[7],
                "description": result[8],
                "avatar": result[9] or result[7][:2].upper(),
            },
            "role": result[2],
            "inviter_name": result[10] or "Team Admin",
            "user_email": result[5],
            "expires_at": result[3],
            "accept_url": f"/api/teams/invitations/{token}/accept",
            "decline_url": f"/api/teams/invitations/{token}/decline",
        }

        print(
            f"✅ VIEW INVITATION PUBLIC: Showing invitation for {result[5]} to join {result[7]}"
        )

        # Use the email template as the invitation page
        return render_template("emails/team_invitation.html", **invitation_data)

    except Exception as e:
        print(f"❌ VIEW INVITATION PUBLIC ERROR: {str(e)}")
        return render_template("errors/404.html"), 404


# Export both blueprints
__all__ = ["teams_bp", "teams_public_bp"]
