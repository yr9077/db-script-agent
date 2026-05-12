"""Pydantic schemas for request/response validation."""
from __future__ import annotations
from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Script schemas
# ---------------------------------------------------------------------------

class ScriptBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    dialect: Literal["mysql", "postgresql", "sqlite"] = "mysql"
    script_type: Literal["ddl", "dml", "maintenance"] = "ddl"
    content: str = Field(..., min_length=1)
    prompt: str = ""


class ScriptCreate(ScriptBase):
    pass


class ScriptUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    status: Optional[Literal["pending", "approved", "rejected"]] = None


class RiskItem(BaseModel):
    level: Literal["safe", "low", "medium", "high", "critical"]
    rule: str
    message: str
    line: Optional[int] = None


class RiskReport(BaseModel):
    overall_level: Literal["safe", "low", "medium", "high", "critical"] = "safe"
    items: List[RiskItem] = []
    summary: str = ""


class ScriptResponse(ScriptBase):
    id: int
    status: Literal["pending", "approved", "rejected"]
    risk_level: Literal["safe", "low", "medium", "high", "critical"]
    risk_details: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Generation schemas
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Natural language description of the SQL needed")
    dialect: Literal["mysql", "postgresql", "sqlite"] = "mysql"
    script_type: Literal["ddl", "dml", "maintenance"] = "ddl"
    session_id: Optional[str] = None  # for multi-turn conversations


class ClarificationRequest(BaseModel):
    session_id: str
    message: str = Field(..., min_length=1)


class GenerateResponse(BaseModel):
    session_id: str
    script_id: Optional[int] = None
    sql: str
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    risk_report: Optional[RiskReport] = None


# ---------------------------------------------------------------------------
# Conversation
# ---------------------------------------------------------------------------

class MessageResponse(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}
