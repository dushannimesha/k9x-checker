from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

FieldStatus = Literal["match", "uncertain", "mismatch", "missing"]
OverallStatus = Literal["MATCH", "PARTIAL", "MISMATCH", "NOT_FOUND"]


class ScanIn(BaseModel):
    """What the robot read from the parcel label (App B OCR output)."""

    robot_id: str = Field(min_length=1, max_length=64)
    shipping_id: str = Field(min_length=1, max_length=64)
    sender: str | None = None
    receiver: str | None = None
    destination: str | None = None
    weight_kg: float | None = Field(default=None, ge=0)
    hazard_labels: list[str] = []
    ocr_confidence: float = Field(default=1.0, ge=0, le=1)
    image_url: str | None = None
    captured_at: datetime | None = None


class ManifestRecord(BaseModel):
    """Official record, normalised to our field names whatever the source API returns."""

    shipping_id: str
    sender: str | None = None
    receiver: str | None = None
    destination: str | None = None
    weight_kg: float | None = None
    hazard_labels: list[str] = []


class FieldResult(BaseModel):
    field: str
    scanned: str | float | list[str] | None
    expected: str | float | list[str] | None
    status: FieldStatus
    similarity: float
    note: str = ""


class VerificationResult(BaseModel):
    inspection_id: int
    shipping_id: str
    status: OverallStatus
    score: float
    halt: bool  # robot should stop and flag the parcel
    manifest_source: str | None
    fields: list[FieldResult]
    created_at: datetime
