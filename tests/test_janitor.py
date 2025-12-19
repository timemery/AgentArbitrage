import pytest
import sqlite3
import os
from datetime import datetime, timedelta, timezone
from keepa_deals.janitor import _clean_stale_deals_logic
from unittest.mock import patch

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_deals.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE deals (id INTEGER PRIMARY KEY, ASIN TEXT, last_seen_utc TIMESTAMP)")
    conn.commit()
    conn.close()
    return str(db_file)

def test_janitor_cleans_old_deals(temp_db):
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Insert deals
    now = datetime.now(timezone.utc)
    old_time = (now - timedelta(hours=25)).isoformat()
    new_time = (now - timedelta(hours=1)).isoformat()

    cursor.execute("INSERT INTO deals (ASIN, last_seen_utc) VALUES ('OLD_DEAL', ?)", (old_time,))
    cursor.execute("INSERT INTO deals (ASIN, last_seen_utc) VALUES ('NEW_DEAL', ?)", (new_time,))
    conn.commit()
    conn.close()

    # Patch DB_PATH in janitor
    with patch('keepa_deals.janitor.DB_PATH', temp_db):
        deleted = _clean_stale_deals_logic(grace_period_hours=24)

    assert deleted == 1

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT ASIN FROM deals")
    rows = cursor.fetchall()
    conn.close()

    asins = [r[0] for r in rows]
    assert 'NEW_DEAL' in asins
    assert 'OLD_DEAL' not in asins
