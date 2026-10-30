import asyncio

from fastapi import WebSocket


class LiveFeed:
    """Pushes every new verification result to connected dashboards."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def broadcast(self, message: dict) -> None:
        async def send(ws: WebSocket) -> None:
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(ws)

        await asyncio.gather(*(send(ws) for ws in list(self._clients)))


live_feed = LiveFeed()
