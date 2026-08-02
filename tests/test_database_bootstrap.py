from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.data.tiffin_seed import seed_tiffin_catalog
from app.models.meal_offering import MealOffering
from app.models.subscription_plan import SubscriptionPlan


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _upgrade_database(database_url: str) -> None:
    alembic_cfg = Config(str(PROJECT_ROOT / 'alembic.ini'))
    alembic_cfg.set_main_option('sqlalchemy.url', database_url)
    command.upgrade(alembic_cfg, 'head')


def test_alembic_upgrade_head_creates_all_tables(tmp_path) -> None:
    database_path = tmp_path / 'empty.db'
    database_url = f'sqlite:///{database_path.as_posix()}'

    _upgrade_database(database_url)

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names()) - {'alembic_version'}
    finally:
        engine.dispose()

    assert tables == {
        'admin_users',
        'conversation_state_records',
        'customer_subscriptions',
        'meal_offerings',
        'meal_skips',
        'order_items',
        'orders',
        'products',
        'subscription_plans',
    }


def test_seed_is_idempotent_and_does_not_overwrite_existing_business_data(tmp_path) -> None:
    database_path = tmp_path / 'seed.db'
    database_url = f'sqlite:///{database_path.as_posix()}'

    _upgrade_database(database_url)
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    session = SessionLocal()
    try:
        seed_tiffin_catalog(session)
        plan = session.query(SubscriptionPlan).filter(SubscriptionPlan.name == 'Weekly Lunch Plan').one()
        meal = session.query(MealOffering).filter(MealOffering.name == 'Chicken Biryani').first()
        assert plan is not None
        assert meal is not None

        plan.description = 'Admin edited plan description'
        plan.is_active = False
        meal.description = 'Admin edited meal description'
        meal.is_active = False
        meal.availability = False
        session.commit()

        seed_tiffin_catalog(session)
        seed_tiffin_catalog(session)

        refreshed_plan = session.query(SubscriptionPlan).filter(SubscriptionPlan.name == 'Weekly Lunch Plan').one()
        refreshed_meal = session.query(MealOffering).filter(MealOffering.name == 'Chicken Biryani').first()

        assert refreshed_plan.description == 'Admin edited plan description'
        assert refreshed_plan.is_active is False
        assert refreshed_meal.description == 'Admin edited meal description'
        assert refreshed_meal.is_active is False
        assert refreshed_meal.availability is False
    finally:
        session.close()
        engine.dispose()


def test_seed_command_reports_success_for_explicit_bootstrap(tmp_path) -> None:
    database_path = tmp_path / 'seed-command.db'
    database_url = f'sqlite:///{database_path.as_posix()}'

    _upgrade_database(database_url)
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    session = SessionLocal()
    try:
        seed_tiffin_catalog(session)
        product_count = session.execute(text('SELECT COUNT(*) FROM products')).scalar_one()
        meal_count = session.execute(text('SELECT COUNT(*) FROM meal_offerings')).scalar_one()
        plan_count = session.execute(text('SELECT COUNT(*) FROM subscription_plans')).scalar_one()
    finally:
        session.close()
        engine.dispose()

    assert product_count > 0
    assert meal_count > 0
    assert plan_count > 0
