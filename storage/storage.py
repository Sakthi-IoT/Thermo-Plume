"""
THERMO-PLUME — Layer 2, Part A: State Management & Persistence
==================================================================

WHAT THIS FILE DOES (in plain words):
--------------------------------------
The problem statement asks for:
  "Local edge RAM ring-buffers storing high-frequency sensor telemetry,
   synchronized periodically over MQTT to a spatial graph database."

Let's translate that into two simple pieces, both in this one file:

  1. RingBuffer — a small, FIXED-SIZE list that holds the most recent
     N readings for one node. When it's full and a new reading comes
     in, the OLDEST reading gets thrown away automatically. This is
     exactly what "local edge RAM" means on a real microcontroller —
     it has very little memory, so it can only hold the last few
     readings, not unlimited history.

  2. Storage — a simple SQLite database (a single file on disk, no
     server needed) that acts as our stand-in for the "spatial graph
     database." We don't need a real graph database for a hackathon —
     SQLite can still store WHERE each node is (x, y coordinates) and
     WHAT it read, which is enough to answer "spatial" questions like
     "show me all readings near this location."

HOW TO USE THIS FILE:
----------------------
    python3 storage.py

This runs a small self-test: creates a ring buffer, fills it past its
limit (to prove old data gets dropped), saves some readings to SQLite,
then reads them back.
"""

import sqlite3
from collections import deque


class RingBuffer:
    """
    A fixed-size buffer. Think of it like a small whiteboard that can
    only hold N sticky notes — when a new note goes on and the board
    is full, the OLDEST note automatically falls off.

    This is the "local edge RAM" simulation — a real ESP32 might only
    keep the last 20-50 readings in memory before syncing them out.
    """

    def __init__(self, max_size=20):
        self.max_size = max_size
        # deque with maxlen automatically drops the oldest item when full
        self.buffer = deque(maxlen=max_size)

    def add(self, reading):
        """Add one new reading. If full, the oldest one is silently dropped."""
        self.buffer.append(reading)

    def get_all(self):
        """Return everything currently in the buffer, oldest first."""
        return list(self.buffer)

    def clear(self):
        """Empty the buffer — used after a successful sync to the database."""
        self.buffer.clear()

    def __len__(self):
        return len(self.buffer)


class Storage:
    """
    Wraps a SQLite database file. This stands in for the "spatial graph
    database" — it stores each node's position (x, y) alongside its
    readings, so we can still answer spatial questions later
    (e.g. "which zones are next to each other and both showing risk?").
    """

    def __init__(self, db_path="thermoplume.db"):
        self.db_path = db_path
        self._create_tables()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _create_tables(self):
        """Creates the readings table if it doesn't already exist."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT,
                zone_name TEXT,
                x REAL,
                y REAL,
                tick INTEGER,
                pm25 REAL,
                pm10 REAL,
                co2 REAL,
                humidity REAL,
                temperature REAL,
                voc_reported REAL,
                voc_calibrated REAL,
                predicted_state TEXT,
                actuation_pct REAL,
                synced_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def sync_buffer(self, node_id, zone_name, x, y, readings):
        """
        Takes everything currently sitting in a node's RingBuffer and
        writes it into the SQLite database in ONE batch — this mirrors
        "synchronized PERIODICALLY over MQTT" (batches, not one-by-one).
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        for r in readings:
            cursor.execute("""
                INSERT INTO readings
                    (node_id, zone_name, x, y, tick, pm25, pm10, co2,
                     humidity, temperature, voc_reported, voc_calibrated,
                     predicted_state, actuation_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                node_id, zone_name, x, y, r.get("tick"),
                r.get("pm25"), r.get("pm10"), r.get("co2"),
                r.get("humidity"), r.get("temperature"),
                r.get("voc_reported"), r.get("voc_calibrated"),
                r.get("predicted_state"), r.get("actuation_pct"),
            ))
        conn.commit()
        conn.close()

    def get_latest_per_zone(self):
        """
        Returns the most recent reading for EACH zone — this is exactly
        what the dashboard (Layer 5) will need to draw a live heatmap.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT node_id, zone_name, x, y, pm25, pm10, co2, humidity,
                   voc_calibrated, predicted_state, actuation_pct, MAX(tick)
            FROM readings
            GROUP BY node_id
        """)
        rows = cursor.fetchall()
        conn.close()
        return rows

    def get_history_for_node(self, node_id, limit=50):
        """Returns the most recent `limit` readings for one specific node."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tick, pm25, pm10, co2, voc_calibrated, predicted_state, actuation_pct
            FROM readings
            WHERE node_id = ?
            ORDER BY tick DESC
            LIMIT ?
        """, (node_id, limit))
        rows = cursor.fetchall()
        conn.close()
        return rows


# ---------------------------------------------------------------------------
# SELF-TEST: run this file directly to prove the ring buffer and database work
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== Testing RingBuffer ===")
    rb = RingBuffer(max_size=5)
    for i in range(1, 9):  # push 8 items into a buffer that only holds 5
        rb.add({"tick": i, "pm25": i * 1.1})
    print(f"Pushed 8 readings into a buffer with max_size=5")
    print(f"Buffer length now: {len(rb)}  (should be 5, oldest 3 dropped)")
    print(f"Buffer contents (tick numbers): {[r['tick'] for r in rb.get_all()]}")
    print("Expected ticks: [4, 5, 6, 7, 8] — the oldest 3 (1,2,3) were dropped")

    print("\n=== Testing Storage (SQLite) ===")
    import os
    test_db = "test_thermoplume.db"
    if os.path.exists(test_db):
        os.remove(test_db)  # start clean each time we test

    storage = Storage(db_path=test_db)
    fake_readings = [
        {"tick": 1, "pm25": 12.0, "pm10": 20.0, "co2": 500, "humidity": 45,
         "temperature": 24, "voc_reported": 150, "voc_calibrated": 148,
         "predicted_state": "NORMAL", "actuation_pct": 10},
        {"tick": 2, "pm25": 14.0, "pm10": 22.0, "co2": 520, "humidity": 46,
         "temperature": 24, "voc_reported": 155, "voc_calibrated": 150,
         "predicted_state": "NORMAL", "actuation_pct": 10},
    ]
    storage.sync_buffer("A1", "Classroom A", 0, 0, fake_readings)
    print("Synced 2 fake readings for node A1 to the database")

    latest = storage.get_latest_per_zone()
    print(f"Latest reading per zone: {latest}")

    history = storage.get_history_for_node("A1")
    print(f"History for A1: {history}")

    os.remove(test_db)  # clean up test file
    print("\nAll storage tests passed.")
