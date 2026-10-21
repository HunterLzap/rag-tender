from fastapi import APIRouter

from app.api.management import router as management_router
from app.api.routes import router

api_router = APIRouter()
api_router.include_router(router)
api_router.include_router(management_router)
