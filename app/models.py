from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Inspection(Base):
    """One robot label scan and the verdict reached against the manifest."""

    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    robot_id: Mapped[str] = mapped_column(String(64), index=True)
    shipping_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    score: Mapped[float] = mapped_column(Float)
    manifest_source: Mapped[str | None] = mapped_column(String(16))
    scan: Mapped[dict] = mapped_column(JSON)
    manifest: Mapped[dict | None] = mapped_column(JSON)
    fields: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class MockManifest(Base):
    """Demo manifest records used while MANIFEST_PROVIDER=mock."""

    __tablename__ = "mock_manifest"

    shipping_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


class ManifestCache(Base):
    """Last record fetched from the external manifest API, per shipping ID."""

    __tablename__ = "manifest_cache"

    shipping_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[dict | None] = mapped_column(JSON)  # None = API said "not found"
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
