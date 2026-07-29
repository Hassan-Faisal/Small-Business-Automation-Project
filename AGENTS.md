# Project Instructions

## Project

WhatsApp-first AI ordering assistant for a small food business.

## Stack

- Python
- FastAPI
- SQLAlchemy 2.x
- Alembic
- Pydantic v2
- LangGraph
- RAG
- ChromaDB
- OpenAI
- SQLite locally
- PostgreSQL-compatible production configuration

## Architecture

Keep these layers separate:

- api/routes: HTTP and webhook transport
- schemas: request and response validation
- models: SQLAlchemy ORM models
- services: deterministic business logic
- langgraph: conversational orchestration
- rag: business document retrieval
- core: configuration, database, lifespan, logging

## Rules

- Inspect existing code before editing.
- Preserve working functionality.
- Do not put business logic inside routes.
- Do not use floating-point numbers for money.
- Menu, pricing, totals, and order status must come from the database.
- RAG is only for policies, timings, delivery information, and FAQs.
- Never allow the LLM to invent products, prices, totals, order IDs, or status.
- Add type hints.
- Add error handling.
- Add tests for every major service.
- Run tests after changes.
- Report changed files and unresolved issues.
- Never expose secrets or commit .env.