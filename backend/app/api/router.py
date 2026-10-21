from fastapi import APIRouter

from app.api.routes import agendas, health, items, meetings

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(items.router)
api_router.include_router(meetings.router)

api_router.include_router(agendas.router)
