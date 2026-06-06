from __future__ import annotations

from services.context_service import compute_london_averages, get_borough_context

BASELINE_COSTS = {
    "pothole": 200.0,
    "graffiti": 50.0,
    "broken_streetlight": 500.0,
    "fly_tipping": 150.0,
}

# Weight of each context signal per issue type (must sum to 1.0)
_CONTEXT_WEIGHTS: dict[str, dict[str, float]] = {
    "pothole":            {"crime": 0.2, "deprivation": 0.3, "tfl": 0.5},
    "graffiti":           {"crime": 0.4, "deprivation": 0.4, "tfl": 0.2},
    "broken_streetlight": {"crime": 0.5, "deprivation": 0.3, "tfl": 0.2},
    "fly_tipping":        {"crime": 0.3, "deprivation": 0.5, "tfl": 0.2},
}
_DEFAULT_WEIGHTS = {"crime": 0.3, "deprivation": 0.4, "tfl": 0.3}


def _context_multiplier(borough: str, issue_type: str, tfl_delay_factor: float) -> float:
    """Return a multiplier in [0.5, 2.0] derived from borough context signals."""
    averages = compute_london_averages()
    ctx = get_borough_context(borough)

    if ctx:
        crime_factor = min(ctx["crime_total_24m"] / max(averages["avg_crime_24m"], 1), 2.0)
        imd_score = ctx["imd_avg_score"] or averages["avg_imd_score"]
        dep_factor = min(imd_score / max(averages["avg_imd_score"], 1), 2.0)
    else:
        crime_factor = 1.0
        dep_factor = 1.0

    # TfL delay is already a relative factor; centre it around 1.0
    tfl_factor = max(0.5, min(tfl_delay_factor, 2.0))

    weights = _CONTEXT_WEIGHTS.get(issue_type, _DEFAULT_WEIGHTS)
    multiplier = (
        weights["crime"] * crime_factor
        + weights["deprivation"] * dep_factor
        + weights["tfl"] * tfl_factor
    )
    return max(0.5, min(multiplier, 2.0))


def calculate_priority_score(
    vlm_severity: float,
    tfl_delay_factor: float,
    population_density: float,
    issue_type: str,
    borough: str = "",
) -> float:
    """
    Priority Score = severity × context_multiplier / baseline_cost_factor

    Context multiplier (0.5–2.0) blends crime rate, deprivation, and TfL
    delay weighted by issue type. Falls back to the original formula when
    no borough is supplied or the context DB is unavailable.
    """
    baseline_cost = max(BASELINE_COSTS.get(issue_type, 100.0), 1.0)

    if borough:
        try:
            multiplier = _context_multiplier(borough, issue_type, tfl_delay_factor)
            return (vlm_severity * multiplier * population_density) / baseline_cost
        except Exception:
            pass

    # Original formula fallback
    return ((vlm_severity * tfl_delay_factor) * population_density) / baseline_cost
