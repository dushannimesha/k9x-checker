from app.config import Settings
from app.matcher import compare, ocr_key, shipping_key
from app.schemas import ManifestRecord, ScanIn

CFG = Settings(_env_file=None)

MANIFEST = ManifestRecord(
    shipping_id="LK-2026-000103",
    sender="Lanka Batteries PLC",
    receiver="Volt Traders FZE, Dubai",
    destination="Dubai, UAE",
    weight_kg=18.0,
    hazard_labels=["UN3480", "CLASS 9"],
)


def scan(**overrides) -> ScanIn:
    base = dict(
        robot_id="k9x-01",
        shipping_id="LK-2026-000103",
        sender="Lanka Batteries PLC",
        receiver="Volt Traders FZE, Dubai",
        destination="Dubai, UAE",
        weight_kg=18.0,
        hazard_labels=["UN3480", "CLASS 9"],
        ocr_confidence=0.95,
    )
    return ScanIn(**{**base, **overrides})


def field(fields, name):
    return next(f for f in fields if f.field == name)


def test_keys_normalise():
    assert shipping_key(" lk-2026 000103 ") == "LK2026000103"
    assert ocr_key("LK-2O26-OOO1O3") == ocr_key("LK-2026-000103")


def test_exact_match():
    status, score, _ = compare(scan(), MANIFEST, CFG)
    assert status == "MATCH"
    assert score == 1.0


def test_formatting_differences_still_match():
    status, _, _ = compare(scan(shipping_id="lk 2026 000103", sender="LANKA BATTERIES plc.", hazard_labels=["class 9", "un3480"]), MANIFEST, CFG)
    assert status == "MATCH"


def test_ocr_confused_id_is_partial():
    status, _, fields = compare(scan(shipping_id="LK-2O26-OOO1O3"), MANIFEST, CFG)
    assert status == "PARTIAL"
    assert field(fields, "shipping_id").status == "uncertain"


def test_different_receiver_is_mismatch():
    status, _, fields = compare(scan(receiver="Unknown Imports LLC, Karachi"), MANIFEST, CFG)
    assert status == "MISMATCH"
    assert field(fields, "receiver").status == "mismatch"


def test_small_typo_in_name_matches():
    status, _, _ = compare(scan(sender="Lanka Baterries PLC"), MANIFEST, CFG)
    assert status == "MATCH"


def test_weight_outside_tolerance():
    status, _, fields = compare(scan(weight_kg=21.0), MANIFEST, CFG)
    assert status == "MISMATCH"
    assert "off by" in field(fields, "weight_kg").note


def test_weight_within_tolerance():
    assert compare(scan(weight_kg=18.5), MANIFEST, CFG)[0] == "MATCH"


def test_undeclared_hazard_is_critical_even_with_low_ocr_confidence():
    status, _, fields = compare(scan(hazard_labels=["UN3480", "CLASS 9", "CLASS 1"], ocr_confidence=0.3), MANIFEST, CFG)
    assert status == "MISMATCH"
    assert "CLASS 1" in field(fields, "hazard_labels").note


def test_declared_hazard_not_seen_is_partial():
    status, _, fields = compare(scan(hazard_labels=["UN3480"]), MANIFEST, CFG)
    assert status == "PARTIAL"
    assert field(fields, "hazard_labels").status == "uncertain"


def test_low_ocr_confidence_downgrades_text_mismatch():
    status, _, fields = compare(scan(receiver="Vxlt Trdrs", ocr_confidence=0.4), MANIFEST, CFG)
    assert status == "PARTIAL"
    assert field(fields, "receiver").status == "uncertain"


def test_unread_field_is_missing():
    status, _, fields = compare(scan(sender=None), MANIFEST, CFG)
    assert status == "PARTIAL"
    assert field(fields, "sender").status == "missing"
