from fastapi import APIRouter, File, Form, UploadFile
from typing import Optional

from services.agent_service import run
from services.scoring_service import calculate_priority_score
from services.tfl_service import get_tfl_delay_factor
from services.datastore_service import get_population_density

router = APIRouter()


@router.post("/analyse-report")
async def analyse_report(
    image: UploadFile = File(...),
    text_description: Optional[str] = Form(None),
):
    """
    Runs the issue-identification agent on a citizen report image.
    Returns a structured classification with issue type, severity, location,
    description, confidence, raw label, AND a deterministic priority score
    enriched with live TfL data, population density, and crime/deprivation context.
    """
    image_bytes = await image.read()
    result = await run(image_bytes, text_description)

    # Enrich with live TfL data and population density, then score
    tfl_delay_factor = get_tfl_delay_factor()
    population_density = get_population_density(result.get("location", "Unknown"))
    borough = result.get("location", "")

    priority_score = calculate_priority_score(
        vlm_severity=result.get("severity", 1),
        tfl_delay_factor=tfl_delay_factor,
        population_density=population_density,
        issue_type=result.get("issue_type", "other"),
        borough=borough,
    )

    # Map score to priority band
    severity = result.get("severity", 1)
    if severity >= 4 or priority_score >= 500:
        priority_band = "HIGH"
    elif severity >= 3 or priority_score >= 200:
        priority_band = "MEDIUM"
    else:
        priority_band = "LOW"

    return {
        "status": "success",
        "priority_score": round(priority_score, 2),
        "priority_band": priority_band,
        "analysis": result,
        "enrichment": {
            "tfl_delay_factor": round(tfl_delay_factor, 2),
            "population_density": population_density,
            "borough": borough,
        },
    }
