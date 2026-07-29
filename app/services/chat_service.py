from app.core.database import SessionLocal
from app.langgraph.workflow import OrderConversationWorkflow
from app.services.tiffin_service import TiffinCatalogService
from app.rag.rag_chain import RAGChain
from app.services.order_service import OrderService
from app.services.product_service import ProductService


class ChatService:
    """Handles chat interactions with the AI assistant."""

    def __init__(
        self,
        rag_chain: RAGChain,
        product_service: ProductService | None = None,
        order_service: OrderService | None = None,
        meal_service: TiffinCatalogService | None = None,
    ):
        self.rag_chain = rag_chain
        self.product_service = product_service
        self.order_service = order_service
        self.meal_service = meal_service

        if product_service is None or order_service is None or meal_service is None:
            db_session = None
            if product_service is not None:
                db_session = product_service.db
            elif order_service is not None:
                db_session = order_service.db
            else:
                db_session = SessionLocal()

            self.product_service = product_service or ProductService(db_session)
            self.order_service = order_service or OrderService(db_session)
            self.meal_service = meal_service or TiffinCatalogService(db_session)

        self.workflow = OrderConversationWorkflow(
            rag_chain=rag_chain,
            product_service=self.product_service,
            order_service=self.order_service,
            meal_service=self.meal_service,
        )

    async def chat(
        self,
        message: str,
        conversation_id: str = "default",
        customer_phone: str | None = None,
        message_id: str | None = None,
    ) -> str:
        """Process a user's message and return an AI response."""

        result = await self.workflow.run(
            message,
            conversation_id=conversation_id,
            customer_phone=customer_phone,
            message_id=message_id,
        )
        return result["response"]
