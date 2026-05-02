from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# 🔥 CRITICAL: Import in correct order
from .user import User
from .team import Team
from .team_member import TeamMember
from .snippet import Snippet
from .collection import Collection

# 🆕 Import new models AFTER base models
try:
    from .team_snippet import TeamSnippet
    from .team_collection import TeamCollection, team_snippet_collections

    print("✅ Team content models imported successfully")
except ImportError as e:
    print(f"⚠️ Team content models not available: {e}")
