from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.meal_offering import MealOffering
from app.models.product import Product
from app.models.subscription_plan import SubscriptionPlan

WEEKLY_TIFFIN_MENU: dict[str, dict[str, list[dict[str, object]]]] = {
    "Monday": {
        "breakfast": [
            {"name": "Anda Paratha", "description": "Two eggs with freshly made paratha.", "price": Decimal("180.00")},
            {"name": "Aloo Paratha with Raita", "description": "Stuffed potato paratha served with raita.", "price": Decimal("170.00")},
            {"name": "Boiled Eggs with Paratha", "description": "Boiled eggs with soft paratha.", "price": Decimal("160.00")},
        ],
        "lunch": [
            {"name": "Chicken Biryani", "description": "Fragrant chicken biryani with raita.", "price": Decimal("320.00")},
            {"name": "Daal Chawal", "description": "Comforting daal with steamed rice.", "price": Decimal("260.00")},
            {"name": "Chicken Qorma", "description": "Rich chicken qorma with naan.", "price": Decimal("350.00")},
        ],
        "dinner": [
            {"name": "Chicken Karahi", "description": "Home-style chicken karahi with roti.", "price": Decimal("380.00")},
            {"name": "Daal Mash with Naan", "description": "Creamy daal mash with naan.", "price": Decimal("240.00")},
            {"name": "Seekh Kabab with Paratha", "description": "Seekh kabab served with paratha.", "price": Decimal("340.00")},
        ],
    },
    "Tuesday": {
        "breakfast": [
            {"name": "Anda Chana", "description": "Eggs with spicy chana and paratha.", "price": Decimal("190.00")},
            {"name": "Halwa Puri", "description": "Traditional halwa puri breakfast.", "price": Decimal("200.00")},
            {"name": "Omelette with Paratha", "description": "Fresh omelette and paratha.", "price": Decimal("175.00")},
        ],
        "lunch": [
            {"name": "Chicken Pulao", "description": "Aromatic chicken pulao with salad.", "price": Decimal("300.00")},
            {"name": "Chicken Karahi", "description": "Special chicken karahi with naan.", "price": Decimal("380.00")},
            {"name": "Aloo Gosht", "description": "Aloo gosht with fresh roti.", "price": Decimal("360.00")},
        ],
        "dinner": [
            {"name": "Chicken Handi", "description": "Creamy chicken handi with naan.", "price": Decimal("390.00")},
            {"name": "Mixed Vegetable Curry", "description": "Seasonal vegetables with roti.", "price": Decimal("250.00")},
            {"name": "Chicken Qorma", "description": "Slow-cooked chicken qorma.", "price": Decimal("350.00")},
        ],
    },
    "Wednesday": {
        "breakfast": [
            {"name": "Naan Chana", "description": "Naan with desi chana.", "price": Decimal("185.00")},
            {"name": "Anda Paratha", "description": "Egg paratha with mint chutney.", "price": Decimal("180.00")},
            {"name": "Daal Mash with Paratha", "description": "Daal mash served with paratha.", "price": Decimal("170.00")},
        ],
        "lunch": [
            {"name": "Beef Kofta Curry", "description": "Beef kofta curry with rice.", "price": Decimal("370.00")},
            {"name": "Chana Pulao", "description": "Chana pulao with salad.", "price": Decimal("270.00")},
            {"name": "Chicken Biryani", "description": "Classic chicken biryani.", "price": Decimal("320.00")},
        ],
        "dinner": [
            {"name": "Aloo Keema", "description": "Aloo keema with roti.", "price": Decimal("300.00")},
            {"name": "Daal Chana with Rice", "description": "Daal chana with steamed rice.", "price": Decimal("230.00")},
            {"name": "Chicken Karahi", "description": "Chicken karahi with paratha.", "price": Decimal("380.00")},
        ],
    },
    "Thursday": {
        "breakfast": [
            {"name": "Boiled Eggs with Paratha", "description": "Protein-packed breakfast box.", "price": Decimal("160.00")},
            {"name": "Aloo Paratha with Raita", "description": "Aloo paratha with yoghurt raita.", "price": Decimal("170.00")},
            {"name": "Omelette with Paratha", "description": "Omelette and paratha combo.", "price": Decimal("175.00")},
        ],
        "lunch": [
            {"name": "Chicken Qorma", "description": "Chicken qorma with naan.", "price": Decimal("350.00")},
            {"name": "Chicken Kabab with Rice", "description": "Kabab and rice meal box.", "price": Decimal("330.00")},
            {"name": "Daal Chawal", "description": "Simple daal chawal lunch box.", "price": Decimal("260.00")},
        ],
        "dinner": [
            {"name": "Mix Sabzi with Roti", "description": "Mixed vegetables with roti.", "price": Decimal("240.00")},
            {"name": "Chicken Handi", "description": "Creamy chicken handi with naan.", "price": Decimal("390.00")},
            {"name": "Seekh Kabab with Paratha", "description": "Seekh kabab and paratha dinner box.", "price": Decimal("340.00")},
        ],
    },
    "Friday": {
        "breakfast": [
            {"name": "Halwa Puri", "description": "Friday breakfast special.", "price": Decimal("200.00")},
            {"name": "Anda Chana", "description": "Egg and chana breakfast.", "price": Decimal("190.00")},
            {"name": "Naan Chana", "description": "Soft naan with chana masala.", "price": Decimal("185.00")},
        ],
        "lunch": [
            {"name": "Chicken Biryani", "description": "Friday lunch biryani box.", "price": Decimal("320.00")},
            {"name": "Beef Kofta Curry", "description": "Beef kofta with rice.", "price": Decimal("370.00")},
            {"name": "Chicken Pulao", "description": "Chicken pulao with salad.", "price": Decimal("300.00")},
        ],
        "dinner": [
            {"name": "Chicken Karahi", "description": "Friday night chicken karahi.", "price": Decimal("380.00")},
            {"name": "Aloo Keema", "description": "Aloo keema with roti.", "price": Decimal("300.00")},
            {"name": "Daal Mash with Naan", "description": "Daal mash and naan dinner.", "price": Decimal("240.00")},
        ],
    },
    "Saturday": {
        "breakfast": [
            {"name": "Anda Paratha", "description": "Weekend egg paratha box.", "price": Decimal("180.00")},
            {"name": "Boiled Eggs with Paratha", "description": "Boiled eggs with paratha.", "price": Decimal("160.00")},
            {"name": "Aloo Paratha with Raita", "description": "Aloo paratha with cooling raita.", "price": Decimal("170.00")},
        ],
        "lunch": [
            {"name": "Chicken Karahi", "description": "Weekend chicken karahi.", "price": Decimal("380.00")},
            {"name": "Chicken Kabab with Rice", "description": "Chicken kabab rice box.", "price": Decimal("330.00")},
            {"name": "Mixed Vegetable Curry", "description": "Mixed vegetable curry with roti.", "price": Decimal("250.00")},
        ],
        "dinner": [
            {"name": "Chicken Handi", "description": "Creamy chicken handi.", "price": Decimal("390.00")},
            {"name": "Chicken Pulao", "description": "Chicken pulao dinner box.", "price": Decimal("300.00")},
            {"name": "Seekh Kabab with Paratha", "description": "Seekh kabab with paratha.", "price": Decimal("340.00")},
        ],
    },
    "Sunday": {
        "breakfast": [
            {"name": "Omelette with Paratha", "description": "Sunday omelette breakfast.", "price": Decimal("175.00")},
            {"name": "Halwa Puri", "description": "Sunday special halwa puri.", "price": Decimal("200.00")},
            {"name": "Naan Chana", "description": "Naan with chana masala.", "price": Decimal("185.00")},
        ],
        "lunch": [
            {"name": "Chicken Biryani", "description": "Sunday family biryani box.", "price": Decimal("320.00")},
            {"name": "Aloo Gosht", "description": "Aloo gosht with naan.", "price": Decimal("360.00")},
            {"name": "Chana Pulao", "description": "Chana pulao with salad.", "price": Decimal("270.00")},
        ],
        "dinner": [
            {"name": "Daal Chana with Rice", "description": "Light dinner of daal chana and rice.", "price": Decimal("230.00")},
            {"name": "Chicken Qorma", "description": "Rich chicken qorma with naan.", "price": Decimal("350.00")},
            {"name": "Mix Sabzi with Roti", "description": "Mixed sabzi with roti.", "price": Decimal("240.00")},
        ],
    },
}

SUBSCRIPTION_PLANS: list[dict[str, object]] = [
    {"name": "Weekly Breakfast Plan", "duration_type": "weekly", "number_of_days": 7, "included_meal_types": ["breakfast"], "price": Decimal("1200.00"), "description": "Seven breakfast boxes for one week."},
    {"name": "Weekly Lunch Plan", "duration_type": "weekly", "number_of_days": 7, "included_meal_types": ["lunch"], "price": Decimal("2100.00"), "description": "Seven lunch boxes for one week."},
    {"name": "Weekly Dinner Plan", "duration_type": "weekly", "number_of_days": 7, "included_meal_types": ["dinner"], "price": Decimal("2200.00"), "description": "Seven dinner boxes for one week."},
    {"name": "Weekly Two-Meal Plan", "duration_type": "weekly", "number_of_days": 7, "included_meal_types": ["breakfast", "lunch"], "price": Decimal("2900.00"), "description": "Breakfast and lunch for the week."},
    {"name": "Weekly Full-Day Plan", "duration_type": "weekly", "number_of_days": 7, "included_meal_types": ["breakfast", "lunch", "dinner"], "price": Decimal("4500.00"), "description": "Three meals a day for one week."},
    {"name": "Monthly Breakfast Plan", "duration_type": "monthly", "number_of_days": 30, "included_meal_types": ["breakfast"], "price": Decimal("4800.00"), "description": "Breakfast meals for one month."},
    {"name": "Monthly Lunch Plan", "duration_type": "monthly", "number_of_days": 30, "included_meal_types": ["lunch"], "price": Decimal("8200.00"), "description": "Lunch meals for one month."},
    {"name": "Monthly Dinner Plan", "duration_type": "monthly", "number_of_days": 30, "included_meal_types": ["dinner"], "price": Decimal("8600.00"), "description": "Dinner meals for one month."},
    {"name": "Monthly Two-Meal Plan", "duration_type": "monthly", "number_of_days": 30, "included_meal_types": ["breakfast", "lunch"], "price": Decimal("10800.00"), "description": "Breakfast and lunch for one month."},
    {"name": "Monthly Full-Day Plan", "duration_type": "monthly", "number_of_days": 30, "included_meal_types": ["breakfast", "lunch", "dinner"], "price": Decimal("16800.00"), "description": "Three meals a day for one month."},
]


def _insert_meal_if_missing(db: Session, *, day_of_week: str, meal_type: str, name: str, description: str, price: Decimal) -> None:
    stmt = select(MealOffering).where(MealOffering.day_of_week == day_of_week, MealOffering.meal_type == meal_type, MealOffering.name == name)
    meal = db.scalars(stmt).first()
    if meal is None:
        db.add(MealOffering(day_of_week=day_of_week, meal_type=meal_type, name=name, description=description, price=price, availability=True, is_active=True))


def _insert_product_if_missing(db: Session, *, name: str, description: str, price: Decimal) -> None:
    stmt = select(Product).where(Product.name == name)
    product = db.scalars(stmt).first()
    if product is None:
        db.add(Product(name=name, description=description, price=price, is_available=True))
        db.flush()


def _insert_plan_if_missing(db: Session, *, name: str, duration_type: str, number_of_days: int, included_meal_types: list[str], price: Decimal, description: str) -> None:
    stmt = select(SubscriptionPlan).where(SubscriptionPlan.name == name)
    plan = db.scalars(stmt).first()
    if plan is None:
        db.add(SubscriptionPlan(name=name, duration_type=duration_type, number_of_days=number_of_days, included_meal_types=included_meal_types, price=price, description=description, is_active=True))


def seed_tiffin_catalog(db: Session) -> None:
    for day_of_week, meals in WEEKLY_TIFFIN_MENU.items():
        for meal_type, offerings in meals.items():
            for offering in offerings:
                name = str(offering["name"])
                description = str(offering["description"])
                price = Decimal(str(offering["price"]))
                _insert_meal_if_missing(db, day_of_week=day_of_week, meal_type=meal_type, name=name, description=description, price=price)
                _insert_product_if_missing(db, name=name, description=description, price=price)

    for plan in SUBSCRIPTION_PLANS:
        _insert_plan_if_missing(
            db,
            name=str(plan["name"]),
            duration_type=str(plan["duration_type"]),
            number_of_days=int(plan["number_of_days"]),
            included_meal_types=list(plan["included_meal_types"]),
            price=Decimal(str(plan["price"])),
            description=str(plan["description"]),
        )

    db.commit()
