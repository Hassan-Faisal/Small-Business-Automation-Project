from __future__ import annotations

import asyncio

import pytest

from app.core.config import Settings
from app.core.database import _engine_kwargs, get_db  # type: ignore[attr-defined]
from app.services.chat_service import ChatService


def test_missing_database_url_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('DATABASE_URL', raising=False)
    with pytest.raises(ValueError, match='DATABASE_URL'):
        Settings(_env_file=None)


def test_postgres_engine_is_configured_with_pool_pre_ping() -> None:
    kwargs = _engine_kwargs('postgresql+psycopg2://postgres:postgres@localhost:5432/tiffin_ai')

    assert kwargs['pool_pre_ping'] is True
    assert kwargs['connect_args'] == {'connect_timeout': 5}
    assert kwargs['echo'] is False


def test_get_db_closes_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    class DummySession:
        def close(self) -> None:
            events.append('closed')

    monkeypatch.setattr('app.core.database.get_session_factory', lambda: (lambda: DummySession()))

    dependency = get_db()
    session = next(dependency)
    assert isinstance(session, DummySession)

    with pytest.raises(StopIteration):
        next(dependency)

    assert events == ['closed']


def test_chat_service_uses_fresh_session_per_interaction(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[object] = []
    closed: list[object] = []

    class DummySession:
        def close(self) -> None:
            closed.append(self)

    class DummyWorkflow:
        def __init__(self, *, rag_chain, product_service, order_service, meal_service, memory) -> None:
            opened.append(product_service.db)

        async def run(self, message: str, conversation_id: str, customer_phone: str | None, message_id: str | None):
            return {'response': f'reply:{message}'}

    class DummyProductService:
        def __init__(self, db) -> None:
            self.db = db

    class DummyOrderService(DummyProductService):
        pass

    class DummyMealService(DummyProductService):
        pass

    class DummyMemory:
        def __init__(self, db) -> None:
            self.db = db

    def session_factory() -> DummySession:
        return DummySession()

    monkeypatch.setattr('app.services.chat_service.OrderConversationWorkflow', DummyWorkflow)
    monkeypatch.setattr('app.services.chat_service.ProductService', DummyProductService)
    monkeypatch.setattr('app.services.chat_service.OrderService', DummyOrderService)
    monkeypatch.setattr('app.services.chat_service.TiffinCatalogService', DummyMealService)
    monkeypatch.setattr('app.services.chat_service.ConversationMemory', DummyMemory)

    class DummyRAG:
        pass

    service = ChatService(rag_chain=DummyRAG(), session_factory=session_factory)

    first = asyncio.run(service.chat('hello', conversation_id='a'))
    second = asyncio.run(service.chat('menu', conversation_id='b'))

    assert first == 'reply:hello'
    assert second == 'reply:menu'
    assert len(opened) == 2
    assert opened[0] is not opened[1]
    assert closed == opened
