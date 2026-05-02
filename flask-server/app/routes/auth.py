from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for,
    current_app,
    flash 
)
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_wtf import FlaskForm 
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Regexp
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import login_user, logout_user, login_required, current_user
import jwt
from werkzeug.security import generate_password_hash

from datetime import datetime, timedelta
import re
from app.models.user import User
from app import db
from flask import current_app
import logging

# Create logger
logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def validate_email(email):
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


def validate_password(password):
    # At least 8 chars, 1 uppercase, 1 lowercase, 1 number
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    return True, "Valid password"


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if current_user.is_authenticated:
            print("User already authenticated, redirecting to dashboard")
            return redirect(url_for("dashboard.index"))
        return render_template("auth/login.html")

    try:
        print("Processing login POST request")
        # Check if the request is JSON or form data
        if request.is_json:
            print("Processing JSON request")
            print(f"Request headers: {dict(request.headers)}")
            print(f"Request origin: {request.headers.get('Origin', 'No origin')}")
            data = request.get_json()
            email = data.get("email", "").strip().lower()
            password = data.get("password", "")
        else:
            print("Processing form data request")
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

        print(f"Login attempt for email: {email}")

        # Validation
        if not email or not password:
            print("Missing email or password")
            if request.is_json:
                return (
                    jsonify(
                        {"success": False, "message": "Email and password are required"}
                    ),
                    400,
                )
            flash("Email and password are required", "error")
            return render_template("auth/login.html")

        if not validate_email(email):
            print("Invalid email format")
            if request.is_json:
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Please enter a valid email address",
                        }
                    ),
                    400,
                )
            flash("Please enter a valid email address", "error")
            return render_template("auth/login.html")

        # Find user
        user = User.query.filter_by(email=email).first()

        if not user:
            print(f"User not found for email: {email}")
            if request.is_json:
                return (
                    jsonify({"success": False, "message": "Invalid email or password"}),
                    401,
                )
            flash("Invalid email or password", "error")
            return render_template("auth/login.html")

        print(f"User found: {user.id}")

        # Check password
        if not check_password_hash(user.password_hash, password):
            print("Password check failed")
            if request.is_json:
                return (
                    jsonify({"success": False, "message": "Invalid email or password"}),
                    401,
                )
            flash("Invalid email or password", "error")
            return render_template("auth/login.html")

        print("Password check passed")

        # Login user
        print("Logging in user")
        login_user(user, remember=True)
        print(f"User logged in: {current_user.is_authenticated}")

        # Record login for analytics
        try:
            if hasattr(user, "record_login"):
                user.record_login()
                db.session.commit()
                print("Login recorded")
        except Exception as e:
            print(f"Error recording login: {str(e)}")
            db.session.rollback()

        # Generate JWT token
        token = jwt.encode(
            {
                "user_id": str(user.id),
                "email": user.email,
                "exp": datetime.utcnow() + timedelta(days=30),
            },
            current_app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        print("JWT token generated")

        # If it's an API request (JSON), return JSON response
        if request.is_json:
            print("=== JWT TOKEN SENDING TO CLIENT ===")
            print(f"Token generated for user {user.email}: {token[:50]}...")
            print(f"Token length: {len(token)} characters")
            print("Sending JSON response with token to client")
            return jsonify(
                {
                    "success": True,
                    "message": "Login successful",
                    "token": token,
                    "user": {
                        "id": str(user.id),
                        "email": user.email,
                        "plan_type": user.plan_type,
                        "created_at": user.created_at.isoformat(),
                    },
                }
            )
        print("=== TOKEN SUCCESSFULLY SENT TO CLIENT ===")
        print(f"Response status: 200")
        print(f"Token included in response: {'token' in locals()}")    

        # For form submissions, redirect to dashboard
        print("Redirecting to dashboard")
        return redirect(url_for("dashboard.index"))

    except Exception as e:
        print(f"Login error: {str(e)}")
        import traceback

        traceback.print_exc()
        if request.is_json:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"An error occurred during login: {str(e)}",
                    }
                ),
                500,
            )
        flash(f"An error occurred during login: {str(e)}", "error")
        return render_template("auth/login.html")


@auth_bp.route("/verify", methods=["POST"])
def verify_token_route():
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"valid": False, "error": "No authorization header"}), 401

        # Extract token (assuming "Bearer <token>" format)
        try:
            token = auth_header.split(" ")[1]
        except IndexError:
            return (
                jsonify(
                    {"valid": False, "error": "Invalid authorization header format"}
                ),
                401,
            )

        # Verify token using your existing function
        payload = verify_token(token)
        if not payload:
            return jsonify({"valid": False, "error": "Invalid or expired token"}), 401

        # Get user from payload
        user_id = payload.get("user_id")
        user = User.query.get(user_id)

        if user:
            return jsonify(
                {
                    "valid": True,
                    "user_id": user_id,
                    "user": {
                        "id": str(user.id),
                        "email": user.email,
                        "plan_type": user.plan_type,
                    },
                }
            )
        else:
            return jsonify({"valid": False, "error": "User not found"}), 401

    except Exception as e:
        return jsonify({"valid": False, "error": str(e)}), 401


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    print("🔍 REGISTER - Route accessed")
    form = RegistrationForm()

    if form.validate_on_submit():
        print("🔍 REGISTER - Form validation passed")
        print(f"📊 REGISTER - Form data:")
        print(f"  📧 Email: {form.email.data}")
        print(f"  👤 Username: {form.username.data}")
        print(f"  🎭 Role: {form.role.data}")

        # Check if user already exists
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            print(f"❌ REGISTER - Email already exists: {form.email.data}")
            flash("Email already registered. Please use a different email.", "error")
            return render_template("auth/register.html", form=form)

        # Check if username already exists
        existing_username = User.query.filter_by(
            username=form.username.data.lower().strip()
        ).first()
        if existing_username:
            print(f"❌ REGISTER - Username already exists: {form.username.data}")
            flash(
                "Username already taken. Please choose a different username.", "error"
            )
            return render_template("auth/register.html", form=form)

        try:
            print("🔍 REGISTER - Creating new user...")

            # FIXED: Create new user with all required fields
            user = User(
                email=form.email.data,
                password=form.password.data,
                username=form.username.data,
                role=form.role.data,
                plan_type="free",
            )

            print(f"✅ REGISTER - User object created:")
            print(f"  📧 Email: {user.email}")
            print(f"  👤 Username: {user.username}")
            print(f"  🎭 Role: {user.profile_settings.get('role', 'Not set')}")
            print(f"  📋 Plan: {user.plan_type}")

            db.session.add(user)
            db.session.commit()

            print(f"✅ REGISTER - User saved to database with ID: {user.id}")

            # Verify the user was saved correctly
            saved_user = User.query.get(user.id)
            if saved_user:
                print(f"✅ REGISTER - Verification successful:")
                print(f"  👤 Saved username: {saved_user.username}")
                print(
                    f"  🎭 Saved role: {saved_user.profile_settings.get('role', 'Not found')}"
                )

            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("auth.login"))

        except Exception as e:
            db.session.rollback()
            print(f"❌ REGISTER - Database error: {str(e)}")
            import traceback

            traceback.print_exc()
            flash(f"Registration failed: {str(e)}", "error")
            return render_template("auth/register.html", form=form)

    # If form validation failed, print the errors
    if form.errors:
        print(f"❌ REGISTER - Form validation errors: {form.errors}")
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "error")

    return render_template("auth/register.html", form=form)


class RegistrationForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(
                min=3, max=20, message="Username must be between 3 and 20 characters"
            ),
            Regexp(
                "^[a-zA-Z0-9_]+$",
                message="Username can only contain letters, numbers, and underscores",
            ),
        ],
    )
    email = StringField("Email", validators=[DataRequired(), Email()])
    role = SelectField(
        "Role",
        choices=[
            ("developer", "Developer"),
            ("designer", "Designer"),
            ("manager", "Manager"),
            ("student", "Student"),
            ("freelancer", "Freelancer"),
            ("entrepreneur", "Entrepreneur"),
            ("other", "Other"),
        ],
        validators=[DataRequired()],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=8, message="Password must be at least 8 characters long"),
        ],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(),
            EqualTo("password", message="Passwords must match"),
        ],
    )
    accept_terms = BooleanField("Accept Terms", validators=[DataRequired()])
    submit = SubmitField("Create Account")


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """Handle user logout with comprehensive logging"""
    from flask_login import logout_user, current_user
    from flask import session, request, jsonify, redirect, current_app, make_response
    import traceback

    # Create a unique request ID for tracking
    import uuid

    request_id = str(uuid.uuid4())[:8]

    try:
        print(f"\n{'='*60}")
        print(f"🚀 LOGOUT REQUEST START - ID: {request_id}")
        print(f"{'='*60}")

        # Log current user info BEFORE logout
        if current_user.is_authenticated:
            user_email = getattr(current_user, "email", "unknown")
            user_id = getattr(current_user, "id", "unknown")
            print(f"👤 BEFORE LOGOUT - User: {user_email} (ID: {user_id})")
        else:
            user_email = "anonymous"
            user_id = "anonymous"
            print(f"👤 BEFORE LOGOUT - User: anonymous")

        # FORCE logout and session clearing
        print(f"\n🔄 PERFORMING LOGOUT...")
        logout_user()
        print(f"   ✅ logout_user() called")

        # Clear session data COMPLETELY
        session.clear()
        print(f"   ✅ session.clear() called")

        # Clear any custom session info
        if hasattr(current_app, "session_info"):
            current_app.session_info.clear()
            print(f"   ✅ current_app.session_info.clear() called")

        # VERIFY logout worked
        print(f"\n🔍 VERIFICATION AFTER LOGOUT:")
        print(f"   current_user.is_authenticated: {current_user.is_authenticated}")
        print(f"   current_user.is_anonymous: {current_user.is_anonymous}")
        print(f"   Session keys after clear: {list(session.keys())}")

        logger.info(f"[{request_id}] User {user_email} logged out successfully")

        # Determine response type
        is_ajax = (
            request.is_json
            or request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.method == "POST"
        )

        if is_ajax:
            response_data = {
                "success": True,
                "message": "Logged out successfully",
                "redirect": "/",
                "request_id": request_id,
                "force_reload": True,  # Add this flag
            }
            print(f"   📤 Returning JSON response: {response_data}")

            # Create response and clear cookies
            response = make_response(jsonify(response_data))
            response.headers["Content-Type"] = "application/json"

            # FORCE clear all authentication cookies
            response.set_cookie("session", "", expires=0, path="/")
            response.set_cookie("remember_token", "", expires=0, path="/")

            print(f"   📤 Cookies cleared in response")
            print(f"{'='*60}")
            print(f"🚀 LOGOUT REQUEST END - ID: {request_id} - SUCCESS")
            print(f"{'='*60}\n")
            return response
        else:
            print(f"   📤 Returning redirect to /")
            response = make_response(redirect("/"))

            # Clear cookies for redirect too
            response.set_cookie("session", "", expires=0, path="/")
            response.set_cookie("remember_token", "", expires=0, path="/")

            print(f"{'='*60}")
            print(f"🚀 LOGOUT REQUEST END - ID: {request_id} - REDIRECT")
            print(f"{'='*60}\n")
            return response

    except Exception as e:
        print(f"\n❌ LOGOUT ERROR in request {request_id}:")
        print(f"   Error: {str(e)}")
        traceback.print_exc()

        logger.error(f"[{request_id}] Logout error: {str(e)}", exc_info=True)

        if is_ajax:
            return jsonify({"success": False, "error": str(e)}), 500
        else:
            return redirect("/")


@auth_bp.route("/debug-user-create", methods=["GET"])
def debug_user_create():
    try:
        # Test user creation
        test_email = f"test_{datetime.utcnow().timestamp()}@example.com"
        test_user = User(email=test_email, password="TestPassword123")
        db.session.add(test_user)
        db.session.commit()
        return jsonify(
            {"success": True, "message": f"Test user created with email: {test_email}"}
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)})


@auth_bp.route("/check-username", methods=["POST"])
def check_username():
    """Check if username is available"""
    try:
        data = request.get_json()
        username = data.get("username", "").strip().lower()

        if not username:
            return jsonify({"available": False, "message": "Username is required"})

        if len(username) < 3:
            return jsonify(
                {
                    "available": False,
                    "message": "Username too short (minimum 3 characters)",
                }
            )

        if len(username) > 20:
            return jsonify(
                {
                    "available": False,
                    "message": "Username too long (maximum 20 characters)",
                }
            )

        # Check for valid characters
        if not re.match(r"^[a-zA-Z0-9_]+$", username):
            return jsonify(
                {
                    "available": False,
                    "message": "Username can only contain letters, numbers, and underscores",
                }
            )

        # Check if username exists
        existing_user = User.query.filter_by(username=username).first()

        if existing_user:
            return jsonify({"available": False, "message": "Username already taken"})
        else:
            return jsonify({"available": True, "message": "Username available"})

    except Exception as e:
        print(f"Error checking username: {str(e)}")
        return jsonify({"available": False, "message": "Error checking username"}), 500


@auth_bp.route("/profile")
@login_required
def profile():
    return jsonify(
        {
            "success": True,
            "user": {
                "id": current_user.id,
                "email": current_user.email,
                "plan_type": current_user.plan_type,
                "created_at": current_user.created_at.isoformat(),
            },
        }
    )


# JWT Token verification for API requests
def verify_token(token):
    try:
        payload = jwt.decode(
            token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


bp = auth_bp
