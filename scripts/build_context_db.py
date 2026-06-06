#!/usr/bin/env python3
"""
build_context_db.py
-------------------
Ingest London Datastore files into a local SQLite context database used by
the ticket prioritisation scoring service and agent tools.

Tables created:
  crime_by_borough     — 24-month crime totals per borough + category (exy3m)
  crime_by_lsoa        — 24-month crime totals per LSOA + category (exy3m)
  deprivation_by_lsoa  — IMD 2019 scores per LSOA (2l15g)
  deprivation_by_borough — IMD 2019 borough summary (2l15g)

Usage:
  python scripts/build_context_db.py
  python scripts/build_context_db.py --data-dir ./data/london --out ./data/context.db
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

DATA_DIR_DEFAULT = Path(__file__).parent.parent / "data" / "london"
OUT_DEFAULT = Path(__file__).parent.parent / "data" / "context.db"

# Monthly columns in the crime CSVs — the 24 month period covered by the dataset
_MONTH_COLS_COUNT = 24


def _month_cols(headers: list[str]) -> list[str]:
    """Return columns that look like YYYYMM (6-digit numeric)."""
    return [h for h in headers if h.isdigit() and len(h) == 6]


# ── Crime ────────────────────────────────────────────────────────────────────

def load_crime_borough(data_dir: Path, conn: sqlite3.Connection) -> None:
    path = data_dir / "exy3m" / "exy3m__MPS Borough Level Crime (most recent 24 months).csv"
    print(f"  Loading {path.name}")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crime_by_borough (
            borough       TEXT NOT NULL,
            major_category TEXT NOT NULL,
            minor_category TEXT NOT NULL,
            total_24m     INTEGER NOT NULL
        )
    """)
    conn.execute("DELETE FROM crime_by_borough")

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        month_cols = _month_cols(headers)
        rows = []
        for row in reader:
            total = sum(int(row[m] or 0) for m in month_cols if row.get(m))
            rows.append((
                row["LookUp_BoroughName"].strip(),
                row["MajorText"].strip(),
                row["MinorText"].strip(),
                total,
            ))
    conn.executemany(
        "INSERT INTO crime_by_borough VALUES (?,?,?,?)", rows
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_crime_borough ON crime_by_borough(borough)")
    print(f"    {len(rows)} rows")


def load_crime_lsoa(data_dir: Path, conn: sqlite3.Connection) -> None:
    path = data_dir / "exy3m" / "exy3m__MPS LSOA Level Crime (most recent 24 months).csv"
    print(f"  Loading {path.name}")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crime_by_lsoa (
            lsoa_code      TEXT NOT NULL,
            lsoa_name      TEXT NOT NULL,
            borough        TEXT NOT NULL,
            major_category TEXT NOT NULL,
            minor_category TEXT NOT NULL,
            total_24m      INTEGER NOT NULL
        )
    """)
    conn.execute("DELETE FROM crime_by_lsoa")

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        month_cols = _month_cols(headers)
        rows = []
        for row in reader:
            total = sum(int(row[m] or 0) for m in month_cols if row.get(m))
            rows.append((
                row["LSOA Code"].strip(),
                row["LSOA Name"].strip(),
                row["Borough"].strip(),
                row["Major Category"].strip(),
                row["Minor Category"].strip(),
                total,
            ))
    conn.executemany(
        "INSERT INTO crime_by_lsoa VALUES (?,?,?,?,?,?)", rows
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_crime_lsoa_code ON crime_by_lsoa(lsoa_code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_crime_lsoa_borough ON crime_by_lsoa(borough)")
    print(f"    {len(rows)} rows")


# ── Deprivation ───────────────────────────────────────────────────────────────

def load_deprivation(data_dir: Path, conn: sqlite3.Connection) -> None:
    import pandas as pd

    path = data_dir / "2l15g" / "2l15g__ID 2019 for London.xlsx"
    print(f"  Loading {path.name}")

    # LSOA-level IMD scores
    conn.execute("""
        CREATE TABLE IF NOT EXISTS deprivation_by_lsoa (
            lsoa_code  TEXT PRIMARY KEY,
            lsoa_name  TEXT,
            borough    TEXT,
            imd_score  REAL,
            imd_rank   INTEGER,
            imd_decile INTEGER,
            income_score     REAL,
            employment_score REAL,
            idaopi_score     REAL
        )
    """)
    conn.execute("DELETE FROM deprivation_by_lsoa")

    imd = pd.read_excel(path, sheet_name="IMD 2019")
    idaopi = pd.read_excel(path, sheet_name="IDACI and IDAOPI")[
        ["LSOA code (2011)", "Income Deprivation Affecting Older People (IDAOPI) Score (rate)"]
    ].rename(columns={
        "LSOA code (2011)": "lsoa_code",
        "Income Deprivation Affecting Older People (IDAOPI) Score (rate)": "idaopi_score",
    })

    imd = imd.rename(columns={
        "LSOA code (2011)": "lsoa_code",
        "LSOA name (2011)": "lsoa_name",
        "Local Authority District name (2019)": "borough",
        "Index of Multiple Deprivation (IMD) Score": "imd_score",
        "Index of Multiple Deprivation (IMD) Rank (where 1 is most deprived)": "imd_rank",
        "Index of Multiple Deprivation (IMD) Decile (where 1 is most deprived 10% of LSOAs)": "imd_decile",
        "Income Score (rate)": "income_score",
        "Employment Score (rate)": "employment_score",
    })
    merged = imd[["lsoa_code","lsoa_name","borough","imd_score","imd_rank","imd_decile","income_score","employment_score"]].merge(
        idaopi, on="lsoa_code", how="left"
    )
    merged.to_sql("deprivation_by_lsoa", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dep_lsoa ON deprivation_by_lsoa(lsoa_code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dep_borough ON deprivation_by_lsoa(borough)")
    print(f"    {len(merged)} rows")

    # Borough-level summary
    conn.execute("""
        CREATE TABLE IF NOT EXISTS deprivation_by_borough (
            borough                 TEXT PRIMARY KEY,
            imd_avg_rank            REAL,
            imd_avg_score           REAL,
            imd_pct_most_deprived   REAL
        )
    """)
    conn.execute("DELETE FROM deprivation_by_borough")

    bsummary = pd.read_excel(path, sheet_name="Borough summary measures").rename(columns={
        "Local Authority District name (2019)": "borough",
        "IMD - Average rank ": "imd_avg_rank",
        "IMD - Average score ": "imd_avg_score",
        "IMD - Proportion of LSOAs in most deprived 10% nationally ": "imd_pct_most_deprived",
    })[["borough","imd_avg_rank","imd_avg_score","imd_pct_most_deprived"]]
    bsummary.to_sql("deprivation_by_borough", conn, if_exists="replace", index=False)
    print(f"    {len(bsummary)} borough rows")


# ── Main ──────────────────────────────────────────────────────────────────────

def build(data_dir: Path, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"Building context DB: {out}")
    with sqlite3.connect(out) as conn:
        print("Crime — borough level")
        load_crime_borough(data_dir, conn)
        print("Crime — LSOA level")
        load_crime_lsoa(data_dir, conn)
        print("Deprivation (IMD 2019)")
        load_deprivation(data_dir, conn)
        conn.commit()
    print(f"\nDone → {out}")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Build local context SQLite DB from London Datastore files.")
    p.add_argument("--data-dir", type=Path, default=DATA_DIR_DEFAULT)
    p.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = p.parse_args(argv)
    build(args.data_dir, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
