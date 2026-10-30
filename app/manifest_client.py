"""Fetches the official manifest record for a shipping ID (mock table or external API, with cache)."""

import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import Settings
from .matcher import ocr_key, shipping_key
from .models import ManifestCache, MockManifest
from .schemas import ManifestRecord

log = logging.getLogger(__name__)

# Maps OUR field name -> key path in the external API's JSON. Adjust this when the real API is known.
# Dotted paths are supported, e.g. "consignor.name".
FIELD_MAP = {
    "shipping_id": "shipping_id",
    "sender": "sender",
    "receiver": "receiver",
    "destination": "destination",
    "weight_kg": "weight_kg",
    "hazard_labels": "hazard_labels",
}


class ManifestUnavailable(Exception):
    """External API failed and there is no cached record to fall back on."""


def _dig(data: dict, path: str):
    for part in path.split("."):
        if not isinstance(data, dict):
            return None
        data = data.get(part)
    return data


def map_record(raw: dict) -> ManifestRecord:
    mapped = {ours: _dig(raw, theirs) for ours, theirs in FIELD_MAP.items()}
    if isinstance(mapped["hazard_labels"], str):
        mapped["hazard_labels"] = [h for h in mapped["hazard_labels"].split(",") if h.strip()]
    mapped["hazard_labels"] = mapped["hazard_labels"] or []
    return ManifestRecord(**mapped)


async def _fetch_http(shipping_id: str, cfg: Settings) -> dict | None:
    url = cfg.manifest_api_url.format(shipping_id=shipping_id)
    headers = {"Accept": "application/json"}
    if cfg.manifest_api_token:
        headers["Authorization"] = f"Bearer {cfg.manifest_api_token}"
    async with httpx.AsyncClient(timeout=cfg.manifest_timeout_s) as client:
        for attempt in range(2):
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                log.warning("manifest API attempt %d failed for %s: %s", attempt + 1, shipping_id, exc)
    raise ManifestUnavailable(shipping_id)


def _aware(dt: datetime) -> datetime:
    # SQLite drops tzinfo; Postgres keeps it.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def get_manifest(session: AsyncSession, shipping_id: str, cfg: Settings) -> tuple[ManifestRecord | None, str]:
    """Returns (record, or None if the ID is unknown; source), source being mock | api | cache | stale-cache."""
    key = shipping_key(shipping_id)

    if cfg.manifest_provider == "mock":
        row = await session.get(MockManifest, key)
        if row is None:
            # OCR may have misread confusable characters (O/0, I/1...); the matcher then reports the ID as uncertain.
            target = ocr_key(shipping_id)
            rows = (await session.scalars(select(MockManifest))).all()
            row = next((r for r in rows if ocr_key(r.shipping_key) == target), None)
        return (map_record(row.data) if row else None), "mock"

    cached = await session.get(ManifestCache, key)
    now = datetime.now(timezone.utc)
    if cached and now - _aware(cached.fetched_at) < timedelta(seconds=cfg.manifest_cache_ttl_s):
        return (map_record(cached.data) if cached.data else None), "cache"

    try:
        raw = await _fetch_http(shipping_id, cfg)
    except ManifestUnavailable:
        if cached and cached.data:
            return map_record(cached.data), "stale-cache"
        raise

    if cached:
        cached.data, cached.fetched_at = raw, now
    else:
        session.add(ManifestCache(shipping_key=key, data=raw, fetched_at=now))
    await session.commit()
    return (map_record(raw) if raw else None), "api"
