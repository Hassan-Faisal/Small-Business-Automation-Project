from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import twilio_router, whatsapp_router

api_router = APIRouter()
api_router.include_router(whatsapp_router)
api_router.include_router(twilio_router)
