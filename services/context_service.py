"""
context_service.py
------------------
Read-only query layer over the local context SQLite database built by
scripts/build_context_db.py.

All public functions return plain dicts so they are trivially JSON-serialisable
and safe to pass as tool outputs to the LangGraph agent.
"""

from __future__ import annotations

import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

DB_PATH = Path(__file__).parent.parent / "data" / "context.db"


@lru_cache(maxsize=1)
def _conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Context DB not found at {DB_PATH}. "
            "Run: python scripts/build_context_db.py"
        )
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# ── Public types ──────────────────────────────────────────────────────────────

class BoroughContext(TypedDict):
    borough: str
    crime_total_24m: int
    crime_by_major_category: dict[str, int]
    imd_avg_score: float | None
    imd_avg_rank: float | None
    imd_pct_most_deprived: float | None
    deprivation_band: str       # low / medium / high / very_high


class LSOAContext(TypedDict):
    lsoa_code: str
    lsoa_name: str
    borough: str
    crime_total_24m: int
    imd_score: float | None
    imd_decile: int | None
    idaopi_score: float | None  # deprivation affecting older people


# ── Borough queries ───────────────────────────────────────────────────────────

def get_borough_context(borough: str) -> BoroughContext | None:
    """Return aggregated crime and deprivation context for a borough name."""
    conn = _conn()

    crime_rows = conn.execute(
        "SELECT major_category, SUM(total_24m) AS total FROM crime_by_borough "
        "WHERE borough = ? GROUP BY major_category",
        (borough,),
    ).fetchall()

    if not crime_rows:
        return None

    crime_by_cat = {r["major_category"]: r["total"] for r in crime_rows}
    crime_total = sum(crime_by_cat.values())

    dep = conn.execute(
        "SELECT imd_avg_score, imd_avg_rank, imd_pct_most_deprived "
        "FROM deprivation_by_borough WHERE borough = ?",
        (borough,),
    ).fetchone()

    imd_score = dep["imd_avg_score"] if dep else None
    imd_rank = dep["imd_avg_rank"] if dep else None
    imd_pct = dep["imd_pct_most_deprived"] if dep else None

    # Band based on % LSOAs in most deprived 10% nationally
    if imd_pct is None:
        band = "unknown"
    elif imd_pct >= 0.3:
        band = "very_high"
    elif imd_pct >= 0.15:
        band = "high"
    elif imd_pct >= 0.05:
        band = "medium"
    else:
        band = "low"

    return BoroughContext(
        borough=borough,
        crime_total_24m=crime_total,
        crime_by_major_category=crime_by_cat,
        imd_avg_score=imd_score,
        imd_avg_rank=imd_rank,
        imd_pct_most_deprived=imd_pct,
        deprivation_band=band,
    )


def list_boroughs() -> list[str]:
    """Return all borough names present in the crime table."""
    rows = _conn().execute(
        "SELECT DISTINCT borough FROM crime_by_borough ORDER BY borough"
    ).fetchall()
    return [r["borough"] for r in rows]


# ── LSOA queries ──────────────────────────────────────────────────────────────

def get_lsoa_context(lsoa_code: str) -> LSOAContext | None:
    """Return crime and deprivation context for a specific LSOA code."""
    conn = _conn()

    crime_rows = conn.execute(
        "SELECT borough, SUM(total_24m) AS total FROM crime_by_lsoa "
        "WHERE lsoa_code = ? GROUP BY borough",
        (lsoa_code,),
    ).fetchall()

    if not crime_rows:
        return None

    borough = crime_rows[0]["borough"]
    crime_total = sum(r["total"] for r in crime_rows)

    dep = conn.execute(
        "SELECT lsoa_name, imd_score, imd_decile, idaopi_score "
        "FROM deprivation_by_lsoa WHERE lsoa_code = ?",
        (lsoa_code,),
    ).fetchone()

    return LSOAContext(
        lsoa_code=lsoa_code,
        lsoa_name=dep["lsoa_name"] if dep else "",
        borough=borough,
        crime_total_24m=crime_total,
        imd_score=dep["imd_score"] if dep else None,
        imd_decile=dep["imd_decile"] if dep else None,
        idaopi_score=dep["idaopi_score"] if dep else None,
    )


# ── Normalisation helpers (used by scoring_service) ──────────────────────────

# Approximate London-wide 24-month totals derived from the dataset for normalisation.
# These are updated each time the DB is rebuilt via compute_london_averages().
_CACHE: dict[str, float] = {}


def compute_london_averages() -> dict[str, float]:
    """Compute London-wide average crime and deprivation for normalisation."""
    if _CACHE:
        return _CACHE

    conn = _conn()

    avg_crime = conn.execute(
        "SELECT AVG(borough_total) FROM ("
        "  SELECT borough, SUM(total_24m) AS borough_total "
        "  FROM crime_by_borough GROUP BY borough"
        ")"
    ).fetchone()[0] or 1.0

    avg_imd = conn.execute(
        "SELECT AVG(imd_avg_score) FROM deprivation_by_borough"
    ).fetchone()[0] or 20.0

    _CACHE["avg_crime_24m"] = avg_crime
    _CACHE["avg_imd_score"] = avg_imd
    return _CACHE
