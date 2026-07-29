# System Architecture

## Document Information

| Field | Details |
|------|---------|
| Product Name | TiffinAI |
| Document Type | System Architecture |
| Version | 1.0 |
| Status | Draft |
| Prepared By | Hassan Faisal |
| Last Updated | July 2026 |

---

# Table of Contents

1. Introduction
2. Architectural Goals
3. Architectural Principles
4. High-Level Architecture
5. Request Lifecycle
6. Core Components
7. AI Orchestration Layer
8. Business Services Layer
9. RAG Pipeline
10. Data Layer
11. Notification Layer
12. Security Considerations
13. Scalability Strategy
14. Future Architecture
15. Architecture Summary

---

# 1. Introduction

TiffinAI follows a modular, service-oriented architecture designed around Agentic AI principles.

Rather than allowing the Large Language Model to directly generate business information, the AI orchestrates deterministic backend services that own the business logic.

This architecture enables the platform to remain reliable, scalable, maintainable, and production-ready while providing customers with natural conversational experiences.

---

# 2. Architectural Goals

The architecture has been designed to achieve the following goals:

- Modular design
- Separation of concerns
- Deterministic business logic
- AI orchestration instead of AI decision making
- Scalability
- High maintainability
- Easy feature expansion
- Independent services
- Reliable conversations
- Human-like customer experience

---

# 3. Architectural Principles

## 3.1 AI is an Orchestrator

The AI determines:

- Customer intent
- Required workflow
- Required tools
- Response composition

The AI does not determine:

- Prices
- Menu
- Inventory
- Order status
- Delivery schedules

---

## 3.2 Deterministic Business Logic

Every business operation is handled by dedicated backend services.

Examples include:

- Menu validation
- Order creation
- Subscription management
- Inventory validation
- Delivery status
- Customer profile management

---

## 3.3 Service-Oriented Design

Every business capability is isolated into independent services.

Examples:

- Menu Service
- Order Service
- Cart Service
- Subscription Service
- Delivery Service
- Notification Service

This keeps the architecture modular and simplifies future maintenance.

---

## 3.4 Single Source of Truth

Business information must exist in exactly one location.

Examples:

| Information | Source |
|------------|--------|
| Menu | Database |
| Prices | Database |
| Orders | Order Service |
| Subscriptions | Subscription Service |
| Policies | RAG Knowledge Base |
| Customer History | Database |

The AI never becomes the source of truth.

---

# 4. High-Level Architecture

The platform consists of the following major layers:

1. Client Layer
2. API Layer
3. Conversation Layer
4. AI Orchestration Layer
5. Business Services Layer
6. Knowledge Layer
7. Data Layer
8. Notification Layer

The complete architecture is illustrated in:

`docs/diagrams/architecture/tiffinai-system-architecture-v2.png`

---

# 5. Request Lifecycle

Every customer interaction follows a deterministic workflow.

## Step 1

Customer sends a WhatsApp message.

↓

## Step 2

Meta Cloud API forwards the message to the FastAPI webhook.

↓

## Step 3

FastAPI validates the request.

↓

## Step 4

Conversation Manager retrieves or creates the conversation state.

↓

## Step 5

LangGraph receives the conversation state.

↓

## Step 6

The Planner identifies the customer's intent.

↓

## Step 7

The Tool Router selects the required business services.

↓

## Step 8

Business services execute deterministic operations.

↓

## Step 9

The AI combines deterministic outputs with conversational context.

↓

## Step 10

The formatted response is returned to the customer.

---

# 6. Core Components

## Customer Channels

Current:

- WhatsApp Business

Future:

- Web Chat
- Mobile Application
- Voice Assistant

---

## Meta Cloud API

Responsible for:

- Receiving customer messages
- Sending assistant responses
- Webhook communication

---

## FastAPI Server

FastAPI acts as the central entry point for the platform.

Responsibilities include:

- Webhook endpoints
- Authentication
- Request validation
- Dependency injection
- Conversation management
- API routing
- Error handling
- Background tasks

---

## Conversation Manager

Responsible for:

- Creating conversations
- Loading conversation memory
- Maintaining conversation state
- Managing idempotency
- Persisting conversation history

---

# 7. AI Orchestration Layer

LangGraph serves as the orchestration engine.

It is responsible for:

- Intent classification
- Entity extraction
- Planning
- Tool selection
- Memory management
- Workflow execution
- Response generation

LangGraph coordinates the backend services but does not implement business rules itself.

---

# 8. Business Services Layer

The platform contains dedicated services for each business capability.

## Menu Service

Responsible for:

- Today's menu
- Weekly menu
- Availability
- Meal validation

---

## Cart Service

Responsible for:

- Add item
- Remove item
- Update quantity
- View cart
- Calculate totals

---

## Order Service

Responsible for:

- Create order
- Confirm order
- Cancel order
- Track order
- Order history

---

## Subscription Service

Responsible for:

- Weekly plans
- Monthly plans
- Pause
- Resume
- Skip meals
- Renewals

---

## Customer Service

Responsible for:

- Customer profiles
- Saved addresses
- Preferences
- Favourite meals
- Previous orders

---

## Delivery Service

Responsible for:

- Rider assignment
- Delivery status
- ETA
- Delivery completion

---

## Notification Service

Responsible for:

- Order updates
- Delivery updates
- Subscription reminders
- Promotional notifications

---

# 9. RAG Pipeline

The Retrieval-Augmented Generation pipeline answers non-transactional questions.

The pipeline consists of:

- Knowledge documents
- Embedding model
- Vector database
- Retriever
- Prompt builder
- LLM

The RAG pipeline is responsible for:

- Business policies
- Delivery policies
- Refund policies
- FAQs
- Business hours

The RAG pipeline is not responsible for:

- Prices
- Orders
- Menu
- Inventory
- Subscription status

---

# 10. Data Layer

The PostgreSQL database stores:

- Customers
- Orders
- Order Items
- Menus
- Products
- Subscriptions
- Riders
- Deliveries
- Conversation History
- Notifications

This layer serves as the single source of truth for transactional data.

---

# 11. Notification Layer

The Notification Layer informs customers about important events.

Examples include:

- Order confirmation
- Preparing order
- Rider assigned
- Out for delivery
- Delivered
- Subscription reminders

Future channels:

- Push notifications
- Email
- SMS

---

# 12. Security Considerations

The architecture incorporates several security measures.

These include:

- Webhook verification
- Environment variable management
- Role-based access control
- Request validation
- Input sanitization
- Idempotent request handling
- Secure secret management
- Logging and auditing

---

# 13. Scalability Strategy

The architecture has been designed to support future growth.

Potential improvements include:

- Redis caching
- Background workers
- Celery
- Kubernetes
- Horizontal scaling
- Multiple AI agents
- Multi-business support
- Multi-region deployment

---

# 14. Future Architecture

Future versions of TiffinAI may include:

- Rider mobile application
- Owner dashboard
- Inventory forecasting
- Recommendation engine
- AI analytics assistant
- Voice ordering
- Image understanding
- Payment gateway integration

The modular architecture enables these capabilities to be added without significant changes to the existing system.

---

# 15. Architecture Summary

TiffinAI follows an Agentic AI architecture in which the Large Language Model functions as an orchestration layer rather than a source of business truth.

Deterministic backend services own all business-critical operations, while LangGraph coordinates workflows and the RAG pipeline provides contextual business knowledge.

This separation enables the platform to deliver reliable, scalable, and production-ready conversational experiences while maintaining operational accuracy.