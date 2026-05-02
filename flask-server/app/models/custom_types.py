from sqlalchemy.types import TypeDecorator, String, JSON as SQLAlchemyJSON
import json
import uuid


class UUIDType(TypeDecorator):
    """Platform-independent UUID type.
    Uses String as storage, but converts to/from UUID objects."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif isinstance(value, uuid.UUID):
            return str(value)
        else:
            return str(uuid.UUID(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            return uuid.UUID(value)

    def __repr__(self):
        return "UUIDType()"


class JSONType(TypeDecorator):
    """Platform-independent JSON type.
    Uses String as storage, but converts to/from dicts/lists."""

    impl = SQLAlchemyJSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "sqlite":
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "sqlite" and isinstance(value, str):
            return json.loads(value)
        return value
