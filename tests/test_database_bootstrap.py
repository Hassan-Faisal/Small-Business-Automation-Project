from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.data.tiffin_seed import seed_tiffin_catalog
from app.models.meal_offering import MealOffering
from app.models.subscription_plan import SubscriptionPlan


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _upgrade_database(database_url: str) -> None:
    settings.DATABASE_URL = database_url
    alembic_cfg = Config(str(PROJECT_ROOT / 'alembic.ini'))
    alembic_cfg.set_main_option('sqlalchemy.url', database_url)
    command.upgrade(alembic_cfg, 'head')


def test_alembic_upgrade_head_creates_all_tables(tmp_path) -> None:
    database_path = tmp_path / 'empty.db'
    database_url = f'sqlite:///{database_path.as_posix()}'

    _upgrade_database(database_url)

    engine = create_engine(database_url, connect_args={'check_same_thread': False})
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names()) - {'alembic_version'}
    finally:
        engine.dispose()

    assert tables == {
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
    engine = create_engine(database_url, connect_args={'check_same_thread': False})
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


def test_app_startup_does_not_modify_seeded_catalog(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / 'startup.db'
    database_url = f'sqlite:///{database_path.as_posix()}'

    _upgrade_database(database_url)
    engine = create_engine(database_url, connect_args={'check_same_thread': False})
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    session = SessionLocal()
    try:
        seed_tiffin_catalog(session)
        plan = session.query(SubscriptionPlan).filter(SubscriptionPlan.name == 'Weekly Lunch Plan').one()
        meal = session.query(MealOffering).filter(MealOffering.name == 'Chicken Biryani').first()
        assert plan is not None and meal is not None

        plan_before = (plan.description, plan.is_active)
        meal_before = (meal.description, meal.is_active, meal.availability)

        import app.core.lifespan as lifespan_module

        class DummyKnowledgeManager:
            def initialize(self) -> None:
                return None

        class DummyRAGChain:
            def __init__(self, *args, **kwargs) -> None:
                return None

        class DummyChatService:
            def __init__(self, *args, **kwargs) -> None:
                return None

        monkeypatch.setattr(lifespan_module, 'KnowledgeManager', DummyKnowledgeManager)
        monkeypatch.setattr(lifespan_module, 'RAGChain', DummyRAGChain)
        monkeypatch.setattr(lifespan_module, 'ChatService', DummyChatService)
        monkeypatch.setattr(lifespan_module, '_get_twilio_request_validator', lambda: None)

        async def run_lifespan() -> None:
            app = FastAPI()
            async with lifespan_module.lifespan(app):
                return None

        import asyncio
        asyncio.run(run_lifespan())

        refreshed_plan = session.query(SubscriptionPlan).filter(SubscriptionPlan.name == 'Weekly Lunch Plan').one()
        refreshed_meal = session.query(MealOffering).filter(MealOffering.name == 'Chicken Biryani').first()

        assert (refreshed_plan.description, refreshed_plan.is_active) == plan_before
        assert (refreshed_meal.description, refreshed_meal.is_active, refreshed_meal.availability) == meal_before
    finally:
        session.close()
        engine.dispose()

