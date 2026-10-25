"""Isolated synthetic service state, never the CoverageGuard hospital-side store."""

import json, os, sqlite3, secrets
from pathlib import Path
from fastapi import Request
from starlette.responses import JSONResponse


class SimulatorState:
    def __init__(self, name, initial):
        self.path = Path(
            os.environ.get(
                f"{name.upper()}_STATE_PATH",
                str(Path(__file__).resolve().parents[1] / "data" / f"{name}.sqlite3"),
            )
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initial = initial

    def read(self):
        with sqlite3.connect(self.path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY, payload TEXT)"
            )
            row = db.execute("SELECT payload FROM state WHERE id=1").fetchone()
            if not row:
                data = self.initial()
                db.execute("INSERT INTO state VALUES (1,?)", (json.dumps(data),))
                return data
            return json.loads(row[0])

    def write(self, data):
        self.read()
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE state SET payload=? WHERE id=1", (json.dumps(data),))


async def local_admin(request: Request, call_next):
    if request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
        return JSONResponse(
            {"detail": "Synthetic simulator is local only."}, status_code=403
        )
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        expected = os.environ.get("SIMULATOR_ADMIN_TOKEN")
        if expected and not secrets.compare_digest(
            expected, request.headers.get("x-simulator-token", "")
        ):
            return JSONResponse(
                {"detail": "Simulator admin token required."}, status_code=403
            )
    return await call_next(request)
