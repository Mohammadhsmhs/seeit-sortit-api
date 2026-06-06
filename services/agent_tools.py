import logging
import os
from functools import lru_cache
from typing import TypedDict

import pandas as pd
import yaml
from langchain_core.tools import tool

from services.context_service import get_borough_context, get_lsoa_context, list_boroughs

logger = logging.getLogger(__name__)

ISSUE_TYPES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "issue_types.yaml")
DENSITY_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "density.csv")


class IssueType(TypedDict):
    slug: str
    label: str
    severity_hint: int


@lru_cache(maxsize=1)
def _load_locations() -> frozenset[str]:
    df = pd.read_csv(DENSITY_CSV_PATH)
    return frozenset(df["Location"].values)


@tool
def get_issue_taxonomy() -> list[IssueType]:
    """Returns the list of valid issue types for council reporting. Call this first before classifying any issue."""
    try:
        with open(ISSUE_TYPES_PATH) as f:
            data = yaml.safe_load(f)
        if not data or "issue_types" not in data:
            logger.error("issue_types.yaml is empty or missing 'issue_types' key")
            return []
        return data["issue_types"]
    except FileNotFoundError:
        logger.error("issue_types.yaml not found at %s", ISSUE_TYPES_PATH)
        return []
    except Exception as exc:
        logger.error("Failed to load issue taxonomy: %s", exc)
        return []


@tool
def validate_location(name: str) -> bool:
    """Check whether a location name is a known London borough in the density database."""
    try:
        return name in _load_locations()
    except FileNotFoundError:
        logger.error("density.csv not found at %s", DENSITY_CSV_PATH)
        return False
    except KeyError:
        logger.error("density.csv is missing the 'Location' column")
        return False
    except Exception as exc:
        logger.error("Failed to validate location: %s", exc)
        return False


@tool
def get_borough_crime_and_deprivation(borough: str) -> dict:
    """
    Return crime and deprivation context for a London borough.

    Use this tool when you need to assess the safety or vulnerability level of
    a location — for example, to reason about ticket priority based on where
    the issue was reported.

    Returns:
      - crime_total_24m: total recorded crimes in the last 24 months
      - crime_by_major_category: breakdown by crime type
      - imd_avg_score: average Index of Multiple Deprivation score (higher = more deprived)
      - imd_pct_most_deprived: proportion of the borough in the most deprived 10% nationally
      - deprivation_band: one of low / medium / high / very_high
    """
    try:
        ctx = get_borough_context(borough)
        if ctx is None:
            return {"error": f"No context data found for borough: {borough}"}
        return dict(ctx)
    except Exception as exc:
        logger.error("get_borough_crime_and_deprivation failed: %s", exc)
        return {"error": str(exc)}


@tool
def get_lsoa_crime_and_deprivation(lsoa_code: str) -> dict:
    """
    Return crime and deprivation context for a specific LSOA code (e.g. E01000001).

    Use this tool when you have a precise LSOA code for the ticket location and
    want finer-grained context than borough-level data provides.

    Returns:
      - crime_total_24m: total recorded crimes in this LSOA over 24 months
      - imd_score: IMD score for this LSOA (higher = more deprived)
      - imd_decile: 1 = most deprived 10%, 10 = least deprived
      - idaopi_score: deprivation rate affecting older people (useful for pavement/lighting issues)
    """
    try:
        ctx = get_lsoa_context(lsoa_code)
        if ctx is None:
            return {"error": f"No context data found for LSOA: {lsoa_code}"}
        return dict(ctx)
    except Exception as exc:
        logger.error("get_lsoa_crime_and_deprivation failed: %s", exc)
        return {"error": str(exc)}


@tool
def list_known_boroughs() -> list[str]:
    """
    Return all London borough names recognised by the context database.

    Use this tool when the reported location does not match any known borough
    to find the closest valid name before calling get_borough_crime_and_deprivation.
    """
    try:
        return list_boroughs()
    except Exception as exc:
        logger.error("list_known_boroughs failed: %s", exc)
        return []
