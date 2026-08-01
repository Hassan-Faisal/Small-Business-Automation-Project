from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class FakeRAGChain:
    async def ask(self, message: str) -> str:
        lower = message.lower()
        if "refund" in lower:
            return "Refunds follow the published TiffinAI refund policy."
        if "deliver" in lower:
            return "TiffinAI delivers in the listed service areas from the policy documents."
        return "I could not find that information in the TiffinAI policy documents. Please contact support."


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run a deterministic smoke demo against an explicit database URL.")
    parser.add_argument(
        '--database-url',
        default=os.environ.get('SMOKE_DATABASE_URL'),
        help='Target database URL for the smoke demo. Defaults to SMOKE_DATABASE_URL.',
    )
    args = parser.parse_args()

    if not args.database_url:
        raise RuntimeError('Provide --database-url or set SMOKE_DATABASE_URL before running the smoke demo.')

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.data.tiffin_seed import seed_tiffin_catalog
    from app.langgraph.memory import ConversationMemory
    from app.langgraph.workflow import OrderConversationWorkflow
    from app.services.order_service import OrderService
    from app.services.product_service import ProductService
    from app.services.tiffin_service import TiffinCatalogService

    alembic_cfg = Config(str(PROJECT_ROOT / 'alembic.ini'))
    alembic_cfg.set_main_option('sqlalchemy.url', args.database_url)
    command.upgrade(alembic_cfg, 'head')

    engine = create_engine(args.database_url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = SessionLocal()
    try:
        seed_tiffin_catalog(session)
        workflow = OrderConversationWorkflow(
            rag_chain=FakeRAGChain(),
            product_service=ProductService(session),
            order_service=OrderService(session),
            meal_service=TiffinCatalogService(session),
            memory=ConversationMemory(session),
        )
        conversation_id = 'smoke-demo'
        customer_phone = '15551234567'
        messages = [
            'hello',
            "today's menu",
            'weekly menu',
            'view cart',
            'add chicken biryani',
            'view cart',
            'confirm order',
            'my address is House 12, Street 4, Islamabad',
            'confirm order',
            'track my order',
            'subscription plans',
            'subscription status',
            'where do you deliver?',
            'what is your refund policy?',
            'human support',
            'unknown request words',
        ]
        for index, message in enumerate(messages, start=1):
            result = await workflow.run(
                message,
                conversation_id=conversation_id,
                customer_phone=customer_phone,
                message_id=f'smoke-{index}',
            )
            print(f'User: {message}')
            print(f"Assistant: {result['response']}")
            print()
    finally:
        session.close()
        engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
