from __future__ import annotations

from collections.abc import Callable
from contextlib import closing

from sqlalchemy.orm import Session

from app.core.database import get_session_factory
from app.langgraph.memory import ConversationMemory
from app.langgraph.workflow import OrderConversationWorkflow
from app.rag.rag_chain import RAGChain
from app.services.order_service import OrderService
from app.services.product_service import ProductService
from app.services.tiffin_service import TiffinCatalogService


class ChatService:
    """Handles chat interactions with the AI assistant."""

    def __init__(
        self,
        rag_chain: RAGChain,
        product_service: ProductService | None = None,
        order_service: OrderService | None = None,
        meal_service: TiffinCatalogService | None = None,
        session_factory: Callable[[], Session] | None = None,
    ):
        self.rag_chain = rag_chain
        self._session_factory = session_factory or get_session_factory()
        self.product_service = product_service
        self.order_service = order_service
        self.meal_service = meal_service
        self.workflow: OrderConversationWorkflow | None = None

        if product_service is not None and order_service is not None and meal_service is not None:
            memory_session = getattr(product_service, "db", None)
            memory = ConversationMemory(memory_session) if isinstance(memory_session, Session) else None
            if memory is not None:
                self.workflow = OrderConversationWorkflow(
                    rag_chain=rag_chain,
                    product_service=product_service,
                    order_service=order_service,
                    meal_service=meal_service,
                    memory=memory,
                )

    async def chat(
        self,
        message: str,
        conversation_id: str = "default",
        customer_phone: str | None = None,
        message_id: str | None = None,
    ) -> str:
        """Process a user's message and return an AI response."""

        if self.workflow is not None:
            result = await self.workflow.run(
                message,
                conversation_id=conversation_id,
                customer_phone=customer_phone,
                message_id=message_id,
            )
            return result["response"]

        with closing(self._session_factory()) as db_session:
            workflow = OrderConversationWorkflow(
                rag_chain=self.rag_chain,
                product_service=ProductService(db_session),
                order_service=OrderService(db_session),
                meal_service=TiffinCatalogService(db_session),
                memory=ConversationMemory(db_session),
            )
            result = await workflow.run(
                message,
                conversation_id=conversation_id,
                customer_phone=customer_phone,
                message_id=message_id,
            )
            return result["response"]
