import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select

from .config import get_settings
from .db import SessionLocal, init_db
from .matcher import shipping_key
from .models import MockManifest
from .routers import manifest, scan
from .ws import live_feed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
ROOT = Path(__file__).resolve().parent.parent


async def seed_mock_manifest() -> None:
    async with SessionLocal() as session:
        if await session.scalar(select(func.count()).select_from(MockManifest)):
            return
        for rec in json.loads((Path(__file__).parent / "seed_manifest.json").read_text()):
            session.add(MockManifest(shipping_key=shipping_key(rec["shipping_id"]), data=rec))
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    if get_settings().manifest_provider == "mock":
        await seed_mock_manifest()
    yield


app = FastAPI(title="K9-X Parcel Verification", version="0.1.0", lifespan=lifespan)
app.include_router(scan.router)
app.include_router(manifest.router)


@app.get("/api/health")
async def health():
    return {"ok": True, "manifest_provider": get_settings().manifest_provider}


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await live_feed.connect(ws)
    try:
        while True:
            await ws.receive_text()  # dashboard keep-alive pings
    except WebSocketDisconnect:
        live_feed.disconnect(ws)


app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="static")
