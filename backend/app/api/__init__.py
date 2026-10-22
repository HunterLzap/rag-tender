from fastapi import APIRouter

from app.api.exports import router as exports_router
from app.api.interpretation import router as interpretation_router
from app.api.library import router as library_router
from app.api.management import router as management_router
from app.api.offline import router as offline_router
from app.api.routes import router

api_router = APIRouter()
api_router.include_router(router)
api_router.include_router(management_router)
api_router.include_router(offline_router)
api_router.include_router(exports_router)
api_router.include_router(library_router)
api_router.include_router(interpretation_router)
