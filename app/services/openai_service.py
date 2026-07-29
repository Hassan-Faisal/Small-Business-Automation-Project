from langchain_core.messages import HumanMessage

from app.core.llm import llm


class OpenAIService:
    """
    Service responsible for communicating with the OpenAI model.
    """

    async def generate_response(self, prompt: str) -> str:
        """
        Generate a response from the language model.
        """
        response = await llm.ainvoke(
            [HumanMessage(content=prompt)]
        )

        return response.content


openai_service = OpenAIService()