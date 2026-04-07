"""
database.py — SQLite persistence + Excel export for scan history
"""
from __future__ import annotations

import io
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from contextlib import closing
from typing import Any, Dict, List, Optional

import pandas as pd

from config import DB_PATH

logger = logging.getLogger(__name__)


# ── Schema ─────────────────────────────────────────────────────────────────────
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS scans (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT    NOT NULL,
    source        TEXT    NOT NULL,   -- 'IP Camera' | 'Upload'
    filename      TEXT,
    image_path    TEXT,
    metal_pct     REAL    NOT NULL,
    non_metal_pct REAL    NOT NULL,
    background_pct REAL   NOT NULL,
    dominant      TEXT,
    model_used    TEXT,
    confidence    TEXT,
    notes         TEXT
)
"""


def _get_conn(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    """Create tables if they don't exist."""
    with closing(_get_conn(db_path)) as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()
    logger.info("Database initialised at %s", db_path)


def save_scan(
    source: str,
    metal_pct: float,
    non_metal_pct: float,
    background_pct: float,
    dominant: str = "",
    model_used: str = "",
    confidence: str = "",
    notes: str = "",
    filename: str = "",
    image_path: str = "",
    db_path: Path = DB_PATH,
) -> int:
    """Insert a new scan record and return its ID."""
    init_db(db_path)
    ts = datetime.now().isoformat(sep=" ", timespec="seconds")
    with closing(_get_conn(db_path)) as conn:
        cur = conn.execute(
            """INSERT INTO scans
               (timestamp, source, filename, image_path,
                metal_pct, non_metal_pct, background_pct,
                dominant, model_used, confidence, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ts, source, filename, image_path,
                metal_pct, non_metal_pct, background_pct,
                dominant, model_used, confidence, notes,
            ),
        )
        conn.commit()
        logger.info("Saved scan id=%s source=%s", cur.lastrowid, source)
        return cur.lastrowid


def get_history(
    limit: int = 100,
    offset: int = 0,
    db_path: Path = DB_PATH,
) -> List[Dict[str, Any]]:
    """Return scan records as list of dicts, newest first."""
    init_db(db_path)
    with closing(_get_conn(db_path)) as conn:
        rows = conn.execute(
            "SELECT * FROM scans ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def get_stats(db_path: Path = DB_PATH) -> Dict[str, Any]:
    """Return aggregate statistics for the dashboard."""
    init_db(db_path)
    with closing(_get_conn(db_path)) as conn:
        row = conn.execute(
            """SELECT
                COUNT(*)              AS total_scans,
                AVG(metal_pct)        AS avg_metal,
                AVG(non_metal_pct)    AS avg_non_metal,
                AVG(background_pct)   AS avg_background,
                MAX(metal_pct)        AS max_metal,
                MIN(metal_pct)        AS min_metal
               FROM scans"""
        ).fetchone()
    return dict(row) if row else {}


def get_total_count(db_path: Path = DB_PATH) -> int:
    init_db(db_path)
    with closing(_get_conn(db_path)) as conn:
        return conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0]


def delete_scan(scan_id: int, db_path: Path = DB_PATH) -> None:
    init_db(db_path)
    with closing(_get_conn(db_path)) as conn:
        conn.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
        conn.commit()


def clear_all(db_path: Path = DB_PATH) -> None:
    init_db(db_path)
    with closing(_get_conn(db_path)) as conn:
        conn.execute("DELETE FROM scans")
        conn.commit()


def export_to_excel(db_path: Path = DB_PATH) -> bytes:
    """Return an in-memory xlsx file as bytes."""
    records = get_history(limit=10_000, db_path=db_path)
    if not records:
        raise ValueError("No records to export.")
    df = pd.DataFrame(records)
    df.rename(
        columns={
            "id": "ID",
            "timestamp": "Timestamp",
            "source": "Source",
            "filename": "Filename",
            "metal_pct": "Metal %",
            "non_metal_pct": "Non-Metal %",
            "background_pct": "Background %",
            "dominant": "Dominant Material",
            "model_used": "AI Model",
            "confidence": "Confidence",
            "notes": "Notes",
            "image_path": "Image Path",
        },
        inplace=True,
    )
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Scan History")
        ws = writer.sheets["Scan History"]
        for col in ws.columns:
            max_len = max(len(str(c.value or "")) for c in col) + 4
            ws.column_dimensions[col[0].column_letter].width = min(max_len, 40)
    return buf.getvalue()
