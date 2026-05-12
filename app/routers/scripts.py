"""API routes for script CRUD, review, and risk checking."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models.db import Script
from app.models.schemas import ScriptCreate, ScriptResponse, ScriptUpdate, RiskReport
from app.services.risk_checker import check_sql

router = APIRouter(prefix="/api/scripts", tags=["scripts"])


@router.get("", response_model=List[ScriptResponse], summary="List all scripts")
async def list_scripts(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    dialect: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Script).order_by(desc(Script.created_at)).offset(skip).limit(limit)
    if dialect:
        q = q.where(Script.dialect == dialect)
    if status:
        q = q.where(Script.status == status)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("", response_model=ScriptResponse, status_code=201, summary="Create a script manually")
async def create_script(payload: ScriptCreate, db: AsyncSession = Depends(get_db)):
    risk = check_sql(payload.content)
    script = Script(
        **payload.model_dump(),
        risk_level=risk.overall_level,
        risk_details=risk.summary,
    )
    db.add(script)
    await db.commit()
    await db.refresh(script)
    return script


@router.get("/{script_id}", response_model=ScriptResponse, summary="Get a single script")
async def get_script(script_id: int, db: AsyncSession = Depends(get_db)):
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    return script


@router.patch("/{script_id}", response_model=ScriptResponse, summary="Update a script")
async def update_script(script_id: int, payload: ScriptUpdate, db: AsyncSession = Depends(get_db)):
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(script, k, v)
    if "content" in update_data:
        risk = check_sql(script.content)
        script.risk_level = risk.overall_level
        script.risk_details = risk.summary
    await db.commit()
    await db.refresh(script)
    return script


@router.delete("/{script_id}", status_code=204, summary="Delete a script")
async def delete_script(script_id: int, db: AsyncSession = Depends(get_db)):
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    await db.delete(script)
    await db.commit()


@router.post("/{script_id}/check", response_model=RiskReport, summary="Re-run risk check on a script")
async def recheck_script(script_id: int, db: AsyncSession = Depends(get_db)):
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    report = check_sql(script.content)
    script.risk_level = report.overall_level
    script.risk_details = report.summary
    await db.commit()
    return report


@router.post("/{script_id}/approve", response_model=ScriptResponse, summary="Approve a script")
async def approve_script(script_id: int, db: AsyncSession = Depends(get_db)):
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    script.status = "approved"
    await db.commit()
    await db.refresh(script)
    return script


@router.post("/{script_id}/reject", response_model=ScriptResponse, summary="Reject a script")
async def reject_script(script_id: int, db: AsyncSession = Depends(get_db)):
    script = await db.get(Script, script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    script.status = "rejected"
    await db.commit()
    await db.refresh(script)
    return script
