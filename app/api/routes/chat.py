from fastapi import APIRouter, Depends

from app.dependencies.chat import get_chat_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post(
    "",
    response_model=ChatResponse,
)
async def chat(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    customer_phone = request.customer_phone or "test:+15550000000"
    answer = await chat_service.chat(
        request.message,
        conversation_id=request.conversation_id or "default",
        customer_phone=customer_phone,
        message_id=request.message_id,
    )

    return ChatResponse(
        response=answer,
    )
