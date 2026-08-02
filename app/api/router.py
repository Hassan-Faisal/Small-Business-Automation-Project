from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import twilio_router, whatsapp_router
from app.api.routes.admin import auth_router as admin_auth_router, router as admin_router

api_router = APIRouter()
api_router.include_router(whatsapp_router)
api_router.include_router(twilio_router)
api_router.include_router(admin_router)
api_router.include_router(admin_auth_router)
