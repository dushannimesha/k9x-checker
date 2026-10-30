from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_api_key
from ..config import get_settings
from ..db import get_session
from ..manifest_client import ManifestUnavailable, get_manifest
from ..matcher import compare
from ..models import Inspection
from ..schemas import FieldResult, ScanIn, VerificationResult
from ..ws import live_feed

router = APIRouter(prefix="/api", tags=["inspections"])


def to_result(row: Inspection) -> VerificationResult:
    return VerificationResult(
        inspection_id=row.id,
        shipping_id=row.shipping_id,
        status=row.status,
        score=row.score,
        halt=row.status != "MATCH",
        manifest_source=row.manifest_source,
        fields=[FieldResult(**f) for f in row.fields],
        created_at=row.created_at,
    )


def to_detail(row: Inspection) -> dict:
    return {
        **to_result(row).model_dump(mode="json"),
        "robot_id": row.robot_id,
        "scan": row.scan,
        "manifest": row.manifest,
    }


@router.post("/scan", response_model=VerificationResult, dependencies=[Depends(require_api_key)])
async def submit_scan(scan: ScanIn, session: AsyncSession = Depends(get_session)):
    """Robot posts what it read from a label; returns the verdict against the manifest."""
    cfg = get_settings()
    try:
        manifest, source = await get_manifest(session, scan.shipping_id, cfg)
    except ManifestUnavailable:
        raise HTTPException(status_code=503, detail="manifest API unavailable and no cached record")

    if manifest is None:
        status, score, fields = "NOT_FOUND", 0.0, []
    else:
        status, score, fields = compare(scan, manifest, cfg)

    row = Inspection(
        robot_id=scan.robot_id,
        shipping_id=scan.shipping_id,
        status=status,
        score=score,
        manifest_source=source,
        scan=scan.model_dump(mode="json"),
        manifest=manifest.model_dump(mode="json") if manifest else None,
        fields=[f.model_dump(mode="json") for f in fields],
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)

    await live_feed.broadcast({"type": "inspection", "data": to_detail(row)})
    return to_result(row)


@router.get("/inspections")
async def list_inspections(
    limit: int = Query(50, ge=1, le=500),
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    q = select(Inspection).order_by(Inspection.id.desc()).limit(limit)
    if status:
        q = q.where(Inspection.status == status.upper())
    return [to_detail(r) for r in (await session.scalars(q)).all()]


@router.get("/inspections/{inspection_id}")
async def get_inspection(inspection_id: int, session: AsyncSession = Depends(get_session)):
    row = await session.get(Inspection, inspection_id)
    if not row:
        raise HTTPException(status_code=404, detail="inspection not found")
    return to_detail(row)


@router.get("/stats")
async def stats(session: AsyncSession = Depends(get_session)):
    rows = await session.execute(select(Inspection.status, func.count()).group_by(Inspection.status))
    counts = dict(rows.all())
    statuses = ("MATCH", "PARTIAL", "MISMATCH", "NOT_FOUND")
    return {"total": sum(counts.values()), **{s: counts.get(s, 0) for s in statuses}}
