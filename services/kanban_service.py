import logging
import os

import httpx

logger = logging.getLogger(__name__)

PRIORITY_MAP = {
    "CRITICAL": "critical",
    "HIGH": "high",
    "MEDIUM": "medium",
    "LOW": "low",
}

DEPARTMENT_MAP = {
    "fly_tipping": "Waste Management",
    "graffiti": "Streetworks",
    "pothole": "Highways",
    "broken_streetlight": "Streetworks",
    "abandoned_vehicle": "Parking & Enforcement",
    "overgrown_vegetation": "Parks & Green Spaces",
    "damaged_sign": "Highways",
    "blocked_drain": "Highways",
    "noise_pollution": "Environmental Health",
    "anti_social_behaviour": "Community Safety",
}

DEFAULT_DEPARTMENT = "Streetworks"


async def create_ticket(
    title: str,
    priority_band: str,
    issue_type: str,
    description: str | None = None,
) -> dict | None:
    """POST a new ticket to the London Council Kanban dashboard.

    Returns the created ticket dict on success, or None if the request fails
    (errors are logged but never raised so the analyse-report response is
    unaffected by kanban availability).
    """
    base_url = os.environ.get("KANBAN_BASE_URL", "").rstrip("/")
    if not base_url:
        logger.warning("KANBAN_BASE_URL not set — skipping ticket creation")
        return None

    priority = PRIORITY_MAP.get(priority_band.upper(), "medium")
    department = DEPARTMENT_MAP.get(issue_type, DEFAULT_DEPARTMENT)

    payload = {
        "title": title,
        "priority": priority,
        "department": department,
    }
    if description:
        payload["description"] = description

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(f"{base_url}/api/tickets", json=payload)
            response.raise_for_status()
            data = response.json()
            ticket = data.get("data", {})
            logger.info("Kanban ticket created: %s", ticket.get("ref"))
            return ticket
    except Exception:
        logger.warning("Failed to create kanban ticket", exc_info=True)
        return None
