from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from services.geo_service import resolve_lsoa


async def test_resolve_lsoa_returns_code_on_success() -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "status": 200,
        "result": [
            {
                "postcode": "E8 1EA",
                "codes": {"lsoa": "E01002345"},
            }
        ],
    }

    with patch("services.geo_service._client") as mock_client:
        mock_client.get = AsyncMock(return_value=mock_response)
        result = await resolve_lsoa(51.5453, -0.0553)

    assert result == "E01002345"


async def test_resolve_lsoa_returns_none_on_timeout() -> None:
    with patch("services.geo_service._client") as mock_client:
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        result = await resolve_lsoa(51.5453, -0.0553)

    assert result is None


async def test_resolve_lsoa_returns_none_on_empty_results() -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"status": 200, "result": []}

    with patch("services.geo_service._client") as mock_client:
        mock_client.get = AsyncMock(return_value=mock_response)
        result = await resolve_lsoa(51.5453, -0.0553)

    assert result is None


async def test_resolve_lsoa_returns_none_on_missing_lsoa_key() -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "status": 200,
        "result": [{"postcode": "E8 1EA", "codes": {}}],
    }

    with patch("services.geo_service._client") as mock_client:
        mock_client.get = AsyncMock(return_value=mock_response)
        result = await resolve_lsoa(51.5453, -0.0553)

    assert result is None


async def test_resolve_lsoa_returns_none_on_http_error() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 404
    with patch("services.geo_service._client") as mock_client:
        mock_client.get = AsyncMock(side_effect=httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_response
        ))
        result = await resolve_lsoa(51.5453, -0.0553)

    assert result is None
