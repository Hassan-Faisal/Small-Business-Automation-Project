# RAG Architecture

## Document Information

| Field | Details |
|---|---|
| Product Name | TiffinAI |
| Document Type | RAG Architecture Specification |
| Version | 1.0 |
| Status | Draft |
| Prepared By | Hassan Faisal |
| Last Updated | July 2026 |

---

# Table of Contents

1. Introduction
2. Purpose
3. RAG Architecture Goals
4. RAG Design Principles
5. RAG Scope
6. Knowledge Sources
7. Document Ingestion Pipeline
8. Document Processing
9. Embedding Architecture
10. Vector Database
11. Retrieval Workflow
12. Query Processing
13. Context Construction
14. Response Generation
15. Metadata Strategy
16. Guardrails
17. Failure Handling
18. Evaluation Strategy
19. Security and Privacy
20. Observability
21. Future Improvements
22. Architecture Summary

---

# 1. Introduction

TiffinAI uses Retrieval-Augmented Generation to answer business knowledge and policy-related questions accurately.

The RAG system retrieves relevant information from approved business documents and provides that information to the language model as context.

RAG is intentionally separated from transactional business services.

Transactional information such as prices, menus, order status, subscription status, inventory, cart totals, and delivery details must come from deterministic business services rather than the RAG knowledge base.

---

# 2. Purpose

This document defines the architecture of the TiffinAI RAG system.

It explains:

- Which information belongs in the knowledge base
- How documents are collected and processed
- How text is divided into chunks
- How embeddings are created
- How data is stored in the vector database
- How relevant knowledge is retrieved
- How retrieved context is passed to the AI Orchestrator
- How hallucination and unsupported answers are prevented
- How retrieval quality is evaluated

---

# 3. RAG Architecture Goals

The RAG architecture is designed to achieve the following goals:

- Provide accurate answers from approved business documents
- Reduce hallucination
- Keep business knowledge separate from transactional data
- Support easy knowledge-base updates
- Retrieve relevant information efficiently
- Preserve document traceability
- Support multilingual customer questions
- Return safe responses when information is unavailable
- Enable evaluation and observability
- Support future multi-business knowledge isolation

---

# 4. RAG Design Principles

## 4.1 Approved Knowledge Only

Only reviewed and approved business documents may be added to the knowledge base.

The assistant must not treat unverified text as an authoritative source.

---

## 4.2 RAG Is Not a Transactional Database

The knowledge base is not responsible for storing dynamic operational information.

RAG must not provide:

- Current menu availability
- Product prices
- Cart totals
- Order status
- Rider location
- Subscription status
- Inventory levels
- Payment status

These values must come from deterministic services and the relational database.

---

## 4.3 Source-Grounded Responses

Every answer generated through RAG must be supported by retrieved context.

If no reliable context is found, the assistant must not invent an answer.

---

## 4.4 Metadata-Aware Retrieval

Every document chunk should contain metadata describing its origin, category, version, and business ownership.

---

## 4.5 Replaceable Components

The embedding model, vector database, retriever, and language model should remain replaceable without redesigning the complete system.

---

# 5. RAG Scope

The RAG system is responsible for answering non-transactional business questions.

## In Scope

Examples include:

- Refund policy
- Cancellation policy
- Delivery policy
- Subscription rules
- Meal preparation information
- Allergy disclaimers
- Business hours
- Delivery areas
- Payment policy
- Customer support process
- Frequently asked questions
- General service information

## Out of Scope

The RAG system must not answer questions requiring live operational data.

Examples include:

- What is today's menu?
- How much is my cart?
- Where is my rider?
- Has my order been confirmed?
- Is this item available?
- When does my subscription renew?
- What is my outstanding payment?

These questions must be routed to the appropriate business service.

---

# 6. Knowledge Sources

The knowledge base may contain approved documents such as:

- Refund policy
- Cancellation policy
- Delivery policy
- Subscription policy
- Business hours
- Service-area information
- Food safety guidelines
- Allergy information
- Payment policy
- Customer support guide
- Frequently asked questions
- Internal support procedures

Recommended source formats include:

- Markdown
- Plain text
- PDF
- DOCX
- Structured JSON
- Approved database exports

All sources should have a clear owner and version.

---

# 7. Document Ingestion Pipeline

The ingestion pipeline prepares business documents for retrieval.

The process follows these stages:

```text
Source Document
       ↓
Document Validation
       ↓
Text Extraction
       ↓
Text Cleaning
       ↓
Chunking
       ↓
Metadata Assignment
       ↓
Embedding Generation
       ↓
Vector Storage
       ↓
Index Validation

## 8. Document Processing

After documents have been ingested, they undergo several processing steps before becoming searchable.

The processing pipeline includes:

- Text normalization
- Removal of unsupported formatting
- Character encoding validation
- Duplicate detection
- Whitespace normalization
- Section identification
- Metadata enrichment

The objective of document processing is to ensure that only clean, structured, and searchable content enters the embedding pipeline.

---

# 9. Embedding Architecture

The embedding model converts document chunks into dense vector representations that capture semantic meaning.

The embedding pipeline consists of:

- Document chunk
- Embedding model
- Vector representation
- Vector storage

Embedding generation should be deterministic for identical document versions to simplify version management and retrieval consistency.

The embedding model should remain replaceable so that future improvements can be adopted without redesigning the overall architecture.

---

# 10. Vector Database

The vector database stores embeddings together with their associated metadata.

The initial implementation uses ChromaDB because it provides:

- Fast semantic retrieval
- Lightweight deployment
- Local development support
- Simple integration with LangChain and LangGraph

Future deployments may migrate to:

- pgvector
- Pinecone
- Weaviate
- Qdrant
- Milvus

Changing the vector database should not require changes to the AI orchestration workflow.

---

# 11. Retrieval Workflow

The retrieval workflow follows these stages:

1. Customer asks a knowledge-based question.
2. AI identifies that RAG is required.
3. User query is converted into an embedding.
4. Semantic search retrieves relevant document chunks.
5. Retrieved chunks are ranked.
6. Relevant context is returned to the AI Orchestrator.
7. The language model generates a grounded response.

Only highly relevant document chunks should be provided to the language model to minimize irrelevant context.

---

# 12. Query Processing

Before retrieval begins, customer queries are processed to improve search quality.

Processing steps include:

- Language normalization
- Spelling correction where appropriate
- Removal of unnecessary formatting
- Query embedding generation
- Semantic similarity search

The original customer intent should always be preserved during query processing.

---

# 13. Context Construction

Retrieved document chunks are combined into a structured context before being provided to the language model.

Context construction should:

- Preserve document meaning
- Avoid duplicate information
- Prioritize higher-confidence matches
- Respect token limits
- Maintain source ordering where appropriate

Only relevant context should be supplied to the language model.

---

# 14. Response Generation

The language model generates responses using:

- Customer question
- Retrieved document context
- Conversation context
- System instructions

Responses should:

- Be grounded in retrieved evidence
- Clearly answer the customer's question
- Avoid unsupported claims
- Remain concise and natural

If sufficient evidence is unavailable, the assistant should acknowledge that the requested information could not be found rather than generating speculative answers.

---

# 15. Metadata Strategy

Each document chunk should contain metadata describing its origin.

Typical metadata includes:

- Document ID
- Document title
- Category
- Version
- Source
- Business owner
- Last updated date
- Language
- Chunk number

Metadata improves retrieval quality, traceability, and future document management.

---

# 16. Guardrails

The RAG system operates within strict guardrails to ensure reliable responses.

The assistant must:

- Answer only from retrieved evidence
- Reject unsupported requests
- Avoid hallucination
- Preserve document meaning
- Respect business policies

The assistant must never:

- Invent policy information
- Generate unsupported business rules
- Answer transactional questions from the knowledge base
- Modify retrieved information

These guardrails maintain trustworthiness and consistency.

---

# 17. Failure Handling

Several failure scenarios may occur during retrieval.

Examples include:

- No relevant documents found
- Embedding generation failure
- Vector database unavailable
- Low retrieval confidence
- Corrupted document metadata

When failures occur, the system should:

- Inform the customer politely
- Avoid unsupported answers
- Log the failure
- Retry safe operations when appropriate
- Escalate persistent issues for investigation

---

# 18. Evaluation Strategy

The quality of the RAG system should be evaluated continuously.

Evaluation metrics include:

- Retrieval precision
- Retrieval recall
- Context relevance
- Grounded response accuracy
- Hallucination rate
- Average retrieval latency
- Customer satisfaction

Regular evaluation ensures that the knowledge base continues to provide accurate and reliable responses.

---

# 19. Security and Privacy

Business knowledge must be protected throughout the retrieval pipeline.

Security considerations include:

- Controlled document access
- Role-based permissions
- Secure vector storage
- Metadata validation
- Encryption where appropriate
- Secure API communication
- Audit logging

Sensitive business information should only be accessible to authorized systems and personnel.

---

# 20. Observability

The RAG pipeline should provide sufficient observability for monitoring and debugging.

Important operational metrics include:

- Number of indexed documents
- Embedding generation success rate
- Retrieval latency
- Vector database availability
- Retrieval confidence
- Failed retrievals
- Knowledge base update frequency

These metrics support continuous improvement and operational reliability.

---

# 21. Future Improvements

Future versions of the RAG system may include:

- Hybrid semantic and keyword search
- Knowledge graph integration
- Automatic document versioning
- Incremental indexing
- Multilingual embeddings
- Business-specific retrieval tuning
- Cross-business knowledge isolation
- Personalized knowledge retrieval
- Advanced reranking models

The architecture has been designed so that these improvements can be introduced with minimal impact on the existing system.

---

# 22. Architecture Summary

The TiffinAI RAG architecture provides a reliable mechanism for retrieving business knowledge while keeping transactional operations separate from conversational intelligence.

Approved documents are processed, embedded, and stored within a vector database, enabling semantic retrieval of relevant information during customer conversations.

By grounding responses in verified business documents and enforcing strict guardrails, the RAG system minimizes hallucination, improves answer reliability, and complements the deterministic business services coordinated by the AI Orchestrator.

This modular architecture ensures that the knowledge retrieval system remains scalable, maintainable, and adaptable to future enhancements.