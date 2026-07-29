from app.services.knowledge_manager import KnowledgeManager
from app.services.openai_service import OpenAIService


class RAGChain:
    """
    Retrieval-Augmented Generation pipeline.
    """

    def __init__(self, knowledge_manager: KnowledgeManager | None = None):
        self.knowledge_manager = knowledge_manager
        self.retriever = None
        self.llm = OpenAIService()

        if knowledge_manager is not None:
            self.retriever = knowledge_manager.get_retriever()

    def build_prompt(self, question: str, context: str) -> str:
        """
        Build the prompt for the language model.
        """

        return f"""You are an AI assistant for ABC Electronics.

                Answer the customer's question using ONLY the information provided in the context below.

                If the answer is not present in the context, politely say that you don't have that information.

                Context:
                --------------------
                {context}
                --------------------

                Customer Question:
                {question}

                Answer:
                """

    async def ask(self, question: str) -> str:
        """
        Answer a user's question using Retrieval-Augmented Generation.
        """
        if self.retriever is None:
            return "I don't have knowledge access configured yet."

        documents = self.retriever.invoke(question)

        context = "\n\n".join(document.page_content for document in documents)

        prompt = self.build_prompt(
            question=question,
            context=context,
        )

        response = await self.llm.generate_response(prompt)

        return response