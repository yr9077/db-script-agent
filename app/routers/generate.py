"""API routes for SQL generation and multi-turn conversation."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.schemas import GenerateRequest, GenerateResponse, ClarificationRequest
from app.services import sql_generator

router = APIRouter(prefix="/api/generate", tags=["generate"])


@router.post("", response_model=GenerateResponse, summary="Generate SQL from natural language")
async def generate_sql(request: GenerateRequest, db: AsyncSession = Depends(get_db)):
    """Accept a natural language prompt and return generated SQL with a risk report."""
    return await sql_generator.generate(request, db)


@router.post("/clarify", response_model=GenerateResponse, summary="Continue a multi-turn generation conversation")
async def clarify(request: ClarificationRequest, db: AsyncSession = Depends(get_db)):
    """Provide clarification in an ongoing conversation and get updated SQL."""
    try:
        return await sql_generator.continue_conversation(request, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
