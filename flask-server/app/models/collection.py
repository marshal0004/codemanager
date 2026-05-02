from ast import Dict
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from app.models import db
from datetime import datetime
from sqlalchemy import JSON
import uuid
from ..models.team_member import TeamMember
from .snippet import snippet_collections
import json
from app.models.custom_types import UUIDType, JSONType  # Import the custom types
from sqlalchemy import String  # if not already imported
from flask import current_app

# Import the association table from snippet model
from .snippet import snippet_collections




class Collection(db.Model):
    __tablename__ = "collections"

    # Nested collections support
    parent = db.relationship(
        "Collection",
        remote_side="Collection.id",
        backref=db.backref("children", lazy="dynamic"),
    )
    level = db.Column(db.Integer, default=0, nullable=False)  # For hierarchy depth
    path = db.Column(
        db.String(1000), nullable=True
    )  # Full path like "parent/child/grandchild"

    # Sharing and permissions
    is_public = db.Column(db.Boolean, default=False, nullable=False)
    share_token = db.Column(db.String(64), unique=True, nullable=True)
    share_expires_at = db.Column(db.DateTime, nullable=True)
    user_id = db.Column(UUIDType, db.ForeignKey("users.id"), nullable=True)

    user = db.relationship("User", back_populates="collections", foreign_keys=[user_id])

    # Collection settings
    color = db.Column(db.String(7), default="#3498db", nullable=False)  # Hex color
    icon = db.Column(db.String(50), default="folder", nullable=False)
    sort_order = db.Column(db.String(20), default="created_at", nullable=False)
    order = db.Column(db.Integer, default=0)
    view_type = db.Column(
        db.String(20), default="grid", nullable=False
    )  # grid, list, cards

    # Analytics
    view_count = db.Column(db.Integer, default=0, nullable=False)
    last_accessed = db.Column(db.DateTime, nullable=True)

    # Template system
    is_template = db.Column(db.Boolean, default=False, nullable=False)
    template_category = db.Column(db.String(100), nullable=True)
    template_tags = db.Column(db.Text, nullable=True)  # JSON array of tags
    # Add this field to your Collection model
    tags = db.Column(db.Text, nullable=True)  # For user-defined tags

    id = db.Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()))
    parent_id = db.Column(UUIDType, db.ForeignKey("collections.id"), nullable=True)

    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    # Add this line to your Collection model
    is_favorite = db.Column(db.Boolean, default=False, nullable=False)

    # ADD THESE LINES:
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(UUIDType, db.ForeignKey("users.id"), nullable=True)

    # Hex color for UI

    # NEW: Team collaboration fields
    team_id = db.Column(UUIDType, db.ForeignKey("teams.id"), nullable=True)
    is_team_collection = db.Column(db.Boolean, default=False)

    # Relationships
    snippets = db.relationship(
        "Snippet", secondary=snippet_collections, back_populates="collections"
    )

    parent = db.relationship(
        "Collection",
        remote_side="Collection.id",
        backref=db.backref("children", lazy="dynamic"),
    )
    collection_collaborators = db.Table(
        "collection_collaborators",
        db.Column(
            "collection_id", UUIDType, db.ForeignKey("collections.id"), primary_key=True
        ),
        db.Column("user_id", UUIDType, db.ForeignKey("users.id"), primary_key=True),
        db.Column("permission", db.String(20), default="view"),  # view, edit, admin
        db.Column("added_at", db.DateTime, default=datetime.utcnow),
        db.Column("added_by", UUIDType, db.ForeignKey("users.id")),
    )

    # ADD THIS NEW TABLE HERE
    collection_team_shares = db.Table(
        "collection_team_shares",
        db.Column("collection_id", db.String(36), db.ForeignKey("collections.id"), primary_key=True),
        db.Column("team_id", db.String(36), db.ForeignKey("teams.id"), primary_key=True),
        db.Column("shared_by_id", db.String(36), db.ForeignKey("users.id"), nullable=False),
        db.Column("shared_at", db.DateTime, default=datetime.utcnow, nullable=False),
        db.Column("permission_level", db.String(20), default="view", nullable=False),
    )

    # Collection collaborators
    collaborators = db.relationship(
        "User",
        secondary="collection_collaborators",
        primaryjoin="Collection.id == collection_collaborators.c.collection_id",
        secondaryjoin="User.id == collection_collaborators.c.user_id",
        backref=db.backref("collaborated_collections", lazy="dynamic"),
        lazy="dynamic",
        foreign_keys=[
            collection_collaborators.c.collection_id,
            collection_collaborators.c.user_id,
        ],
    )
    # NEW: Sharing and permissions
    visibility = db.Column(db.String(20), default="private")  # private, team, public
    sharing_settings = db.Column(
        JSONType,
        default=lambda: {
            "allow_view": True,
            "allow_copy": False,
            "allow_edit": False,
            "allow_share": False,
            "password_protected": False,
            "password_hash": None,
            "expires_at": None,
        },
    )

    # NEW: Team permissions
    team_permissions = db.Column(
        JSONType,
        default=lambda: {
            "owners": [],  # User IDs with full access
            "editors": [],  # User IDs who can edit
            "viewers": [],  # User IDs who can only view
            "inherit_from_team": True,  # Use team default permissions
        },
    )

    # NEW: Advanced organization

    sort_order = db.Column(db.Integer, default=0)
    is_favorite = db.Column(db.Boolean, default=False)

    # NEW: Template and automation

    auto_organize_rules = db.Column(
        JSONType,
        default=lambda: {
            "enabled": False,
            "rules": [],  # Array of auto-organization rules
        },
    )

    # NEW: Analytics and usage
    access_count = db.Column(db.Integer, default=0)
    last_accessed_at = db.Column(db.DateTime)
    contributor_count = db.Column(db.Integer, default=1)

    # NEW: Collaboration tracking
    last_modified_by = db.Column(UUIDType, db.ForeignKey("users.id"))
    collaboration_history = db.Column(JSONType, default=list)  # Track changes

    # Relationships

    team = db.relationship("Team", backref=db.backref("collections", lazy="dynamic"))
    last_modifier = db.relationship("User", foreign_keys=[last_modified_by])

    # NEW: Team member permissions (many-to-many)
    team_member_permissions = db.relationship(
        "CollectionPermission", backref="collection", cascade="all, delete-orphan"
    )

    def ensure_collection_team_shares_table():
        """Ensure collection_team_shares table is registered"""
        try:
            from app.models import db

            # Force the table to be part of metadata
            if "collection_team_shares" not in db.metadata.tables:
                print("🔧 Manually registering collection_team_shares table")

                # The table should already be defined above, this just ensures it's registered
                db.metadata.reflect(bind=db.engine)

            print(f"📋 Tables in metadata: {list(db.metadata.tables.keys())}")

        except Exception as e:
            print(f"❌ Error ensuring table registration: {e}")

    # Call this function when the module is imported
    ensure_collection_team_shares_table()

    def update_path(self):
        """Update the full path of the collection"""
        if self.parent_id:
            parent = Collection.query.get(self.parent_id)
            if parent:
                self.path = (
                    f"{parent.path}/{self.name}"
                    if parent.path
                    else f"{parent.name}/{self.name}"
                )
                self.level = parent.level + 1
            else:
                self.path = self.name
                self.level = 0
        else:
            self.path = self.name
            self.level = 0

        db.session.commit()

        # Update all children paths
        for child in self.children.all():
            child.update_path()

    def __init__(
        self, user_id, name, description=None, color="#3B82F6", tags=None, **kwargs
    ):
        super(Collection, self).__init__(**kwargs)
        self.id = str(uuid.uuid4())
        self.user_id = user_id
        self.name = name.strip()
        self.description = description.strip() if description else None
        self.color = color
        self.tags = tags.strip() if tags else None

    # NEW: Permission checking methods
    def can_user_access(self, user_id, permission_type="view"):
        """Check if user has specific permission on this collection"""
        if self.user_id == user_id:  # Owner has all permissions
            return True

        if self.is_team_collection and self.team_id:
            # Check team membership
            team_member = TeamMember.query.filter_by(
                team_id=self.team_id, user_id=user_id, status="active"
            ).first()

            if not team_member:
                return False

            # Check specific permissions
            permissions = self.team_permissions
            if permission_type == "view":
                return (
                    user_id in permissions.get("viewers", [])
                    or user_id in permissions.get("editors", [])
                    or user_id in permissions.get("owners", [])
                )
            elif permission_type == "edit":
                return user_id in permissions.get(
                    "editors", []
                ) or user_id in permissions.get("owners", [])
            elif permission_type == "admin":
                return user_id in permissions.get("owners", [])

        return self.visibility == "public" and permission_type == "view"

    # NEW: Sharing methods
    def generate_share_link(self, permission_level="view", expires_in_days=None):
        """Generate a shareable link for the collection"""
        import secrets
        from datetime import timedelta

        share_token = secrets.token_urlsafe(32)
        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        # Store share link in database (you'd need a ShareLink model)
        return f"/shared/collection/{share_token}"




    def share_with_teams(self, team_ids, shared_by_user_id, permission_level="view"):
        """Share collection with multiple teams"""
        try:
            from sqlalchemy import text
            
            current_app.logger.info(f"🔗 SHARE_COLLECTION: Sharing collection {self.id} with teams {team_ids}")
            
            shared_teams = []
            for team_id in team_ids:
                try:
                    # Check if already shared
                    existing = db.session.execute(
                        text("SELECT * FROM collection_team_shares WHERE collection_id = :collection_id AND team_id = :team_id"),
                        {"collection_id": self.id, "team_id": team_id}
                    ).first()
                    
                    if existing:
                        # Update existing share
                        db.session.execute(
                            text("""UPDATE collection_team_shares 
                                SET permission_level = :permission, shared_at = :shared_at, shared_by_id = :shared_by
                                WHERE collection_id = :collection_id AND team_id = :team_id"""),
                            {
                                "permission": permission_level,
                                "shared_at": datetime.utcnow(),
                                "shared_by": shared_by_user_id,
                                "collection_id": self.id,
                                "team_id": team_id
                            }
                        )
                        current_app.logger.info(f"✅ SHARE_COLLECTION: Updated existing share with team {team_id}")
                    else:
                        # Create new share
                        db.session.execute(
                            text("""INSERT INTO collection_team_shares 
                                (collection_id, team_id, shared_by_id, shared_at, permission_level)
                                VALUES (:collection_id, :team_id, :shared_by, :shared_at, :permission)"""),
                            {
                                "collection_id": self.id,
                                "team_id": team_id,
                                "shared_by": shared_by_user_id,
                                "shared_at": datetime.utcnow(),
                                "permission": permission_level
                            }
                        )
                        current_app.logger.info(f"✅ SHARE_COLLECTION: Created new share with team {team_id}")
                    
                    shared_teams.append(team_id)
                    
                except Exception as team_error:
                    current_app.logger.error(f"❌ SHARE_COLLECTION: Error sharing with team {team_id}: {str(team_error)}")
                    continue
            
            db.session.commit()
            current_app.logger.info(f"✅ SHARE_COLLECTION: Successfully shared with {len(shared_teams)} teams")
            
            return {
                "success": True,
                "shared_teams": shared_teams,
                "message": f"Collection shared with {len(shared_teams)} teams"
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"❌ SHARE_COLLECTION ERROR: {str(e)}")
            import traceback
            current_app.logger.error(f"❌ SHARE_COLLECTION TRACEBACK: {traceback.format_exc()}")
            raise


    # NEW: Analytics methods
    def track_access(self, user_id=None):
        """Track collection access for analytics"""
        self.access_count += 1
        self.last_accessed_at = datetime.utcnow()

        # Log access in collaboration history
        if user_id:
            self.collaboration_history.append(
                {
                    "action": "accessed",
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        db.session.commit()

    # NEW: Team collaboration methods
    def add_team_member_permission(self, user_id, permission_level):
        """Add specific permission for a team member"""
        permissions = self.team_permissions.copy()

        # Remove from other permission levels
        for level in ["viewers", "editors", "owners"]:
            if user_id in permissions.get(level, []):
                permissions[level].remove(user_id)

        # Add to new permission level
        if permission_level in permissions:
            if user_id not in permissions[permission_level]:
                permissions[permission_level].append(user_id)

        self.team_permissions = permissions
        db.session.commit()

    def to_dict(self, include_snippets=False, user_id=None):
        """Convert collection to dictionary with team permissions"""
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "tags": self.tags,  # Add tags field
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_public": self.is_public,
            "color": self.color,
            "parent_id": self.parent_id,  # Add parent_id
            "snippet_count": self.get_snippet_count(),
            "languages": self.get_languages(),
            "total_lines": self.get_total_lines(),
            "total_characters": self.get_total_characters(),
            # Team fields
            "team_id": self.team_id,
            "is_team_collection": self.is_team_collection,
            "visibility": self.visibility,
            "sharing_settings": self.sharing_settings,
            # UI fields
            "color": self.color,
            "icon": self.icon,
            "sort_order": self.sort_order,
            "is_favorite": self.is_favorite,
            "is_template": self.is_template,
            "template_category": self.template_category,
            # Analytics
            "access_count": self.access_count,
            "last_accessed_at": (
                self.last_accessed_at.isoformat() if self.last_accessed_at else None
            ),
            "contributor_count": self.contributor_count,
        }

        # Add user-specific permissions
        if user_id:
            data["permissions"] = {
                "can_view": self.can_user_access(user_id, "view"),
                "can_edit": self.can_user_access(user_id, "edit"),
                "can_admin": self.can_user_access(user_id, "admin"),
                "is_owner": self.user_id == user_id,
            }

        # Include snippets if requested
        if include_snippets:
            data["snippets"] = [snippet.to_dict() for snippet in self.snippets]
        else:
            data["recent_snippets"] = [
                snippet.to_dict(include_code=False)
                for snippet in self.get_recent_snippets(3)
            ]

        # Include child collections count
        data["children_count"] = len(self.children)

        return data

    def __repr__(self):
        return f"<Collection {self.name}>"

    def get_full_path(self):
        """Get the full hierarchical path"""
        return self.path or self.name

    def get_breadcrumbs(self):
        """Get breadcrumb navigation for this collection"""
        breadcrumbs = []
        current = self

        while current:
            breadcrumbs.insert(
                0,
                {
                    "id": current.id,
                    "name": current.name,
                    "url": f"/collections/{current.id}",
                },
            )
            current = current.parent

        return breadcrumbs

    def get_all_children(self, include_self=False):
        """Get all nested children collections"""
        children = []

        if include_self:
            children.append(self)

        for child in self.children:
            children.extend(child.get_all_children(include_self=True))

        return children

    def get_all_snippets(self, include_nested=True):
        """Get all snippets in this collection and optionally nested collections"""
        snippet_ids = [s.id for s in self.snippets]

        if include_nested:
            for child in self.get_all_children():
                snippet_ids.extend([s.id for s in child.snippets])

        from .snippet import Snippet

        return Snippet.query.filter(Snippet.id.in_(snippet_ids)).all()

    def can_move_to(self, target_parent_id):
        """Check if collection can be moved to target parent (prevent circular references)"""
        if not target_parent_id:
            return True

        # Can't move to itself
        if target_parent_id == self.id:
            return False

        # Can't move to its own children
        child_ids = [c.id for c in self.get_all_children()]
        if target_parent_id in child_ids:
            return False

        return True

    def move_to_parent(self, new_parent_id, moved_by_user_id):
        """Move collection to a new parent"""
        if not self.can_move_to(new_parent_id):
            return False

        old_parent_id = self.parent_id
        self.parent_id = new_parent_id
        self.update_path()

        # Log activity
        self.log_activity(
            moved_by_user_id,
            "moved",
            {"from_parent": old_parent_id, "to_parent": new_parent_id},
        )

        return True

    def generate_share_token(self, expires_hours=24):
        """Generate a shareable token for this collection"""
        import secrets

        self.share_token = secrets.token_urlsafe(32)
        if expires_hours:
            from datetime import timedelta

            self.share_expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
        db.session.commit()
        return self.share_token

    def is_share_valid(self):
        """Check if share token is still valid"""
        if not self.share_token:
            return False
        if self.share_expires_at and datetime.utcnow() > self.share_expires_at:
            return False
        return True

    def increment_view_count(self):
        """Increment view count and update last accessed time"""
        self.view_count += 1
        self.last_accessed = datetime.utcnow()
        db.session.commit()

    def add_collaborator(self, user_id, permission="view", added_by_user_id=None):
        """Add a collaborator to this collection"""
        from sqlalchemy import text

        if permission not in ["view", "edit", "admin"]:
            return False

        # Check if already a collaborator
        existing = db.session.execute(
            text(
                "SELECT * FROM collection_collaborators WHERE collection_id = :collection_id AND user_id = :user_id"
            ),
            {"collection_id": self.id, "user_id": user_id},
        ).fetchone()

        if existing:
            # Update permission
            db.session.execute(
                text(
                    "UPDATE collection_collaborators SET permission = :permission WHERE collection_id = :collection_id AND user_id = :user_id"
                ),
                {
                    "permission": permission,
                    "collection_id": self.id,
                    "user_id": user_id,
                },
            )
        else:
            # Add new collaborator
            db.session.execute(
                text(
                    "INSERT INTO collection_collaborators (collection_id, user_id, permission, added_by) VALUES (:collection_id, :user_id, :permission, :added_by)"
                ),
                {
                    "collection_id": self.id,
                    "user_id": user_id,
                    "permission": permission,
                    "added_by": added_by_user_id,
                },
            )

        # Log activity
        self.log_activity(
            added_by_user_id or user_id,
            "collaborator_added",
            {"collaborator_id": user_id, "permission": permission},
        )

        db.session.commit()
        return True

    def can_user_access(self, user_id, required_permission="view"):
        """Check if user can access this collection with required permission"""
        # Owner has all permissions
        if self.user_id == user_id:
            return True

        # Public collections can be viewed
        if self.is_public and required_permission == "view":
            return True

        # Check collaborator permissions
        from sqlalchemy import text

        collab = db.session.execute(
            text(
                "SELECT permission FROM collection_collaborators WHERE collection_id = :collection_id AND user_id = :user_id"
            ),
            {"collection_id": self.id, "user_id": user_id},
        ).fetchone()

        if not collab:
            return False

        permission_hierarchy = {"view": 1, "edit": 2, "admin": 3}
        user_level = permission_hierarchy.get(collab.permission, 0)
        required_level = permission_hierarchy.get(required_permission, 0)

        return user_level >= required_level

    def log_activity(self, user_id, action, details=None):
        """Log an activity for this collection"""
        activity = CollectionActivity(
            collection_id=self.id,
            user_id=user_id,
            action=action,
            details=json.dumps(details) if details else None,
        )
        db.session.add(activity)
        db.session.commit()

    def get_recent_activity(self, limit=10):
        """Get recent activity for this collection"""
        return self.activities.limit(limit).all()

    def create_from_template(self, user_id, new_name, template_data=None):
        """Create a new collection from this template"""
        if not self.is_template:
            return None

        new_collection = Collection(
            name=new_name,
            description=f"Created from template: {self.name}",
            user_id=user_id,
            color=self.color,
            icon=self.icon,
            sort_order=self.sort_order,
            view_type=self.view_type,
        )

        db.session.add(new_collection)
        db.session.flush()  # Get the new collection ID

        # Copy snippets if template has any
        for snippet in self.snippets:
            from .snippet import Snippet

            new_snippet = Snippet(
                title=snippet.title,
                content=snippet.content,
                description=snippet.description,
                language=snippet.language,
                tags=snippet.tags,
                user_id=user_id,
                collection_id=new_collection.id,
            )
            db.session.add(new_snippet)

        # Log activity
        new_collection.log_activity(
            user_id,
            "created_from_template",
            {"template_id": self.id, "template_name": self.name},
        )

        db.session.commit()
        return new_collection

    def track_view(self, user_id=None):
        """Track when collection is viewed with enhanced logging"""
        try:
            print(
                f"🔍 TRACKING COLLECTION VIEW - Collection ID: {self.id}, User ID: {user_id}"
            )

            self.view_count += 1
            self.last_accessed = datetime.utcnow()

            if user_id:
                # Log access in collaboration history
                if not self.collaboration_history:
                    self.collaboration_history = []

                self.collaboration_history.append(
                    {
                        "action": "viewed",
                        "user_id": str(user_id),
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
                print(f"✅ Added collaboration history entry for user: {user_id}")

            db.session.commit()
            print(f"✅ COLLECTION VIEW TRACKED - New count: {self.view_count}")

        except Exception as e:
            print(f"❌ ERROR tracking collection view: {str(e)}")
            import traceback

            traceback.print_exc()
            db.session.rollback()

    def get_statistics(self):
        """Get statistics for this collection"""
        return {
            "snippet_count": len(self.snippets),
            "total_snippets_nested": len(self.get_all_snippets()),
            "children_count": len(self.children),
            "total_children_nested": len(self.get_all_children()),
            "view_count": self.view_count,
            "last_accessed": (
                self.last_accessed.isoformat() if self.last_accessed else None
            ),
            "collaborators_count": self.collaborators.count(),
            "is_public": self.is_public,
            "level": self.level,
            "has_active_share": self.is_share_valid(),
        }

    def add_snippet(self, snippet):
        """Add a snippet to this collection"""
        if snippet not in self.snippets:
            self.snippets.append(snippet)
            self.updated_at = datetime.utcnow()
            return True
        return False

    def remove_snippet(self, snippet):
        """Remove a snippet from this collection"""
        if snippet in self.snippets:
            self.snippets.remove(snippet)
            self.updated_at = datetime.utcnow()
            return True
        return False

    def get_snippet_count(self):
        """Get total number of snippets in this collection"""
        return len(self.snippets)

    def get_languages(self):
        """Get unique languages of snippets in this collection"""
        languages = set()
        for snippet in self.snippets:
            languages.add(snippet.language)
        return list(languages)

    def get_active_snippets(self):
        """Get all active (non-deleted) snippets in this collection"""
        return [s for s in self.snippets if not getattr(s, "is_deleted", False)]

    def get_snippet_count(self):
        """Get total number of active snippets in this collection"""
        return len(self.get_active_snippets())

    def get_recent_snippets(self, limit=5):
        """Get most recently added snippets in this collection"""
        return sorted(self.snippets, key=lambda x: x.created_at, reverse=True)[:limit]

    def is_owner(self, user_id):
        """Check if user is the owner of this collection"""
        return self.user_id == user_id

    def has_snippet(self, snippet_id):
        """Check if collection contains a specific snippet"""
        return any(snippet.id == snippet_id for snippet in self.snippets)

    def get_total_lines(self):
        """Get total lines of code in all snippets"""
        return sum(snippet.get_line_count() for snippet in self.snippets)

    def get_total_characters(self):
        """Get total characters in all snippets"""
        return sum(snippet.get_character_count() for snippet in self.snippets)

    def to_dict(self, include_snippets=False):
        """Convert collection to dictionary"""
        data = {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_public": self.is_public,
            "color": self.color,
            "snippet_count": self.get_snippet_count(),
            "languages": self.get_languages(),
            "total_lines": self.get_total_lines(),
            "total_characters": self.get_total_characters(),
        }

        if include_snippets:
            data["snippets"] = [
                snippet.to_dict(include_code=False) for snippet in self.snippets
            ]
        else:
            data["recent_snippets"] = [
                snippet.to_dict(include_code=False)
                for snippet in self.get_recent_snippets(3)
            ]

        return data

    @staticmethod
    def get_user_collections(user_id):
        """Get all collections for a specific user"""
        return (
            Collection.query.filter_by(user_id=user_id)
            .order_by(Collection.updated_at.desc())
            .all()
        )



    def get_user_teams_for_sharing(self, user_id: int) -> Dict:
        """Get teams user can share this collection with - ENHANCED LOGGING"""
        try:
            from sqlalchemy import text
            
            print(f"🎯 COLLECTION_TEAMS: Getting teams for collection {self.id} by user {user_id}")
            
            # Get teams where user is member and can share
            teams_query = text("""
                SELECT t.id, t.name, t.description, tm.role, t.member_count,
                    CASE WHEN cts.team_id IS NOT NULL THEN 1 ELSE 0 END as already_shared
                FROM teams t
                JOIN team_members tm ON t.id = tm.team_id
                LEFT JOIN collection_team_shares cts ON t.id = cts.team_id AND cts.collection_id = :collection_id
                WHERE tm.user_id = :user_id 
                AND tm.is_active = 1 
                AND tm.invitation_status = 'ACCEPTED'
                ORDER BY t.name ASC
            """)
            
            result = db.session.execute(teams_query, {
                "user_id": str(user_id),
                "collection_id": str(self.id)
            })
            teams_data = result.fetchall()
            
            print(f"✅ COLLECTION_TEAMS: Found {len(teams_data)} teams")
            
            created_teams = []
            joined_teams = []
            
            for team in teams_data:
                team_data = {
                    "id": str(team.id),
                    "name": team.name,
                    "description": team.description or "",
                    "role": team.role,
                    "member_count": team.member_count or 0,
                    "already_shared": bool(team.already_shared),
                    "can_share": team.role in ['OWNER', 'ADMIN', 'EDITOR']
                }
                
                if team.role == 'OWNER':
                    created_teams.append(team_data)
                else:
                    joined_teams.append(team_data)
                
                print(f"  ✅ Team: {team.name} (Role: {team.role}, Shared: {bool(team.already_shared)})")
            
            return {
                "created_teams": created_teams,
                "joined_teams": joined_teams,
                "total_teams": len(teams_data)
            }
            
        except Exception as e:
            print(f"❌ COLLECTION_TEAMS ERROR: {str(e)}")
            import traceback
            print(f"❌ COLLECTION_TEAMS TRACEBACK: {traceback.format_exc()}")
            return {
                "created_teams": [],
                "joined_teams": [],
                "error": str(e)
            }
        

    @staticmethod
    def search_by_name(query, user_id=None):
        """Search collections by name or description"""
        search_query = Collection.query

        # Filter by user if specified
        if user_id:
            search_query = search_query.filter_by(user_id=user_id)

        # Search in name and description
        search_term = f"%{query}%"
        search_query = search_query.filter(
            db.or_(
                Collection.name.ilike(search_term),
                Collection.description.ilike(search_term),
            )
        )

        return search_query.order_by(Collection.updated_at.desc())


# ADD these new association tables (add after your model class):


# Collection collaborators association table


# Collection activity log
class CollectionActivity(db.Model):
    __tablename__ = "collection_activity"

    id = db.Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()))
    collection_id = db.Column(UUIDType, db.ForeignKey("collections.id"), nullable=False)
    user_id = db.Column(UUIDType, db.ForeignKey("users.id"), nullable=False)
    action = db.Column(
        db.String(50), nullable=False
    )  # created, updated, deleted, shared, etc.
    details = db.Column(db.Text, nullable=True)  # JSON details about the action
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    collection = db.relationship(
        "Collection",
        backref=db.backref(
            "activities",
            lazy="dynamic",
            order_by="CollectionActivity.created_at.desc()",
        ),
    )

    # NEW: Collection Permission model for granular team permissions


class CollectionPermission(db.Model):
    __tablename__ = "collection_permissions"

    id = db.Column(UUIDType, primary_key=True, default=lambda: str(uuid.uuid4()))
    collection_id = db.Column(UUIDType, db.ForeignKey("collections.id"), nullable=False)
    user_id = db.Column(UUIDType, db.ForeignKey("users.id"), nullable=False)
    permission_type = db.Column(db.String(20), nullable=False)  # view, edit, admin
    granted_by = db.Column(UUIDType, db.ForeignKey("users.id"))
    granted_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)

    # Relationships

    granter = db.relationship("User", foreign_keys=[granted_by])

    def is_expired(self):
        """Check if permission has expired"""
        return self.expires_at and datetime.utcnow() > self.expires_at

    def to_dict(self):
        return {
            "id": self.id,
            "collection_id": self.collection_id,
            "user_id": self.user_id,
            "permission_type": self.permission_type,
            "granted_by": self.granted_by,
            "granted_at": self.granted_at.isoformat() if self.granted_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_expired": self.is_expired(),
        }
