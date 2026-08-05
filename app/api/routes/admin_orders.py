from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.dependencies.admin import require_active_admin
from app.dependencies.database import get_db
from app.models.admin_user import AdminUser
from app.schemas.admin_order import AdminOrderDeliveryUpdate, AdminOrderDetailResponse, AdminOrderListResponse, AdminOrderStatusUpdate
from app.services.admin_order_service import AdminOrderInvalidStatusError, AdminOrderInvalidTransitionError, AdminOrderNotFoundError, AdminOrderService, AdminOrderTransactionError

router = APIRouter(prefix="/admin/orders", tags=["admin-orders"])


def get_admin_order_service(db: Session = Depends(get_db)) -> AdminOrderService:
    return AdminOrderService(db)


@router.get("", response_model=AdminOrderListResponse)
def list_admin_orders(
    status_filter: str | None = Query(default=None, alias="status", max_length=50),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    customer_phone: str | None = Query(default=None, max_length=30),
    order_number: str | None = Query(default=None, max_length=50),
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    _admin: AdminUser = Depends(require_active_admin),
    service: AdminOrderService = Depends(get_admin_order_service),
) -> AdminOrderListResponse:
    try:
        return service.list_orders(status=status_filter, date_from=date_from, date_to=date_to, customer_phone=customer_phone, order_number=order_number, search=search, page=page, page_size=page_size)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to list orders.") from None


@router.get("/{order_id}", response_model=AdminOrderDetailResponse)
def get_admin_order(order_id: int, _admin: AdminUser = Depends(require_active_admin), service: AdminOrderService = Depends(get_admin_order_service)) -> AdminOrderDetailResponse:
    try:
        return service.get_detail(order_id)
    except AdminOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to retrieve order.") from None


@router.patch("/{order_id}/status", response_model=AdminOrderDetailResponse)
def update_admin_order_status(order_id: int, payload: AdminOrderStatusUpdate, admin: AdminUser = Depends(require_active_admin), service: AdminOrderService = Depends(get_admin_order_service)) -> AdminOrderDetailResponse:
    try:
        return service.update_status(order_id, payload.status, admin)
    except AdminOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except AdminOrderInvalidStatusError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except AdminOrderInvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except AdminOrderTransactionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from None
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to update order status.") from None


@router.patch("/{order_id}/delivery", response_model=AdminOrderDetailResponse)
def update_admin_order_delivery(order_id: int, payload: AdminOrderDeliveryUpdate, admin: AdminUser = Depends(require_active_admin), service: AdminOrderService = Depends(get_admin_order_service)) -> AdminOrderDetailResponse:
    try:
        return service.update_delivery(order_id, payload, admin)
    except AdminOrderNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except AdminOrderTransactionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from None
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to update delivery details.") from None


