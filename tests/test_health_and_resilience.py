from __future__ import annotations

import asyncio

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import settings


def test_live_endpoint(client):
    test_client, _ = client

    response = test_client.get('/live')

    assert response.status_code == 200
    assert response.json() == {'status': 'alive'}


def test_health_endpoint(client):
    test_client, _ = client

    response = test_client.get('/health')

    assert response.status_code == 200
    assert response.json() == {'status': 'ok', 'version': settings.APP_VERSION}


def test_ready_endpoint_success(client):
    test_client, _ = client

    response = test_client.get('/ready')

    assert response.status_code == 200
    assert response.json() == {'status': 'ready'}


def test_ready_endpoint_failure(app, monkeypatch):
    import app.api.routes.health as health_module

    monkeypatch.setattr(health_module, 'check_database_connection', lambda: (_ for _ in ()).throw(RuntimeError('database unavailable')))

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get('/ready')

    assert response.status_code == 503
    assert response.json() == {
        'error': {
            'type': 'http_exception',
            'message': 'Database unavailable',
        }
    }


def test_validation_error_uses_safe_format(client):
    test_client, _ = client

    response = test_client.post('/chat', json={'conversation_id': 'conv-1'})

    assert response.status_code == 422
    body = response.json()
    assert body['error']['type'] == 'validation_error'
    assert body['error']['message'] == 'Request validation failed'
    assert isinstance(body['error']['details'], list)


def test_unhandled_exception_uses_safe_format(app):
    async def boom() -> None:
        raise RuntimeError('boom')

    app.add_api_route('/boom', boom, methods=['GET'])

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get('/boom')

    assert response.status_code == 500
    assert response.json() == {
        'error': {
            'type': 'internal_server_error',
            'message': 'An unexpected error occurred.',
        }
    }


def test_lifespan_starts_without_running_migrations_or_seed(monkeypatch):
    from fastapi import FastAPI

    import app.core.lifespan as lifespan_module

    called: dict[str, object] = {}

    class DummyKnowledgeManager:
        pass

    class DummyRAGChain:
        def __init__(self, *args, **kwargs) -> None:
            called['rag_initialized'] = True

    class DummyChatService:
        def __init__(self, *args, **kwargs) -> None:
            called['chat_initialized'] = True

    def fake_check_database_connection() -> None:
        called['database_checked'] = True

    def fake_session_factory():
        called['session_factory_used'] = True
        return object()

    monkeypatch.setattr(settings, 'TWILIO_SIGNATURE_VERIFICATION_ENABLED', False, raising=False)
    monkeypatch.setattr(lifespan_module, 'check_database_connection', fake_check_database_connection)
    monkeypatch.setattr(lifespan_module, 'get_session_factory', lambda: fake_session_factory)
    monkeypatch.setattr(lifespan_module, 'KnowledgeManager', DummyKnowledgeManager)
    monkeypatch.setattr(lifespan_module, 'RAGChain', DummyRAGChain)
    monkeypatch.setattr(lifespan_module, 'ChatService', DummyChatService)

    async def run_lifespan() -> None:
        app = FastAPI()
        async with lifespan_module.lifespan(app):
            assert app.state.db_session_factory is fake_session_factory

    asyncio.run(run_lifespan())

    assert called['database_checked'] is True
    assert called['rag_initialized'] is True
    assert called['chat_initialized'] is True
    assert 'session_factory_used' not in called


def test_lifespan_requires_database_url(monkeypatch):
    from fastapi import FastAPI

    import app.core.lifespan as lifespan_module

    monkeypatch.setattr(settings, 'DATABASE_URL', '', raising=False)
    monkeypatch.setattr(settings, 'TWILIO_SIGNATURE_VERIFICATION_ENABLED', False, raising=False)

    async def run_lifespan() -> None:
        async with lifespan_module.lifespan(FastAPI()):
            return None

    try:
        asyncio.run(run_lifespan())
    except RuntimeError as exc:
        assert str(exc) == 'Missing required setting: DATABASE_URL'
    else:
        raise AssertionError('Expected startup to fail when DATABASE_URL is missing.')


def test_lifespan_does_not_require_openai_api_key(monkeypatch):
    from fastapi import FastAPI

    import app.core.lifespan as lifespan_module

    monkeypatch.setattr(settings, 'DATABASE_URL', 'postgresql+psycopg2://postgres:postgres@localhost:5432/tiffin_ai', raising=False)
    monkeypatch.setattr(settings, 'OPENAI_API_KEY', '', raising=False)
    monkeypatch.setattr(settings, 'TWILIO_SIGNATURE_VERIFICATION_ENABLED', False, raising=False)
    monkeypatch.setattr(lifespan_module, 'check_database_connection', lambda: None)
    monkeypatch.setattr(lifespan_module, 'get_session_factory', lambda: (lambda: object()))

    class DummyKnowledgeManager:
        pass

    class DummyRAGChain:
        def __init__(self, *args, **kwargs) -> None:
            return None

    class DummyChatService:
        def __init__(self, *args, **kwargs) -> None:
            return None

    monkeypatch.setattr(lifespan_module, 'KnowledgeManager', DummyKnowledgeManager)
    monkeypatch.setattr(lifespan_module, 'RAGChain', DummyRAGChain)
    monkeypatch.setattr(lifespan_module, 'ChatService', DummyChatService)

    async def run_lifespan() -> None:
        async with lifespan_module.lifespan(FastAPI()):
            return None

    asyncio.run(run_lifespan())
