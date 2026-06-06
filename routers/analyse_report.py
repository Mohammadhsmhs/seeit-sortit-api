from fastapi import APIRouter, File, Form, UploadFile
from typing import Optional

from services.agent_service import run

router = APIRouter()


@router.post("/analyse-report")
async def analyse_report(
    image: UploadFile = File(...),
    text_description: Optional[str] = Form(None),
):
    """
    Runs the issue-identification agent on a citizen report image.
    Returns a structured classification: issue type, severity, location,
    description, confidence, and raw label.
    """
    image_bytes = await image.read()
    result = await run(image_bytes, text_description)
    return {"status": "success", "analysis": result}
