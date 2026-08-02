from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import TypeVar

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.meal_offering import MealOffering
from app.models.order_item import OrderItem
from app.models.product import Product
from app.schemas.admin_menu import normalize_day_of_week, normalize_meal_type, normalize_menu_name

T = TypeVar("T")


class AdminMenuError(Exception):
    pass


class MenuItemNotFoundError(AdminMenuError):
    pass


class MenuItemConflictError(AdminMenuError):
    pass


class MenuItemValidationError(AdminMenuError):
    pass


class MenuItemPersistenceError(AdminMenuError):
    pass


class AdminMenuService:
    """Manage scheduled MealOffering rows and their name-linked orderable Products."""

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _normalized_name(name: str) -> str:
        return " ".join(name.strip().lower().split())

    def _product_for_name(self, name: str) -> Product | None:
        normalized = self._normalized_name(name)
        return self.db.scalars(
            select(Product).where(func.lower(func.trim(Product.name)) == normalized)
        ).first()

    def _offering_for_id(self, menu_item_id: int) -> MealOffering:
        offering = self.db.get(MealOffering, menu_item_id)
        if offering is None:
            raise MenuItemNotFoundError(f"Menu item {menu_item_id} was not found.")
        return offering

    def _duplicate_exists(
        self,
        *,
        day_of_week: str,
        meal_type: str,
        name: str,
        exclude_id: int | None = None,
    ) -> bool:
        stmt = select(MealOffering.id).where(
            func.lower(MealOffering.day_of_week) == day_of_week.lower(),
            func.lower(MealOffering.meal_type) == meal_type.lower(),
            func.lower(func.trim(MealOffering.name)) == self._normalized_name(name),
        )
        if exclude_id is not None:
            stmt = stmt.where(MealOffering.id != exclude_id)
        return self.db.scalar(stmt.limit(1)) is not None

    def _group_offerings(self, name: str, *, exclude_id: int | None = None) -> list[MealOffering]:
        stmt = select(MealOffering).where(
            func.lower(func.trim(MealOffering.name)) == self._normalized_name(name)
        )
        if exclude_id is not None:
            stmt = stmt.where(MealOffering.id != exclude_id)
        return list(self.db.scalars(stmt).all())

    def _has_order_history(self, product: Product) -> bool:
        return self.db.scalar(select(OrderItem.id).where(OrderItem.product_id == product.id).limit(1)) is not None

    def _sync_product_availability(self, product: Product, name: str) -> None:
        available_offering = self.db.scalar(
            select(MealOffering.id).where(
                func.lower(func.trim(MealOffering.name)) == self._normalized_name(name),
                MealOffering.is_active.is_(True),
                MealOffering.availability.is_(True),
            ).limit(1)
        )
        product.is_available = available_offering is not None

    def _write(self, operation: Callable[[], T]) -> T:
        try:
            result = operation()
            self.db.flush()
            self.db.commit()
            return result
        except AdminMenuError:
            self.db.rollback()
            raise
        except IntegrityError as exc:
            self.db.rollback()
            raise MenuItemConflictError("A menu item or orderable product with these values already exists.") from exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise MenuItemPersistenceError("Unable to save the menu item.") from exc

    def list_menu_items(
        self,
        *,
        meal_type: str | None = None,
        day_of_week: str | None = None,
        availability: bool | None = None,
        is_active: bool | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[MealOffering], int]:
        try:
            normalized_meal_type = normalize_meal_type(meal_type) if meal_type is not None else None
            normalized_day = normalize_day_of_week(day_of_week) if day_of_week is not None else None
        except ValueError as exc:
            raise MenuItemValidationError(str(exc)) from exc

        filters = []
        if normalized_meal_type is not None:
            filters.append(func.lower(MealOffering.meal_type) == normalized_meal_type)
        if normalized_day is not None:
            filters.append(func.lower(MealOffering.day_of_week) == normalized_day.lower())
        if availability is not None:
            filters.append(MealOffering.availability.is_(availability))
        if is_active is not None:
            filters.append(MealOffering.is_active.is_(is_active))
        if search is not None and search.strip():
            term = f"%{search.strip()}%"
            filters.append(or_(MealOffering.name.ilike(term), MealOffering.description.ilike(term)))

        stmt = select(MealOffering).where(*filters)
        total = int(self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
        items = list(
            self.db.scalars(
                stmt.order_by(MealOffering.day_of_week, MealOffering.meal_type, MealOffering.name, MealOffering.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return items, total

    def get_menu_item(self, menu_item_id: int) -> MealOffering:
        return self._offering_for_id(menu_item_id)

    def create_menu_item(
        self,
        *,
        name: str,
        description: str | None,
        price: Decimal,
        meal_type: str,
        day_of_week: str,
        availability: bool,
        is_active: bool,
    ) -> MealOffering:
        try:
            normalized_name = normalize_menu_name(name)
            normalized_meal_type = normalize_meal_type(meal_type)
            normalized_day = normalize_day_of_week(day_of_week)
        except ValueError as exc:
            raise MenuItemValidationError(str(exc)) from exc
        if price <= Decimal("0.00"):
            raise MenuItemValidationError("Price must be greater than zero.")

        def operation() -> MealOffering:
            if self._duplicate_exists(day_of_week=normalized_day, meal_type=normalized_meal_type, name=normalized_name):
                raise MenuItemConflictError("This menu item already exists for the selected day and meal type.")

            product = self._product_for_name(normalized_name)
            if product is not None and Decimal(str(product.price)) != price:
                raise MenuItemConflictError("An orderable product with this name already uses a different price.")
            if product is None:
                product = Product(name=normalized_name, description=description, price=price, is_available=False)
                self.db.add(product)
            elif product.description is None and description is not None:
                product.description = description

            offering = MealOffering(
                name=normalized_name,
                description=description,
                price=price,
                meal_type=normalized_meal_type,
                day_of_week=normalized_day,
                availability=availability,
                is_active=is_active,
            )
            self.db.add(offering)
            self.db.flush()
            self._sync_product_availability(product, normalized_name)
            return offering

        offering = self._write(operation)
        self.db.refresh(offering)
        return offering

    def update_menu_item(self, menu_item_id: int, changes: dict[str, object]) -> MealOffering:
        offering = self._offering_for_id(menu_item_id)
        if not changes:
            return offering

        def operation() -> MealOffering:
            old_name = offering.name
            old_normalized_name = self._normalized_name(old_name)
            new_name = str(changes.get("name", offering.name))
            new_price = Decimal(str(changes.get("price", offering.price)))
            new_meal_type = str(changes.get("meal_type", offering.meal_type))
            new_day = str(changes.get("day_of_week", offering.day_of_week))
            try:
                new_name = normalize_menu_name(new_name)
                new_meal_type = normalize_meal_type(new_meal_type)
                new_day = normalize_day_of_week(new_day)
            except ValueError as exc:
                raise MenuItemValidationError(str(exc)) from exc
            if new_price <= Decimal("0.00"):
                raise MenuItemValidationError("Price must be greater than zero.")
            if self._duplicate_exists(day_of_week=new_day, meal_type=new_meal_type, name=new_name, exclude_id=offering.id):
                raise MenuItemConflictError("This update conflicts with another menu item.")

            old_product = self._product_for_name(old_name)
            new_normalized_name = self._normalized_name(new_name)
            target_product = old_product

            if new_normalized_name != old_normalized_name:
                existing_target = self._product_for_name(new_name)
                if existing_target is not None:
                    if Decimal(str(existing_target.price)) != new_price:
                        raise MenuItemConflictError("The target product name already uses a different price.")
                    target_product = existing_target
                elif old_product is not None and not self._group_offerings(old_name, exclude_id=offering.id) and not self._has_order_history(old_product):
                    old_product.name = new_name
                    target_product = old_product
                else:
                    target_product = Product(
                        name=new_name,
                        description=changes.get("description", offering.description),
                        price=new_price,
                        is_available=False,
                    )
                    self.db.add(target_product)
            elif target_product is None:
                target_product = Product(
                    name=new_name,
                    description=changes.get("description", offering.description),
                    price=new_price,
                    is_available=False,
                )
                self.db.add(target_product)
            elif "name" in changes:
                target_product.name = new_name
                for peer in self._group_offerings(old_name, exclude_id=offering.id):
                    peer.name = new_name

            offering.name = new_name
            offering.price = new_price
            offering.meal_type = new_meal_type
            offering.day_of_week = new_day
            if "description" in changes:
                offering.description = changes["description"]
                target_product.description = changes["description"]
            if "availability" in changes:
                offering.availability = bool(changes["availability"])
            if "is_active" in changes:
                offering.is_active = bool(changes["is_active"])

            if "price" in changes:
                target_product.price = new_price
                for peer in self._group_offerings(new_name, exclude_id=offering.id):
                    peer.price = new_price

            self.db.flush()
            if old_product is not None and old_product is not target_product:
                self._sync_product_availability(old_product, old_name)
            self._sync_product_availability(target_product, new_name)
            return offering

        updated = self._write(operation)
        self.db.refresh(updated)
        return updated

    def update_availability(self, menu_item_id: int, availability: bool) -> MealOffering:
        offering = self._offering_for_id(menu_item_id)

        def operation() -> MealOffering:
            offering.availability = availability
            product = self._product_for_name(offering.name)
            self.db.flush()
            if product is not None:
                self._sync_product_availability(product, offering.name)
            return offering

        updated = self._write(operation)
        self.db.refresh(updated)
        return updated

    def deactivate_menu_item(self, menu_item_id: int) -> MealOffering:
        offering = self._offering_for_id(menu_item_id)

        def operation() -> MealOffering:
            offering.is_active = False
            offering.availability = False
            product = self._product_for_name(offering.name)
            self.db.flush()
            if product is not None:
                self._sync_product_availability(product, offering.name)
            return offering

        deactivated = self._write(operation)
        self.db.refresh(deactivated)
        return deactivated
