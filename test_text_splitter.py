from app.rag.document_loader import DocumentLoader
from app.rag.text_splitter import TextSplitter

loader = DocumentLoader("app/data/knowledge_base")
documents = loader.load_documents()

splitter = TextSplitter()

chunks = splitter.split_documents(documents)

print(f"Original documents: {len(documents)}")
print(f"Chunks created: {len(chunks)}")

print("\nFirst Chunk:\n")
print("=" * 60)
print(chunks[0].page_content)