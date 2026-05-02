from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
import requests
import json
import base64
import uuid

from ..models.user import User
from ..models.snippet import Snippet
from ..models.collection import Collection
from ..services.github_service import GitHubService
from ..services.webhook_service import WebhookService
from ..utils.validators import validate_integration_data
from .. import db

integrations_bp = Blueprint("integrations", __name__, url_prefix="/api/v1/integrations")


@integrations_bp.route("/", methods=["GET"])
@jwt_required()
def get_user_integrations():
    """Get all user integrations with status and analytics"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        # Get integration status and data
        integrations = {
            "github": {
                "connected": bool(user.github_token),
                "username": user.github_username,
                "avatar": user.github_avatar,
                "connected_at": (
                    user.github_connected_at.isoformat()
                    if user.github_connected_at
                    else None
                ),
                "last_sync": (
                    user.github_last_sync.isoformat() if user.github_last_sync else None
                ),
                "repositories": user.get_github_repos_count(),
                "gists": user.get_github_gists_count(),
                "status": "active" if user.is_github_token_valid() else "expired",
            },
            "vscode": {
                "connected": bool(user.vscode_settings),
                "sync_enabled": (
                    user.vscode_settings.get("sync_enabled", False)
                    if user.vscode_settings
                    else False
                ),
                "last_sync": (
                    user.vscode_last_sync.isoformat() if user.vscode_last_sync else None
                ),
                "snippets_synced": user.get_vscode_snippets_count(),
                "auto_sync": (
                    user.vscode_settings.get("auto_sync", False)
                    if user.vscode_settings
                    else False
                ),
            },
            "slack": {
                "connected": bool(user.slack_token),
                "team_name": user.slack_team_name,
                "username": user.slack_username,
                "connected_at": (
                    user.slack_connected_at.isoformat()
                    if user.slack_connected_at
                    else None
                ),
                "webhooks_active": user.get_active_slack_webhooks_count(),
                "channels": user.get_slack_channels_count(),
            },
            "webhooks": {
                "total_webhooks": user.get_webhooks_count(),
                "active_webhooks": user.get_active_webhooks_count(),
                "last_triggered": user.get_last_webhook_trigger(),
                "monthly_calls": user.get_monthly_webhook_calls(),
            },
        }

        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "integrations": integrations,
                        "usage_stats": {
                            "total_syncs": user.get_total_sync_count(),
                            "last_30_days": user.get_sync_count_30d(),
                            "most_used": user.get_most_used_integration(),
                        },
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"Error fetching integrations: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to fetch integrations",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            500,
        )


@integrations_bp.route("/github/connect", methods=["POST"])
@jwt_required()
def connect_github():
    """Connect GitHub account with OAuth flow"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        if not data.get("code"):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Authorization code required",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                400,
            )

        # Exchange code for access token
        github_service = GitHubService()
        token_response = github_service.exchange_code_for_token(data["code"])

        if not token_response["success"]:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": token_response["error"],
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                400,
            )

        access_token = token_response["access_token"]

        # Get user info from GitHub
        user_info = github_service.get_user_info(access_token)
        if not user_info["success"]:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Failed to fetch GitHub user info",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                400,
            )

        # Update user with GitHub info
        user = User.query.get(user_id)
        user.github_token = access_token
        user.github_username = user_info["data"]["login"]
        user.github_avatar = user_info["data"]["avatar_url"]
        user.github_connected_at = datetime.utcnow()

        db.session.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "username": user_info["data"]["login"],
                        "avatar": user_info["data"]["avatar_url"],
                        "repositories": user_info["data"]["public_repos"],
                        "connected_at": user.github_connected_at.isoformat(),
                    },
                    "message": "GitHub connected successfully",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error connecting GitHub: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to connect GitHub",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            500,
        )


@integrations_bp.route("/github/repositories", methods=["GET"])
@jwt_required()
def get_github_repositories():
    """Get user's GitHub repositories for snippet export"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if not user.github_token:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "GitHub not connected",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                400,
            )

        github_service = GitHubService()
        repos = github_service.get_user_repositories(user.github_token)

        if not repos["success"]:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": repos["error"],
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                400,
            )

        # Filter and format repositories
        formatted_repos = []
        for repo in repos["data"]:
            formatted_repos.append(
                {
                    "id": repo["id"],
                    "name": repo["name"],
                    "full_name": repo["full_name"],
                    "description": repo["description"],
                    "private": repo["private"],
                    "language": repo["language"],
                    "stars": repo["stargazers_count"],
                    "forks": repo["forks_count"],
                    "updated_at": repo["updated_at"],
                    "permissions": repo["permissions"],
                }
            )

        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "repositories": formatted_repos,
                        "total_count": len(formatted_repos),
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"Error fetching GitHub repos: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to fetch repositories",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            500,
        )


@integrations_bp.route("/github/export", methods=["POST"])
@jwt_required()
def export_to_github():
    """Export snippets to GitHub repository or gist"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        user = User.query.get(user_id)
        if not user.github_token:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "GitHub not connected",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                400,
            )

        export_type = data.get("type", "gist")  # 'gist' or 'repository'
        snippet_ids = data.get("snippet_ids", [])

        if not snippet_ids:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "No snippets selected for export",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                400,
            )

        # Get snippets
        snippets = Snippet.query.filter(
            Snippet.id.in_(snippet_ids), Snippet.user_id == user_id
        ).all()

        github_service = GitHubService()

        if export_type == "gist":
            result = github_service.create_gist(
                user.github_token,
                snippets,
                data.get("description", "Code snippets from Snippet Manager"),
                data.get("public", False),
            )
        else:
            result = github_service.create_repository_files(
                user.github_token,
                data["repository"],
                snippets,
                data.get("branch", "main"),
                data.get("path", "snippets/"),
            )

        if result["success"]:
            # Update snippets with GitHub info
            for snippet in snippets:
                snippet.github_url = result["data"]["url"]
                snippet.exported_at = datetime.utcnow()
                snippet.export_count += 1

            db.session.commit()

            return (
                jsonify(
                    {
                        "success": True,
                        "data": result["data"],
                        "message": f"Successfully exported {len(snippets)} snippets to GitHub",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                200,
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": result["error"],
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                400,
            )

    except Exception as e:
        current_app.logger.error(f"Error exporting to GitHub: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to export to GitHub",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            500,
        )


@integrations_bp.route("/vscode/sync", methods=["POST"])
@jwt_required()
def sync_vscode_snippets():
    """Sync snippets with VS Code"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        user = User.query.get(user_id)
        sync_direction = data.get("direction", "both")  # 'upload', 'download', 'both'

        results = {"uploaded": 0, "downloaded": 0, "updated": 0, "errors": []}

        if sync_direction in ["upload", "both"]:
            # Upload snippets to VS Code format
            snippets = Snippet.query.filter_by(user_id=user_id).all()

            vscode_snippets = {}
            for snippet in snippets:
                # Convert to VS Code snippet format
                vscode_key = f"{snippet.language}_{snippet.id[:8]}"
                vscode_snippets[vscode_key] = {
                    "prefix": snippet.title.lower().replace(" ", "_"),
                    "body": snippet.code.split("\n"),
                    "description": snippet.description or snippet.title,
                    "scope": snippet.language,
                }

            # Save to user's VS Code settings
            if not user.vscode_settings:
                user.vscode_settings = {}

            user.vscode_settings["snippets"] = vscode_snippets
            user.vscode_settings["last_upload"] = datetime.utcnow().isoformat()
            results["uploaded"] = len(snippets)

        if sync_direction in ["download", "both"]:
            # Download from VS Code format (if user provides snippets)
            vscode_data = data.get("vscode_snippets", {})

            for key, vscode_snippet in vscode_data.items():
                # Check if snippet already exists
                existing = Snippet.query.filter_by(
                    user_id=user_id, title=vscode_snippet.get("description", key)
                ).first()

                if existing:
                    # Update existing
                    existing.code = "\n".join(vscode_snippet["body"])
                    existing.updated_at = datetime.utcnow()
                    results["updated"] += 1
                else:
                    # Create new snippet
                    new_snippet = Snippet(
                        id=str(uuid.uuid4()),
                        title=vscode_snippet.get("description", key),
                        code="\n".join(vscode_snippet["body"]),
                        language=vscode_snippet.get("scope", "text"),
                        user_id=user_id,
                        source="vscode_sync",
                    )
                    db.session.add(new_snippet)
                    results["downloaded"] += 1

        # Update sync timestamp
        user.vscode_last_sync = datetime.utcnow()
        db.session.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "data": results,
                    "message": "VS Code sync completed successfully",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error syncing VS Code: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to sync with VS Code",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            500,
        )


@integrations_bp.route("/slack/connect", methods=["POST"])
@jwt_required()
def connect_slack():
    """Connect Slack workspace"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        if not data.get("code"):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Authorization code required",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                400,
            )

        # Exchange code for access token
        slack_oauth_url = "https://slack.com/api/oauth.v2.access"
        oauth_data = {
            "client_id": current_app.config["SLACK_CLIENT_ID"],
            "client_secret": current_app.config["SLACK_CLIENT_SECRET"],
            "code": data["code"],
            "redirect_uri": data.get("redirect_uri"),
        }

        response = requests.post(slack_oauth_url, data=oauth_data)
        slack_data = response.json()

        if not slack_data.get("ok"):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": slack_data.get("error", "Slack authorization failed"),
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                400,
            )

        # Update user with Slack info
        user = User.query.get(user_id)
        user.slack_token = slack_data["access_token"]
        user.slack_team_id = slack_data["team"]["id"]
        user.slack_team_name = slack_data["team"]["name"]
        user.slack_user_id = slack_data["authed_user"]["id"]
        user.slack_connected_at = datetime.utcnow()

        db.session.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "team_name": slack_data["team"]["name"],
                        "user_id": slack_data["authed_user"]["id"],
                        "scopes": slack_data["scope"].split(","),
                        "connected_at": user.slack_connected_at.isoformat(),
                    },
                    "message": "Slack connected successfully",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error connecting Slack: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to connect Slack",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            500,
        )


@integrations_bp.route("/slack/channels", methods=["GET"])
@jwt_required()
def get_slack_channels():
    """Get Slack channels for snippet sharing"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if not user.slack_token:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Slack not connected",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                400,
            )

        # Get channels from Slack API
        headers = {"Authorization": f"Bearer {user.slack_token}"}
        response = requests.get(
            "https://slack.com/api/conversations.list",
            headers=headers,
            params={"types": "public_channel,private_channel"},
        )

        slack_data = response.json()

        if not slack_data.get("ok"):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Failed to fetch Slack channels",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                400,
            )

        channels = []
        for channel in slack_data["channels"]:
            channels.append(
                {
                    "id": channel["id"],
                    "name": channel["name"],
                    "is_private": channel["is_private"],
                    "is_member": channel["is_member"],
                    "purpose": channel.get("purpose", {}).get("value", ""),
                    "member_count": channel.get("num_members", 0),
                }
            )

        return (
            jsonify(
                {
                    "success": True,
                    "data": {"channels": channels, "total_count": len(channels)},
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"Error fetching Slack channels: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to fetch Slack channels",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            500,
        )


@integrations_bp.route("/slack/share", methods=["POST"])
@jwt_required()
def share_to_slack():
    """Share snippet to Slack channel"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        user = User.query.get(user_id)
        if not user.slack_token:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Slack not connected",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                400,
            )

        snippet_id = data.get("snippet_id")
        channel_id = data.get("channel_id")
        message = data.get("message", "")

        snippet = Snippet.query.filter_by(id=snippet_id, user_id=user_id).first()
        if not snippet:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Snippet not found",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                404,
            )

        # Format snippet for Slack
        slack_message = {
            "channel": channel_id,
            "text": message or f"Shared code snippet: {snippet.title}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{snippet.title}*\n{snippet.description or 'No description'}",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"```{snippet.language}\n{snippet.code}\n```",
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Shared by {user.name} via Snippet Manager",
                        }
                    ],
                },
            ],
        }

        # Send to Slack
        headers = {
            "Authorization": f"Bearer {user.slack_token}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers=headers,
            json=slack_message,
        )

        slack_data = response.json()

        if slack_data.get("ok"):
            # Update snippet share count
            snippet.share_count += 1
            snippet.last_shared_at = datetime.utcnow()
            db.session.commit()

            return (
                jsonify(
                    {
                        "success": True,
                        "data": {
                            "message_ts": slack_data["ts"],
                            "channel": slack_data["channel"],
                            "permalink": slack_data.get("permalink", ""),
                        },
                        "message": "Snippet shared to Slack successfully",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                200,
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": slack_data.get("error", "Failed to share to Slack"),
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                400,
            )

    except Exception as e:
        current_app.logger.error(f"Error sharing to Slack: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to share to Slack",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            500,
        )


@integrations_bp.route("/webhooks", methods=["GET"])
@jwt_required()
def get_webhooks():
    """Get user's webhooks with analytics"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        webhooks = user.get_webhooks_with_stats()

        return (
            jsonify(
                {
                    "success": True,
                    "data": {
                        "webhooks": webhooks,
                        "total_count": len(webhooks),
                        "active_count": sum(
                            1 for w in webhooks if w["status"] == "active"
                        ),
                        "monthly_calls": sum(w["monthly_calls"] for w in webhooks),
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )

    except Exception as e:
        current_app.logger.error(f"Error fetching webhooks: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to fetch webhooks",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            500,
        )


@integrations_bp.route("/webhooks", methods=["POST"])
@jwt_required()
def create_webhook():
    """Create new webhook for snippet events"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        validation_result = validate_integration_data(data, "webhook")
        if not validation_result["valid"]:
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

        # Create webhook
        webhook_service = WebhookService()
        webhook = webhook_service.create_webhook(
            user_id=user_id,
            url=data["url"],
            events=data["events"],
            name=data.get("name", "Unnamed Webhook"),
            secret=data.get("secret", ""),
            active=data.get("active", True),
        )

        if webhook["success"]:
            return (
                jsonify(
                    {
                        "success": True,
                        "data": webhook["data"],
                        "message": "Webhook created successfully",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                201,
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": webhook["error"],
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                400,
            )

    except Exception as e:
        current_app.logger.error(f"Error creating webhook: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to create webhook",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            500,
        )


@integrations_bp.route("/webhooks/<webhook_id>/test", methods=["POST"])
@jwt_required()
def test_webhook(webhook_id):
    """Test webhook with sample payload"""
    try:
        user_id = get_jwt_identity()

        webhook_service = WebhookService()
        result = webhook_service.test_webhook(webhook_id, user_id)

        if result["success"]:
            return (
                jsonify(
                    {
                        "success": True,
                        "data": result["data"],
                        "message": "Webhook test completed",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                200,
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": result["error"],
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                400,
            )

    except Exception as e:
        current_app.logger.error(f"Error testing webhook: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Failed to test webhook",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            500,
        )


@integrations_bp.route("/disconnect/<integration_type>", methods=["POST"])
@jwt_required()
def disconnect_integration(integration_type):
    """Disconnect an integration"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if integration_type == "github":
            user.github_token = None
            user.github_username = None
            user.github_avatar = None
            user.github_connected_at = None
        elif integration_type == "slack":
            user.slack_token = None
            user.slack_team_id = None
            user.slack_team_name = None
            user.slack_user_id = None
            user.slack_connected_at = None
        elif integration_type == "vscode":
            user.vscode_settings = None
            user.vscode_last_sync = None
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Invalid integration type",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
                400,
            )

        db.session.commit()

        return (
            jsonify(
                {
                    "success": True,
                    "message": f"{integration_type.title()} disconnected successfully",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            200,
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error disconnecting {integration_type}: {str(e)}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Failed to disconnect {integration_type}",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            500,
        )
