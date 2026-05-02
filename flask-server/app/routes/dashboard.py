from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for,
    flash,
    current_app,
)
import os
import uuid
from werkzeug.utils import secure_filename
from PIL import Image
import io
import base64
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import desc, func, or_
from app.models.user import User
from app.models.snippet import Snippet
from app.models.collection import Collection
from app.services.analytics_service import AnalyticsService
from app.services.search_engine import SearchEngine
from app.utils.helpers import (
    get_user_preferences,
    get_user_stats,
    update_user_activity,
    update_user_activity_simple,
)
from sqlalchemy.orm.attributes import flag_modified  # Add this line


from app import db
import json
# Add this after your existing imports


dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")

@dashboard_bp.before_request
def log_dashboard_requests():
    current_app.logger.info(f"🎯 DASHBOARD REQUEST: {request.method} {request.path}")
    current_app.logger.info(
        f"🎯 DASHBOARD USER: {current_user.email if current_user.is_authenticated else 'Not authenticated'}"
    )
    current_app.logger.info(f"🎯 DASHBOARD ENDPOINT: {request.endpoint}")

@dashboard_bp.route("/")
@login_required
def index():
    """Main dashboard view with analytics and overview"""
    try:
        print(
            f"🔍 DASHBOARD - User: {current_user.id}, authenticated: {current_user.is_authenticated}"
        )

        # Update user activity
        update_user_activity_simple(current_user.id)

        # Get user statistics
        stats = {
            # NEW - only counts active (non-deleted) snippets
            "total_snippets": Snippet.query.filter_by(
                user_id=current_user.id, is_deleted=False
            ).count(),
            # NEW - only count non-deleted collections (if you have is_deleted field)
            "total_collections": Collection.query.filter_by(
                user_id=current_user.id
            ).count(),
            # NEW - only count active snippets from this week
            "snippets_this_week": Snippet.query.filter(
                Snippet.user_id == current_user.id,
                Snippet.is_deleted == False,
                Snippet.created_at >= datetime.utcnow() - timedelta(days=7),
            ).count(),
            "most_used_language": get_most_used_language(current_user.id),
            "recent_activity": get_recent_activity(current_user.id),
        }

        print("✅ DASHBOARD - Stats calculated successfully")

        # Get recent snippets (last 10)
        recent_snippets = (
            Snippet.query.filter_by(user_id=current_user.id, is_deleted=False)
            .order_by(desc(Snippet.updated_at))
            .limit(10)
            .all()
        )

        print(f"✅ DASHBOARD - Retrieved {len(recent_snippets)} recent snippets")

        # Get favorite collections
        favorite_collections = (
            Collection.query.filter_by(user_id=current_user.id, is_favorite=True)
            .limit(5)
            .all()
        )

        print(
            f"✅ DASHBOARD - Retrieved {len(favorite_collections)} favorite collections"
        )

        # Get language distribution for charts
        language_stats = get_language_distribution(current_user.id)

        print(
            f"✅ DASHBOARD - Retrieved language stats with {len(language_stats)} entries"
        )

        # Get user preferences
        user_prefs = get_user_preferences(current_user.id)

        print("✅ DASHBOARD - Retrieved user preferences")

        # ENHANCED: Get enhanced user data with avatar
        enhanced_user_data = {
            "id": current_user.id,
            "email": current_user.email,
            "username": getattr(
                current_user, "username", current_user.email.split("@")[0]
            ),
            "plan_type": getattr(current_user, "plan_type", "free"),
            "profile_settings": getattr(current_user, "profile_settings", {}) or {},
            "created_at": getattr(current_user, "created_at", None),
        }

        # Enhanced avatar URL handling with multiple fallbacks
        avatar_url = None

        # Priority 1: Direct avatar_url field
        if hasattr(current_user, "avatar_url") and current_user.avatar_url:
            avatar_url = current_user.avatar_url
            print(f"✅ DASHBOARD - Avatar from direct field: {avatar_url}")

        # Priority 2: Profile settings avatar_url
        elif enhanced_user_data["profile_settings"].get("avatar_url"):
            avatar_url = enhanced_user_data["profile_settings"].get("avatar_url")
            print(f"✅ DASHBOARD - Avatar from profile settings: {avatar_url}")

        # Priority 3: Default fallback
        else:
            avatar_url = "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=40&h=40&fit=crop&crop=face"
            print(f"✅ DASHBOARD - Using default avatar: {avatar_url}")

        enhanced_user_data["avatar_url"] = avatar_url

        print(f"✅ DASHBOARD - Enhanced user data prepared:")
        print(f"  📧 Email: {enhanced_user_data['email']}")
        print(f"  👤 Username: {enhanced_user_data['username']}")
        print(f"  🖼️ Avatar URL: {avatar_url}")
        print(f"  📊 Plan: {enhanced_user_data['plan_type']}")
        print(
            f"  ⚙️ Profile settings keys: {list(enhanced_user_data['profile_settings'].keys())}"
        )

        print("🔍 DASHBOARD - Rendering template with enhanced data")

        return render_template(
            "dashboard/index.html",
            stats=stats,
            recent_snippets=recent_snippets,
            favorite_collections=favorite_collections,
            language_stats=language_stats,
            user_preferences=user_prefs,
            user=enhanced_user_data,  # Pass enhanced user data instead of current_user
        )

    except Exception as e:
        print(f"❌ DASHBOARD - Critical error: {str(e)}")
        import traceback

        print("❌ DASHBOARD - Full traceback:")
        traceback.print_exc()
        flash(f"Error loading dashboard: {str(e)}", "error")
        return redirect(url_for("auth.login"))


@dashboard_bp.route("/snippets")
@login_required
def snippets():
    """Snippet management interface"""
    try:
        # Get filter parameters
        search_query = request.args.get("search", "")
        language_filter = request.args.get("language", "")
        collection_filter = request.args.get("collection", "")
        tag_filter = request.args.get("tags", "")
        date_filter = request.args.get("date_range", "")
        sort_by = request.args.get("sort", "updated_at")
        sort_order = request.args.get("order", "desc")
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)

        # Build query
        query = Snippet.query.filter_by(user_id=current_user.id)

        # Apply filters
        if search_query:
            query = query.filter(
                or_(
                    Snippet.title.contains(search_query),
                    Snippet.description.contains(search_query),
                    Snippet.code.contains(search_query),
                    Snippet.tags.contains(search_query),
                )
            )

        if language_filter:
            query = query.filter(Snippet.language == language_filter)

        if collection_filter and collection_filter != "all":
            if collection_filter == "uncategorized":
                query = query.filter(Snippet.collection_id.is_(None))
            else:
                query = query.filter(Snippet.collection_id == collection_filter)

        if tag_filter:
            query = query.filter(Snippet.tags.contains(tag_filter))

        if date_filter:
            if date_filter == "today":
                query = query.filter(Snippet.created_at >= datetime.utcnow().date())
            elif date_filter == "week":
                query = query.filter(
                    Snippet.created_at >= datetime.utcnow() - timedelta(days=7)
                )
            elif date_filter == "month":
                query = query.filter(
                    Snippet.created_at >= datetime.utcnow() - timedelta(days=30)
                )

        # Apply sorting
        if sort_order == "desc":
            query = query.order_by(desc(getattr(Snippet, sort_by)))
        else:
            query = query.order_by(getattr(Snippet, sort_by))

        # Paginate results
        snippets = query.paginate(page=page, per_page=per_page, error_out=False)

        # Get available languages and collections for filters
        languages = (
            db.session.query(Snippet.language)
            .filter_by(user_id=current_user.id)
            .distinct()
            .all()
        )
        languages = [lang[0] for lang in languages if lang[0]]

        collections = Collection.query.filter_by(user_id=current_user.id).all()

        # Get all unique tags
        all_tags = set()
        for snippet in Snippet.query.filter_by(user_id=current_user.id).all():
            if snippet.tags:
                tags = snippet.tags.split(",")
                all_tags.update([tag.strip() for tag in tags])

        return render_template(
            "dashboard/snippets.html",
            snippets=snippets,
            languages=languages,
            collections=collections,
            all_tags=sorted(all_tags),
            current_filters={
                "search": search_query,
                "language": language_filter,
                "collection": collection_filter,
                "tags": tag_filter,
                "date_range": date_filter,
                "sort": sort_by,
                "order": sort_order,
            },
        )

    except Exception as e:
        flash(f"Error loading snippets: {str(e)}", "error")
        return redirect(url_for("dashboard.index"))


@dashboard_bp.route("/api/snippets")
@login_required
def api_snippets():
    """API endpoint to get user snippets with enhanced logging and favorite support"""
    try:
        print(f"🔍 API SNIPPETS - Starting for user: {current_user.id}")

        # Get all snippets from all collections belonging to the user
        all_snippets = []

        # Method 1: Get snippets from collections (exclude deleted)
        collections = Collection.query.filter_by(user_id=current_user.id).all()
        print(f"🔍 Found {len(collections)} collections for user {current_user.id}")

        collection_snippets = []
        for collection in collections:
            print(f"🔍 Processing collection: {collection.name} (ID: {collection.id})")
            for snippet in collection.snippets:
                if not getattr(snippet, "is_deleted", False):
                    collection_snippets.append(snippet)
                    print(
                        f"  ✅ Collection snippet: {snippet.title} (Favorite: {getattr(snippet, 'is_favorite', False)})"
                    )

        # Method 2: Get all user snippets directly (including those not in collections)
        direct_snippets = Snippet.query.filter_by(
            user_id=current_user.id, is_deleted=False
        ).all()
        print(
            f"🔍 Found {len(direct_snippets)} direct snippets for user {current_user.id}"
        )

        # Combine and deduplicate snippets
        snippet_ids = set()
        for snippet in collection_snippets + direct_snippets:
            if snippet.id not in snippet_ids:
                all_snippets.append(snippet)
                snippet_ids.add(snippet.id)
                print(f"  ✅ Added unique snippet: {snippet.title} (ID: {snippet.id})")

        print(f"🔍 Total unique snippets after deduplication: {len(all_snippets)}")

        # Sort by updated_at descending
        all_snippets.sort(key=lambda x: x.updated_at, reverse=True)

        # Convert to JSON-serializable format with enhanced logging
        snippets_data = []
        favorite_count = 0

        for snippet in all_snippets:
            # Safely get favorite status
            is_favorite = getattr(snippet, "is_favorite", False)
            if is_favorite:
                favorite_count += 1

            print(
                f"🔍 Processing snippet {snippet.id}: '{snippet.title}' (Favorite: {is_favorite})"
            )

            # Safely get tags
            try:
                tags = (
                    snippet.get_tags_list() if hasattr(snippet, "get_tags_list") else []
                )
            except:
                tags = snippet.tags.split(",") if snippet.tags else []

            snippet_dict = {
                "id": snippet.id,
                "title": snippet.title,
                "description": getattr(snippet, "description", ""),
                "code": snippet.code,
                "language": snippet.language,
                "tags": tags,
                "created_at": (
                    snippet.created_at.isoformat() if snippet.created_at else None
                ),
                "updated_at": (
                    snippet.updated_at.isoformat() if snippet.updated_at else None
                ),
                "source_url": getattr(snippet, "source_url", ""),
                "view_count": getattr(snippet, "view_count", 0),
                "line_count": len(snippet.code.split("\n")) if snippet.code else 0,
                "character_count": len(snippet.code) if snippet.code else 0,
                "is_favorite": is_favorite,  # CRITICAL: Include favorite status
                "collection_id": getattr(snippet, "collection_id", None),
            }
            snippets_data.append(snippet_dict)

        print(f"✅ API SNIPPETS SUCCESS:")
        print(f"  📊 Total snippets: {len(snippets_data)}")
        print(f"  ⭐ Favorite snippets: {favorite_count}")
        print(f"  📁 Collections processed: {len(collections)}")

        # Log sample of favorite snippets for debugging
        favorites = [s for s in snippets_data if s["is_favorite"]]
        if favorites:
            print(f"⭐ FAVORITE SNIPPETS DETAILS:")
            for fav in favorites[:3]:  # Show first 3 favorites
                print(
                    f"  - {fav['id']}: '{fav['title']}' (is_favorite: {fav['is_favorite']})"
                )

        return jsonify({"snippets": snippets_data})

    except Exception as e:
        print(f"❌ CRITICAL ERROR in API snippets: {str(e)}")
        import traceback

        print(f"❌ FULL TRACEBACK:")
        traceback.print_exc()
        return jsonify({"error": str(e), "success": False}), 500


@dashboard_bp.route("/api/collections")
@login_required
def api_collections():
    """API endpoint to get user collections"""
    try:
        collections = Collection.query.filter_by(user_id=current_user.id).all()

        # Convert to JSON-serializable format
        collections_data = []
        for collection in collections:
            # Use the relationship to count snippets
            snippet_count = len(collection.snippets)
            collections_data.append(
                {
                    "id": collection.id,
                    "name": collection.name,
                    "description": collection.description,
                    "is_favorite": collection.is_favorite,
                    "created_at": (
                        collection.created_at.isoformat()
                        if collection.created_at
                        else None
                    ),
                    "updated_at": (
                        collection.updated_at.isoformat()
                        if collection.updated_at
                        else None
                    ),
                    "snippet_count": snippet_count,
                }
            )

        return jsonify({"collections": collections_data})

    except Exception as e:
        print(f"Error in API collections: {str(e)}")
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/integrations")
@login_required
def integrations():
    """Render the integrations page"""
    # Get user stats for sidebar
    stats = {
        "total_snippets": Snippet.query.filter_by(user_id=current_user.id).count(),
        "total_collections": Collection.query.filter_by(
            user_id=current_user.id
        ).count(),
    }

    # Check if user has GitHub integration - safely check attributes
    github_connected = False
    slack_connected = False
    vscode_connected = False

    try:
        github_connected = hasattr(current_user, "github_token") and bool(
            current_user.github_token
        )
        slack_connected = hasattr(current_user, "slack_token") and bool(
            current_user.slack_token
        )
        vscode_connected = hasattr(current_user, "vscode_settings") and bool(
            current_user.vscode_settings
        )
    except:
        # If any attribute error occurs, just use defaults
        pass

    # Integration data to pass to template
    integrations_data = {
        "github": {
            "connected": github_connected,
            "status": "Connected" if github_connected else "Disconnected",
            "status_class": (
                "status-connected" if github_connected else "status-disconnected"
            ),
        },
        "slack": {
            "connected": slack_connected,
            "status": "Connected" if slack_connected else "Disconnected",
            "status_class": (
                "status-connected" if slack_connected else "status-disconnected"
            ),
        },
        "vscode": {
            "connected": vscode_connected,
            "status": "Installed" if vscode_connected else "Not Installed",
            "status_class": (
                "status-connected" if vscode_connected else "status-disconnected"
            ),
        },
        "webhooks": {
            "count": 0,
            "status": "No Webhooks",
            "status_class": "status-disconnected",
        },
    }

    return render_template(
        "dashboard/integrations.html", stats=stats, integrations=integrations_data
    )


@dashboard_bp.route("/teams")
@login_required
def teams():
    """Teams management page with enhanced logging"""
    try:
        current_app.logger.info(
            f"🎯 TEAMS DASHBOARD: User {current_user.email} accessing teams page"
        )

        # Get user stats for sidebar (same as other routes)
        stats = {
            "total_snippets": Snippet.query.filter_by(
                user_id=current_user.id, is_deleted=False
            ).count(),
            "total_collections": Collection.query.filter_by(
                user_id=current_user.id
            ).count(),
            "snippets_this_week": Snippet.query.filter(
                Snippet.user_id == current_user.id,
                Snippet.is_deleted == False,
                Snippet.created_at >= datetime.utcnow() - timedelta(days=7),
            ).count(),
            "shared_count": 0,  # Add this for template compatibility
        }

        current_app.logger.info(f"✅ TEAMS DASHBOARD: Stats calculated: {stats}")
        current_app.logger.info(f"✅ TEAMS DASHBOARD: Rendering teams.html template")

        return render_template(
            "dashboard/teams.html", user=current_user, stats=stats, page_title="Teams"
        )

    except Exception as e:
        current_app.logger.error(f"❌ TEAMS DASHBOARD ERROR: {str(e)}")
        import traceback

        current_app.logger.error(f"❌ TEAMS TRACEBACK: {traceback.format_exc()}")
        flash(f"Error loading teams page: {str(e)}", "error")
        return redirect(url_for("dashboard.index"))


@dashboard_bp.route("/collections")
@login_required
def collections():
    try:
        print("Collections route accessed")

        # Get collections with snippet counts
        collections = (
            Collection.query.filter_by(user_id=current_user.id)
            .order_by(Collection.created_at.desc())
            .all()
        )

        print(
            f"📊 COLLECTIONS - Found {len(collections)} collections for user {current_user.id}"
        )

        # Calculate REAL stats
        total_collections = len(collections)
        total_snippets = Snippet.query.filter_by(user_id=current_user.id).count()
        shared_collections = Collection.query.filter_by(
            user_id=current_user.id, is_public=True
        ).count()

        # Calculate organization rate
        organization_rate = 0  # Default for now
        if total_snippets > 0:
            snippets_in_collections = 0
            for collection in collections:
                snippets_in_collections += len(collection.snippets)
            organization_rate = round((snippets_in_collections / total_snippets * 100))

        # Calculate collection stats
        collection_stats = {}
        for collection in collections:
            snippet_count = len(collection.snippets)
            collection_stats[collection.id] = {
                "snippet_count": snippet_count,
                "last_updated": collection.updated_at,
                "view_count": getattr(collection, "view_count", 0),
                "contributor_count": getattr(collection, "contributor_count", 1),
                "completion_rate": (snippet_count * 10) if snippet_count > 0 else 0,
            }

        # Count uncategorized snippets
        all_user_snippets = Snippet.query.filter_by(user_id=current_user.id).all()
        uncategorized_count = 0
        for snippet in all_user_snippets:
            if len(snippet.collections) == 0:
                uncategorized_count += 1

        # Pass real stats to template
        real_stats = {
            "total_collections": total_collections,
            "total_snippets": total_snippets,
            "shared_collections": shared_collections,
            "organization_rate": organization_rate,
        }

        return render_template(
            "dashboard/collections.html",
            collections=collections,
            collection_stats=collection_stats,
            uncategorized_count=uncategorized_count,
            stats=real_stats,
        )
    except Exception as e:
        print(f"Error in collections route: {str(e)}")
        import traceback

        traceback.print_exc()
        flash(f"Error loading collections: {str(e)}", "error")
        return redirect(url_for("dashboard.index"))


@dashboard_bp.route("/collections/<collection_id>")
@login_required
def view_collection(collection_id):
    try:
        collection = Collection.query.filter_by(
            id=collection_id, user_id=current_user.id
        ).first_or_404()

        # Track the view
        collection.track_view(current_user.id)

        # Get all snippets in this collection
        snippets = collection.snippets

        # Calculate REAL collection stats
        languages = list(set([s.language for s in snippets if s.language]))
        total_lines = sum([s.get_line_count() for s in snippets])
        view_count = sum([getattr(s, "view_count", 0) for s in snippets])

        collection_stats = {
            "snippet_count": len(snippets),
            "language_count": len(languages),
            "languages": languages,
            "total_lines": total_lines,
            "view_count": view_count,
            "fork_count": getattr(collection, "share_count", 0),
            "last_updated": collection.updated_at,
            "created_at": collection.created_at,
            "is_favorited": getattr(collection, "is_favorite", False),
        }

        # Pass real data to template
        return render_template(
            "dashboard/collection_detail.html",
            collection=collection,
            snippets=snippets,
            collection_stats=collection_stats,
        )
    except Exception as e:
        flash(f"Error loading collection: {str(e)}", "error")
        return redirect(url_for("dashboard.collections"))


@dashboard_bp.route("/api/collections/<collection_id>", methods=["PUT"])
@login_required
def update_collection(collection_id):
    """Update collection details"""
    try:
        collection = Collection.query.filter_by(
            id=collection_id, user_id=current_user.id
        ).first_or_404()

        data = request.get_json()

        # Update fields
        if "name" in data:
            collection.name = data["name"].strip()
        if "description" in data:
            collection.description = data["description"].strip()
        if "color" in data:
            collection.color = data["color"]
        if "icon" in data:
            collection.icon = data["icon"]
        if "is_public" in data:
            collection.is_public = data["is_public"]
        if "parent_id" in data:
            collection.parent_id = data["parent_id"] if data["parent_id"] else None

        collection.updated_at = datetime.utcnow()

        # Add this right before db.session.commit()
        try:
            print(f"🔍 COMMIT ATTEMPT - About to commit changes")
            print(f"🔍 COMMIT - User ID: {current_user.id}")
            print(f"🔍 COMMIT - Profile settings: {current_user.profile_settings}")
            print(f"🔍 COMMIT - Session dirty objects: {list(db.session.dirty)}")
            print(f"🔍 COMMIT - Session new objects: {list(db.session.new)}")

            db.session.commit()

            # Verify the save worked
            fresh_user = User.query.get(current_user.id)
            print(
                f"✅ COMMIT SUCCESS - Fresh profile settings: {fresh_user.profile_settings}"
            )

        except Exception as commit_error:
            print(f"❌ COMMIT ERROR: {str(commit_error)}")
            db.session.rollback()
            raise
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": "Collection updated successfully",
                "collection": {
                    "id": collection.id,
                    "name": collection.name,
                    "description": collection.description,
                    "color": collection.color,
                    "icon": collection.icon,
                    "is_public": collection.is_public,
                },
            }
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@dashboard_bp.route("/debug/user-profile-db")
@login_required
def debug_user_profile_db():
    """Debug route to check actual database state"""
    try:
        print(f"🔍 DEBUG DB - Checking database state for user: {current_user.id}")

        # Get fresh user from database
        fresh_user = User.query.get(current_user.id)

        debug_data = {
            "user_id": fresh_user.id,
            "user_email": fresh_user.email,
            "profile_settings_raw": fresh_user.profile_settings,
            "profile_settings_type": type(fresh_user.profile_settings).__name__,
            "has_profile_settings_attr": hasattr(fresh_user, "profile_settings"),
            "profile_settings_is_none": fresh_user.profile_settings is None,
            "all_user_columns": [
                column.name for column in fresh_user.__table__.columns
            ],
        }

        print(f"✅ DEBUG DB - Database state: {debug_data}")
        return jsonify(debug_data)

    except Exception as e:
        print(f"❌ DEBUG DB ERROR: {str(e)}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/api/user-profile", methods=["GET"])
@login_required
def get_user_profile():
    """Get comprehensive user profile data"""
    try:
        print(f"🔍 USER PROFILE API - Starting for user: {current_user.id}")

        # Get user with all related data
        user = User.query.get(current_user.id)
        if not user:
            print(f"❌ USER PROFILE API - User not found: {current_user.id}")
            return jsonify({"success": False, "message": "User not found"}), 404

        # Calculate real stats
        total_snippets = user.snippets.filter_by(is_deleted=False).count()
        total_collections = user.collections.count()

        # Calculate account age
        account_age_days = (
            (datetime.utcnow() - user.created_at).days if user.created_at else 0
        )

        # Calculate snippets this month
        start_of_month = datetime.utcnow().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        snippets_this_month = user.snippets.filter(
            Snippet.created_at >= start_of_month, Snippet.is_deleted == False
        ).count()

        # Get favorite languages
        favorite_languages = []
        if hasattr(user, "favorite_languages") and user.favorite_languages:
            try:
                if isinstance(user.favorite_languages, str):
                    favorite_languages = json.loads(user.favorite_languages)
                elif isinstance(user.favorite_languages, list):
                    favorite_languages = user.favorite_languages
            except:
                favorite_languages = []

        # Prepare stats
        stats = {
            "total_snippets": total_snippets,
            "total_collections": total_collections,
            "account_age_days": account_age_days,
            "snippets_this_month": snippets_this_month,
            "total_views": getattr(user, "total_session_time", 0),
            "last_login": (
                user.last_login_at
                if hasattr(user, "last_login_at") and user.last_login_at
                else user.created_at
            ),
            "favorite_languages": favorite_languages,
        }

        # Get profile settings with defaults
        profile_settings = (
            user.profile_settings
            if hasattr(user, "profile_settings") and user.profile_settings
            else {}
        )

        # Ensure all required fields exist
        default_profile = {
            "avatar_url": None,
            "bio": "",
            "location": "",
            "website": "",
            "twitter": "",
            "github": "",
            "linkedin": "",
            "timezone": "UTC",
            "language": "en",
            "profile_visibility": "public",
        }

        # Merge with defaults
        for key, default_value in default_profile.items():
            if key not in profile_settings:
                profile_settings[key] = default_value

        # Prepare user data
        user_data = {
            "id": str(user.id),
            "email": user.email,
            "username": getattr(user, "username", user.email.split("@")[0]),
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "plan_type": getattr(user, "plan_type", "free"),
            "theme_preference": getattr(user, "theme_preference", "dark"),
        }

        response_data = {
            "success": True,
            "data": {
                "user": user_data,
                "profile_settings": profile_settings,
                "stats": stats,
                "preferences": getattr(user, "preferences", {}),
            },
        }

        print(f"✅ USER PROFILE API - Success for user: {user.email}")
        print(f"📊 USER PROFILE API - Stats: {stats}")
        print(f"👤 USER PROFILE API - Profile: {profile_settings}")

        return jsonify(response_data)

    except Exception as e:
        print(f"❌ USER PROFILE API - Error: {str(e)}")
        import traceback

        traceback.print_exc()
        return (
            jsonify({"success": False, "message": f"Error loading profile: {str(e)}"}),
            500,
        )


@dashboard_bp.route("/api/update-profile", methods=["POST"])
@login_required
def update_user_profile():
    """Update user profile information"""
    try:
        print(f"🔍 UPDATE PROFILE API - Starting for user: {current_user.id}")

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        user = User.query.get(current_user.id)
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404

        # Get current profile settings or create new
        profile_settings = (
            user.profile_settings
            if hasattr(user, "profile_settings") and user.profile_settings
            else {}
        )

        # Update profile settings
        updated_fields = []
        for field in ["bio", "location", "website", "github", "twitter", "linkedin"]:
            if field in data:
                old_value = profile_settings.get(field, "")
                new_value = data[field].strip() if data[field] else ""
                if old_value != new_value:
                    profile_settings[field] = new_value
                    updated_fields.append(field)
                    print(f"✅ Updated {field}: '{old_value}' -> '{new_value}'")

        # Update email if provided
        if "email" in data and data["email"] != user.email:
            # Check if email already exists
            existing_user = User.query.filter_by(email=data["email"]).first()
            if existing_user and existing_user.id != user.id:
                return (
                    jsonify({"success": False, "message": "Email already in use"}),
                    400,
                )

            user.email = data["email"]
            updated_fields.append("email")

        # Save profile settings
        user.profile_settings = profile_settings

        # Mark as modified for SQLAlchemy
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(user, "profile_settings")

        db.session.commit()

        print(f"✅ UPDATE PROFILE API - Success. Updated fields: {updated_fields}")

        return jsonify(
            {
                "success": True,
                "message": "Profile updated successfully",
                "updated_fields": updated_fields,
            }
        )

    except Exception as e:
        print(f"❌ UPDATE PROFILE API - Error: {str(e)}")
        db.session.rollback()
        import traceback

        traceback.print_exc()
        return (
            jsonify({"success": False, "message": f"Error updating profile: {str(e)}"}),
            500,
        )


@dashboard_bp.route("/analytics")
@login_required
def analytics():
    """Analytics and insights page"""
    try:
        analytics_service = AnalyticsService()

        # Get comprehensive analytics
        analytics_data = {
            "usage_trends": analytics_service.get_usage_trends(current_user.id),
            "language_breakdown": analytics_service.get_language_breakdown(
                current_user.id
            ),
            "creation_patterns": analytics_service.get_creation_patterns(
                current_user.id
            ),
            "collection_insights": analytics_service.get_collection_insights(
                current_user.id
            ),
            "productivity_metrics": analytics_service.get_productivity_metrics(
                current_user.id
            ),
        }

        return jsonify(analytics_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/search")
@login_required
def search():
    """Advanced search endpoint"""
    try:
        query = request.args.get("q", "")
        filters = {
            "language": request.args.get("language"),
            "collection": request.args.get("collection"),
            "tags": request.args.get("tags"),
            "date_from": request.args.get("date_from"),
            "date_to": request.args.get("date_to"),
        }

        search_engine = SearchEngine()
        results = search_engine.search_snippets(
            user_id=current_user.id, query=query, filters=filters
        )

        return jsonify(
            {
                "results": results,
                "total": len(results),
                "query": query,
                "filters": filters,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/api/stats")
@login_required
def api_stats():
    """API endpoint to get user stats"""
    try:
        # Get user statistics - FIXED to exclude deleted snippets
        stats = {
            "total_snippets": Snippet.query.filter_by(
                user_id=current_user.id, is_deleted=False
            ).count(),
            "total_collections": Collection.query.filter_by(
                user_id=current_user.id
            ).count(),
            "snippets_this_week": Snippet.query.filter(
                Snippet.user_id == current_user.id,
                Snippet.is_deleted == False,
                Snippet.created_at >= datetime.utcnow() - timedelta(days=7),
            ).count(),
            "most_used_language": get_most_used_language(current_user.id),
            "language_distribution": get_language_distribution(current_user.id),
            "views_today": 0,
            "shared_count": 0,
        }

        return jsonify(stats)

    except Exception as e:
        print(f"Error in API stats: {str(e)}")
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/preferences", methods=["GET", "POST"])
@login_required
def preferences():
    """User preferences management"""
    if request.method == "POST":
        try:
            preferences = request.json

            # Update user preferences
            current_user.theme = preferences.get("theme", "dark")
            current_user.default_language = preferences.get(
                "default_language", "javascript"
            )
            current_user.snippets_per_page = preferences.get("snippets_per_page", 20)
            current_user.auto_save = preferences.get("auto_save", True)
            current_user.syntax_highlighting = preferences.get(
                "syntax_highlighting", True
            )
            current_user.show_line_numbers = preferences.get("show_line_numbers", True)
            current_user.notifications_enabled = preferences.get(
                "notifications_enabled", True
            )

            db.session.commit()

            return jsonify(
                {"success": True, "message": "Preferences updated successfully"}
            )

        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500

    else:
        # Return current preferences
        return jsonify(
            {
                "theme": current_user.theme or "dark",
                "default_language": current_user.default_language or "javascript",
                "snippets_per_page": current_user.snippets_per_page or 20,
                "auto_save": current_user.auto_save or True,
                "syntax_highlighting": current_user.syntax_highlighting or True,
                "show_line_numbers": current_user.show_line_numbers or True,
                "notifications_enabled": current_user.notifications_enabled or True,
            }
        )


# Helper functions
def get_most_used_language(user_id):
    """Get the most frequently used programming language"""
    try:
        result = (
            db.session.query(
                Snippet.language, func.count(Snippet.language).label("count")
            )
            .filter_by(user_id=user_id)
            .group_by(Snippet.language)
            .order_by(desc("count"))
            .first()
        )

        return result[0] if result else "JavaScript"
    except:
        return "JavaScript"


@dashboard_bp.route("/recent")
@login_required
def recent():
    """Show recently viewed/accessed snippets and collections"""
    try:
        print(f"🔍 RECENT ROUTE - Starting for user: {current_user.id}")
        print(f"🔍 CURRENT USER DEBUG:")
        print(f"  - ID: {current_user.id}")
        print(f"  - Email: {getattr(current_user, 'email', 'NO EMAIL ATTR')}")
        print(f"  - Has username attr: {hasattr(current_user, 'username')}")
        print(f"  - Is authenticated: {current_user.is_authenticated}")
        print(f"  - User type: {type(current_user)}")

        # Get recently viewed snippets (check multiple fields)
        recent_snippets_query = Snippet.query.filter_by(
            user_id=current_user.id, is_deleted=False
        )

        # Try last_viewed_at first, then last_accessed
        if hasattr(Snippet, "last_viewed_at"):
            print("🔍 Using last_viewed_at field")
            recent_snippets = (
                recent_snippets_query.filter(Snippet.last_viewed_at.isnot(None))
                .order_by(desc(Snippet.last_viewed_at))
                .limit(20)
                .all()
            )
        elif hasattr(Snippet, "last_accessed"):
            print("🔍 Using last_accessed field")
            recent_snippets = (
                recent_snippets_query.filter(Snippet.last_accessed.isnot(None))
                .order_by(desc(Snippet.last_accessed))
                .limit(20)
                .all()
            )
        else:
            print("🔍 No view tracking fields found, using updated_at")
            recent_snippets = []

        print(f"🔍 Found {len(recent_snippets)} recently viewed snippets")

        # Get recently accessed collections
        recent_collections_query = Collection.query.filter_by(user_id=current_user.id)

        if hasattr(Collection, "last_accessed"):
            recent_collections = (
                recent_collections_query.filter(Collection.last_accessed.isnot(None))
                .order_by(desc(Collection.last_accessed))
                .limit(10)
                .all()
            )
        else:
            recent_collections = []

        print(f"🔍 Found {len(recent_collections)} recently accessed collections")

        # If no recent views, get recently updated items
        if not recent_snippets:
            print("🔍 No recent views found, getting recently updated snippets")
            recent_snippets = (
                Snippet.query.filter_by(user_id=current_user.id, is_deleted=False)
                .order_by(desc(Snippet.updated_at))
                .limit(15)
                .all()
            )
            print(f"🔍 Got {len(recent_snippets)} recently updated snippets")

        if not recent_collections:
            print(
                "🔍 No recent collection access, getting recently updated collections"
            )
            recent_collections = (
                Collection.query.filter_by(user_id=current_user.id)
                .order_by(desc(Collection.updated_at))
                .limit(8)
                .all()
            )
            print(f"🔍 Got {len(recent_collections)} recently updated collections")

        # Get stats for sidebar
        stats = {
            "total_snippets": Snippet.query.filter_by(
                user_id=current_user.id, is_deleted=False
            ).count(),
            "total_collections": Collection.query.filter_by(
                user_id=current_user.id
            ).count(),
        }
        print(f"🔍 Stats: {stats}")

        # Get activity summary with safe date filtering
        today = datetime.utcnow().date()
        print(f"🔍 Calculating activity for date: {today}")

        try:
            if hasattr(Snippet, "last_viewed_at"):
                snippets_viewed_today = Snippet.query.filter(
                    Snippet.user_id == current_user.id,
                    func.date(Snippet.last_viewed_at) == today,
                ).count()
            else:
                snippets_viewed_today = 0
        except Exception as e:
            print(f"⚠️ Error calculating snippets viewed today: {e}")
            snippets_viewed_today = 0

        try:
            if hasattr(Collection, "last_accessed"):
                collections_accessed_today = Collection.query.filter(
                    Collection.user_id == current_user.id,
                    func.date(Collection.last_accessed) == today,
                ).count()
            else:
                collections_accessed_today = 0
        except Exception as e:
            print(f"⚠️ Error calculating collections accessed today: {e}")
            collections_accessed_today = 0

        activity_summary = {
            "snippets_viewed_today": snippets_viewed_today,
            "collections_accessed_today": collections_accessed_today,
            "total_views_today": snippets_viewed_today + collections_accessed_today,
        }
        print(f"🔍 Activity Summary: {activity_summary}")

        print("✅ RECENT ROUTE - Rendering template")
        return render_template(
            "dashboard/recent.html",
            snippets=recent_snippets,
            collections=recent_collections,
            stats=stats,
            activity_summary=activity_summary,
            page_title="Recent Activity",
        )

    except Exception as e:
        print(f"❌ CRITICAL ERROR in recent route: {str(e)}")
        import traceback

        print("❌ FULL TRACEBACK:")
        traceback.print_exc()
        flash(f"Error loading recent activity: {str(e)}", "error")
        return redirect(url_for("dashboard.index"))


@dashboard_bp.route("/favorites")
@login_required
def favorites():
    """Display user's favorite snippets and collections"""
    try:
        print(f"⭐ FAVORITES ROUTE - Starting for user: {current_user.id}")

        # Get favorite snippets
        favorite_snippets = (
            Snippet.query.filter_by(
                user_id=current_user.id, is_deleted=False, is_favorite=True
            )
            .order_by(desc(Snippet.updated_at))
            .all()
        )

        print(f"⭐ Found {len(favorite_snippets)} favorite snippets")

        # Get favorite collections
        favorite_collections = (
            Collection.query.filter_by(user_id=current_user.id, is_favorite=True)
            .order_by(desc(Collection.updated_at))
            .all()
        )

        print(f"⭐ Found {len(favorite_collections)} favorite collections")

        # Get stats for sidebar
        stats = {
            "total_snippets": Snippet.query.filter_by(
                user_id=current_user.id, is_deleted=False
            ).count(),
            "total_collections": Collection.query.filter_by(
                user_id=current_user.id
            ).count(),
        }

        print(f"⭐ Stats: {stats}")
        print("✅ FAVORITES ROUTE - Rendering template")

        return render_template(
            "dashboard/favorite.html",
            favorite_snippets=favorite_snippets,
            favorite_collections=favorite_collections,
            stats=stats,
            page_title="Favorites",
        )

    except Exception as e:
        print(f"❌ CRITICAL ERROR in favorites route: {str(e)}")
        import traceback

        print("❌ FULL TRACEBACK:")
        traceback.print_exc()
        flash(f"Error loading favorites: {str(e)}", "error")
        return redirect(url_for("dashboard.index"))


@dashboard_bp.route("/shared")
@login_required
def shared():
    """Shared snippets and collections page"""
    try:
        # Get snippets shared by user
        shared_by_user = (
            Snippet.query.filter_by(user_id=current_user.id, is_public=True)
            .order_by(Snippet.created_at.desc())
            .limit(10)
            .all()
        )

        # Get snippets shared with user (if you have team functionality)
        shared_with_user = []  # Implement based on your team model

        # Get public snippets by user
        public_snippets = Snippet.query.filter_by(
            user_id=current_user.id, is_public=True
        ).count()

        # Calculate share analytics
        total_views = sum(snippet.view_count or 0 for snippet in shared_by_user)

        share_stats = {
            "shared_by_me": len(shared_by_user),
            "shared_with_me": len(shared_with_user),
            "public_snippets": public_snippets,
            "total_views": total_views,
            "total_shares": len(shared_by_user) + len(shared_with_user),
        }

        return render_template(
            "dashboard/shared.html",
            shared_by_user=shared_by_user,
            shared_with_user=shared_with_user,
            share_stats=share_stats,
            stats=get_user_stats(current_user.id),
        )

    except Exception as e:
        flash(f"Error loading shared content: {str(e)}", "error")
        return redirect(url_for("dashboard.index"))


@dashboard_bp.route("/api/shared-snippets")
@login_required
def api_shared_snippets():
    try:
        shared_snippets = Snippet.query.filter_by(
            user_id=current_user.id, is_public=True
        ).all()

        return jsonify(
            {
                "success": True,
                "snippets": [snippet.to_dict() for snippet in shared_snippets],
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@dashboard_bp.route("/api/public-snippets")
@login_required
def api_public_snippets():
    try:
        public_snippets = (
            Snippet.query.filter_by(is_public=True)
            .order_by(Snippet.view_count.desc())
            .limit(20)
            .all()
        )

        return jsonify(
            {
                "success": True,
                "snippets": [snippet.to_dict() for snippet in public_snippets],
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@dashboard_bp.route("/api/snippet/<int:snippet_id>/unshare", methods=["POST"])
@login_required
def api_unshare_snippet(snippet_id):
    try:
        snippet = Snippet.query.filter_by(
            id=snippet_id, user_id=current_user.id
        ).first()
        if snippet:
            snippet.is_public = False
            snippet.share_token = None
            db.session.commit()
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Snippet not found"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@dashboard_bp.route("/profile")
@login_required
def profile():
    """Enhanced profile route with proper avatar loading"""
    try:
        print(f"🔍 PROFILE ROUTE - ===== STARTING =====")
        print(f"🔍 PROFILE ROUTE - User: {current_user.id} ({current_user.email})")

        # Get fresh user data
        user = User.query.get(current_user.id)
        if not user:
            print(f"❌ PROFILE ROUTE - User not found: {current_user.id}")
            flash("User not found", "error")
            return redirect(url_for("dashboard.index"))

        print(f"✅ PROFILE ROUTE - User loaded: {user.email}")

        # Calculate real stats with enhanced logging
        total_snippets = user.snippets.filter_by(is_deleted=False).count()
        total_collections = user.collections.count()
        account_age_days = (
            (datetime.utcnow() - user.created_at).days if user.created_at else 0
        )

        start_of_month = datetime.utcnow().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        snippets_this_month = user.snippets.filter(
            Snippet.created_at >= start_of_month, Snippet.is_deleted == False
        ).count()

        # Get favorite languages
        favorite_languages = []
        if hasattr(user, "favorite_languages") and user.favorite_languages:
            try:
                if isinstance(user.favorite_languages, str):
                    favorite_languages = json.loads(user.favorite_languages)
                elif isinstance(user.favorite_languages, list):
                    favorite_languages = user.favorite_languages
            except:
                favorite_languages = []

        stats = {
            "total_snippets": total_snippets,
            "total_collections": total_collections,
            "account_age_days": account_age_days,
            "snippets_this_month": snippets_this_month,
            "total_views": getattr(user, "total_session_time", 0),
            "last_login": (
                user.last_login_at
                if hasattr(user, "last_login_at") and user.last_login_at
                else user.created_at
            ),
            "favorite_languages": favorite_languages,
        }

        print(f"✅ PROFILE ROUTE - Stats calculated: {stats}")

        # Get profile settings with enhanced avatar handling
        profile_settings = (
            user.profile_settings
            if hasattr(user, "profile_settings") and user.profile_settings
            else {}
        )

        # Enhanced avatar URL handling - check multiple sources
        avatar_url = None

        # Priority 1: Direct avatar_url field (new method)
        if hasattr(user, "avatar_url") and user.avatar_url:
            avatar_url = user.avatar_url
            print(f"✅ PROFILE ROUTE - Avatar from direct field: {avatar_url}")

        # Priority 2: Profile settings avatar_url (backward compatibility)
        elif profile_settings.get("avatar_url"):
            avatar_url = profile_settings.get("avatar_url")
            print(f"✅ PROFILE ROUTE - Avatar from profile settings: {avatar_url}")

        # Priority 3: Default avatar
        else:
            avatar_url = "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=120&h=120&fit=crop&crop=face"
            print(f"✅ PROFILE ROUTE - Using default avatar: {avatar_url}")

        # Ensure avatar_url is in profile_settings for template compatibility
        profile_settings["avatar_url"] = avatar_url

        print(f"✅ PROFILE ROUTE - Final avatar URL: {avatar_url}")
        print(f"✅ PROFILE ROUTE - Profile settings: {profile_settings}")

        # Enhanced user data for template
        enhanced_user_data = {
            "id": user.id,
            "email": user.email,
            "username": getattr(user, "username", user.email.split("@")[0]),
            "created_at": user.created_at,
            "plan_type": getattr(user, "plan_type", "free"),
            "avatar_url": avatar_url,
            "profile_settings": profile_settings,
        }

        print(f"✅ PROFILE ROUTE - Enhanced user data prepared")
        print(f"✅ PROFILE ROUTE - ===== RENDERING TEMPLATE =====")

        return render_template(
            "dashboard/profile.html",
            user=enhanced_user_data,
            stats=stats,
            profile_settings=profile_settings,
        )

    except Exception as e:
        print(f"❌ PROFILE ROUTE - ===== CRITICAL ERROR =====")
        print(f"❌ PROFILE ROUTE - Error: {str(e)}")
        import traceback

        traceback.print_exc()
        flash("Error loading profile", "error")
        return redirect(url_for("dashboard.index"))


@dashboard_bp.route("/api/user-profile", methods=["GET"])
@login_required
def api_user_profile():
    """API endpoint to get user profile data with enhanced logging"""
    try:
        print(f"🔍 API USER PROFILE - Starting for user: {current_user.id}")

        # Get comprehensive user data
        profile_data = {
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "created_at": (
                    current_user.created_at.isoformat()
                    if current_user.created_at
                    else None
                ),
                "plan_type": current_user.plan_type,
                "last_login": getattr(current_user, "last_login_at", None),
            },
            "profile_settings": getattr(current_user, "profile_settings", {}) or {},
            "preferences": getattr(current_user, "preferences", {}) or {},
            "stats": {
                "total_snippets": Snippet.query.filter_by(
                    user_id=current_user.id, is_deleted=False
                ).count(),
                "total_collections": Collection.query.filter_by(
                    user_id=current_user.id
                ).count(),
                "account_age_days": (
                    (datetime.utcnow() - current_user.created_at).days
                    if current_user.created_at
                    else 0
                ),
            },
        }

        print(f"✅ API USER PROFILE - Data prepared successfully")
        return jsonify({"success": True, "data": profile_data})

    except Exception as e:
        print(f"❌ ERROR in API user profile: {str(e)}")
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/api/update-profile", methods=["POST"])
@login_required
def api_update_profile():
    """Update user profile via API with comprehensive logging"""
    try:
        print(f"🔍 API UPDATE PROFILE - Starting for user: {current_user.id}")

        data = request.get_json()
        print(f"🔍 UPDATE PROFILE - Received data: {data}")

        if not data:
            print("❌ UPDATE PROFILE - No data received")
            return jsonify({"success": False, "message": "No data provided"}), 400

        updated_fields = []

        # Update profile settings
        # Update profile settings with proper database handling
        current_profile = getattr(current_user, "profile_settings", {}) or {}
        print(f"🔍 BEFORE UPDATE - Current profile: {current_profile}")

        profile_fields = [
            "bio",
            "location",
            "website",
            "github",
            "twitter",
            "linkedin",
            "timezone",
            "language",
        ]

        # Update each field
        for field in profile_fields:
            if field in data:
                current_profile[field] = data[field]
                updated_fields.append(f"profile.{field}")
                print(f"🔍 Updated {field}: {data[field]}")

        # CRITICAL: Force SQLAlchemy to detect the change
        from sqlalchemy.orm.attributes import flag_modified

        current_user.profile_settings = current_profile
        flag_modified(current_user, "profile_settings")  # This is the key fix!
        db.session.add(current_user)  # Explicitly add to session
        print(f"🔍 AFTER UPDATE - New profile: {current_profile}")

        # Update email if provided and different
        if "email" in data and data["email"] != current_user.email:
            # Check if email is already taken
            existing_user = User.query.filter_by(email=data["email"]).first()
            if existing_user and existing_user.id != current_user.id:
                print(f"❌ Email already in use: {data['email']}")
                return (
                    jsonify({"success": False, "message": "Email already in use"}),
                    400,
                )

            current_user.email = data["email"]
            updated_fields.append("email")
            print(f"🔍 Updated email: {data['email']}")

        # Update theme preference
        if "theme_preference" in data:
            current_user.theme_preference = data["theme_preference"]
            updated_fields.append("theme_preference")
            print(f"🔍 Updated theme: {data['theme_preference']}")

        db.session.commit()
        print(f"✅ UPDATE PROFILE - Successfully updated fields: {updated_fields}")

        return jsonify(
            {
                "success": True,
                "message": "Profile updated successfully",
                "updated_fields": updated_fields,
            }
        )

    except Exception as e:
        print(f"❌ UPDATE PROFILE ERROR: {str(e)}")
        import traceback

        traceback.print_exc()
        db.session.rollback()
        return (
            jsonify(
                {"success": False, "message": f"Failed to update profile: {str(e)}"}
            ),
            500,
        )


# ADD THIS ROUTE in dashboard.py:
@dashboard_bp.route("/api/team-analytics/<team_id>")
@login_required
def get_team_analytics_dashboard(team_id):
    """Get team analytics for dashboard display"""
    try:
        # Initialize analytics service
        analytics_service = AnalyticsService(db.session)

        # Get comprehensive team analytics
        analytics = analytics_service.get_team_dashboard_analytics(team_id, days=30)

        return jsonify({"success": True, "analytics": analytics})

    except Exception as e:
        current_app.logger.error(f"Error loading team analytics: {str(e)}")
        return (
            jsonify({"success": False, "error": "Failed to load team analytics"}),
            500,
        )


@dashboard_bp.route("/api/upload-avatar", methods=["POST"])
@login_required
def upload_avatar():
    """Handle avatar upload with comprehensive logging and proper path handling"""
    print(f"🔍 AVATAR UPLOAD - ===== STARTING =====")
    print(f"🔍 AVATAR UPLOAD - User: {current_user.id}")
    print(f"🔍 AVATAR UPLOAD - App root path: {current_app.root_path}")
    print(f"🔍 AVATAR UPLOAD - Static folder: {current_app.static_folder}")

    try:
        # Check if file is in request
        if "avatar" not in request.files:
            print("❌ AVATAR UPLOAD - No file in request")
            return jsonify({"success": False, "message": "No file provided"}), 400

        file = request.files["avatar"]

        # Check if file is selected
        if file.filename == "":
            print("❌ AVATAR UPLOAD - No file selected")
            return jsonify({"success": False, "message": "No file selected"}), 400

        print(f"📁 AVATAR UPLOAD - File received: {file.filename}")

        # Read file content for validation
        file_content = file.read()
        file.seek(0)  # Reset file pointer

        print(f"📁 AVATAR UPLOAD - File size: {len(file_content)} bytes")

        # Validate file type
        allowed_extensions = {"png", "jpg", "jpeg", "gif", "webp"}
        file_ext = (
            file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
        )

        if file_ext not in allowed_extensions:
            print(f"❌ AVATAR UPLOAD - Invalid file type: {file_ext}")
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f'Invalid file type. Allowed: {", ".join(allowed_extensions)}',
                    }
                ),
                400,
            )

        # Check file size (5MB limit)
        if len(file_content) > 5 * 1024 * 1024:  # 5MB
            print(f"❌ AVATAR UPLOAD - File too large: {len(file_content)} bytes")
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "File too large. Maximum size is 5MB.",
                    }
                ),
                400,
            )

        print(f"✅ AVATAR UPLOAD - File validation passed")

        # Process image with PIL
        try:
            image = Image.open(io.BytesIO(file_content))
            print(f"📷 AVATAR UPLOAD - Original image size: {image.size}")

            # Convert to RGB if necessary
            if image.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                if image.mode == "P":
                    image = image.convert("RGBA")
                background.paste(
                    image, mask=image.split()[-1] if image.mode == "RGBA" else None
                )
                image = background

            # Resize to 300x300 (high quality for profile)
            image = image.resize((300, 300), Image.Resampling.LANCZOS)
            print(f"📷 AVATAR UPLOAD - Resized to: {image.size}")

            # Save as JPEG with high quality
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=90, optimize=True)
            processed_image_data = output.getvalue()

            print(
                f"📷 AVATAR UPLOAD - Processed image size: {len(processed_image_data)} bytes"
            )

        except Exception as e:
            print(f"❌ AVATAR UPLOAD - Image processing error: {str(e)}")
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Invalid image file or processing error",
                    }
                ),
                400,
            )

        # CRITICAL: Use the correct upload directory (static folder from Flask config)
        upload_dir = os.path.join(current_app.static_folder, "uploads", "avatars")

        # Also create backup location for compatibility
        backup_upload_dir = os.path.join(
            current_app.root_path, "static", "uploads", "avatars"
        )

        # Create both directories
        for directory in [upload_dir, backup_upload_dir]:
            os.makedirs(directory, exist_ok=True)
            print(f"📁 AVATAR UPLOAD - Created/verified directory: {directory}")

        print(f"📁 AVATAR UPLOAD - Primary upload directory: {upload_dir}")
        print(f"📁 AVATAR UPLOAD - Backup upload directory: {backup_upload_dir}")
        print(
            f"📁 AVATAR UPLOAD - Primary directory exists: {os.path.exists(upload_dir)}"
        )
        print(
            f"📁 AVATAR UPLOAD - Backup directory exists: {os.path.exists(backup_upload_dir)}"
        )

        # Generate unique filename
        unique_filename = f"{current_user.id}_{uuid.uuid4().hex[:8]}.jpg"

        # Save to primary location
        primary_file_path = os.path.join(upload_dir, unique_filename)
        backup_file_path = os.path.join(backup_upload_dir, unique_filename)

        # Save processed image to both locations
        for file_path, location_name in [
            (primary_file_path, "primary"),
            (backup_file_path, "backup"),
        ]:
            try:
                with open(file_path, "wb") as f:
                    f.write(processed_image_data)
                print(f"💾 AVATAR UPLOAD - File saved to {location_name}: {file_path}")
                print(
                    f"💾 AVATAR UPLOAD - {location_name.title()} file exists: {os.path.exists(file_path)}"
                )
            except Exception as e:
                print(f"❌ AVATAR UPLOAD - Failed to save to {location_name}: {str(e)}")

        # CRITICAL: Generate correct URL for the avatar
        avatar_url = f"/static/uploads/avatars/{unique_filename}"
        print(f"🔗 AVATAR UPLOAD - Avatar URL: {avatar_url}")

        # Update user's profile settings
        user = User.query.get(current_user.id)
        if not user.profile_settings:
            user.profile_settings = {}

        # Store old avatar URL for cleanup
        old_avatar_url = user.profile_settings.get("avatar_url")
        print(f"🔗 AVATAR UPLOAD - Old avatar URL: {old_avatar_url}")

        # Update avatar URL in profile settings
        user.profile_settings["avatar_url"] = avatar_url

        # CRITICAL: Also update direct avatar_url field if it exists
        if hasattr(user, "avatar_url"):
            user.avatar_url = avatar_url
            print(f"✅ AVATAR UPLOAD - Updated direct avatar_url field")

        # Mark as modified for SQLAlchemy
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(user, "profile_settings")

        # Commit to database
        try:
            db.session.commit()
            print(f"✅ AVATAR UPLOAD - Database updated successfully")

            # Verify the save worked
            fresh_user = User.query.get(current_user.id)
            print(
                f"✅ AVATAR UPLOAD - Verified avatar URL in DB: {fresh_user.profile_settings.get('avatar_url')}"
            )

        except Exception as commit_error:
            print(f"❌ AVATAR UPLOAD - Database commit error: {str(commit_error)}")
            db.session.rollback()
            # Clean up the uploaded files
            for file_path in [primary_file_path, backup_file_path]:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        print(
                            f"🗑️ AVATAR UPLOAD - Cleaned up failed upload: {file_path}"
                        )
                    except:
                        pass
            raise

        # Clean up old avatar files
        if old_avatar_url and old_avatar_url.startswith("/static/uploads/avatars/"):
            old_filename = old_avatar_url.split("/")[-1]
            old_file_paths = [
                os.path.join(upload_dir, old_filename),
                os.path.join(backup_upload_dir, old_filename),
            ]

            for old_file_path in old_file_paths:
                try:
                    if os.path.exists(old_file_path):
                        os.remove(old_file_path)
                        print(
                            f"🗑️ AVATAR UPLOAD - Cleaned up old avatar: {old_file_path}"
                        )
                except Exception as e:
                    print(
                        f"⚠️ AVATAR UPLOAD - Failed to cleanup old avatar {old_file_path}: {str(e)}"
                    )

        # Test if the file is accessible via the web
        test_paths = [
            os.path.join(
                current_app.static_folder, "uploads", "avatars", unique_filename
            ),
            os.path.join(
                current_app.root_path, "static", "uploads", "avatars", unique_filename
            ),
        ]

        for test_path in test_paths:
            print(f"🧪 AVATAR UPLOAD - Test file access: {test_path}")
            print(f"🧪 AVATAR UPLOAD - Test file exists: {os.path.exists(test_path)}")

        print(f"🎉 AVATAR UPLOAD - ===== COMPLETED SUCCESSFULLY =====")

        return jsonify(
            {
                "success": True,
                "message": "Avatar uploaded successfully!",
                "avatar_url": avatar_url,
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "avatar_url": avatar_url,
                },
                "debug": {
                    "primary_file_path": primary_file_path,
                    "backup_file_path": backup_file_path,
                    "primary_exists": os.path.exists(primary_file_path),
                    "backup_exists": os.path.exists(backup_file_path),
                    "upload_dir": upload_dir,
                    "backup_upload_dir": backup_upload_dir,
                    "unique_filename": unique_filename,
                    "static_folder": current_app.static_folder,
                },
            }
        )

    except Exception as e:
        print(f"❌ AVATAR UPLOAD - ===== CRITICAL ERROR =====")
        print(f"❌ AVATAR UPLOAD - Error: {str(e)}")
        import traceback

        traceback.print_exc()
        db.session.rollback()

        return jsonify({"success": False, "message": f"Upload failed: {str(e)}"}), 500


@dashboard_bp.route("/api/team-analytics/<team_id>")
@login_required
def get_team_analytics_api(team_id):
    """Get team analytics for dashboard display"""
    try:
        print(f"🏢 TEAM ANALYTICS API: Loading analytics for team {team_id}")

        # Verify user is team member
        from app.models.team_member import TeamMember

        membership = TeamMember.query.filter_by(
            team_id=team_id, user_id=current_user.id, is_active=True
        ).first()

        if not membership:
            print(
                f"❌ TEAM ANALYTICS API: User {current_user.id} not member of team {team_id}"
            )
            return jsonify({"success": False, "error": "Not a team member"}), 403

        # Initialize analytics service
        analytics_service = AnalyticsService(db.session)

        # Get comprehensive team analytics
        analytics = analytics_service.get_team_dashboard_analytics(team_id, days=30)

        print(
            f"✅ TEAM ANALYTICS API: Analytics loaded successfully for team {team_id}"
        )

        return jsonify(
            {
                "success": True,
                "analytics": analytics,
                "team_id": team_id,
                "user_role": membership.role.value,
            }
        )

    except Exception as e:
        print(f"❌ TEAM ANALYTICS API ERROR: {str(e)}")
        import traceback

        traceback.print_exc()
        return (
            jsonify({"success": False, "error": "Failed to load team analytics"}),
            500,
        )


@dashboard_bp.route("/settings")
@login_required
def settings():
    """User settings page with all preferences"""
    try:
        print(f"🔍 SETTINGS ROUTE - Starting for user: {current_user.id}")

        # Get all user settings safely
        user_settings = {
            "theme_preference": getattr(current_user, "theme_preference", "dark"),
            "notification_settings": getattr(current_user, "notification_settings", {})
            or {},
            "editor_preferences": getattr(current_user, "editor_preferences", {}) or {},
            "integration_settings": getattr(current_user, "integration_settings", {})
            or {},
            "security_settings": getattr(current_user, "security_settings", {}) or {},
            "dashboard_settings": {
                "sidebar_collapsed": getattr(current_user, "sidebar_collapsed", False),
                "show_analytics": getattr(current_user, "show_analytics", True),
                "snippets_per_page": getattr(current_user, "snippets_per_page", 20),
                "auto_save_enabled": getattr(current_user, "auto_save_enabled", True),
            },
        }

        # Get stats for sidebar
        stats = {
            "total_snippets": Snippet.query.filter_by(
                user_id=current_user.id, is_deleted=False
            ).count(),
            "total_collections": Collection.query.filter_by(
                user_id=current_user.id
            ).count(),
        }

        print(f"✅ SETTINGS ROUTE - Settings loaded successfully")

        return render_template(
            "dashboard/settings.html",
            user=current_user,
            settings=user_settings,
            stats=stats,
            page_title="Settings",
        )

    except Exception as e:
        print(f"❌ CRITICAL ERROR in settings route: {str(e)}")
        import traceback

        traceback.print_exc()
        flash(f"Error loading settings: {str(e)}", "error")
        return redirect(url_for("dashboard.index"))


@dashboard_bp.route("/api/update-settings", methods=["POST"])
@login_required
def update_settings():
    """Update user settings via API with enhanced logging"""
    try:
        print(f"🔍 UPDATE SETTINGS API - Starting for user: {current_user.id}")

        data = request.get_json()
        print(f"🔍 UPDATE SETTINGS - Received data: {data}")

        if not data:
            print("❌ UPDATE SETTINGS - No data received")
            return jsonify({"success": False, "message": "No data provided"}), 400

        updated_settings = []

        # Update theme preference
        if "theme" in data:
            current_user.theme_preference = data["theme"]
            updated_settings.append("theme")
            print(f"🔍 UPDATE SETTINGS - Theme updated to: {data['theme']}")

        # Update notification settings
        if "notifications" in data:
            current_notifications = (
                getattr(current_user, "notification_settings", {}) or {}
            )
            current_notifications.update(data["notifications"])
            current_user.notification_settings = current_notifications
            updated_settings.append("notifications")
            print(f"🔍 UPDATE SETTINGS - Notifications updated")

        # Update editor preferences
        if "editor" in data:
            current_editor = getattr(current_user, "editor_preferences", {}) or {}
            current_editor.update(data["editor"])
            current_user.editor_preferences = current_editor
            updated_settings.append("editor")
            print(f"🔍 UPDATE SETTINGS - Editor preferences updated")

        # Update dashboard settings
        if "dashboard" in data:
            dashboard_data = data["dashboard"]
            if "sidebar_collapsed" in dashboard_data:
                current_user.sidebar_collapsed = dashboard_data["sidebar_collapsed"]
            if "show_analytics" in dashboard_data:
                current_user.show_analytics = dashboard_data["show_analytics"]
            if "snippets_per_page" in dashboard_data:
                current_user.snippets_per_page = dashboard_data["snippets_per_page"]
            if "auto_save_enabled" in dashboard_data:
                current_user.auto_save_enabled = dashboard_data["auto_save_enabled"]
            updated_settings.append("dashboard")
            print(f"🔍 UPDATE SETTINGS - Dashboard settings updated")

        db.session.commit()

        print(f"✅ UPDATE SETTINGS - Successfully updated: {updated_settings}")

        return jsonify(
            {
                "success": True,
                "message": "Settings updated successfully",
                "updated": updated_settings,
            }
        )

    except Exception as e:
        print(f"❌ UPDATE SETTINGS ERROR: {str(e)}")
        import traceback

        traceback.print_exc()
        db.session.rollback()
        return (
            jsonify(
                {"success": False, "message": f"Failed to update settings: {str(e)}"}
            ),
            500,
        )


@dashboard_bp.route("/api/log-user-action", methods=["POST"])
@login_required
def log_user_action():
    """Log user actions for analytics and debugging"""
    try:
        data = request.get_json()
        action = data.get("action", "unknown")
        details = data.get("details", {})

        print(
            f"📊 USER ACTION LOG - User: {current_user.id}, Action: {action}, Details: {details}"
        )

        # You can store this in a separate analytics table if needed
        # For now, just log it for debugging

        return jsonify({"success": True})

    except Exception as e:
        print(f"❌ LOG USER ACTION ERROR: {str(e)}")
        return jsonify({"success": False}), 500


@dashboard_bp.route("/debug/profile-data")
@login_required
def debug_profile_data():
    """Debug route to check profile data"""
    try:
        print(f"🔍 DEBUG - Checking profile data for user: {current_user.id}")

        debug_data = {
            "user_id": current_user.id,
            "user_email": current_user.email,
            "user_created": (
                current_user.created_at.isoformat() if current_user.created_at else None
            ),
            "profile_settings": getattr(current_user, "profile_settings", {}),
            "snippets_count": Snippet.query.filter_by(
                user_id=current_user.id, is_deleted=False
            ).count(),
            "collections_count": Collection.query.filter_by(
                user_id=current_user.id
            ).count(),
        }

        print(f"✅ DEBUG - Profile data: {debug_data}")
        return jsonify(debug_data)

    except Exception as e:
        print(f"❌ DEBUG ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500


@dashboard_bp.route("/api/snippets/<snippet_id>/view", methods=["POST"])
@login_required
def track_snippet_view(snippet_id):
    """Track snippet view with enhanced logging"""
    try:
        print(f"🔍 TRACK SNIPPET VIEW - ID: {snippet_id}, User: {current_user.id}")

        snippet = Snippet.query.filter_by(
            id=snippet_id, user_id=current_user.id, is_deleted=False
        ).first()

        if not snippet:
            print(f"❌ Snippet not found: {snippet_id}")
            return jsonify({"error": "Snippet not found"}), 404

        print(f"🔍 Found snippet: {snippet.title}")

        # Track the view
        snippet.track_view(current_user.id)

        print(f"✅ View tracked successfully. New count: {snippet.view_count}")

        return jsonify(
            {
                "success": True,
                "view_count": snippet.view_count,
                "message": "View tracked successfully",
                "snippet_id": snippet_id,
            }
        )

    except Exception as e:
        print(f"❌ ERROR in track_snippet_view: {str(e)}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e), "success": False}), 500


@dashboard_bp.route("/api/collections/<collection_id>/view", methods=["POST"])
@login_required
def track_collection_view(collection_id):
    """Track collection view with enhanced logging"""
    try:
        print(
            f"🔍 TRACK COLLECTION VIEW - ID: {collection_id}, User: {current_user.id}"
        )

        collection = Collection.query.filter_by(
            id=collection_id, user_id=current_user.id
        ).first()

        if not collection:
            print(f"❌ Collection not found: {collection_id}")
            return jsonify({"error": "Collection not found"}), 404

        print(f"🔍 Found collection: {collection.name}")

        # Track the view
        collection.track_view(current_user.id)

        print(
            f"✅ Collection view tracked successfully. New count: {collection.view_count}"
        )

        return jsonify(
            {
                "success": True,
                "view_count": collection.view_count,
                "message": "Collection view tracked successfully",
                "collection_id": collection_id,
            }
        )

    except Exception as e:
        print(f"❌ ERROR in track_collection_view: {str(e)}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e), "success": False}), 500


def get_recent_activity(user_id, limit=10):
    """Get recent user activity"""
    try:
        activities = []

        # Recent snippets
        recent_snippets = (
            Snippet.query.filter_by(user_id=user_id)
            .order_by(desc(Snippet.updated_at))
            .limit(limit)
            .all()
        )

        for snippet in recent_snippets:
            activities.append(
                {
                    "type": "snippet_updated",
                    "title": snippet.title,
                    "timestamp": snippet.updated_at,
                    "id": snippet.id,
                }
            )

        # Recent collections
        recent_collections = (
            Collection.query.filter_by(user_id=user_id)
            .order_by(desc(Collection.updated_at))
            .limit(5)
            .all()
        )

        for collection in recent_collections:
            activities.append(
                {
                    "type": "collection_updated",
                    "title": collection.name,
                    "timestamp": collection.updated_at,
                    "id": collection.id,
                }
            )

        # Sort by timestamp and return limited results
        activities.sort(key=lambda x: x["timestamp"], reverse=True)
        return activities[:limit]

    except:
        return []


def get_language_distribution(user_id):
    """Get programming language distribution for charts"""
    try:
        results = (
            db.session.query(
                Snippet.language, func.count(Snippet.language).label("count")
            )
            .filter_by(user_id=user_id)
            .group_by(Snippet.language)
            .all()
        )

        return [{"language": r[0] or "Unknown", "count": r[1]} for r in results]
    except:
        return []


def get_most_used_collection(user_id):
    """Get the collection with most snippets"""
    try:
        result = (
            db.session.query(
                Collection.name, func.count(Snippet.id).label("snippet_count")
            )
            .join(Snippet, Collection.id == Snippet.collection_id)
            .filter(Collection.user_id == user_id)
            .group_by(Collection.id, Collection.name)
            .order_by(desc("snippet_count"))
            .first()
        )

        return result[0] if result else "No collections"
    except:
        return "No collections"
