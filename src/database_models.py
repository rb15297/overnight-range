"""
Database models for overnight range analysis.
Minimal ORM models for SQLAlchemy with custom DateTime handling for SQLite.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, DateTime, TypeDecorator
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SQLiteDateTime(TypeDecorator):
    """Custom DateTime type that stores as string in SQLite with full precision"""
    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'sqlite':
            return dialect.type_descriptor(String)
        else:
            return dialect.type_descriptor(DateTime)

    def process_bind_param(self, value, dialect):
        if value is not None:
            if dialect.name == 'sqlite':
                # Store as ISO format string with timezone info
                if isinstance(value, datetime):
                    # If naive datetime, assume UTC
                    if value.tzinfo is None:
                        value = value.replace(tzinfo=timezone.utc)
                    return value.isoformat()
                return str(value)
            else:
                return value
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if dialect.name == 'sqlite':
                # Parse ISO format string back to datetime
                if isinstance(value, str):
                    # First try fromisoformat (handles ISO format with timezone offsets)
                    try:
                        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        # Ensure timezone-aware (UTC)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        return dt
                    except (ValueError, AttributeError):
                        # Fall back to strptime for formats without timezone offsets
                        try:
                            dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S.%f')
                        except ValueError:
                            try:
                                dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                dt = datetime.strptime(value, '%Y-%m-%d')
                        # Add UTC timezone to parsed naive datetimes
                        return dt.replace(tzinfo=timezone.utc)
                # If already a datetime object, ensure it's timezone-aware
                elif isinstance(value, datetime):
                    if value.tzinfo is None:
                        return value.replace(tzinfo=timezone.utc)
                    return value
                return value
            else:
                return value
        return value


class RawBar1Min(Base):
    """Raw 1-minute bars from historical data source"""
    __tablename__ = 'raw_bars_1min'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(SQLiteDateTime, index=True)
    symbol = Column(String(10), index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
