from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Incoming chat request."""

    message: str
    conversation_id: str | None = None
    customer_phone: str | None = Field(default=None, max_length=30)
    message_id: str | None = None


class ChatResponse(BaseModel):
    """Outgoing chat response."""

    response: str
