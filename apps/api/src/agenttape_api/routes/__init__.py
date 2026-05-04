from __future__ import annotations

from agenttape_api.routes.admin import router as admin_router
from agenttape_api.routes.agents import router as agents_router
from agenttape_api.routes.discovery import router as discovery_router
from agenttape_api.routes.events import router as events_router
from agenttape_api.routes.indexes import router as indexes_router
from agenttape_api.routes.movers import router as movers_router
from agenttape_api.routes.search import router as search_router
from agenttape_api.routes.sectors import router as sectors_router
from agenttape_api.routes.tags import router as tags_router

ROUTERS = [
    agents_router,
    indexes_router,
    movers_router,
    search_router,
    sectors_router,
    tags_router,
    events_router,
    discovery_router,
    admin_router,
]
