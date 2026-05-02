import sqlite3
import os
from flask import current_app
from sqlalchemy import inspect
from app import db


def initialize_database():
    """Automatically sync ALL database tables with model definitions - reads from actual models"""
    try:
        # Get database path
        db_path = os.path.join(current_app.root_path, "..", "data", "dev_snippets.db")

        print(f"🔧 Checking database: {db_path}")

        # Connect directly to SQLite
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Import all your models
        from app.models.user import User
        from app.models.snippet import Snippet, SnippetHistory, SnippetShare
        from app.models.collection import Collection
        from app.models.team import Team
        from app.models.team_member import TeamMember

        # List of all models to sync
        models_to_sync = [
            User,
            Snippet,
            Collection,
            Team,
            TeamMember,
            SnippetHistory,
            SnippetShare,
        ]

        # Sync each model automatically
        for model in models_to_sync:
            sync_model_table(model, cursor)

        # Create relationship tables
        create_relationship_tables(cursor)

        conn.commit()
        conn.close()

        print("✅ All database tables synced automatically!")
        return True

    except Exception as e:
        print(f"❌ Database sync failed: {e}")
        print("🔧 Falling back to basic table creation...")
        try:
            # Fallback: create basic tables
            create_basic_tables(cursor if "cursor" in locals() else None)
            return True
        except:
            return False


def sync_model_table(model, cursor):
    """Automatically sync any SQLAlchemy model with database table"""
    table_name = model.__tablename__
    print(f"🔍 Syncing {table_name} table from {model.__name__} model...")

    # Get model columns automatically
    required_columns = {}

    for column in model.__table__.columns:
        col_name = column.name
        col_type = get_sqlite_type(column.type)

        # Handle constraints
        constraints = []
        if column.primary_key:
            constraints.append("PRIMARY KEY")
        if not column.nullable and not column.primary_key:
            constraints.append("NOT NULL")
        if column.unique:
            constraints.append("UNIQUE")

        # Handle defaults
        default_value = None
        if column.default is not None:
            if hasattr(column.default, "arg"):
                default_value = column.default.arg
            elif callable(column.default.arg):
                # Skip callable defaults for now
                pass
            else:
                default_value = column.default.arg

        # Build column definition
        col_definition = col_type
        if constraints:
            col_definition += " " + " ".join(constraints)
        if default_value is not None:
            if isinstance(default_value, bool):
                col_definition += f" DEFAULT {str(default_value).upper()}"
            elif isinstance(default_value, (int, float)):
                col_definition += f" DEFAULT {default_value}"
            else:
                col_definition += f' DEFAULT "{default_value}"'

        required_columns[col_name] = col_definition

    # Sync the table
    sync_table(table_name, required_columns, cursor)


def get_sqlite_type(sqlalchemy_type):
    """Convert SQLAlchemy types to SQLite types"""
    type_name = str(sqlalchemy_type).upper()

    if "VARCHAR" in type_name or "STRING" in type_name:
        return "VARCHAR"
    elif "TEXT" in type_name:
        return "TEXT"
    elif "INTEGER" in type_name:
        return "INTEGER"
    elif "FLOAT" in type_name or "NUMERIC" in type_name:
        return "FLOAT"
    elif "BOOLEAN" in type_name:
        return "BOOLEAN"
    elif "DATETIME" in type_name:
        return "DATETIME"
    elif "UUID" in type_name:
        return "VARCHAR"
    else:
        return "TEXT"  # Default fallback


def sync_table(table_name, required_columns, cursor):
    """Generic function to sync any table with its required columns"""
    # Check if table exists
    cursor.execute(
        f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
    )
    table_exists = cursor.fetchone()

    if not table_exists:
        print(f"🔧 Creating {table_name} table...")
        # Create table with all columns
        columns_sql = ", ".join(
            [f"{col} {definition}" for col, definition in required_columns.items()]
        )
        try:
            cursor.execute(f"CREATE TABLE {table_name} ({columns_sql})")
            print(f"✅ {table_name} table created!")
        except Exception as e:
            print(f"⚠️ Could not create {table_name}: {e}")
    else:
        # Get existing columns
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1]: row[2] for row in cursor.fetchall()}

        # Add missing columns
        added_count = 0
        for col_name, col_definition in required_columns.items():
            if col_name not in existing_columns:
                try:
                    # Extract just the type part for ALTER TABLE
                    parts = col_definition.split()
                    col_type = parts[0]

                    # Handle defaults for ALTER TABLE
                    default_part = ""
                    if "DEFAULT" in col_definition:
                        default_idx = parts.index("DEFAULT")
                        if default_idx + 1 < len(parts):
                            default_value = parts[default_idx + 1]
                            if default_value.upper() in ["FALSE", "TRUE"]:
                                default_part = f" DEFAULT {default_value.upper()}"
                            elif (
                                default_value.replace(".", "")
                                .replace("-", "")
                                .isdigit()
                            ):
                                default_part = f" DEFAULT {default_value}"
                            else:
                                default_part = f" DEFAULT {default_value}"

                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}{default_part}"
                    cursor.execute(alter_sql)
                    print(f"✅ Added {table_name}.{col_name}")
                    added_count += 1
                except Exception as e:
                    if "duplicate column name" not in str(e):
                        print(f"⚠️ Could not add {table_name}.{col_name}: {e}")

        if added_count == 0:
            print(f"✅ {table_name} table is up to date!")
        else:
            print(f"✅ Added {added_count} columns to {table_name}!")


def create_relationship_tables(cursor):
    """Create relationship/junction tables that aren't models"""
    print("🔍 Checking relationship tables...")

    # Snippet-Collections relationship table
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='snippet_collections'"
    )
    if not cursor.fetchone():
        cursor.execute(
            """
            CREATE TABLE snippet_collections (
                snippet_id VARCHAR NOT NULL,
                collection_id INTEGER NOT NULL,
                PRIMARY KEY (snippet_id, collection_id)
            )
        """
        )
        print("✅ snippet_collections table created!")

    # Snippet collaborators table
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='snippet_collaborators'"
    )
    if not cursor.fetchone():
        cursor.execute(
            """
            CREATE TABLE snippet_collaborators (
                snippet_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                permission VARCHAR(20) DEFAULT 'view',
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (snippet_id, user_id)
            )
        """
        )
        print("✅ snippet_collaborators table created!")


def create_basic_tables(cursor):
    """Fallback: create basic tables if model reading fails"""
    if cursor is None:
        return

    print("🔧 Creating basic tables as fallback...")

    # Basic users table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id VARCHAR PRIMARY KEY,
            email VARCHAR(120) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at DATETIME NOT NULL
        )
    """
    )

    # Basic snippets table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS snippets (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL,
            title VARCHAR(200) NOT NULL,
            code TEXT NOT NULL,
            language VARCHAR(50) NOT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )
    """
    )

    # Basic collections table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            user_id VARCHAR NOT NULL,
            created_at DATETIME NOT NULL
        )
    """
    )

    print("✅ Basic tables created!")
