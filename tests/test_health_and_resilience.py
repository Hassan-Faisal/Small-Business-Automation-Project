from __future__ import annotations

import logging

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


def test_lifespan_does_not_create_schema_or_seed(monkeypatch):
    from fastapi import FastAPI

    import app.core.database as database_module
    import app.core.lifespan as lifespan_module

    called = {"create_all": False}

    def fail_create_all(*args, **kwargs):
        called["create_all"] = True
        raise AssertionError("create_all should not be called during startup")

    class DummyKnowledgeManager:
        def initialize(self) -> None:
            return None

    class DummyRAGChain:
        def __init__(self, *args, **kwargs) -> None:
            return None

    class DummyChatService:
        def __init__(self, *args, **kwargs) -> None:
            return None

    monkeypatch.setattr(database_module.Base.metadata, "create_all", fail_create_all)
    monkeypatch.setattr(lifespan_module, "KnowledgeManager", DummyKnowledgeManager)
    monkeypatch.setattr(lifespan_module, "RAGChain", DummyRAGChain)
    monkeypatch.setattr(lifespan_module, "ChatService", DummyChatService)
    monkeypatch.setattr(lifespan_module, "_get_twilio_request_validator", lambda: None)

    async def run_lifespan() -> None:
        async with lifespan_module.lifespan(FastAPI()):
            return None

    import asyncio

    asyncio.run(run_lifespan())
    assert called == {"create_all": False}
