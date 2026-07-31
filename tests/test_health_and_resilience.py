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
    class FailingFactory:
        def __call__(self):
            raise RuntimeError('database unavailable')

    app.state.db_session_factory = FailingFactory()

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


def test_lifespan_bootstraps_database_and_seed(monkeypatch):
    from fastapi import FastAPI

    import app.core.lifespan as lifespan_module

    called: dict[str, object] = {}

    class DummySession:
        def close(self) -> None:
            called['session_closed'] = True

    class DummyKnowledgeManager:
        def initialize(self) -> None:
            called['knowledge_initialized'] = True

    class DummyRAGChain:
        def __init__(self, *args, **kwargs) -> None:
            called['rag_initialized'] = True

    class DummyChatService:
        def __init__(self, *args, **kwargs) -> None:
            called['chat_initialized'] = True

    def fake_session_factory() -> DummySession:
        called['session_factory_used'] = True
        return DummySession()

    monkeypatch.setattr(settings, 'OPENAI_API_KEY', 'test-openai-key', raising=False)
    monkeypatch.setattr(settings, 'TWILIO_AUTH_TOKEN', 'test-twilio-token', raising=False)
    monkeypatch.setattr(settings, 'TWILIO_SIGNATURE_VERIFICATION_ENABLED', True, raising=False)
    monkeypatch.setattr(lifespan_module, 'initialize_database', lambda: called.__setitem__('database_initialized', True))
    monkeypatch.setattr(lifespan_module, 'build_session_factory', lambda: fake_session_factory)
    monkeypatch.setattr(lifespan_module, 'seed_tiffin_catalog', lambda session: called.__setitem__('seed_session', session))
    monkeypatch.setattr(lifespan_module, 'KnowledgeManager', DummyKnowledgeManager)
    monkeypatch.setattr(lifespan_module, 'RAGChain', DummyRAGChain)
    monkeypatch.setattr(lifespan_module, 'ChatService', DummyChatService)
    monkeypatch.setattr(lifespan_module, '_get_twilio_request_validator', lambda: None)

    async def run_lifespan() -> None:
        app = FastAPI()
        async with lifespan_module.lifespan(app):
            assert app.state.db_session_factory is fake_session_factory

    asyncio.run(run_lifespan())

    assert called['database_initialized'] is True
    assert called['session_factory_used'] is True
    assert called['session_closed'] is True
    assert called['seed_session'].__class__ is DummySession
    assert called['knowledge_initialized'] is True
    assert called['rag_initialized'] is True
    assert called['chat_initialized'] is True


def test_lifespan_requires_openai_api_key(monkeypatch):
    from fastapi import FastAPI

    import app.core.lifespan as lifespan_module

    monkeypatch.setattr(settings, 'DATABASE_URL', 'sqlite:///./test.db', raising=False)
    monkeypatch.setattr(settings, 'OPENAI_API_KEY', '', raising=False)
    monkeypatch.setattr(settings, 'TWILIO_AUTH_TOKEN', 'test-twilio-token', raising=False)
    monkeypatch.setattr(settings, 'TWILIO_SIGNATURE_VERIFICATION_ENABLED', True, raising=False)

    async def run_lifespan() -> None:
        async with lifespan_module.lifespan(FastAPI()):
            return None

    try:
        asyncio.run(run_lifespan())
    except RuntimeError as exc:
        assert str(exc) == 'Missing required setting: OPENAI_API_KEY'
    else:
        raise AssertionError('Expected startup to fail when OPENAI_API_KEY is missing.')
