from fastapi import APIRouter

from app.api.routes import router

api_router = APIRouter()
api_router.include_router(router)
