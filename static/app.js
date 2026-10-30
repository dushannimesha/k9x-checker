const rowsEl = document.getElementById("rows");
const emptyEl = document.getElementById("empty");
const detailEl = document.getElementById("detail");
const connEl = document.getElementById("conn");
const inspections = new Map();
let selectedId = null;

const esc = (v) => String(v ?? "—").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (v) => (Array.isArray(v) ? (v.length ? v.join(", ") : "none") : v);
const time = (iso) => new Date(iso).toLocaleTimeString();

function rowHtml(i) {
  return `<td>${i.inspection_id}</td><td>${time(i.created_at)}</td><td>${esc(i.robot_id)}</td>
    <td>${esc(i.shipping_id)}</td><td><span class="badge ${i.status}">${i.status.replace("_", " ")}</span></td>
    <td>${(i.score * 100).toFixed(0)}%</td>`;
}

function addRow(i, isNew) {
  inspections.set(i.inspection_id, i);
  const tr = document.createElement("tr");
  tr.dataset.id = i.inspection_id;
  tr.innerHTML = rowHtml(i);
  if (isNew) { tr.classList.add("new"); rowsEl.prepend(tr); } else rowsEl.append(tr);
  emptyEl.hidden = true;
}

function showDetail(id) {
  selectedId = id;
  document.querySelectorAll("tbody tr").forEach((tr) => tr.classList.toggle("sel", +tr.dataset.id === id));
  const i = inspections.get(id);
  if (!i) return;
  const fields = i.fields.length
    ? `<table class="cmp"><thead><tr><th>Field</th><th>Robot read</th><th>Manifest</th><th></th></tr></thead><tbody>
        ${i.fields.map((f) => `<tr><td>${esc(f.field)}</td><td>${esc(fmt(f.scanned))}</td><td>${esc(fmt(f.expected))}</td>
          <td><span class="badge ${f.status}">${f.status}</span>${f.note ? `<div class="note">${esc(f.note)}</div>` : ""}</td></tr>`).join("")}
      </tbody></table>`
    : `<p class="muted">Shipping ID <b>${esc(i.shipping_id)}</b> was not found in the manifest.</p>`;
  detailEl.innerHTML = `<h2>Inspection #${i.inspection_id} <span class="badge ${i.status}">${i.status.replace("_", " ")}</span></h2>
    <p class="muted">${esc(i.robot_id)} · ${new Date(i.created_at).toLocaleString()} · source: ${esc(i.manifest_source)}
      · OCR confidence ${esc(i.scan?.ocr_confidence)}</p>
    ${i.halt ? `<div class="halt">Robot told to halt and flag this parcel</div>` : ""}
    ${fields}`;
}

rowsEl.addEventListener("click", (e) => {
  const tr = e.target.closest("tr");
  if (tr) showDetail(+tr.dataset.id);
});

async function refreshStats() {
  const s = await fetch("api/stats").then((r) => r.json());
  for (const k of ["total", "MATCH", "PARTIAL", "MISMATCH", "NOT_FOUND"]) document.getElementById(`s-${k}`).textContent = s[k];
}

async function loadInitial() {
  const list = await fetch("api/inspections?limit=100").then((r) => r.json());
  rowsEl.innerHTML = "";
  list.forEach((i) => addRow(i, false));
  emptyEl.hidden = list.length > 0;
  refreshStats();
}

function connect() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}${location.pathname.replace(/[^/]*$/, "")}ws/live`);
  let ping;
  ws.onopen = () => {
    connEl.textContent = "live"; connEl.className = "conn on";
    ping = setInterval(() => ws.send("ping"), 25000);
    loadInitial();
  };
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type !== "inspection") return;
    addRow(msg.data, true);
    refreshStats();
    if (selectedId === null) showDetail(msg.data.inspection_id);
  };
  ws.onclose = () => {
    clearInterval(ping);
    connEl.textContent = "offline – reconnecting"; connEl.className = "conn off";
    setTimeout(connect, 2000);
  };
}

const form = document.getElementById("test-form");
const formMsg = document.getElementById("form-msg");
try { form.api_key.value = localStorage.getItem("k9x_api_key") || ""; } catch {}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = new FormData(form);
  try { localStorage.setItem("k9x_api_key", f.get("api_key")); } catch {}
  const num = (v) => (v === "" ? null : Number(v));
  const body = {
    robot_id: "dashboard-test",
    shipping_id: f.get("shipping_id"),
    sender: f.get("sender") || null,
    receiver: f.get("receiver") || null,
    destination: f.get("destination") || null,
    weight_kg: num(f.get("weight_kg")),
    ocr_confidence: num(f.get("ocr_confidence")) ?? 1,
    hazard_labels: f.get("hazard_labels").split(",").map((s) => s.trim()).filter(Boolean),
    captured_at: new Date().toISOString(),
  };
  const res = await fetch("api/scan", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": f.get("api_key") },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  formMsg.textContent = res.ok ? `→ ${data.status} (score ${(data.score * 100).toFixed(0)}%)` : `Error ${res.status}: ${JSON.stringify(data.detail)}`;
  if (res.ok) showDetail(data.inspection_id);
});

connect();
