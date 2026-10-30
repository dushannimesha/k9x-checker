# K9-X Parcel Verification Backend

Real-time label/manifest check for **Project K9-X** (Security domain, App B).
The robot reads a parcel label using OCR and posts the shipping ID and label details to this API. The backend
looks up the official manifest record, compares the two field by field, stores the inspection in
PostgreSQL, tells the robot whether to halt and flag the parcel, and pushes the result to a live dashboard.

```
Robot (OCR)  ──POST /api/scan──▶  FastAPI ──▶ manifest provider (external API | mock table)
                                     │            └── cached in manifest_cache
                                     ├─▶ matcher (field-by-field verdict)
                                     ├─▶ PostgreSQL (inspections)
                                     └─▶ WebSocket /ws/live ──▶ dashboard
```

## Verdicts

| Field | Rule |
|---|---|
| shipping_id | exact after normalising case/spaces/dashes; equal only after fixing OCR-confusable chars (O/0, I/1, S/5…) is reported as *uncertain* |
| sender, receiver, destination | fuzzy `token_sort_ratio` ≥ 85 = match, 70–85 = uncertain, below that = mismatch |
| weight_kg | within ±`WEIGHT_TOLERANCE_PCT` (default 5 %) |
| hazard_labels | a hazard label on the parcel that the manifest does not declare is always a **critical mismatch**; a declared hazard the robot didn't see is uncertain |
| low OCR confidence | below `MIN_OCR_CONFIDENCE`, text and weight mismatches are downgraded to uncertain |

Overall result: `MATCH` · `PARTIAL` (something uncertain or not read) · `MISMATCH` · `NOT_FOUND` (ID not in manifest).
`halt` is `true` for anything except `MATCH`.

## API

All write endpoints need the header `X-API-Key` (one of `ROBOT_API_KEYS`). Interactive docs: `/docs`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/scan` | Robot submits a label scan, gets the verdict |
| GET | `/api/inspections?limit=&status=` | Recent inspections |
| GET | `/api/inspections/{id}` | One inspection with the scan, manifest and field breakdown |
| GET | `/api/stats` | Counts per status |
| GET | `/api/manifest/lookup/{shipping_id}` | What the manifest provider returns (debug) |
| GET/POST | `/api/manifest/mock` | List or add demo manifest records |
| WS | `/ws/live` | Live stream of new inspections |

Scan payload:

```json
{
  "robot_id": "k9x-01",
  "shipping_id": "LK-2026-000103",
  "sender": "Lanka Batteries PLC",
  "receiver": "Volt Traders FZE, Dubai",
  "destination": "Dubai, UAE",
  "weight_kg": 18.0,
  "hazard_labels": ["UN3480", "CLASS 9"],
  "ocr_confidence": 0.94,
  "image_url": null,
  "captured_at": "2026-10-30T09:15:00Z"
}
```

## Connecting the real manifest API

1. In `.env` set `MANIFEST_PROVIDER=http`, `MANIFEST_API_URL=https://…/shipments/{shipping_id}` and `MANIFEST_API_TOKEN=…`
   (sent as `Authorization: Bearer …`).
2. If the API's JSON uses different field names, edit `FIELD_MAP` in `app/manifest_client.py` (dotted paths allowed,
   e.g. `"sender": "consignor.name"`).
3. `scripts/run.sh restart`. Records are cached for `MANIFEST_CACHE_TTL_S`; if the API goes down, the last cached
   record is used (`manifest_source: stale-cache`).

## Running on tesla

```bash
ssh jump-box
cd ~/k9x-checker
scripts/pg.sh init          # first time only: user-space Postgres on 127.0.0.1:5433, writes .env
scripts/run.sh start        # API + dashboard on 127.0.0.1:8077
```

Later: `scripts/pg.sh start|stop|status|psql`, `scripts/run.sh start|stop|restart|status|logs`.
Postgres and the API don't start on their own after a server reboot, so run both `start` commands again.

Open the dashboard from your laptop through an SSH tunnel:

```bash
ssh -N -L 8077:127.0.0.1:8077 jump-box
# then browse http://localhost:8077
```

Demo traffic: `API_KEY=<key> scripts/sample_scans.sh`

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```
Tests use a temporary SQLite file and the mock manifest, so they don't need Postgres.
