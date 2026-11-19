"""Immutable, question-owned outcome records. Use one database per dashboard."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path


def record(path, question, horizon, rule, outcome):
    """Freeze one outcome per versioned target, including its supporting evidence."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    key = (question, horizon, rule["version"])
    payload = json.dumps({"rule": rule, **outcome}, sort_keys=True, allow_nan=False)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("""CREATE TABLE IF NOT EXISTS outcomes (
            question TEXT, horizon TEXT, version INTEGER, payload TEXT,
            recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (question, horizon, version))""")
        db.execute("INSERT OR IGNORE INTO outcomes (question, horizon, version, payload) VALUES (?, ?, ?, ?)", (*key, payload))
        stored, = db.execute("SELECT payload FROM outcomes WHERE question=? AND horizon=? AND version=?", key).fetchone()
        if stored != payload:
            raise ValueError(f"Conflicting resolution for {key}")


def snapshot(path):
    if not Path(path).exists():
        return {}
    with closing(sqlite3.connect(path)) as db:
        return {(q, h, v): dict(json.loads(payload), recorded_at=stamp) for q, h, v, payload, stamp in
                db.execute("SELECT question, horizon, version, payload, recorded_at FROM outcomes")}


def correct(path, question, horizon, rule, outcome, *, previous, reason):
    """Replace exactly the decision the reviewer inspected. Keep its full lineage."""
    if not reason.strip() or not previous:
        raise ValueError("A correction requires the previous decision and a reason")
    key = (question, horizon, rule["version"])
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT payload, recorded_at FROM outcomes WHERE question=? AND horizon=? AND version=?",
                         key).fetchone()
        if not row or dict(json.loads(row[0]), recorded_at=row[1]) != previous or previous["rule"] != rule:
            raise ValueError("The prior resolution or its rule changed")
        payload = {"rule": rule, **outcome, "supersedes": previous, "correction_reason": reason}
        db.execute("UPDATE outcomes SET payload=?, recorded_at=CURRENT_TIMESTAMP WHERE question=? AND horizon=? AND version=?",
                   (json.dumps(payload, sort_keys=True, allow_nan=False), *key))
