import logging

import httpx

logger = logging.getLogger(__name__)

_POSTCODES_IO_URL = "https://api.postcodes.io/postcodes"
_TIMEOUT = 3.0

_client = httpx.AsyncClient(timeout=_TIMEOUT)


async def resolve_lsoa(lat: float, lon: float) -> str | None:
    """Look up the LSOA code for a WGS84 coordinate pair via postcodes.io.

    Returns the ONS LSOA code (e.g. "E01002345") or None on any failure.
    """
    try:
        response = await _client.get(_POSTCODES_IO_URL, params={"lat": lat, "lon": lon})
        response.raise_for_status()
        data = response.json()
        results = data.get("result") or []
        if not results:
            logger.warning("postcodes.io returned no results for lat=%s lon=%s", lat, lon)
            return None
        first = results[0]
        if not isinstance(first, dict):
            logger.warning("postcodes.io unexpected result format for lat=%s lon=%s", lat, lon)
            return None
        lsoa = first.get("codes", {}).get("lsoa")
        if not lsoa:
            logger.warning("postcodes.io result missing LSOA code for lat=%s lon=%s", lat, lon)
            return None
        return lsoa
    except httpx.TimeoutException:
        logger.warning("postcodes.io timed out for lat=%s lon=%s", lat, lon)
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning("postcodes.io HTTP error %s for lat=%s lon=%s", exc.response.status_code, lat, lon)
        return None
    except httpx.RequestError as exc:
        logger.warning("postcodes.io network error for lat=%s lon=%s: %s", lat, lon, exc)
        return None
    except Exception:
        logger.error("postcodes.io unexpected error for lat=%s lon=%s", lat, lon, exc_info=True)
        return None
