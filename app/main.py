from __future__ import annotations

# The historical API surface remains in app.api. app.main is now the
# composition root so RC15 can add isolated, testable routers without growing
# the already-large API module.
from . import api as _api
from . import provenance_models as _provenance_models  # noqa: F401
from .api import *  # noqa: F401,F403
from .legacy_cases_api import router as legacy_cases_router
from .procurement_api import router as procurement_router
from .rc15_api import router as rc15_router

# Re-export private helpers too: maintenance scripts/tests import a few symbols
# directly from app.main. Keeping them avoids an accidental compatibility break
# while the legacy API module is split from the composition root.
for _name, _value in vars(_api).items():
    if not _name.startswith("__"):
        globals().setdefault(_name, _value)

app = _api.app

# app.api created the legacy metadata before RC15/provenance models were imported.
# Local/dev installations intentionally use create_all, so create only any new
# metadata now registered. Production keeps auto-create disabled and uses the
# Alembic migration instead.
if _api.settings.auto_create_schema:
    _api.Base.metadata.create_all(bind=_api.engine)

# The historical decision endpoint predates qualified judgment provenance.
# Replace only that POST route at composition time so every supported decision
# path records the same fail-closed provenance without growing app.api further.
_legacy_case_decision_path = "/api/cases/{case_id}/decision"
app.router.routes[:] = [
    route
    for route in app.router.routes
    if not (
        getattr(route, "path", None) == _legacy_case_decision_path
        and "POST" in (getattr(route, "methods", None) or set())
    )
]

# app.api mounts StaticFiles at '/'. Starlette resolves routes in order, so the
# catch-all static mount must remain last after additional routes are registered.
_static_routes = [route for route in app.router.routes if getattr(route, "name", None) == "static"]
for _route in _static_routes:
    app.router.routes.remove(_route)
app.include_router(legacy_cases_router)
app.include_router(rc15_router)
app.include_router(procurement_router)
app.router.routes.extend(_static_routes)
