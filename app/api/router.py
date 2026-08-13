from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import meta_router, twilio_router, whatsapp_router
from app.api.routes.admin import auth_router as admin_auth_router, router as admin_router
from app.api.routes.admin_dashboard import router as admin_dashboard_router
from app.api.routes.admin_menu import router as admin_menu_router
from app.api.routes.admin_meta import router as admin_meta_router
from app.api.routes.admin_orders import router as admin_orders_router

api_router = APIRouter()
api_router.include_router(whatsapp_router)
api_router.include_router(meta_router)
api_router.include_router(twilio_router)
api_router.include_router(admin_router)
api_router.include_router(admin_auth_router)
api_router.include_router(admin_dashboard_router)
api_router.include_router(admin_menu_router)
api_router.include_router(admin_orders_router)
api_router.include_router(admin_meta_router)


