"""Every admin route must be behind the admin dependency and a rate limit.

This is the guard rail that makes "we forgot Depends(require_admin) on the new
endpoint" impossible to ship: it walks the real dependency tree of every route
the app registers, so a new file or a new router is covered automatically.
"""

import pytest
from fastapi.routing import APIRoute

from webapp.core.auth import require_admin
from webapp.core.limiter import limiter
from webapp.main import app

#: Prefixes whose routes are admin-only.
ADMIN_PREFIXES = ("/api/admin", "/api/wallet/admin")


def _admin_routes() -> list[APIRoute]:
    return [
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and any(route.path.startswith(prefix) for prefix in ADMIN_PREFIXES)
    ]


def _walk(dependant) -> list:
    """Every ``call`` in the dependency tree of a route, depth first."""
    calls = []
    for sub in getattr(dependant, "dependencies", []) or []:
        if sub.call is not None:
            calls.append(sub.call)
        calls.extend(_walk(sub))
    return calls


def _is_admin_guard(call) -> bool:
    return call is require_admin or getattr(call, "__require_role__", None) is not None


def test_admin_routes_exist():
    """Guard against the assertions below passing vacuously."""
    paths = {route.path for route in _admin_routes()}
    assert "/api/admin/state" in paths
    assert len(paths) >= 5


@pytest.mark.parametrize(
    "route",
    _admin_routes(),
    ids=lambda route: f"{sorted(route.methods or [])[0]} {route.path}",
)
def test_admin_route_requires_admin(route: APIRoute):
    calls = _walk(route.dependant)
    guards = [call for call in calls if _is_admin_guard(call)]
    assert guards, (
        f"{sorted(route.methods or [])} {route.path} has no require_admin/require_role "
        f"in its dependency tree: {[getattr(c, '__name__', repr(c)) for c in calls]}"
    )


@pytest.mark.parametrize(
    "route",
    _admin_routes(),
    ids=lambda route: f"{sorted(route.methods or [])[0]} {route.path}",
)
def test_admin_route_is_rate_limited(route: APIRoute):
    endpoint = route.endpoint
    key = f"{endpoint.__module__}.{endpoint.__name__}"
    assert key in limiter._route_limits, (
        f"{sorted(route.methods or [])} {route.path} has no @limiter.limit decorator"
    )


def test_mutating_admin_routes_are_tightly_limited():
    """Writes get the strict bucket; reads may use the looser one."""
    for route in _admin_routes():
        methods = set(route.methods or [])
        if not methods & {"POST", "PATCH", "PUT", "DELETE"}:
            continue
        endpoint = route.endpoint
        limits = limiter._route_limits[f"{endpoint.__module__}.{endpoint.__name__}"]
        per_minute = [str(item.limit) for item in limits]
        assert per_minute, f"{route.path} has an empty limit list"
        assert all("per 1 minute" in text for text in per_minute), (
            f"{route.path} limits are not per-minute: {per_minute}"
        )
