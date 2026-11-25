"""Tests for optional reverse geocoding."""

import httpx
import pytest

from app.api import location


@pytest.mark.asyncio
async def test_reverse_geocode_returns_city_and_caches_result(monkeypatch) -> None:
    calls = 0

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, *, params, headers):
            nonlocal calls
            calls += 1
            assert url == "https://nominatim.openstreetmap.org/reverse"
            assert headers["User-Agent"].startswith("AgeLens/")
            return httpx.Response(
                200,
                json={"address": {"city": "Jakarta Selatan", "state": "Jakarta"}},
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr(location.httpx, "AsyncClient", FakeClient)
    location._cache.clear()
    location._last_request_at = 0
    first = await location.reverse_geocode(lat=-6.2, lon=106.8)
    second = await location.reverse_geocode(lat=-6.2, lon=106.8)

    assert first == second == {"location": "Jakarta Selatan"}
    assert calls == 1


@pytest.mark.asyncio
async def test_reverse_geocode_maps_upstream_failure_to_502(monkeypatch) -> None:
    class FailedClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            raise httpx.ConnectError("offline")

    monkeypatch.setattr(location.httpx, "AsyncClient", FailedClient)
    location._cache.clear()
    location._last_request_at = 0

    with pytest.raises(location.HTTPException) as error:
        await location.reverse_geocode(lat=-7.8, lon=110.3)

    assert error.value.status_code == 502
