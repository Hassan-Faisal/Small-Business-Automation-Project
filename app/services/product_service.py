from __future__ import annotations

from decimal import Decimal
from difflib import SequenceMatcher
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.meal_offering import MealOffering
from app.models.product import Product


PRODUCT_QUERY_STOP_WORDS = {"a", "an", "and", "are", "can", "chahiye", "chahye", "do", "dain", "dena", "for", "get", "give", "i", "in", "mein", "me", "mujhe", "mujhay", "my", "order", "please", "kar", "karo", "karna", "add", "want", "would", "you", "the", "to", "one", "two", "three", "meal", "meals", "dish", "dishes", "something", "related", "kind", "type", "food"}
class ProductService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def normalize_name(name: str) -> str:
        return " ".join(name.strip().lower().split())

    @staticmethod
    def normalize_token(token: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "", token.lower())
        if len(normalized) > 4 and normalized.endswith(("ay", "ey")):
            normalized = normalized[:-1]
        elif len(normalized) > 4 and normalized.endswith("s"):
            normalized = normalized[:-1]
        return normalized

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

    def resolve_available_products(self, query: str, candidates: list[Product] | None = None) -> list[Product]:
        """Return only the highest-scoring safe product candidates."""
        normalized_query = self.normalize_name(query)
        if not normalized_query:
            return []
        products = candidates if candidates is not None else self.list_available_products()
        exact = [product for product in products if self.normalize_name(product.name) == normalized_query]
        if exact:
            return exact

        # Preserve natural-language requests such as "please add Chicken Biryani"
        # without treating the surrounding filler as part of the product name.
        contained = [
            product
            for product in products
            if self.normalize_name(product.name) in normalized_query
        ]
        if contained:
            return contained

        query_tokens = [self.normalize_token(token) for token in normalized_query.split()]
        query_tokens = [token for token in query_tokens if token not in PRODUCT_QUERY_STOP_WORDS]
        query_tokens = [token for token in query_tokens if not token.isdigit()]
        query_tokens = [token for token in query_tokens if token]
        scored: list[tuple[float, Product]] = []
        for product in products:
            product_tokens = [self.normalize_token(token) for token in self.normalize_name(product.name).split()]
            if not product_tokens:
                continue
            token_scores = [
                max(SequenceMatcher(None, token, candidate).ratio() for candidate in product_tokens)
                for token in query_tokens
            ]
            if not token_scores:
                continue
            score = sum(token_scores) / len(token_scores)
            if all(score_value >= 0.82 for score_value in token_scores):
                scored.append((score, product))

        if not scored:
            return []
        highest = max(score for score, _ in scored)
        return [product for score, product in scored if score >= 0.82 and highest - score <= 0.06]

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
