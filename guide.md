# SmallBusinessBrain — Engineering Guide

> This document is the single source of truth for the engineering standards, architecture decisions, and development workflow of the SmallBusinessBrain project.
> Every team member must read and follow this guide throughout the project.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Project Philosophy](#2-project-philosophy)
3. [Development Strategy](#3-development-strategy)
4. [Folder Structure](#4-folder-structure)
5. [Backend Architecture](#5-backend-architecture)
6. [Database Guidelines](#6-database-guidelines)
7. [API Design Guidelines](#7-api-design-guidelines)
8. [Business Logic Rules](#8-business-logic-rules)
9. [AI Architecture Guidelines](#9-ai-architecture-guidelines)
10. [RAG Guidelines](#10-rag-guidelines)
11. [Memory Strategy](#11-memory-strategy)
12. [WhatsApp Integration Guidelines](#12-whatsapp-integration-guidelines)
13. [Coding Standards](#13-coding-standards)
14. [Testing Strategy](#14-testing-strategy)
15. [Git Workflow](#15-git-workflow)
16. [Development Milestones](#16-development-milestones)
17. [Non-Negotiable Rules](#17-non-negotiable-rules)
18. [Project Completion Checklist](#18-project-completion-checklist)

---

## 1. Project Overview

**Project Name:** SmallBusinessBrain

**Purpose:**
An AI-powered WhatsApp-based business assistant for small Pakistani businesses (initial domain: local salons/parlours) that allows customers to:

- Book appointments
- Check service availability and prices
- Ask policy questions (timings, cancellation, etc.)
- Receive confirmations and reminders
- Get answers in Urdu and English

**What this is NOT:**
- Not a menu-based chatbot
- Not a keyword-triggered bot
- Not a web app customers need to download or visit

**What this IS:**
- An Agentic AI application
- A WhatsApp-native experience
- A RAG-powered knowledge assistant grounded in real business data
- A system that escalates to the human owner when it cannot confidently help

**Initial Target User:**
A local salon/parlour owner in Pakistan who receives 50–100+ WhatsApp messages daily asking repetitive questions about timings, prices, and appointment availability — and answers every single one manually.

---

## 2. Project Philosophy

### 2.1 Core Principles

| Principle | What it means in this project |
|---|---|
| Single Responsibility | Every module, class, and function does one thing only |
| Clean Architecture | Business logic is completely independent of frameworks |
| Layered Architecture | Routes → Services → Repositories → Database. No skipping layers |
| Dependency Injection | Dependencies are injected, never instantiated inside functions |
| Explicit Business Rules | All rules live in Python, never inside prompts or LLM responses |
| Deterministic Services | Prices, availability, and appointments are calculated in Python — never by the LLM |
| Composition over Inheritance | Prefer composing small units over deep class hierarchies |
| Agent Orchestration Separation | AI orchestration logic is completely separate from business logic |

### 2.2 The Golden Rule

> The LLM is a language interface. It understands the customer's intent and generates human-friendly responses. It never makes business decisions, never writes to the database, and never calculates anything.

### 2.3 Trust Hierarchy

```
Customer Message
      ↓
LLM (understands intent, generates response)
      ↓
Tools (bridge between LLM and Python services)
      ↓
Services (enforce business rules, deterministic logic)
      ↓
Repositories (database operations only)
      ↓
PostgreSQL (source of truth)
```

---

## 3. Development Strategy

### 3.1 Approach

**Never build everything at once.**

The biggest mistake student teams make is trying to integrate WhatsApp + AI + RAG + database all in week one. This leads to a broken system nobody understands.

Build in strict layers. Each milestone must be working and tested before the next one begins.

### 3.2 Milestone-First Development

| Phase | Focus | Goal |
|---|---|---|
| Phase 1 | Foundation | Project structure, config, database running locally |
| Phase 2 | Database | All models defined, migrations working, seed data ready |
| Phase 3 | Services | Business logic working independently with unit tests |
| Phase 4 | API Layer | REST endpoints working, tested via Postman/curl |
| Phase 5 | AI Core | RAG pipeline working, agent answering from knowledge base |
| Phase 6 | Conversation | Full multi-turn conversation working in terminal/test |
| Phase 7 | WhatsApp | Meta Cloud API integrated, real messages flowing |
| Phase 8 | Polish | Escalation, daily summary, owner notifications |

### 3.3 What "done" means for each phase

A phase is done only when:
- The feature works end-to-end
- It has at least basic tests
- The team has reviewed it together
- It is committed to the main branch

---

## 4. Folder Structure

```
smallbusinessbrain/
│
├── app/
│   ├── api/                        # Route handlers only — thin layer
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── webhook.py          # WhatsApp webhook endpoint
│   │   │   ├── appointments.py     # Appointment management endpoints
│   │   │   ├── knowledge.py        # Knowledge upload endpoints
│   │   │   └── health.py           # Health check endpoint
│   │   └── __init__.py
│   │
│   ├── services/                   # All business logic lives here
│   │   ├── __init__.py
│   │   ├── appointment_service.py  # Booking, cancellation, availability
│   │   ├── knowledge_service.py    # Document ingestion, chunking
│   │   ├── message_service.py      # Incoming message processing
│   │   ├── escalation_service.py   # Human handoff logic
│   │   └── summary_service.py      # Daily summary generation
│   │
│   ├── repositories/               # Database operations only
│   │   ├── __init__.py
│   │   ├── appointment_repo.py
│   │   ├── business_repo.py
│   │   ├── conversation_repo.py
│   │   └── message_repo.py
│   │
│   ├── models/                     # SQLAlchemy database models
│   │   ├── __init__.py
│   │   ├── business.py
│   │   ├── appointment.py
│   │   ├── conversation.py
│   │   ├── message.py
│   │   └── document.py
│   │
│   ├── schemas/                    # Pydantic request/response schemas
│   │   ├── __init__.py
│   │   ├── appointment.py
│   │   ├── message.py
│   │   ├── webhook.py
│   │   └── knowledge.py
│   │
│   ├── ai/                         # All AI-related code
│   │   ├── __init__.py
│   │   ├── agent.py                # Main agent orchestration
│   │   ├── tools/                  # LangChain tools (bridge to services)
│   │   │   ├── __init__.py
│   │   │   ├── appointment_tools.py
│   │   │   ├── knowledge_tools.py
│   │   │   └── escalation_tool.py
│   │   ├── rag/                    # RAG pipeline
│   │   │   ├── __init__.py
│   │   │   ├── ingestion.py        # Document loading and chunking
│   │   │   ├── embeddings.py       # Embedding generation
│   │   │   ├── retriever.py        # Vector search
│   │   │   └── grounding.py        # Hallucination prevention
│   │   └── prompts/                # All system prompts
│   │       ├── __init__.py
│   │       ├── system_prompt.py
│   │       └── templates.py
│   │
│   ├── core/                       # Shared core utilities
│   │   ├── __init__.py
│   │   ├── config.py               # Environment configuration
│   │   ├── database.py             # DB session management
│   │   ├── dependencies.py         # FastAPI dependency injection
│   │   ├── exceptions.py           # Custom exception classes
│   │   └── logging.py              # Logging configuration
│   │
│   ├── integrations/               # External service integrations
│   │   ├── __init__.py
│   │   ├── whatsapp.py             # Meta WhatsApp Cloud API client
│   │   └── vector_store.py         # Qdrant client
│   │
│   └── main.py                     # FastAPI app entry point
│
├── alembic/                        # Database migrations
│   ├── versions/
│   └── env.py
│
├── tests/                          # All tests
│   ├── unit/
│   ├── integration/
│   └── conftest.py
│
├── docs/                           # Project documentation
├── .env.example                    # Environment variable template
├── .gitignore
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── guide.md                        # This file
```

### 4.1 Layer Communication Rules

| Layer | Can talk to | Cannot talk to |
|---|---|---|
| Routes (api/) | Services, Schemas | Repositories, Models, AI directly |
| Services | Repositories, other Services | Routes, Database directly |
| Repositories | Models, Database session | Services, Routes, AI |
| AI Tools | Services only | Repositories, Database, Routes |
| AI Agent | Tools only | Services, Repositories, Database directly |

---

## 5. Backend Architecture

### 5.1 Routes (api/)

Routes are the thinnest possible layer. They only:
- Receive HTTP requests
- Validate input via Pydantic schemas
- Call one service method
- Return the response

**Routes must never contain business logic.**

```
# Good
@router.post("/appointments")
async def book_appointment(data: AppointmentCreate, service: AppointmentService = Depends()):
    return await service.book(data)

# Bad — business logic inside route
@router.post("/appointments")
async def book_appointment(data: AppointmentCreate, db: Session = Depends()):
    if data.time < datetime.now():
        raise HTTPException(...)  # This belongs in service
```

### 5.2 Services

Services contain all business logic. They:
- Enforce business rules
- Coordinate between repositories
- Make decisions (is this slot available? should we escalate?)
- Never interact with HTTP or WhatsApp directly

Every service method should be independently testable without a running server.

### 5.3 Repositories

Repositories only interact with the database. They:
- Execute queries via SQLAlchemy
- Return model objects or None
- Never make business decisions
- Never call other services

### 5.4 Schemas

Pydantic schemas handle all input/output validation. Separate schemas for:
- Request input (e.g. `AppointmentCreate`)
- Response output (e.g. `AppointmentResponse`)
- Internal data transfer (e.g. `AppointmentData`)

Never return raw SQLAlchemy model objects from API endpoints.

### 5.5 Dependency Injection

All dependencies (database session, services, repositories) are injected via FastAPI's `Depends()`. Nothing is instantiated inside route functions directly.

---

## 6. Database Guidelines

### 6.1 Core Tables

| Table | Purpose |
|---|---|
| `businesses` | Business profile, WhatsApp number, owner info |
| `services` | Services offered (haircut, facial, etc.) with prices and duration |
| `appointments` | All bookings with status tracking |
| `conversations` | One record per customer conversation session |
| `messages` | Every individual message sent and received |
| `documents` | Uploaded knowledge files (FAQs, policies, service menus) |
| `daily_summaries` | Auto-generated end-of-day summaries per business |

### 6.2 Naming Conventions

- Table names: `snake_case`, plural (e.g. `appointments`)
- Column names: `snake_case` (e.g. `created_at`, `customer_phone`)
- Primary keys: always `id` (UUID preferred over integer for portability)
- Foreign keys: `{table_singular}_id` (e.g. `business_id`, `conversation_id`)
- Timestamps: always include `created_at` and `updated_at` on every table
- Boolean columns: prefix with `is_` or `has_` (e.g. `is_confirmed`, `is_escalated`)

### 6.3 Migrations

- Use Alembic for all schema changes
- Never modify the database manually
- Every migration must be reversible (include `downgrade()`)
- Migration filenames must be descriptive: `add_escalation_flag_to_conversations`
- Never edit an already-applied migration — create a new one

### 6.4 Indexes

Add indexes on:
- All foreign key columns
- `customer_phone` on messages/conversations (frequent lookup)
- `appointment_date` on appointments (frequent filtering)
- `business_id` on all business-scoped tables

### 6.5 Constraints

- All foreign keys must have explicit `ON DELETE` behavior defined
- Use `NOT NULL` wherever null values make no business sense
- Use `CHECK` constraints for status enums at the database level
- Appointment times must be validated at both application and database level

### 6.6 Transactions

Any operation that writes to multiple tables must be wrapped in a single transaction. If any part fails, everything rolls back. Never commit partial state.

---

## 7. API Design Guidelines

### 7.1 REST Conventions

| Action | Method | Path |
|---|---|---|
| List appointments | GET | `/api/v1/appointments` |
| Get one appointment | GET | `/api/v1/appointments/{id}` |
| Book appointment | POST | `/api/v1/appointments` |
| Update appointment | PATCH | `/api/v1/appointments/{id}` |
| Cancel appointment | DELETE | `/api/v1/appointments/{id}` |
| Upload knowledge doc | POST | `/api/v1/knowledge/upload` |
| WhatsApp webhook | POST | `/api/v1/webhook/whatsapp` |

### 7.2 Versioning

All endpoints are prefixed with `/api/v1/`. When breaking changes are needed, introduce `/api/v2/` without removing v1 immediately.

### 7.3 Response Format

All responses follow a consistent structure:

```json
{
  "success": true,
  "data": { },
  "message": "Appointment booked successfully"
}
```

Error responses:

```json
{
  "success": false,
  "error": "SLOT_NOT_AVAILABLE",
  "message": "This time slot is already booked. Please choose another time."
}
```

### 7.4 Error Handling

- Never expose internal exceptions or stack traces to the client
- Use custom exception classes defined in `core/exceptions.py`
- Map exceptions to appropriate HTTP status codes in a central exception handler
- Log full exception details internally, return safe messages externally

### 7.5 Status Codes

| Situation | Code |
|---|---|
| Success | 200 |
| Created | 201 |
| Bad request / validation error | 400 |
| Unauthorized | 401 |
| Forbidden | 403 |
| Not found | 404 |
| Conflict (e.g. slot taken) | 409 |
| Server error | 500 |

---

## 8. Business Logic Rules

This section is critical. Every team member must understand and follow these rules.

### 8.1 Where Business Logic Lives

**Business logic belongs ONLY in services. Period.**

| What | Where |
|---|---|
| Is this slot available? | `appointment_service.py` |
| Should this be escalated? | `escalation_service.py` |
| What is the price of this service? | `appointment_service.py` |
| Is this a valid appointment time? | `appointment_service.py` |
| How many messages have been sent today? | `message_service.py` |

### 8.2 What the LLM is Allowed to Do

| Allowed | Not Allowed |
|---|---|
| Understand customer intent | Calculate prices |
| Generate friendly responses | Check slot availability directly |
| Decide which tool to call | Write to the database |
| Maintain conversation context | Enforce cancellation policies |
| Translate between Urdu and English | Make booking decisions |

### 8.3 Escalation Rules (defined in Python, not prompts)

The system must escalate to the human owner when:
- Customer explicitly asks to speak to a human
- AI confidence is below threshold after 2 retrieval attempts
- Customer expresses frustration or complaint
- Request involves pricing negotiation or special discounts
- Any query the AI cannot answer from the knowledge base

These rules are checked in `escalation_service.py`, not decided by the LLM.

---

## 9. AI Architecture Guidelines

### 9.1 Agent Design

The agent is a LangChain/LangGraph-based orchestrator. It:
- Receives the customer's message
- Decides which tool to call based on intent
- Calls the tool
- Receives the tool result
- Generates a natural language response

The agent does NOT directly access the database, call WhatsApp, or make business decisions.

### 9.2 Tools

Tools are the only bridge between the AI agent and your Python services.

Each tool:
- Has a single, clear purpose
- Calls exactly one service method
- Returns structured data (not a natural language string)
- Is independently testable

| Tool | What it does | Calls |
|---|---|---|
| `check_availability` | Returns available slots for a date | `appointment_service.get_available_slots()` |
| `book_appointment` | Books a slot | `appointment_service.book()` |
| `cancel_appointment` | Cancels a booking | `appointment_service.cancel()` |
| `search_knowledge` | RAG search over business docs | `rag.retriever.search()` |
| `escalate_to_human` | Flags conversation for owner | `escalation_service.escalate()` |

### 9.3 Nodes (LangGraph)

Keep nodes small and focused. Each node does one thing:

- `receive_message` — parse and log incoming message
- `retrieve_context` — RAG retrieval if needed
- `run_agent` — LLM reasoning and tool selection
- `execute_tool` — tool execution
- `send_response` — format and send WhatsApp reply
- `check_escalation` — evaluate if human handoff needed

### 9.4 State Design

The conversation state passed between nodes should include:

```python
class ConversationState:
    business_id: str
    customer_phone: str
    conversation_id: str
    messages: list          # Full conversation history
    retrieved_context: str  # RAG results for current turn
    tool_calls: list        # Tools called this turn
    should_escalate: bool   # Escalation flag
    response: str           # Final response to send
```

### 9.5 When NOT to Call the LLM

The LLM should not be called when:
- The incoming message is a WhatsApp verification token (webhook setup)
- The message is empty or contains only media with no text
- The conversation is already flagged as escalated (route to human directly)
- A system-generated confirmation message is being sent

---

## 10. RAG Guidelines

### 10.1 What Belongs in RAG

RAG (Retrieval Augmented Generation) is used to ground the AI's answers in the business's actual knowledge.

| Belongs in RAG | Does NOT belong in RAG |
|---|---|
| Service menu and prices | Appointment availability (use DB) |
| Business timings and location | Customer order history (use DB) |
| Cancellation and return policies | Real-time slot data (use DB) |
| FAQs about services | Pricing calculations (use Python) |
| Staff information | Payment confirmation (use DB) |

### 10.2 Document Ingestion Pipeline

```
Owner uploads file (PDF / Excel / text)
        ↓
File stored in /uploads directory
        ↓
Text extracted (PyMuPDF for PDF, openpyxl for Excel)
        ↓
Text split into chunks (500 tokens, 50 token overlap)
        ↓
Each chunk embedded via OpenAI embeddings
        ↓
Embeddings stored in Qdrant with metadata
        ↓
Document record saved in PostgreSQL
```

### 10.3 Chunking Strategy

- Chunk size: 500 tokens
- Overlap: 50 tokens
- Each chunk must carry metadata: `business_id`, `document_id`, `source_filename`
- Never mix chunks from different businesses in the same Qdrant collection

### 10.4 Retrieval

- Retrieve top 3 most relevant chunks per query
- Always filter by `business_id` to prevent cross-business data leakage
- Include similarity score in retrieval result
- If top result score is below 0.75, do not use it — escalate instead

### 10.5 Hallucination Prevention

- The system prompt must explicitly instruct: "Answer ONLY from the provided context"
- If context is empty or irrelevant, the agent must say it doesn't know — never guess
- Prices must NEVER come from the LLM — always retrieved from the database
- After every RAG answer, log the source chunk used for auditability

---

## 11. Memory Strategy

### 11.1 Short-Term Memory (Within a Conversation)

- Full message history of the current conversation is passed to the LLM on every turn
- Stored in the `messages` table and retrieved per `conversation_id`
- Limit context window to last 10 messages to avoid token overflow
- Summarize older messages if conversation exceeds 10 turns

### 11.2 Long-Term Memory (Across Conversations)

For MVP scope, long-term memory is limited to:
- Customer's name (extracted and stored on first interaction)
- Customer's last appointment (retrieved from `appointments` table)
- Customer's preferred service (stored in customer profile if they mention it)

Do not over-engineer memory for the MVP. Get the core working first.

### 11.3 What NOT to Store

- Do not store sensitive personal information beyond what is needed
- Do not store raw LLM outputs as facts
- Do not store anything the customer has not explicitly provided

---

## 12. WhatsApp Integration Guidelines

### 12.1 Meta WhatsApp Cloud API Flow

```
Customer sends message on WhatsApp
        ↓
Meta sends POST request to your webhook URL
        ↓
FastAPI webhook endpoint receives it
        ↓
Verify request signature (X-Hub-Signature-256)
        ↓
Extract message, sender phone, business number
        ↓
Pass to message_service for processing
        ↓
Agent generates response
        ↓
Call Meta Send Message API with response
        ↓
Customer receives reply
```

### 12.2 Webhook Verification

Meta requires a one-time GET request verification when setting up the webhook. Handle this separately from the POST message handler. Never skip signature verification on incoming messages.

### 12.3 Message Types to Handle

| Type | Handle |
|---|---|
| Text message | Yes — core flow |
| Image | Acknowledge, escalate to human |
| Audio/voice note | Acknowledge, escalate to human (STT optional later) |
| Document | Forward to owner |
| Location | Extract for delivery context if needed |

### 12.4 Rate Limits and Error Handling

- Meta API has rate limits — implement exponential backoff on failed sends
- If a message fails to send, log it and retry once after 30 seconds
- Never lose a customer message — log everything before processing

### 12.5 The 24-Hour Window

Meta only allows free-form messages within 24 hours of the last customer message. After 24 hours, only pre-approved template messages can be sent. For MVP, this is not a blocker — all interactions are customer-initiated.

---

## 13. Coding Standards

### 13.1 Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Files | `snake_case` | `appointment_service.py` |
| Classes | `PascalCase` | `AppointmentService` |
| Functions | `snake_case` | `get_available_slots()` |
| Variables | `snake_case` | `customer_phone` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRY_ATTEMPTS` |
| Pydantic models | `PascalCase` | `AppointmentCreate` |

### 13.2 Function Size

- No function should exceed 30 lines
- If a function is getting long, it is doing too many things — split it
- Each function should have one clear purpose readable from its name

### 13.3 Typing

- All function parameters and return types must be annotated
- Use `Optional[X]` instead of `X | None` for clarity
- Never use `Any` unless absolutely unavoidable

### 13.4 Docstrings

Every service method and tool must have a docstring explaining:
- What it does
- What parameters it expects
- What it returns
- What exceptions it can raise

### 13.5 Exception Handling

- Define custom exceptions in `core/exceptions.py`
- Catch specific exceptions, never bare `except:`
- Always log the full exception before re-raising or returning an error response
- Never expose stack traces to external clients

### 13.6 Environment Configuration

- All secrets and configuration live in `.env`
- Never hardcode API keys, database URLs, or phone numbers
- Use `pydantic-settings` for typed configuration loading
- `.env` is in `.gitignore` — always provide `.env.example`

### 13.7 Logging

- Use Python's built-in `logging` module, configured in `core/logging.py`
- Log every incoming WhatsApp message (phone number + timestamp)
- Log every tool call made by the agent
- Log every escalation event
- Never log sensitive customer data (message content should be logged at DEBUG level only)

---

## 14. Testing Strategy

### 14.1 Unit Tests

Test every service method in isolation. Mock all repositories and external dependencies.

What to unit test:
- `appointment_service` — slot availability, booking validation, cancellation rules
- `escalation_service` — escalation condition logic
- `knowledge_service` — document processing, chunking

### 14.2 Integration Tests

Test the full flow from API endpoint to database.

What to integration test:
- POST `/api/v1/appointments` — full booking flow
- POST `/api/v1/webhook/whatsapp` — message received → response generated
- POST `/api/v1/knowledge/upload` — document uploaded → ingested into Qdrant

### 14.3 AI / Conversation Testing

Test that the agent gives correct answers for a defined set of questions:

```python
test_cases = [
    {"input": "What is the price of a facial?", "expected_contains": "Rs."},
    {"input": "Book me for tomorrow at 3pm", "expected_tool": "book_appointment"},
    {"input": "I want to speak to someone", "expected_tool": "escalate_to_human"},
]
```

### 14.4 RAG Evaluation

For each document ingested, maintain a small set of ground truth Q&A pairs. After ingestion, run these questions through the RAG pipeline and verify the answers are correct and grounded in the document.

### 14.5 Test File Naming

- Unit tests: `tests/unit/test_{module_name}.py`
- Integration tests: `tests/integration/test_{feature}.py`
- Use `pytest` and `pytest-asyncio` for async test support

---

## 15. Git Workflow

### 15.1 Branch Strategy

| Branch | Purpose |
|---|---|
| `main` | Production-ready code only |
| `develop` | Integration branch — all features merge here first |
| `feature/{name}` | Individual feature development |
| `fix/{name}` | Bug fixes |
| `milestone/{name}` | Milestone-level branches if needed |

### 15.2 Commit Message Format

```
type(scope): short description

Examples:
feat(appointments): add slot availability check
fix(webhook): handle empty message body gracefully
refactor(rag): improve chunking strategy
test(services): add unit tests for escalation service
docs(guide): update database schema section
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

### 15.3 Pull Request Rules

- No direct commits to `main` or `develop`
- Every PR must be reviewed by at least one other team member
- PR description must explain what changed and why
- All tests must pass before merging
- Keep PRs small and focused — one feature per PR

---

## 16. Development Milestones

### Milestone 1 — Project Foundation (Week 1)
- [ ] Repository created and cloned by all team members
- [ ] Folder structure set up as defined in this guide
- [ ] `.env.example` created with all required variables
- [ ] FastAPI app running locally (`/health` endpoint returns 200)
- [ ] Docker Compose running PostgreSQL locally
- [ ] Alembic initialized

**Exit criteria:** `uvicorn app.main:app` starts without errors. `/health` returns 200.

---

### Milestone 2 — Database (Week 2)
- [ ] All SQLAlchemy models defined
- [ ] All Alembic migrations created and applied
- [ ] Seed data script written (sample business, services, FAQs)
- [ ] All repositories implemented and manually tested

**Exit criteria:** Database tables exist. Seed data inserts successfully. Repositories return correct data.

---

### Milestone 3 — Business Services (Week 3)
- [ ] `appointment_service` implemented and unit tested
- [ ] `escalation_service` implemented and unit tested
- [ ] `knowledge_service` document ingestion working
- [ ] All services return correct results independent of API layer

**Exit criteria:** All service unit tests pass. Business rules enforced correctly.

---

### Milestone 4 — API Layer (Week 3–4)
- [ ] All REST endpoints implemented
- [ ] Request/response schemas validated
- [ ] Error handling middleware working
- [ ] Endpoints tested via Postman

**Exit criteria:** All endpoints return correct responses. Invalid inputs return proper error messages.

---

### Milestone 5 — RAG Pipeline (Week 4)
- [ ] Qdrant running via Docker
- [ ] Document ingestion pipeline working (PDF + Excel)
- [ ] Embeddings generated and stored
- [ ] Retrieval returning relevant chunks
- [ ] Hallucination guard implemented

**Exit criteria:** Upload a service menu PDF. Query it. Correct answer returned. Wrong answer not hallucinated.

---

### Milestone 6 — AI Agent (Week 5)
- [ ] All tools implemented and tested independently
- [ ] Agent orchestration working in terminal (no WhatsApp yet)
- [ ] Multi-turn conversation maintaining context
- [ ] Escalation logic triggering correctly
- [ ] Conversation test suite passing

**Exit criteria:** Run a full simulated conversation in terminal. Agent books an appointment, answers FAQs, and escalates when needed.

---

### Milestone 7 — WhatsApp Integration (Week 6)
- [ ] Meta WhatsApp Cloud API credentials set up
- [ ] Webhook endpoint verified by Meta
- [ ] Incoming messages processed and replied to
- [ ] Signature verification working
- [ ] End-to-end test: real WhatsApp message → AI reply

**Exit criteria:** Send a real WhatsApp message to the business number. Receive an AI-generated reply within 5 seconds.

---

### Milestone 8 — Polish and Real Users (Week 7–8)
- [ ] Daily summary generation working
- [ ] Owner escalation notifications working
- [ ] At least 3 real salon owners testing on live chats
- [ ] Feedback collected and critical issues fixed
- [ ] Demo video recorded

**Exit criteria:** 3 real owners have used it. At least one says it saved them time.

---

## 17. Non-Negotiable Rules

These rules are not optional. Breaking them will cause bugs that are hard to find and fix.

```
NEVER let the LLM write directly to PostgreSQL.
NEVER let the LLM calculate prices or check slot availability.
NEVER put business logic inside routes.
NEVER put SQL queries inside services — use repositories.
NEVER hardcode API keys, phone numbers, or secrets.
NEVER skip input validation — always use Pydantic schemas.
NEVER expose internal exception messages to customers.
NEVER mix data from different businesses in the same Qdrant query.
NEVER commit directly to main.
NEVER skip the escalation path — always give the customer a way to reach a human.
NEVER let the AI answer a price question from memory — always retrieve from DB.
NEVER deploy without testing the webhook signature verification.

ALWAYS inject dependencies via FastAPI Depends().
ALWAYS wrap multi-table writes in a transaction.
ALWAYS log every incoming WhatsApp message before processing.
ALWAYS filter Qdrant queries by business_id.
ALWAYS include created_at and updated_at on every database table.
ALWAYS keep AI tools small — one tool, one service method.
ALWAYS test services independently before integrating with the agent.
ALWAYS provide .env.example when adding new environment variables.
```

---

## 18. Project Completion Checklist

### Code Quality
- [ ] No business logic inside routes
- [ ] No SQL inside services
- [ ] No hardcoded secrets anywhere in codebase
- [ ] All functions have type annotations
- [ ] All service methods have docstrings
- [ ] No bare `except:` blocks

### Database
- [ ] All migrations applied cleanly on a fresh database
- [ ] All foreign keys defined with ON DELETE behavior
- [ ] Indexes on all frequently queried columns
- [ ] Seed data script working

### AI / RAG
- [ ] RAG never answers price questions — always from DB
- [ ] Hallucination guard in place (similarity threshold check)
- [ ] Escalation triggers correctly in all defined scenarios
- [ ] Conversation context limited to avoid token overflow

### WhatsApp
- [ ] Webhook signature verification working
- [ ] All incoming message types handled (text, image, audio)
- [ ] Rate limit handling and retry logic implemented
- [ ] No customer message can be silently lost

### Testing
- [ ] Unit tests for all services
- [ ] Integration tests for all API endpoints
- [ ] Conversation test suite passing
- [ ] RAG ground truth evaluation passing

### Security
- [ ] `.env` is in `.gitignore`
- [ ] No API keys in any committed file
- [ ] Internal errors never exposed to customers
- [ ] WhatsApp webhook signature verified on every request

### Demo Readiness
- [ ] At least 3 real business owners have tested it
- [ ] At least one owner has confirmed it saved them time
- [ ] Demo video recorded showing real WhatsApp conversation
- [ ] All team members can explain every part of the system

---

*This guide was written for the SmallBusinessBrain project — Cohort 1 Product Challenge, Comebck Pakistan.*
*Last updated: Week 1*