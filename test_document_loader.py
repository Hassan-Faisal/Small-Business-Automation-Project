from app.rag.document_loader import DocumentLoader


loader = DocumentLoader(
    "app/data/knowledge_base"
)

documents = loader.load_documents()

print(f"Loaded {len(documents)} document(s).\n")

for document in documents:
    print("=" * 60)
    print(document.page_content)