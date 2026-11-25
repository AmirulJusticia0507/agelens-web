"""Optional reverse geocoding for the job search location filter."""

import asyncio
from time import monotonic

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/location", tags=["location"])
_cache: dict[tuple[float, float], str] = {}
_request_lock = asyncio.Lock()
_last_request_at = 0.0


@router.get("/reverse")
async def reverse_geocode(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
) -> dict[str, str]:
    """Resolve a user-requested coordinate to a city using Nominatim."""
    global _last_request_at
    key = (round(lat, 4), round(lon, 4))
    if key in _cache:
        return {"location": _cache[key]}

    async with _request_lock:
        if key in _cache:
            return {"location": _cache[key]}
        delay = 1.0 - (monotonic() - _last_request_at)
        if delay > 0:
            await asyncio.sleep(delay)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    "https://nominatim.openstreetmap.org/reverse",
                    params={"lat": lat, "lon": lon, "format": "jsonv2", "addressdetails": 1},
                    headers={"User-Agent": "AgeLens/0.1 (job search location lookup)"},
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(status_code=502, detail="Layanan pencarian lokasi tidak tersedia.") from exc
        finally:
            _last_request_at = monotonic()

        address = data.get("address", {})
        city = next(
            (address[field] for field in ("city", "town", "village", "municipality", "county", "state") if address.get(field)),
            None,
        )
        if not city:
            raise HTTPException(status_code=404, detail="Nama kota tidak ditemukan untuk lokasi ini.")
        _cache[key] = city
        return {"location": city}
