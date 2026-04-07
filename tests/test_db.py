import sqlite3
from pathlib import Path

import pytest

import database


@pytest.fixture
def temp_db(tmp_path: Path):
    """Provide a temporary database file for tests."""
    db_file = tmp_path / "test_db.sqlite"
    database.init_db(db_file)
    yield db_file
    if db_file.exists():
        db_file.unlink()


def test_save_and_retrieve(temp_db):
    """Test saving a scan and retrieving history."""
    scan_id = database.save_scan(
        source="Upload",
        metal_pct=40.5,
        non_metal_pct=50.0,
        background_pct=9.5,
        dominant="Plastic",
        db_path=temp_db
    )
    assert scan_id > 0
    
    history = database.get_history(db_path=temp_db)
    assert len(history) == 1
    assert history[0]["metal_pct"] == 40.5
    assert history[0]["dominant"] == "Plastic"


def test_get_stats_empty(temp_db):
    """Test gathering stats on an empty database."""
    stats = database.get_stats(db_path=temp_db)
    assert stats["total_scans"] == 0
    assert stats["avg_metal"] is None


def test_get_stats_populated(temp_db):
    """Test stats aggregations."""
    database.save_scan("S1", 10, 80, 10, db_path=temp_db)
    database.save_scan("S2", 50, 40, 10, db_path=temp_db)
    
    stats = database.get_stats(db_path=temp_db)
    assert stats["total_scans"] == 2
    assert stats["avg_metal"] == 30.0 # (10+50)/2
    assert stats["max_metal"] == 50.0
