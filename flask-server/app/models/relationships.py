def setup_relationships():
    """Setup relationships between models after they're all defined"""
    from .user import User
    from .snippet import Snippet
    from .collection import Collection

    # Setup any additional relationships here if needed
