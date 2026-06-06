from fastapi import APIRouter, File, UploadFile, Form
from typing import Optional

from services.agent_service import run
from services.tfl_service import get_tfl_delay_factor
from services.datastore_service import get_population_density
from services.scoring_service import calculate_priority_score

router = APIRouter()


@router.post("/submit-report")
async def submit_report(
    image: UploadFile = File(...),
    text_description: Optional[str] = Form(None),
    tfl_app_key: Optional[str] = None,
):
    """
    Ingests a citizen report (image) of a city issue.
    Runs it through the agentic VLM pipeline, enriches with static CSV data
    and live TfL data, and returns a deterministic priority score.
    """

    # 1. Read Image
    image_bytes = await image.read()

    # 2. Extract data via Agentic VLM Pipeline
    vlm_data = await run(image_bytes, text_description)

    # 3. Enrich with Live API data (TfL)
    tfl_delay_factor = get_tfl_delay_factor(app_key=tfl_app_key)

    # 4. Enrich with Static CSV data (Population Density)
    borough = vlm_data.get("location", "Unknown")
    population_density = get_population_density(borough)

    # 5. Calculate Priority Score
    priority_score = calculate_priority_score(
        vlm_severity=vlm_data.get("severity", 1),
        tfl_delay_factor=tfl_delay_factor,
        population_density=population_density,
        issue_type=vlm_data.get("issue_type", "other"),
        borough=borough,
    )

    # 6. Map to priority band
    severity = vlm_data.get("severity", 1)
    if severity >= 4 or priority_score >= 500:
        priority_band = "HIGH"
    elif severity >= 3 or priority_score >= 200:
        priority_band = "MEDIUM"
    else:
        priority_band = "LOW"

    # 7. Return Final Payload
    return {
        "status": "success",
        "priority_score": round(priority_score, 2),
        "priority_band": priority_band,
        "details": {
            "vlm_analysis": vlm_data,
            "enrichment": {
                "tfl_delay_factor": round(tfl_delay_factor, 2),
                "population_density": population_density,
            },
        },
    }
