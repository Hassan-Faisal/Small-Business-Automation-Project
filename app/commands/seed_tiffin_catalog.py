from __future__ import annotations

import argparse
import sys

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import dispose_database_resources, get_session_factory
from app.data.tiffin_seed import seed_tiffin_catalog
from app.models.meal_offering import MealOffering
from app.models.product import Product
from app.models.subscription_plan import SubscriptionPlan


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed missing tiffin catalog records without overwriting existing data.")
    parser.parse_args()

    session_factory = get_session_factory()
    session = session_factory()
    try:
        seed_tiffin_catalog(session)
        products = session.scalar(select(func.count()).select_from(Product)) or 0
        meals = session.scalar(select(func.count()).select_from(MealOffering)) or 0
        plans = session.scalar(select(func.count()).select_from(SubscriptionPlan)) or 0
        print("seed_complete=True")
        print(f"products={products}")
        print(f"meal_offerings={meals}")
        print(f"subscription_plans={plans}")
        return 0
    except SQLAlchemyError as exc:
        session.rollback()
        print(f"seed_complete=False\nerror={exc}", file=sys.stderr)
        return 1
    finally:
        session.close()
        dispose_database_resources()


if __name__ == "__main__":
    raise SystemExit(main())
