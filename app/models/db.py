"""SQLAlchemy database models."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Script(Base):
    __tablename__ = "scripts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    dialect = Column(String(50), nullable=False, default="mysql")
    script_type = Column(String(50), nullable=False, default="ddl")  # ddl / dml / maintenance
    content = Column(Text, nullable=False)
    status = Column(
        SAEnum("pending", "approved", "rejected", name="script_status"),
        default="pending",
    )
    risk_level = Column(
        SAEnum("safe", "low", "medium", "high", "critical", name="risk_level"),
        default="safe",
    )
    risk_details = Column(Text, default="")
    prompt = Column(Text, default="")  # original NL prompt
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class ConversationMessage(Base):
    """Tracks multi-turn LLM conversations for a script generation session."""

    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), index=True, nullable=False)
    role = Column(String(20), nullable=False)  # system / user / assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utcnow)
