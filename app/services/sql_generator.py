"""SQL generator — orchestrates LLM calls, risk checking, and persistence."""
from __future__ import annotations
from typing import Optional, List, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import Script, ConversationMessage
from app.models.schemas import GenerateRequest, GenerateResponse, ClarificationRequest
from app.services import llm_service
from app.services.risk_checker import check_sql, lint_sql

_MAX_TITLE_LEN = 80


def _make_title(prompt: str) -> str:
    """Truncate a prompt to a suitable script title."""
    return prompt[:_MAX_TITLE_LEN] + ("…" if len(prompt) > _MAX_TITLE_LEN else "")


async def _load_history(session: AsyncSession, session_id: str) -> List[Dict[str, str]]:
    result = await session.execute(
        select(ConversationMessage)
        .where(ConversationMessage.session_id == session_id)
        .order_by(ConversationMessage.created_at)
    )
    rows = result.scalars().all()
    return [{"role": r.role, "content": r.content} for r in rows]


async def _save_messages(session: AsyncSession, session_id: str, messages: List[Dict[str, str]]) -> None:
    for msg in messages:
        session.add(ConversationMessage(session_id=session_id, role=msg["role"], content=msg["content"]))
    await session.commit()


async def generate(request: GenerateRequest, db: AsyncSession) -> GenerateResponse:
    """Generate SQL from the given natural-language request."""
    session_id = request.session_id or llm_service.new_session_id()
    history = await _load_history(db, session_id)

    result = await llm_service.generate_sql(
        prompt=request.prompt,
        dialect=request.dialect,
        script_type=request.script_type,
        conversation_history=history,
    )

    # Persist conversation turn
    new_messages = [
        {"role": "user", "content": request.prompt},
    ]
    if result["needs_clarification"]:
        new_messages.append({"role": "assistant", "content": "CLARIFY: " + result["clarification_question"]})
        await _save_messages(db, session_id, new_messages)
        return GenerateResponse(
            session_id=session_id,
            sql="",
            needs_clarification=True,
            clarification_question=result["clarification_question"],
        )

    sql = result["sql"]
    new_messages.append({"role": "assistant", "content": sql})
    await _save_messages(db, session_id, new_messages)

    # Risk-check the generated SQL
    risk_report = check_sql(sql)
    lint_warnings = lint_sql(sql)
    if lint_warnings:
        from app.models.schemas import RiskItem
        for w in lint_warnings:
            risk_report.items.append(RiskItem(level="low", rule="LINT", message=w))

    # Persist script
    script = Script(
        title=_make_title(request.prompt),
        description=request.prompt,
        dialect=request.dialect,
        script_type=request.script_type,
        content=sql,
        prompt=request.prompt,
        risk_level=risk_report.overall_level,
        risk_details=risk_report.summary,
    )
    db.add(script)
    await db.commit()
    await db.refresh(script)

    return GenerateResponse(
        session_id=session_id,
        script_id=script.id,
        sql=sql,
        needs_clarification=False,
        risk_report=risk_report,
    )


async def continue_conversation(request: ClarificationRequest, db: AsyncSession) -> GenerateResponse:
    """Continue a multi-turn conversation with a user's clarification."""
    history = await _load_history(db, request.session_id)
    if not history:
        raise ValueError("Session not found.")

    # Determine dialect/type from first user message context (default fallback)
    dialect = "mysql"
    script_type = "ddl"

    result = await llm_service.generate_sql(
        prompt=request.message,
        dialect=dialect,
        script_type=script_type,
        conversation_history=history,
    )

    new_messages = [{"role": "user", "content": request.message}]

    if result["needs_clarification"]:
        new_messages.append({"role": "assistant", "content": "CLARIFY: " + result["clarification_question"]})
        await _save_messages(db, request.session_id, new_messages)
        return GenerateResponse(
            session_id=request.session_id,
            sql="",
            needs_clarification=True,
            clarification_question=result["clarification_question"],
        )

    sql = result["sql"]
    new_messages.append({"role": "assistant", "content": sql})
    await _save_messages(db, request.session_id, new_messages)

    risk_report = check_sql(sql)

    script = Script(
        title=_make_title(request.message),
        description=request.message,
        dialect=dialect,
        script_type=script_type,
        content=sql,
        prompt=request.message,
        risk_level=risk_report.overall_level,
        risk_details=risk_report.summary,
    )
    db.add(script)
    await db.commit()
    await db.refresh(script)

    return GenerateResponse(
        session_id=request.session_id,
        script_id=script.id,
        sql=sql,
        needs_clarification=False,
        risk_report=risk_report,
    )
