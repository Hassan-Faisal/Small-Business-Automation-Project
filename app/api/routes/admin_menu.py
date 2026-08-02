from __future__ import annotations

import logging
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.dependencies.admin import require_active_admin
from app.dependencies.database import get_db
from app.models.admin_user import AdminUser
from app.schemas.admin_menu import (
    AdminMenuAvailabilityUpdate,
    AdminMenuItemCreate,
    AdminMenuItemDeactivationResponse,
    AdminMenuItemListResponse,
    AdminMenuItemResponse,
    AdminMenuItemUpdate,
)
from app.services.admin_menu_service import (
    AdminMenuError,
    AdminMenuService,
    MenuItemConflictError,
    MenuItemNotFoundError,
    MenuItemPersistenceError,
    MenuItemValidationError,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/menu-items", tags=["admin-menu"])


def get_admin_menu_service(db: Session = Depends(get_db)) -> AdminMenuService:
    return AdminMenuService(db)


def _raise_http_error(exc: AdminMenuError) -> NoReturn:
    if isinstance(exc, MenuItemNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, MenuItemConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if isinstance(exc, MenuItemValidationError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if isinstance(exc, MenuItemPersistenceError):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to save the menu item.") from exc
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to manage the menu item.") from exc


@router.get("", response_model=AdminMenuItemListResponse)
def list_menu_items(
    meal_type: str | None = None,
    day_of_week: str | None = None,
    availability: bool | None = None,
    is_active: bool | None = None,
    search: str | None = Query(default=None, max_length=150),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    _admin: AdminUser = Depends(require_active_admin),
    service: AdminMenuService = Depends(get_admin_menu_service),
) -> AdminMenuItemListResponse:
    try:
        items, total = service.list_menu_items(
            meal_type=meal_type,
            day_of_week=day_of_week,
            availability=availability,
            is_active=is_active,
            search=search,
            page=page,
            page_size=page_size,
        )
    except AdminMenuError as exc:
        _raise_http_error(exc)
    return AdminMenuItemListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=AdminMenuItemResponse, status_code=status.HTTP_201_CREATED)
def create_menu_item(
    payload: AdminMenuItemCreate,
    admin: AdminUser = Depends(require_active_admin),
    service: AdminMenuService = Depends(get_admin_menu_service),
) -> AdminMenuItemResponse:
    try:
        item = service.create_menu_item(**payload.model_dump())
    except AdminMenuError as exc:
        _raise_http_error(exc)
    logger.info("admin_menu_item_created", extra={"event": "admin_menu_item_created", "menu_item_id": item.id, "admin_id": admin.id})
    return AdminMenuItemResponse.model_validate(item)


@router.get("/{menu_item_id}", response_model=AdminMenuItemResponse)
def get_menu_item(
    menu_item_id: int,
    _admin: AdminUser = Depends(require_active_admin),
    service: AdminMenuService = Depends(get_admin_menu_service),
) -> AdminMenuItemResponse:
    try:
        item = service.get_menu_item(menu_item_id)
    except AdminMenuError as exc:
        _raise_http_error(exc)
    return AdminMenuItemResponse.model_validate(item)


@router.patch("/{menu_item_id}", response_model=AdminMenuItemResponse)
def update_menu_item(
    menu_item_id: int,
    payload: AdminMenuItemUpdate,
    admin: AdminUser = Depends(require_active_admin),
    service: AdminMenuService = Depends(get_admin_menu_service),
) -> AdminMenuItemResponse:
    try:
        item = service.update_menu_item(menu_item_id, payload.model_dump(exclude_unset=True))
    except AdminMenuError as exc:
        _raise_http_error(exc)
    logger.info("admin_menu_item_updated", extra={"event": "admin_menu_item_updated", "menu_item_id": item.id, "admin_id": admin.id})
    return AdminMenuItemResponse.model_validate(item)


@router.patch("/{menu_item_id}/availability", response_model=AdminMenuItemResponse)
def update_menu_item_availability(
    menu_item_id: int,
    payload: AdminMenuAvailabilityUpdate,
    admin: AdminUser = Depends(require_active_admin),
    service: AdminMenuService = Depends(get_admin_menu_service),
) -> AdminMenuItemResponse:
    try:
        item = service.update_availability(menu_item_id, payload.availability)
    except AdminMenuError as exc:
        _raise_http_error(exc)
    logger.info("admin_menu_item_availability_changed", extra={"event": "admin_menu_item_availability_changed", "menu_item_id": item.id, "admin_id": admin.id})
    return AdminMenuItemResponse.model_validate(item)


@router.delete("/{menu_item_id}", response_model=AdminMenuItemDeactivationResponse)
def deactivate_menu_item(
    menu_item_id: int,
    admin: AdminUser = Depends(require_active_admin),
    service: AdminMenuService = Depends(get_admin_menu_service),
) -> AdminMenuItemDeactivationResponse:
    try:
        item = service.deactivate_menu_item(menu_item_id)
    except AdminMenuError as exc:
        _raise_http_error(exc)
    logger.info("admin_menu_item_deactivated", extra={"event": "admin_menu_item_deactivated", "menu_item_id": item.id, "admin_id": admin.id})
    return AdminMenuItemDeactivationResponse(
        id=item.id,
        message="Menu item deactivated successfully.",
        availability=item.availability,
        is_active=item.is_active,
    )
