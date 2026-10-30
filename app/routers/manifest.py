from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_api_key
from ..config import get_settings
from ..db import get_session
from ..manifest_client import ManifestUnavailable, get_manifest
from ..matcher import shipping_key
from ..models import MockManifest
from ..schemas import ManifestRecord

router = APIRouter(prefix="/api/manifest", tags=["manifest"], dependencies=[Depends(require_api_key)])


@router.get("/mock", response_model=list[ManifestRecord])
async def list_mock(session: AsyncSession = Depends(get_session)):
    rows = (await session.scalars(select(MockManifest).order_by(MockManifest.shipping_key))).all()
    return [ManifestRecord(**r.data) for r in rows]


@router.post("/mock", response_model=ManifestRecord)
async def upsert_mock(record: ManifestRecord, session: AsyncSession = Depends(get_session)):
    await session.merge(MockManifest(shipping_key=shipping_key(record.shipping_id), data=record.model_dump()))
    await session.commit()
    return record


@router.get("/lookup/{shipping_id}", response_model=ManifestRecord)
async def lookup(shipping_id: str, session: AsyncSession = Depends(get_session)):
    """Debug: what the configured provider returns for this ID."""
    try:
        record, _ = await get_manifest(session, shipping_id, get_settings())
    except ManifestUnavailable:
        raise HTTPException(status_code=503, detail="manifest API unavailable")
    if not record:
        raise HTTPException(status_code=404, detail="shipping ID not in manifest")
    return record
