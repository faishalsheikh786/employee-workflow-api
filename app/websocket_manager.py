import json
from collections import defaultdict

from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, employee_id: int, websocket: WebSocket):
        await websocket.accept()
        self.connections[employee_id].add(websocket)

    def disconnect(self, employee_id: int, websocket: WebSocket):
        self.connections[employee_id].discard(websocket)
        if not self.connections[employee_id]:
            self.connections.pop(employee_id, None)

    async def send(self, employee_id: int, payload: dict):
        dead: list[WebSocket] = []
        for websocket in list(self.connections.get(employee_id, set())):
            try:
                await websocket.send_text(json.dumps(payload))
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(employee_id, websocket)

manager = ConnectionManager()
