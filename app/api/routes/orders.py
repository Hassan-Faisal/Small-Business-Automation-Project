from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.schemas.order import OrderCreate, OrderResponse, OrderStatusUpdate
from app.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])


def get_order_service(db: Session = Depends(get_db)) -> OrderService:
    return OrderService(db)


def _map_value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    if "not found" in message:
        code = status.HTTP_404_NOT_FOUND
    elif "already confirmed" in message:
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=message)


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate,
    order_service: OrderService = Depends(get_order_service),
) -> OrderResponse:
    try:
        return order_service.create_draft_order(payload)
    except ValueError as exc:
        raise _map_value_error(exc) from exc


@router.get("/{order_number}", response_model=OrderResponse)
def get_order(
    order_number: str,
    order_service: OrderService = Depends(get_order_service),
) -> OrderResponse:
    order = order_service.retrieve_order_by_order_number(order_number)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


@router.post("/{order_number}/confirm", response_model=OrderResponse)
def confirm_order(
    order_number: str,
    order_service: OrderService = Depends(get_order_service),
) -> OrderResponse:
    try:
        return order_service.confirm_order(order_number)
    except ValueError as exc:
        raise _map_value_error(exc) from exc


@router.patch("/{order_number}/status", response_model=OrderResponse)
def update_order_status(
    order_number: str,
    payload: OrderStatusUpdate,
    order_service: OrderService = Depends(get_order_service),
) -> OrderResponse:
    try:
        return order_service.update_order_status(order_number, payload.status)
    except ValueError as exc:
        raise _map_value_error(exc) from exc
