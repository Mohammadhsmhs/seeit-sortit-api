import logging

from fastapi import APIRouter, File, Form, UploadFile

from services.agent_service import run
from services.kanban_service import create_ticket
from services.scoring_service import calculate_priority_score
from services.tfl_service import get_tfl_delay_factor
from services.datastore_service import get_population_density
from services.geo_service import resolve_lsoa

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/analyse-report")
async def analyse_report(
    image: UploadFile = File(...),
    text_description: str | None = Form(None),
    borough: str | None = Form(None),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
):
    """Run the issue-identification agent on a citizen report image.

    GPS fields (borough, latitude, longitude) are optional. When latitude and
    longitude are both provided, the LSOA code is resolved via postcodes.io and
    passed to the agent for finer-grained context. If resolution fails, the
    request continues at borough-level precision. If no location fields are
    provided, the agent infers the borough from the image.
    """
    image_bytes = await image.read()

    lsoa_code: str | None = None
    if latitude is not None and longitude is not None:
        try:
            lsoa_code = await resolve_lsoa(latitude, longitude)
        except Exception:
            logger.warning("LSOA resolution failed for (%s, %s)", latitude, longitude, exc_info=True)
            lsoa_code = None

    result = await run(image_bytes, text_description, borough, lsoa_code)

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

    if description := result.get("description"):
        result["description"] = description.replace("{priority_band}", priority_band)

    issue_type_label = result.get("issue_type", "Council issue").replace("_", " ").title()
    ticket_title = f"{issue_type_label} in {result.get('location', 'Unknown')}"
    await create_ticket(
        title=ticket_title,
        priority_band=priority_band,
        issue_type=result.get("issue_type", ""),
        description=result.get("description"),
    )

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
