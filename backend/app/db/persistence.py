"""Transactional SQLite snapshots with queryable policy identity and revision columns.

The domain store remains the small prototype's unit-of-work. Persisted rows preserve
all legacy models and new catalog/document/sync records in a single transaction.
"""

import json
import os
import sqlite3


def write_snapshot(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=15) as db:
        os.chmod(path, 0o600)
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute(
            "CREATE TABLE IF NOT EXISTS records (kind TEXT, id TEXT, insurer_id TEXT, policy_id TEXT, version TEXT, payload TEXT NOT NULL, PRIMARY KEY(kind,id))"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS insurer_policy ON records(insurer_id,policy_id,version)"
        )
        db.execute("DELETE FROM records")
        for kind, value in data.items():
            entries = (
                value.items()
                if isinstance(value, dict) and kind not in {"settings"}
                else [("_", value)]
            )
            for key, item in entries:
                meta = item if isinstance(item, dict) else {}
                db.execute(
                    "INSERT INTO records VALUES (?,?,?,?,?,?)",
                    (
                        kind,
                        str(key),
                        meta.get("insurer_id"),
                        meta.get("policy_id") or meta.get("rule_id"),
                        str(meta.get("version") or meta.get("revision") or ""),
                        json.dumps(item, default=str),
                    ),
                )


def read_snapshot(path):
    with sqlite3.connect(path, timeout=15) as db:
        rows = db.execute("SELECT kind,id,payload FROM records").fetchall()
    data = {}
    for kind, key, payload in rows:
        item = json.loads(payload)
        if key == "_":
            data[kind] = item
        else:
            data.setdefault(kind, {})[key] = item
    return data
