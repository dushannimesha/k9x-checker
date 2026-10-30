#!/usr/bin/env bash
# Sends demo scans the way the robot would. Usage: API_KEY=... scripts/sample_scans.sh [base_url]
set -euo pipefail
BASE="${1:-http://127.0.0.1:8077}"
KEY="${API_KEY:?set API_KEY to one of ROBOT_API_KEYS}"

send() {
  echo "--- $1"
  curl -s -X POST "$BASE/api/scan" -H "Content-Type: application/json" -H "X-API-Key: $KEY" -d "$2" \
    | python3 -c 'import json,sys; r=json.load(sys.stdin); print(r["status"], r["score"], "halt" if r["halt"] else "ok", [f["field"]+"="+f["status"] for f in r["fields"] if f["status"]!="match"])'
}

send "exact match" '{"robot_id":"k9x-01","shipping_id":"LK-2026-000101","sender":"Ceylon Tea Exports Ltd, Colombo","receiver":"Harrods Food Hall, London","destination":"London, UK","weight_kg":12.5,"ocr_confidence":0.97}'
send "OCR misread ID (O for 0)" '{"robot_id":"k9x-01","shipping_id":"LK-2O26-OOO1O2","sender":"Kandy Gems & Jewellery","receiver":"Tiffany Distribution, New York","destination":"New York, USA","weight_kg":2.1,"ocr_confidence":0.8}'
send "undeclared hazard" '{"robot_id":"k9x-01","shipping_id":"LK-2026-000104","sender":"Galle Spice Co","receiver":"Gewurzhaus GmbH, Berlin","destination":"Berlin, Germany","weight_kg":6.75,"hazard_labels":["CLASS 1"],"ocr_confidence":0.9}'
send "wrong receiver + overweight" '{"robot_id":"k9x-01","shipping_id":"LK-2026-000106","sender":"Negombo Garments","receiver":"Unknown Imports LLC","destination":"Karachi, Pakistan","weight_kg":31,"ocr_confidence":0.93}'
send "not in manifest" '{"robot_id":"k9x-01","shipping_id":"LK-2026-999999","ocr_confidence":0.9}'
