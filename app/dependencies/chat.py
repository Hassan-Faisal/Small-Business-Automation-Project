from fastapi import Request

from app.services.chat_service import ChatService


def get_chat_service(
    request: Request,
) -> ChatService:
    """
    Return the shared ChatService instance.
    """

    return request.app.state.chat_service