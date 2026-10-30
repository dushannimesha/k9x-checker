"""Field-by-field comparison of a robot label scan against the official manifest."""

import re

from rapidfuzz import fuzz

from .config import Settings
from .schemas import FieldResult, ManifestRecord, ScanIn

# Characters OCR commonly confuses; both sides are mapped to the same canonical char.
_OCR_CONFUSABLE = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2"})


def shipping_key(raw: str) -> str:
    """Upper-case alphanumerics only: 'lk-2026 00123' -> 'LK202600123'."""
    return re.sub(r"[^A-Z0-9]", "", raw.upper())


def ocr_key(raw: str) -> str:
    return shipping_key(raw).translate(_OCR_CONFUSABLE)


def _norm_text(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.lower())).strip()


def compare_shipping_id(scanned: str, expected: str) -> FieldResult:
    if shipping_key(scanned) == shipping_key(expected):
        return FieldResult(field="shipping_id", scanned=scanned, expected=expected, status="match", similarity=1.0)
    if ocr_key(scanned) == ocr_key(expected):
        return FieldResult(
            field="shipping_id", scanned=scanned, expected=expected, status="uncertain", similarity=0.9,
            note="matches only after correcting OCR-confusable characters",
        )
    sim = fuzz.ratio(shipping_key(scanned), shipping_key(expected)) / 100
    return FieldResult(field="shipping_id", scanned=scanned, expected=expected, status="mismatch", similarity=sim)


def compare_text(field: str, scanned: str | None, expected: str | None, cfg: Settings, low_conf: bool) -> FieldResult:
    if not expected:
        return FieldResult(field=field, scanned=scanned, expected=expected, status="match", similarity=1.0,
                           note="not present in manifest")
    if not scanned:
        return FieldResult(field=field, scanned=scanned, expected=expected, status="missing", similarity=0.0,
                           note="not read from label")
    sim = fuzz.token_sort_ratio(_norm_text(scanned), _norm_text(expected))
    if sim >= cfg.name_match_threshold:
        status, note = "match", ""
    elif sim >= cfg.name_uncertain_threshold:
        status, note = "uncertain", "close but not exact"
    elif low_conf:
        status, note = "uncertain", "differs, but OCR confidence is low"
    else:
        status, note = "mismatch", ""
    return FieldResult(field=field, scanned=scanned, expected=expected, status=status, similarity=sim / 100, note=note)


def compare_weight(scanned: float | None, expected: float | None, cfg: Settings, low_conf: bool) -> FieldResult:
    if expected is None:
        return FieldResult(field="weight_kg", scanned=scanned, expected=expected, status="match", similarity=1.0,
                           note="not present in manifest")
    if scanned is None:
        return FieldResult(field="weight_kg", scanned=scanned, expected=expected, status="missing", similarity=0.0,
                           note="not read from label")
    diff_pct = abs(scanned - expected) / expected * 100 if expected else (0.0 if scanned == 0 else 100.0)
    sim = max(0.0, 1 - diff_pct / 100)
    if diff_pct <= cfg.weight_tolerance_pct:
        return FieldResult(field="weight_kg", scanned=scanned, expected=expected, status="match", similarity=sim)
    status = "uncertain" if low_conf else "mismatch"
    return FieldResult(field="weight_kg", scanned=scanned, expected=expected, status=status, similarity=sim,
                       note=f"off by {diff_pct:.1f}% (tolerance {cfg.weight_tolerance_pct:g}%)")


def compare_hazards(scanned: list[str], expected: list[str]) -> FieldResult:
    s = {h.strip().upper() for h in scanned if h.strip()}
    e = {h.strip().upper() for h in expected if h.strip()}
    base = dict(field="hazard_labels", scanned=sorted(s), expected=sorted(e))
    undeclared, unseen = s - e, e - s
    if undeclared:
        # A hazard marking on the parcel that the manifest doesn't declare is always critical.
        return FieldResult(**base, status="mismatch", similarity=0.0,
                           note=f"undeclared hazard: {', '.join(sorted(undeclared))}")
    if unseen:
        return FieldResult(**base, status="uncertain", similarity=len(s) / len(e),
                           note=f"declared but not seen on label: {', '.join(sorted(unseen))}")
    return FieldResult(**base, status="match", similarity=1.0)


def compare(scan: ScanIn, manifest: ManifestRecord, cfg: Settings) -> tuple[str, float, list[FieldResult]]:
    low_conf = scan.ocr_confidence < cfg.min_ocr_confidence
    fields = [
        compare_shipping_id(scan.shipping_id, manifest.shipping_id),
        compare_text("sender", scan.sender, manifest.sender, cfg, low_conf),
        compare_text("receiver", scan.receiver, manifest.receiver, cfg, low_conf),
        compare_text("destination", scan.destination, manifest.destination, cfg, low_conf),
        compare_weight(scan.weight_kg, manifest.weight_kg, cfg, low_conf),
        compare_hazards(scan.hazard_labels, manifest.hazard_labels),
    ]
    statuses = {f.status for f in fields}
    if "mismatch" in statuses:
        overall = "MISMATCH"
    elif statuses & {"uncertain", "missing"}:
        overall = "PARTIAL"
    else:
        overall = "MATCH"
    score = round(sum(f.similarity for f in fields) / len(fields), 3)
    return overall, score, fields
