# flask-server/app/routes/main.py

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    jsonify,
    session,
)
from flask_login import current_user
import logging

main = Blueprint("main", __name__)
logger = logging.getLogger(__name__)


@main.route("/")
def index():
    """Serve landing page for unauthenticated users, redirect authenticated users to dashboard"""
    try:
        logger.info(f"Root route accessed from {request.remote_addr}")

        # Enhanced authentication debugging
        logger.info(f"current_user.is_authenticated: {current_user.is_authenticated}")
        logger.info(f"current_user.is_anonymous: {current_user.is_anonymous}")

        if hasattr(current_user, "email"):
            logger.info(f"current_user.email: {current_user.email}")

        # Check session
        logger.info(f"Session keys: {list(session.keys())}")
        logger.info(f"Session data: {dict(session)}")

        # If user is already authenticated, redirect to dashboard
        if current_user.is_authenticated:
            logger.info(
                f"Authenticated user {getattr(current_user, 'email', 'unknown')} redirected to dashboard"
            )
            return redirect("/dashboard")

        # Serve landing page for unauthenticated users
        logger.info("Serving landing page to unauthenticated user")
        return render_template("public/landing.html")

    except Exception as e:
        logger.error(f"Error in root route: {str(e)}", exc_info=True)
        # Fallback landing page
        return (
            """
        <!DOCTYPE html>
        <html>
        <head><title>CodeVault - Code Snippet Manager</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>Welcome to CodeVault</h1>
            <p>The Ultimate Code Snippet Manager</p>
            <a href="/auth/login" style="padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px;">Login</a>
            <a href="/auth/register" style="padding: 10px 20px; background: #28a745; color: white; text-decoration: none; border-radius: 5px; margin-left: 10px;">Register</a>
        </body>
        </html>
        """,
            200,
        )


@main.route("/test-landing")
def test_landing():
    """Test landing page without authentication check"""
    try:
        logger.info("Test landing page accessed")
        return render_template("public/landing.html")
    except Exception as e:
        logger.error(f"Error serving test landing page: {str(e)}")
        return (
            f"<h1>Test Landing Page</h1><p>Template error: {str(e)}</p><a href='/auth/login'>Login</a>",
            200,
        )


@main.route("/debug/auth-status")
def debug_auth_status():
    """Debug route to check authentication status"""
    try:
        auth_info = {
            "is_authenticated": current_user.is_authenticated,
            "is_anonymous": current_user.is_anonymous,
            "user_id": getattr(current_user, "id", None),
            "user_email": getattr(current_user, "email", None),
        }
        logger.info(f"Auth debug: {auth_info}")
        return jsonify(auth_info)
    except Exception as e:
        logger.error(f"Auth debug error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@main.route("/landing")
def landing():
    """Alternative landing page route"""
    try:
        return render_template("public/landing.html")
    except Exception as e:
        logger.error(f"Error serving landing page: {str(e)}")
        return redirect(url_for("main.index"))
