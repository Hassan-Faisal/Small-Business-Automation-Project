from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["products"])


def get_product_service(db: Session = Depends(get_db)) -> ProductService:
    return ProductService(db)


@router.get("", response_model=list[ProductResponse])
def list_products(
    product_service: ProductService = Depends(get_product_service),
) -> list[ProductResponse]:
    return product_service.list_available_products()


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    product_service: ProductService = Depends(get_product_service),
) -> ProductResponse:
    product = product_service.retrieve_product_by_id(product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    product_service: ProductService = Depends(get_product_service),
) -> ProductResponse:
    try:
        return product_service.create_product(
            name=payload.name,
            description=payload.description,
            price=payload.price,
            is_available=payload.is_available,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    product_service: ProductService = Depends(get_product_service),
) -> ProductResponse:
    try:
        if payload.is_available is not None and payload.name is None and payload.description is None and payload.price is None:
            return product_service.update_product_availability(product_id, payload.is_available)

        product = product_service.retrieve_product_by_id(product_id)
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

        if payload.name is not None:
            product.name = payload.name.strip()
        if payload.description is not None:
            product.description = payload.description
        if payload.price is not None:
            product.price = payload.price
        if payload.is_available is not None:
            product.is_available = payload.is_available

        product_service.db.commit()
        product_service.db.refresh(product)
        return product
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
