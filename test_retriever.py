from app.services.knowledge_manager import KnowledgeManager


def main():
    knowledge_manager = KnowledgeManager()
    knowledge_manager.initialize()

    retriever = knowledge_manager.get_retriever()

    db = knowledge_manager.vector_store.db
    print(f"Documents stored in Chroma: {db._collection.count()}")

    # Test query
    query = "Do you accept JazzCash?"

    print(f"\nQuery: {query}\n")
    print("=" * 60)

    # Retrieve relevant documents
    # documents = retriever.invoke(query)
    documents = retriever.invoke("electronics")
    print(f"\nRetrieved {len(documents)} document(s).\n")

    for index, document in enumerate(documents, start=1):
        print(f"\nChunk {index}")
        print("-" * 60)
        print(document.page_content)


if __name__ == "__main__":
    main()