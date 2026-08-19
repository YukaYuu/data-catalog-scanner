"""Loads the real chiyoda-bunkyo mansion-transaction dataset into a
Postgres "source" schema, standing in for one of the heterogeneous
systems a real data catalog would scan (an on-prem RDB, in Quollio's
world). Split into two tables on purpose so there's an actual foreign
key relationship for the scanner to discover, not one flat table.
"""

import os

import pandas as pd
import psycopg2
import psycopg2.extras

CSV_PATH = os.path.join(os.path.dirname(__file__), "merged_cleaned.csv")

CREATE_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS source_realestate;

CREATE TABLE IF NOT EXISTS source_realestate.ward_population (
    ward TEXT PRIMARY KEY,
    night_population INTEGER NOT NULL,
    day_population INTEGER NOT NULL,
    day_night_ratio NUMERIC NOT NULL
);

CREATE TABLE IF NOT EXISTS source_realestate.transactions (
    id SERIAL PRIMARY KEY,
    ward TEXT NOT NULL REFERENCES source_realestate.ward_population(ward),
    district TEXT,
    nearest_station TEXT,
    station_distance_min NUMERIC,
    price_total_yen BIGINT,
    floor_plan TEXT,
    area_sqm NUMERIC,
    built_year INTEGER,
    building_age_years NUMERIC,
    building_structure TEXT,
    transaction_year INTEGER NOT NULL,
    transaction_quarter INTEGER NOT NULL,
    price_per_sqm NUMERIC
);
"""


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = [
        "最寄駅距離_分",
        "取引価格（総額）",
        "面積（㎡）",
        "建築年_数値",
        "築年数",
        "㎡単価",
        "夜間人口",
        "昼間人口",
        "昼夜間人口比率",
        "取引年",
        "取引四半期",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_postgres_source() -> None:
    dsn = os.environ["POSTGRES_DSN"]
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
    df = _clean(df)

    ward_pop = (
        df[["区", "夜間人口", "昼間人口", "昼夜間人口比率"]]
        .dropna(subset=["区"])
        .drop_duplicates(subset=["区"])
    )

    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_SCHEMA_SQL)
            # This source gets rebuilt fresh on every seed run (compose
            # dependency resolution can legitimately re-run seed), so
            # start from empty rather than accumulating duplicates.
            cur.execute("TRUNCATE TABLE source_realestate.transactions")
            cur.execute(
                "TRUNCATE TABLE source_realestate.ward_population RESTART IDENTITY CASCADE"
            )

            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO source_realestate.ward_population
                    (ward, night_population, day_population, day_night_ratio)
                VALUES %s
                ON CONFLICT (ward) DO NOTHING
                """,
                [
                    (row["区"], int(row["夜間人口"]), int(row["昼間人口"]), row["昼夜間人口比率"])
                    for _, row in ward_pop.iterrows()
                ],
            )

            rows = [
                (
                    row["区"],
                    row.get("地区名") if pd.notna(row.get("地区名")) else None,
                    row.get("最寄駅：名称") if pd.notna(row.get("最寄駅：名称")) else None,
                    row["最寄駅距離_分"] if pd.notna(row["最寄駅距離_分"]) else None,
                    int(row["取引価格（総額）"]) if pd.notna(row["取引価格（総額）"]) else None,
                    row.get("間取り") if pd.notna(row.get("間取り")) else None,
                    row["面積（㎡）"] if pd.notna(row["面積（㎡）"]) else None,
                    int(row["建築年_数値"]) if pd.notna(row["建築年_数値"]) else None,
                    row["築年数"] if pd.notna(row["築年数"]) else None,
                    row.get("建物の構造") if pd.notna(row.get("建物の構造")) else None,
                    int(row["取引年"]),
                    int(row["取引四半期"]),
                    row["㎡単価"] if pd.notna(row["㎡単価"]) else None,
                )
                for _, row in df.dropna(subset=["区", "取引年", "取引四半期"]).iterrows()
            ]
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO source_realestate.transactions
                    (ward, district, nearest_station, station_distance_min,
                     price_total_yen, floor_plan, area_sqm, built_year,
                     building_age_years, building_structure,
                     transaction_year, transaction_quarter, price_per_sqm)
                VALUES %s
                """,
                rows,
            )
        conn.commit()
        print(f"Loaded {len(ward_pop)} wards and {len(rows)} transactions into source_realestate.")
    finally:
        conn.close()


if __name__ == "__main__":
    load_postgres_source()
