from __future__ import annotations

import os
from collections.abc import Generator
from decimal import Decimal
from pathlib import Path
from typing import Any

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/tiffin_ai")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test-twilio-token")

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.api.routes.orders import router as orders_router
from app.api.routes.twilio import router as twilio_router
from app.api.routes.products import router as products_router
from app.api.routes.root import router as root_router
from app.api.routes.webhook import router as webhook_router
from app.core.config import settings
from app.core.database import dispose_database_resources, get_db
from app.core.middleware import RequestLoggingMiddleware
from app.dependencies.chat import get_chat_service
from app.langgraph.memory import ConversationMemory
from app.langgraph.workflow import OrderConversationWorkflow
from app.data.tiffin_seed import seed_tiffin_catalog
from app.services.tiffin_service import TiffinCatalogService
from app.main import http_exception_handler, request_validation_exception_handler, unhandled_exception_handler
from app.services.chat_service import ChatService
from app.services.order_service import OrderService
from app.services.product_service import ProductService
from tests.openai_test_guard import OfflineClassifier, install_openai_guard, reset_guard_state

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_TMP_ROOT = PROJECT_ROOT / ".pytest_tmp"
LOCAL_TMP_ROOT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("TMPDIR", str(LOCAL_TMP_ROOT))
os.environ.setdefault("TEMP", str(LOCAL_TMP_ROOT))
os.environ.setdefault("TMP", str(LOCAL_TMP_ROOT))


@pytest.fixture(autouse=True)
def reset_openai_test_guard() -> None:
    reset_guard_state()


def pytest_configure(config: pytest.Config) -> None:
    config.option.basetemp = str(LOCAL_TMP_ROOT / f"basetemp-{os.getpid()}")
    if os.getenv("RUN_OPENAI_INTEGRATION_TESTS") != "1":
        install_openai_guard()


@pytest.fixture()
def test_database_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture()
def engine(test_database_path: Path, monkeypatch: pytest.MonkeyPatch):
    database_url = f"sqlite:///{test_database_path.as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", database_url)
    dispose_database_resources()
    alembic_cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_cfg, "head")
    engine = create_engine(database_url)
    try:
        yield engine
    finally:
        engine.dispose()
        dispose_database_resources()


@pytest.fixture()
def db_session(engine) -> Generator[Session, None, None]:
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class FakeRAGChain:
    def __init__(self, response: str = "policy response") -> None:
        self.response = response
        self.calls: list[str] = []

    async def ask(self, message: str) -> str:
        self.calls.append(message)
        return self.response


@pytest.fixture()
def fake_rag_chain() -> FakeRAGChain:
    return FakeRAGChain(response="policy response")


@pytest.fixture()
def seeded_products(db_session: Session) -> dict[str, Any]:
    service = ProductService(db_session)
    burger = service.create_product(
        name='Burger',
        description='Classic burger',
        price=Decimal('10.00'),
        is_available=True,
    )
    pizza = service.create_product(
        name='Pizza',
        description='Cheese pizza',
        price=Decimal('15.00'),
        is_available=True,
    )
    fries = service.create_product(
        name='Fries',
        description='Side fries',
        price=Decimal('5.50'),
        is_available=True,
    )
    soup = service.create_product(
        name='Soup',
        description='Unavailable soup',
        price=Decimal('4.00'),
        is_available=False,
    )
    return {
        'burger': burger,
        'pizza': pizza,
        'fries': fries,
        'soup': soup,
        'service': service,
    }


@pytest.fixture()
def seeded_tiffin_catalog(db_session: Session) -> TiffinCatalogService:
    seed_tiffin_catalog(db_session)
    return TiffinCatalogService(db_session)


@pytest.fixture()
def workflow(
    db_session: Session,
    fake_rag_chain: FakeRAGChain,
    seeded_tiffin_catalog: TiffinCatalogService,
) -> OrderConversationWorkflow:
    product_service = ProductService(db_session)
    order_service = OrderService(db_session)
    return OrderConversationWorkflow(
        rag_chain=fake_rag_chain,  # type: ignore[arg-type]
        product_service=product_service,
        order_service=order_service,
        meal_service=seeded_tiffin_catalog,
        memory=ConversationMemory(db_session),
        classifier=OfflineClassifier(),
    )


@pytest.fixture()
def conversation_id() -> str:
    return "conv-test"


@pytest.fixture()
def customer_phone() -> str:
    return "15551234567"


@pytest.fixture()
def message_ids() -> dict[str, str]:
    return {
        "hello": "msg-hello",
        "menu": "msg-menu",
        "add_burger": "msg-add-burger",
        "view_cart": "msg-view-cart",
        "address": "msg-address",
        "policy": "msg-policy",
        "confirm": "msg-confirm",
        "track": "msg-track",
    }


@pytest.fixture()
def app(
    db_session: Session,
    fake_rag_chain: FakeRAGChain,
    seeded_products: dict[str, Any],
    seeded_tiffin_catalog: TiffinCatalogService,
) -> Generator[FastAPI, None, None]:
    test_app = FastAPI()
    test_app.include_router(root_router)
    test_app.include_router(health_router)
    test_app.include_router(products_router)
    test_app.include_router(twilio_router)
    test_app.include_router(orders_router)
    test_app.include_router(chat_router)
    test_app.include_router(webhook_router)
    test_app.add_middleware(RequestLoggingMiddleware)
    test_app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    test_app.add_exception_handler(HTTPException, http_exception_handler)
    test_app.add_exception_handler(Exception, unhandled_exception_handler)

    product_service = ProductService(db_session)
    order_service = OrderService(db_session)
    chat_service = ChatService(
        rag_chain=fake_rag_chain,  # type: ignore[arg-type]
        product_service=product_service,
        order_service=order_service,
        meal_service=seeded_tiffin_catalog,
    )
    chat_service.workflow = OrderConversationWorkflow(
        rag_chain=fake_rag_chain,  # type: ignore[arg-type]
        product_service=product_service,
        order_service=order_service,
        meal_service=seeded_tiffin_catalog,
        memory=ConversationMemory(db_session),
        classifier=OfflineClassifier(),
    )

    def override_get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = override_get_db
    test_app.dependency_overrides[get_chat_service] = lambda: chat_service
    test_app.state.chat_service = chat_service
    test_app.state.db_session_factory = sessionmaker(
        bind=db_session.get_bind(),
        autoflush=False,
        expire_on_commit=False,
    )
    yield test_app
    test_app.dependency_overrides.clear()


@pytest.fixture()
def client(app: FastAPI) -> Generator[tuple[TestClient, ChatService], None, None]:
    with TestClient(app) as test_client:
        yield test_client, app.state.chat_service
