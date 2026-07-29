import asyncio 
from app.rag.rag_chain import RAGChain


async def main():
    rag = RAGChain()

    question = "What is in Menu?"

    print(f"\nQuestion: {question}")
    print("=" * 60)

    answer = await rag.ask(question)

    print("\nAnswer:\n")
    print(answer)


if __name__ == "__main__":
    asyncio.run(main())