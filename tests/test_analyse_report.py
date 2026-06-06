from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

MOCK_ANALYSIS = {
    "issue_type": "pothole",
    "severity": 3,
    "location": "Hackney",
    "description": "Pothole on residential street.",
    "confidence": 0.85,
    "raw_label": None,
}

FAKE_IMAGE = b"fake_jpeg_bytes"


def _post(extra_data: dict | None = None) -> dict:
    data = extra_data or {}
    response = client.post(
        "/analyse-report",
        files={"image": ("test.jpg", FAKE_IMAGE, "image/jpeg")},
        data=data,
    )
    assert response.status_code == 200
    return response.json()


async def test_analyse_report_backward_compat_no_gps() -> None:
    with (
        patch("routers.analyse_report.resolve_lsoa", new_callable=AsyncMock) as mock_lsoa,
        patch("routers.analyse_report.run", new_callable=AsyncMock) as mock_run,
    ):
        mock_run.return_value = MOCK_ANALYSIS
        result = _post()

    mock_lsoa.assert_not_called()
    mock_run.assert_called_once_with(FAKE_IMAGE, None, None, None)
    assert result["status"] == "success"
    assert result["analysis"]["issue_type"] == "pothole"


async def test_analyse_report_with_borough_only() -> None:
    with (
        patch("routers.analyse_report.resolve_lsoa", new_callable=AsyncMock) as mock_lsoa,
        patch("routers.analyse_report.run", new_callable=AsyncMock) as mock_run,
    ):
        mock_run.return_value = MOCK_ANALYSIS
        result = _post({"borough": "Hackney"})

    mock_lsoa.assert_not_called()
    mock_run.assert_called_once_with(FAKE_IMAGE, None, "Hackney", None)
    assert result["status"] == "success"


async def test_analyse_report_resolves_lsoa_when_coords_provided() -> None:
    with (
        patch("routers.analyse_report.resolve_lsoa", new_callable=AsyncMock, return_value="E01002345") as mock_lsoa,
        patch("routers.analyse_report.run", new_callable=AsyncMock) as mock_run,
    ):
        mock_run.return_value = MOCK_ANALYSIS
        result = _post({"borough": "Hackney", "latitude": "51.5453", "longitude": "-0.0553"})

    mock_lsoa.assert_called_once_with(51.5453, -0.0553)
    mock_run.assert_called_once_with(FAKE_IMAGE, None, "Hackney", "E01002345")
    assert result["status"] == "success"


async def test_analyse_report_passes_none_lsoa_on_resolution_failure() -> None:
    with (
        patch("routers.analyse_report.resolve_lsoa", new_callable=AsyncMock, return_value=None) as mock_lsoa,
        patch("routers.analyse_report.run", new_callable=AsyncMock) as mock_run,
    ):
        mock_run.return_value = MOCK_ANALYSIS
        result = _post({"borough": "Hackney", "latitude": "51.5453", "longitude": "-0.0553"})

    mock_lsoa.assert_called_once_with(51.5453, -0.0553)
    mock_run.assert_called_once_with(FAKE_IMAGE, None, "Hackney", None)
    assert result["status"] == "success"


async def test_analyse_report_resolves_lsoa_without_borough() -> None:
    with (
        patch("routers.analyse_report.resolve_lsoa", new_callable=AsyncMock, return_value="E01002345") as mock_lsoa,
        patch("routers.analyse_report.run", new_callable=AsyncMock) as mock_run,
    ):
        mock_run.return_value = MOCK_ANALYSIS
        result = _post({"latitude": "51.5453", "longitude": "-0.0553"})

    mock_lsoa.assert_called_once_with(51.5453, -0.0553)
    mock_run.assert_called_once_with(FAKE_IMAGE, None, None, "E01002345")
    assert result["status"] == "success"
