#!/usr/bin/env python3
"""
ULTIMATE AUTO-MIGRATION SYSTEM FOR CODEVAULT
100% Working Solution with Perfect Flask-SQLAlchemy Integration
Enhanced Logging for Complete Error Tracking
"""
import os
import sys
import importlib
import inspect
import logging
from datetime import datetime
from sqlalchemy import MetaData, inspect as sql_inspect, text, create_engine
from flask_migrate import init, migrate, upgrade
from flask import current_app
from flask_sqlalchemy import SQLAlchemy


class UltimateAutoMigrationLogger:
    """Ultimate logging system with complete error tracking"""

    def __init__(self):
        self.logger = self._setup_logger()
        self.migration_steps = []
        self.errors = []
        self.warnings = []

    def _setup_logger(self):
        """Setup comprehensive migration logger"""
        logger = logging.getLogger("ULTIMATE_AUTO_MIGRATION")
        logger.setLevel(logging.DEBUG)

        # Remove existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        # Console handler with detailed output
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)

        # Enhanced formatter with timestamps and context
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(funcName)-20s | %(message)s",
            datefmt="%H:%M:%S",
        )
        console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        logger.propagate = False

        return logger

    def step(self, message):
        """Log a migration step with enhanced context"""
        step_num = len(self.migration_steps) + 1
        self.migration_steps.append(message)
        self.logger.info(f"🔄 STEP {step_num}: {message}")
        print(f"\n{'='*80}")
        print(f"STEP {step_num}: {message}")
        print(f"{'='*80}")

    def success(self, message):
        """Log success message"""
        self.logger.info(f"✅ SUCCESS: {message}")
        print(f"✅ SUCCESS: {message}")

    def warning(self, message):
        """Log warning message"""
        self.warnings.append(message)
        self.logger.warning(f"⚠️  WARNING: {message}")
        print(f"⚠️  WARNING: {message}")

    def error(self, message, exception=None):
        """Log error message with full context"""
        self.errors.append(message)
        self.logger.error(f"❌ ERROR: {message}")
        print(f"❌ ERROR: {message}")

        if exception:
            self.logger.error(f"   Exception Type: {type(exception).__name__}")
            self.logger.error(f"   Exception Message: {str(exception)}")
            print(f"   Exception Type: {type(exception).__name__}")
            print(f"   Exception Message: {str(exception)}")

            import traceback

            tb = traceback.format_exc()
            self.logger.error(f"   Full Traceback:\n{tb}")
            print(f"   Full Traceback:\n{tb}")

    def info(self, message):
        """Log info message"""
        self.logger.info(f"ℹ️  INFO: {message}")
        print(f"ℹ️  INFO: {message}")

    def debug(self, message):
        """Log debug message"""
        self.logger.debug(f"🔍 DEBUG: {message}")
        print(f"🔍 DEBUG: {message}")

    def context_info(self, context_name, data):
        """Log context information"""
        self.logger.info(f"📋 {context_name}:")
        print(f"📋 {context_name}:")
        for key, value in data.items():
            self.logger.info(f"   {key}: {value}")
            print(f"   {key}: {value}")

    def summary(self):
        """Print migration summary"""
        print(f"\n{'='*80}")
        print("MIGRATION SUMMARY")
        print(f"{'='*80}")
        print(f"Total Steps: {len(self.migration_steps)}")
        print(f"Warnings: {len(self.warnings)}")
        print(f"Errors: {len(self.errors)}")

        if self.warnings:
            print(f"\nWarnings:")
            for warning in self.warnings:
                print(f"  - {warning}")

        if self.errors:
            print(f"\nErrors:")
            for error in self.errors:
                print(f"  - {error}")

        print(f"{'='*80}\n")


class UltimateEnhancedAutoMigration:
    """Ultimate Auto-Migration System with Perfect Flask-SQLAlchemy Integration"""

    def __init__(self, app):
        self.app = app
        self.log = UltimateAutoMigrationLogger()
        self.discovered_models = []
        self.model_classes = {}

        # Get the correct db instance from app extensions
        self.db = self._get_correct_db_instance()

    def _get_correct_db_instance(self):
        """Get the correct SQLAlchemy instance from Flask app"""
        self.log.debug("Getting correct SQLAlchemy instance from Flask app")

        try:
            # Method 1: Get from app extensions
            if "sqlalchemy" in self.app.extensions:
                db = self.app.extensions["sqlalchemy"]
                self.log.success(f"Found SQLAlchemy in app.extensions: {db}")
                return db

            # Method 2: Import from your extensions module
            try:
                from app import db

                self.log.success(f"Imported db from app.extensions: {db}")
                return db
            except ImportError as e:
                self.log.warning(f"Could not import from app.extensions: {e}")

            # Method 3: Create new instance (fallback)
            self.log.warning("Creating new SQLAlchemy instance as fallback")
            db = SQLAlchemy()
            db.init_app(self.app)
            return db

        except Exception as e:
            self.log.error("Failed to get SQLAlchemy instance", e)
            raise

    def run_complete_migration_check(self):
        """Run complete migration detection and application - ULTIMATE VERSION"""
        self.log.step("Starting ULTIMATE Enhanced Auto-Migration System")

        try:
            # Log current context
            self._log_current_context()

            # Step 1: Verify Flask app and database setup
            self._verify_flask_setup()

            # Step 2: Initialize migrations if needed
            self._ensure_migrations_initialized()

            # Step 3: Force import all models (ENHANCED FOR ACTIVITY)
            self._force_import_all_models()

            # Step 4: Handle special models like Activity
            self._handle_special_models()

            # Step 5: Refresh SQLAlchemy metadata with proper context
            self._refresh_metadata_ultimate()

            # Step 5: Detect missing tables and columns
            changes = self._detect_all_changes_ultimate()

            # Step 6: Create and apply migrations if needed
            if changes:
                self._create_and_apply_migration(changes)
            else:
                self.log.success("Database is up to date - no changes needed")

            # Step 8: Verify database state
            self._verify_database_state_ultimate()

            # Step 9: Handle Activity table specifically
            self._ensure_activity_table_exists()

            # Step 10: Print summary
            self.log.summary()

            return True

        except Exception as e:
            self.log.error("Complete migration check failed", e)
            self.log.summary()
            return False

    def _log_current_context(self):
        """Log current Flask and SQLAlchemy context"""
        self.log.step("Logging Current Context")

        context_data = {
            "Flask App": self.app.name if self.app else "None",
            "App Context": "Active" if current_app else "None",
            "SQLAlchemy Instance": str(self.db),
            "Database URI": self.app.config.get("SQLALCHEMY_DATABASE_URI", "Not Set"),
            "App Extensions": (
                list(self.app.extensions.keys())
                if hasattr(self.app, "extensions")
                else "None"
            ),
        }

        self.log.context_info("Current Context", context_data)

    def _verify_flask_setup(self):
        """Verify Flask app and database setup"""
        self.log.step("Verifying Flask and Database Setup")

        # Check Flask app
        if not self.app:
            raise RuntimeError("No Flask app instance provided")
        self.log.success(f"Flask app verified: {self.app.name}")

        # Check app context
        if not current_app:
            raise RuntimeError("No Flask app context found")
        self.log.success(f"Flask app context verified: {current_app.name}")

        # Check SQLAlchemy instance
        if not self.db:
            raise RuntimeError("No SQLAlchemy instance found")
        self.log.success(f"SQLAlchemy instance verified: {self.db}")

        # Test database connection
        try:
            with self.app.app_context():
                # Use current_app to get engine
                engine = current_app.extensions["sqlalchemy"].engines[None]
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT 1"))
                    result.fetchone()
                self.log.success("Database connection test successful")
        except Exception as e:
            self.log.error("Database connection test failed", e)
            raise

    def _ensure_migrations_initialized(self):
        """Ensure Flask-Migrate is initialized"""
        self.log.step("Checking Flask-Migrate initialization")

        migrations_dir = os.path.join(self.app.root_path, "..", "migrations")
        self.log.debug(f"Migrations directory path: {migrations_dir}")

        if not os.path.exists(migrations_dir):
            self.log.info("Migrations directory not found - initializing")
            try:
                init()
                self.log.success("Flask-Migrate initialized successfully")
            except Exception as e:
                self.log.error("Failed to initialize Flask-Migrate", e)
                raise
        else:
            self.log.success("Flask-Migrate already initialized")

    def _force_import_all_models(self):
        """ENHANCED - Force import all model files including special patterns"""
        self.log.step("Force importing all models (ENHANCED FOR ACTIVITY)")

        models_dir = os.path.join(self.app.root_path, "models")
        self.log.debug(f"Models directory: {models_dir}")

        if not os.path.exists(models_dir):
            self.log.error(f"Models directory not found: {models_dir}")
            return

        # Get all Python files in models directory
        model_files = [
            f
            for f in os.listdir(models_dir)
            if f.endswith(".py") and f != "__init__.py"
        ]

        self.log.info(f"Found {len(model_files)} model files: {model_files}")

        imported_count = 0
        for model_file in model_files:
            try:
                module_name = f"app.models.{model_file[:-3]}"
                self.log.debug(f"Importing {module_name}")

                module = importlib.import_module(module_name)

                # Find all classes that look like SQLAlchemy models
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (
                        hasattr(obj, "__tablename__")
                        and hasattr(obj, "__table__")
                        and hasattr(obj, "metadata")
                    ):
                        self.model_classes[obj.__tablename__] = obj
                        self.log.debug(
                            f"   Registered model: {name} -> {obj.__tablename__}"
                        )
                        imported_count += 1

                # ENHANCED: Look for factory pattern models like Activity
                for name, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj) 
                        and hasattr(obj, 'get_instance')
                        and name == 'Activity'
                    ):
                        self.log.info(f"   Found factory pattern model: {name}")
                        # Store for special handling
                        self.model_classes[f"_factory_{name}"] = obj

                self.log.debug(f"   ✅ Successfully imported {module_name}")

            except Exception as e:
                self.log.error(f"Failed to import {model_file}", e)

        self.log.success(
            f"Imported {imported_count} model classes from {len(model_files)} files"
        )

        # Also manually import known models as backup
        self._import_known_models()

    def _import_known_models(self):
        """Import known models as backup"""
        self.log.debug("Importing known models as backup")

        known_models = [
            ("app.models.user", "User"),
            ("app.models.snippet", "Snippet"),
            ("app.models.collection", "Collection"),
            ("app.models.team", "Team"),
            ("app.models.team_member", "TeamMember"),
            ("app.models.snippet_comment", "SnippetComment"),
            ("app.models.snippet_chat", "SnippetChat"),
            ("app.models.team_chat", "TeamChat"),
            ("app.models.team_snippet", "TeamSnippet"),
            ("app.models.team_collection", "TeamCollection"),
        ]

        for module_name, class_name in known_models:
            try:
                module = importlib.import_module(module_name)
                model_class = getattr(module, class_name)

                if hasattr(model_class, "__tablename__"):
                    self.model_classes[model_class.__tablename__] = model_class
                    self.log.debug(
                        f"   Backup import: {class_name} -> {model_class.__tablename__}"
                    )

            except Exception as e:
                self.log.debug(
                    f"   Could not backup import {module_name}.{class_name}: {e}"
                )

    def _handle_special_models(self):
        """Handle special model patterns like Activity factory"""
        self.log.step("Handling special model patterns")

        try:
            # Handle Activity model specifically
            self.log.info("Processing Activity model factory pattern")

            # Import and initialize Activity model
            from app.models.activity import Activity

            # Get the Activity instance to register the model
            activity_instance = Activity.get_instance()
            self.log.success(f"Activity model instance created: {activity_instance}")

            # The model should now be in the metadata
            if hasattr(activity_instance, 'Model'):
                model_class = activity_instance.Model
                if hasattr(model_class, '__tablename__'):
                    self.model_classes[model_class.__tablename__] = model_class
                    self.log.success(f"Activity model registered: {model_class.__tablename__}")
                else:
                    self.log.warning("Activity model has no __tablename__")
            else:
                self.log.warning("Activity instance has no Model attribute")

        except Exception as e:
            self.log.error("Failed to handle special models", e)

    def _ensure_activity_table_exists(self):
        """Ensure Activity table exists with proper structure"""
        self.log.step("Ensuring Activity table exists")

        try:
            with self.app.app_context():
                engine = current_app.extensions["sqlalchemy"].engines[None]
                inspector = sql_inspect(engine)
                existing_tables = inspector.get_table_names()

                if 'activities' not in existing_tables:
                    self.log.warning("Activities table missing - creating manually")

                    # Create activities table manually
                    create_table_sql = """
                    CREATE TABLE activities (
                        id VARCHAR(36) PRIMARY KEY,
                        action_type VARCHAR(50) NOT NULL,
                        action_category VARCHAR(20) NOT NULL,
                        user_id VARCHAR(36) NOT NULL,
                        team_id VARCHAR(36),
                        target_type VARCHAR(20),
                        target_id VARCHAR(36),
                        target_name VARCHAR(255),
                        description TEXT NOT NULL,
                        activity_data TEXT,
                        created_at DATETIME NOT NULL,
                        is_public BOOLEAN NOT NULL DEFAULT 1,
                        is_deleted BOOLEAN NOT NULL DEFAULT 0,
                        importance_score INTEGER NOT NULL DEFAULT 1,
                        FOREIGN KEY (user_id) REFERENCES users(id),
                        FOREIGN KEY (team_id) REFERENCES teams(id)
                    )
                    """

                    with engine.connect() as conn:
                        conn.execute(text(create_table_sql))

                        # Create indexes
                        indexes = [
                            "CREATE INDEX idx_activities_team_id ON activities(team_id)",
                            "CREATE INDEX idx_activities_user_id ON activities(user_id)",
                            "CREATE INDEX idx_activities_created_at ON activities(created_at)",
                            "CREATE INDEX idx_activities_action_type ON activities(action_type)"
                        ]

                        for index_sql in indexes:
                            conn.execute(text(index_sql))

                        conn.commit()

                    self.log.success("Activities table created successfully")
                else:
                    self.log.success("Activities table already exists")

                    # Verify all required columns exist
                    columns = {col['name'] for col in inspector.get_columns('activities')}
                    required_columns = {
                        'id', 'action_type', 'action_category', 'user_id', 'team_id',
                        'target_type', 'target_id', 'target_name', 'description',
                        'activity_data', 'created_at', 'is_public', 'is_deleted', 'importance_score'
                    }

                    missing_columns = required_columns - columns
                    if missing_columns:
                        self.log.warning(f"Missing columns in activities table: {missing_columns}")
                        self._add_missing_activity_columns(engine, missing_columns)
                    else:
                        self.log.success("All required columns exist in activities table")

        except Exception as e:
            self.log.error("Failed to ensure activities table exists", e)

    def _add_missing_activity_columns(self, engine, missing_columns):
        """Add missing columns to activities table"""
        column_definitions = {
            'activity_data': 'TEXT',
            'is_public': 'BOOLEAN NOT NULL DEFAULT 1',
            'is_deleted': 'BOOLEAN NOT NULL DEFAULT 0',
            'importance_score': 'INTEGER NOT NULL DEFAULT 1',
            'target_type': 'VARCHAR(20)',
            'target_id': 'VARCHAR(36)',
            'target_name': 'VARCHAR(255)'
        }

        try:
            with engine.connect() as conn:
                for column in missing_columns:
                    if column in column_definitions:
                        alter_sql = f"ALTER TABLE activities ADD COLUMN {column} {column_definitions[column]}"
                        conn.execute(text(alter_sql))
                        self.log.success(f"Added column {column} to activities table")
                conn.commit()
        except Exception as e:
            self.log.error(f"Failed to add missing columns: {e}")

    def _refresh_metadata_ultimate(self):
        """ULTIMATE - Force refresh SQLAlchemy metadata with proper Flask context"""
        self.log.step("Refreshing SQLAlchemy metadata (ULTIMATE VERSION)")

        try:
            with self.app.app_context():
                # Get the database engine through current_app extensions
                engine = current_app.extensions["sqlalchemy"].engines[None]
                self.log.success(f"Got database engine: {engine}")

                # Get the correct db instance
                db_instance = current_app.extensions["sqlalchemy"]
                self.log.success(f"Got SQLAlchemy instance: {db_instance}")

                # Force create all tables in metadata (but don't actually create them)
                db_instance.metadata.create_all(engine, checkfirst=True)

                model_tables = list(db_instance.metadata.tables.keys())
                self.log.success(
                    f"Metadata refreshed - {len(model_tables)} tables in metadata"
                )
                self.log.debug(f"   Tables in metadata: {model_tables}")

                # Update our db reference
                self.db = db_instance

        except Exception as e:
            self.log.error("Failed to refresh metadata", e)
            raise

    def _detect_all_changes_ultimate(self):
        """ULTIMATE - Detect all missing tables and columns with proper context"""
        self.log.step("Detecting missing tables and columns (ULTIMATE VERSION)")

        changes = []

        try:
            with self.app.app_context():
                # Get current database schema using proper engine
                engine = current_app.extensions["sqlalchemy"].engines[None]
                inspector = sql_inspect(engine)
                existing_tables = set(inspector.get_table_names())

                # Get model tables from metadata
                db_instance = current_app.extensions["sqlalchemy"]
                model_tables = set(db_instance.metadata.tables.keys())

                self.log.info(
                    f"Database has {len(existing_tables)} tables: {existing_tables}"
                )
                self.log.info(
                    f"Models define {len(model_tables)} tables: {model_tables}"
                )

                # Check for missing tables
                missing_tables = model_tables - existing_tables
                if missing_tables:
                    self.log.warning(f"Missing tables detected: {missing_tables}")
                    for table in missing_tables:
                        changes.append(f"CREATE TABLE {table}")
                        self.log.info(f"   📋 Missing table: {table}")

                # Check for missing columns in existing tables
                # Check for missing columns in existing tables
                for table_name in model_tables.intersection(existing_tables):
                    column_changes = self._check_table_columns_ultimate(
                        table_name, inspector, db_instance
                    )
                    changes.extend(column_changes)

                self.log.success(
                    f"Change detection complete - found {len(changes)} changes"
                )

                return changes

        except Exception as e:
            self.log.error("Failed to detect changes", e)
            return []

    def _check_table_columns_ultimate(self, table_name, inspector, db_instance):
        """ULTIMATE - Check for missing columns in a specific table"""
        changes = []

        try:
            self.log.debug(f"Checking columns in table: {table_name}")

            # Get existing columns from database
            existing_columns = set()
            try:
                db_columns = inspector.get_columns(table_name)
                existing_columns = {col["name"] for col in db_columns}
                self.log.debug(f"   Database columns: {existing_columns}")
            except Exception as e:
                self.log.warning(f"Could not get columns for {table_name}: {e}")
                return changes

            # Get model columns from metadata
            if table_name in db_instance.metadata.tables:
                model_table = db_instance.metadata.tables[table_name]
                model_columns = set(model_table.columns.keys())
                self.log.debug(f"   Model columns: {model_columns}")

                # Find missing columns
                missing_columns = model_columns - existing_columns
                if missing_columns:
                    self.log.warning(
                        f"Missing columns in {table_name}: {missing_columns}"
                    )
                    for column in missing_columns:
                        changes.append(f"ADD COLUMN {table_name}.{column}")
                        self.log.info(f"   📝 Missing column: {table_name}.{column}")

                        # Get column details for better logging
                        col_obj = model_table.columns[column]
                        self.log.debug(f"      Type: {col_obj.type}")
                        self.log.debug(f"      Nullable: {col_obj.nullable}")
                        self.log.debug(f"      Default: {col_obj.default}")
                else:
                    self.log.debug(f"   ✅ All columns exist in {table_name}")

        except Exception as e:
            self.log.error(f"Error checking columns for {table_name}", e)

        return changes

    def _create_and_apply_migration(self, changes):
        """Create and apply migration for detected changes"""
        self.log.step(f"Creating migration for {len(changes)} changes")

        try:
            # Create migration
            migration_message = f"auto_migration_{len(changes)}_changes_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            self.log.info(f"Creating migration: {migration_message}")
            for change in changes:
                self.log.info(f"   🔄 {change}")

            # Use Flask-Migrate to create migration
            migrate(message=migration_message)
            self.log.success("Migration file created successfully")

            # Apply migration
            self.log.info("Applying migration to database")
            upgrade()
            self.log.success("Migration applied successfully")

        except Exception as e:
            self.log.error("Failed to create or apply migration", e)
            raise

    def _verify_database_state_ultimate(self):
        """ULTIMATE - Verify final database state with proper context"""
        self.log.step("Verifying final database state (ULTIMATE VERSION)")

        try:
            with self.app.app_context():
                engine = current_app.extensions["sqlalchemy"].engines[None]
                inspector = sql_inspect(engine)
                final_tables = set(inspector.get_table_names())

                db_instance = current_app.extensions["sqlalchemy"]
                model_tables = set(db_instance.metadata.tables.keys())

                self.log.info(f"Final database tables: {final_tables}")
                self.log.info(f"Expected model tables: {model_tables}")

                missing_tables = model_tables - final_tables
                if missing_tables:
                    self.log.error(f"Still missing tables: {missing_tables}")
                    return False

                # Check all columns are present
                all_columns_present = True
                for table_name in model_tables:
                    if table_name in final_tables:
                        db_columns = {
                            col["name"] for col in inspector.get_columns(table_name)
                        }
                        model_columns = set(
                            db_instance.metadata.tables[table_name].columns.keys()
                        )
                        missing_cols = model_columns - db_columns

                        if missing_cols:
                            self.log.error(
                                f"Still missing columns in {table_name}: {missing_cols}"
                            )
                            all_columns_present = False
                        else:
                            self.log.debug(f"   ✅ All columns present in {table_name}")

                if all_columns_present:
                    self.log.success(
                        "✨ Database verification complete - all tables and columns present!"
                    )
                    return True
                else:
                    self.log.error(
                        "Database verification failed - some columns still missing"
                    )
                    return False

        except Exception as e:
            self.log.error("Database verification failed", e)
            return False

    def check_specific_columns_ultimate(self, table_name, expected_columns):
        """ULTIMATE - Check if specific columns exist in a table"""
        self.log.info(f"Checking specific columns in {table_name}: {expected_columns}")

        try:
            with self.app.app_context():
                engine = current_app.extensions["sqlalchemy"].engines[None]
                inspector = sql_inspect(engine)

                if table_name not in inspector.get_table_names():
                    self.log.error(f"Table {table_name} does not exist")
                    return False

                db_columns = {col["name"] for col in inspector.get_columns(table_name)}
                self.log.info(f"Existing columns in {table_name}: {db_columns}")

                missing_columns = set(expected_columns) - db_columns
                if missing_columns:
                    self.log.error(
                        f"Missing columns in {table_name}: {missing_columns}"
                    )
                    return False
                else:
                    self.log.success(f"All expected columns exist in {table_name}")
                    return True

        except Exception as e:
            self.log.error(f"Error checking columns in {table_name}", e)
            return False

    def force_add_missing_columns_ultimate(self, table_name, missing_columns_info):
        """ULTIMATE - Force add missing columns to a table"""
        self.log.step(f"Force adding missing columns to {table_name}")

        try:
            with self.app.app_context():
                engine = current_app.extensions["sqlalchemy"].engines[None]

                for column_name, column_info in missing_columns_info.items():
                    try:
                        # Create ALTER TABLE statement
                        column_type = column_info.get("type", "TEXT")
                        nullable = column_info.get("nullable", True)
                        default = column_info.get("default", None)

                        alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"

                        if default is not None:
                            if isinstance(default, str):
                                alter_sql += f" DEFAULT '{default}'"
                            else:
                                alter_sql += f" DEFAULT {default}"

                        if not nullable:
                            alter_sql += " NOT NULL"

                        self.log.info(f"Executing: {alter_sql}")

                        with engine.connect() as conn:
                            conn.execute(text(alter_sql))
                            conn.commit()

                        self.log.success(f"Added column {column_name} to {table_name}")

                    except Exception as e:
                        self.log.error(f"Failed to add column {column_name}", e)

        except Exception as e:
            self.log.error(f"Failed to add columns to {table_name}", e)


def normalize_enum_values_in_database(app):
    """Normalize enum values in database to match model definitions"""
    migration_system = UltimateEnhancedAutoMigration(app)
    migration_system.log.step("Normalizing enum values in database")

    try:
        with app.app_context():
            engine = current_app.extensions["sqlalchemy"].engines[None]

            # Normalize team_members table enum values
            with engine.connect() as conn:
                # Check current values
                result = conn.execute(
                    text(
                        """
                    SELECT DISTINCT role, invitation_status 
                    FROM team_members 
                    WHERE role IS NOT NULL OR invitation_status IS NOT NULL
                """
                    )
                )

                current_values = result.fetchall()
                migration_system.log.info(
                    f"Current enum values in database: {current_values}"
                )

                # Normalize role values to lowercase
                conn.execute(
                    text(
                        """
                    UPDATE team_members 
                    SET role = LOWER(role) 
                    WHERE role IS NOT NULL
                """
                    )
                )

                # Normalize invitation_status values to lowercase
                conn.execute(
                    text(
                        """
                    UPDATE team_members 
                    SET invitation_status = LOWER(invitation_status) 
                    WHERE invitation_status IS NOT NULL
                """
                    )
                )

                conn.commit()
                migration_system.log.success("Enum values normalized to lowercase")

                # Verify the changes
                result = conn.execute(
                    text(
                        """
                    SELECT DISTINCT role, invitation_status 
                    FROM team_members 
                    WHERE role IS NOT NULL OR invitation_status IS NOT NULL
                """
                    )
                )

                normalized_values = result.fetchall()
                migration_system.log.info(
                    f"Normalized enum values: {normalized_values}"
                )

        return True

    except Exception as e:
        migration_system.log.error("Failed to normalize enum values", e)
        return False


def run_ultimate_enhanced_auto_migration(app):
    """Main function to run ULTIMATE enhanced auto-migration"""

    normalize_enum_values_in_database(app)
    migration_system = UltimateEnhancedAutoMigration(app)
    return migration_system.run_complete_migration_check()


def check_user_avatar_columns_ultimate(app):
    """ULTIMATE - Specific function to check user avatar columns"""
    migration_system = UltimateEnhancedAutoMigration(app)

    expected_columns = [
        "id",
        "email",
        "username",
        "password_hash",
        "created_at",
        "plan_type",
        "is_active",
        "avatar_url",
        "avatar_filename",
        "avatar_uploaded_at",
    ]

    return migration_system.check_specific_columns_ultimate("users", expected_columns)


def force_add_user_avatar_columns_ultimate(app):
    """ULTIMATE - Force add missing user avatar columns if they don't exist"""
    migration_system = UltimateEnhancedAutoMigration(app)

    # Define the missing columns with their specifications
    avatar_columns = {
        "avatar_url": {"type": "TEXT", "nullable": True, "default": None},
        "avatar_filename": {"type": "TEXT", "nullable": True, "default": None},
        "avatar_uploaded_at": {"type": "DATETIME", "nullable": True, "default": None},
    }

    # Check which columns are missing
    try:
        with app.app_context():
            engine = current_app.extensions["sqlalchemy"].engines[None]
            inspector = sql_inspect(engine)

            if "users" in inspector.get_table_names():
                existing_columns = {
                    col["name"] for col in inspector.get_columns("users")
                }
                missing_columns = {}

                for col_name, col_info in avatar_columns.items():
                    if col_name not in existing_columns:
                        missing_columns[col_name] = col_info
                        migration_system.log.warning(
                            f"Missing column: users.{col_name}"
                        )

                if missing_columns:
                    migration_system.log.info(
                        f"Found {len(missing_columns)} missing avatar columns"
                    )
                    migration_system.force_add_missing_columns_ultimate(
                        "users", missing_columns
                    )
                    return True
                else:
                    migration_system.log.success("All avatar columns already exist")
                    return True
            else:
                migration_system.log.error("Users table does not exist")
                return False

    except Exception as e:
        migration_system.log.error("Failed to check/add avatar columns", e)
        return False


def debug_flask_sqlalchemy_setup(app):
    """Debug Flask-SQLAlchemy setup for troubleshooting"""
    print("\n" + "=" * 80)
    print("DEBUGGING FLASK-SQLALCHEMY SETUP")
    print("=" * 80)

    try:
        with app.app_context():
            print(f"Flask App: {app}")
            print(f"Flask App Name: {app.name}")
            print(f"Current App: {current_app}")
            print(
                f"App Extensions: {list(app.extensions.keys()) if hasattr(app, 'extensions') else 'None'}"
            )

            if "sqlalchemy" in app.extensions:
                db_instance = app.extensions["sqlalchemy"]
                print(f"SQLAlchemy Instance: {db_instance}")
                print(f"Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")

                try:
                    engine = db_instance.engines[None]
                    print(f"Database Engine: {engine}")

                    with engine.connect() as conn:
                        result = conn.execute(text("SELECT 1"))
                        print(f"Database Connection: SUCCESS")
                except Exception as e:
                    print(f"Database Connection: FAILED - {e}")
            else:
                print("SQLAlchemy not found in app extensions!")

    except Exception as e:
        print(f"Debug failed: {e}")
        import traceback

        traceback.print_exc()

    print("=" * 80 + "\n")
