"""Builds a SQLite file from the real tokyo-anaba spots/areas dataset,
standing in for a second, differently-shaped heterogeneous source (a
lightweight embedded DB, as opposed to source_realestate's full RDB).
"""

import json
import os
import sqlite3

DATA_DIR = os.path.dirname(__file__)

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS areas (
    name TEXT PRIMARY KEY,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    congestion REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS spots (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_en TEXT,
    category TEXT NOT NULL,
    source TEXT NOT NULL,
    address TEXT,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    area TEXT NOT NULL REFERENCES areas(name),
    congestion REAL NOT NULL,
    distance_to_area_center_km REAL
);
"""


def build_sqlite_source() -> None:
    sqlite_path = os.environ["SQLITE_PATH"]
    with open(os.path.join(DATA_DIR, "areas.json"), encoding="utf-8") as f:
        areas = json.load(f)
    with open(os.path.join(DATA_DIR, "spots.json"), encoding="utf-8") as f:
        spots = json.load(f)

    os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.executescript(CREATE_TABLES_SQL)
        conn.executemany(
            "INSERT OR REPLACE INTO areas (name, lat, lon, congestion) VALUES (?, ?, ?, ?)",
            [(a["name"], a["lat"], a["lon"], a["congestion"]) for a in areas],
        )
        conn.executemany(
            """
            INSERT OR REPLACE INTO spots
                (id, name, name_en, category, source, address, lat, lon,
                 area, congestion, distance_to_area_center_km)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    s["id"], s["name"], s["nameEn"], s["category"], s["source"],
                    s["address"], s["lat"], s["lon"], s["area"], s["congestion"],
                    s["distanceToAreaCenterKm"],
                )
                for s in spots
            ],
        )
        conn.commit()
        print(f"Built {sqlite_path}: {len(areas)} areas, {len(spots)} spots.")
    finally:
        conn.close()


if __name__ == "__main__":
    build_sqlite_source()
