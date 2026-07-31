from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.meal_offering import MealOffering
from app.models.product import Product


class ProductService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def normalize_name(name: str) -> str:
        return " ".join(name.strip().lower().split())

    def list_available_products(self) -> list[Product]:
        stmt = select(Product).where(Product.is_available.is_(True)).order_by(Product.name)
        return list(self.db.scalars(stmt).all())

    def retrieve_product_by_id(self, product_id: int) -> Product | None:
        return self.db.get(Product, product_id)

    def retrieve_product_by_normalized_name(self, name: str) -> Product | None:
        normalized = self.normalize_name(name)
        stmt = select(Product).where(
            func.lower(func.trim(Product.name)) == normalized,
        )
        return self.db.scalars(stmt).first()

    def get_or_create_product_for_meal(self, meal: MealOffering) -> Product:
        existing = self.retrieve_product_by_normalized_name(meal.name)
        if existing is not None:
            return existing

        product = Product(
            name=meal.name.strip(),
            description=meal.description,
            price=Decimal(str(meal.price)),
            is_available=bool(meal.availability and meal.is_active),
        )
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product

    def create_product(
        self,
        *,
        name: str,
        description: str | None,
        price: Decimal,
        is_available: bool = True,
    ) -> Product:
        if not name or not name.strip():
            raise ValueError("Product name is required.")

        product = Product(
            name=name.strip(),
            description=description,
            price=price,
            is_available=is_available,
        )
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product

    def update_product_availability(self, product_id: int, is_available: bool) -> Product:
        product = self.db.get(Product, product_id)
        if product is None:
            raise ValueError(f"Product {product_id} not found.")

        product.is_available = is_available
        self.db.commit()
        self.db.refresh(product)
        return product
