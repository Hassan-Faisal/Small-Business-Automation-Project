# AI Agent Architecture

## Document Information

| Field | Details |
|---|---|
| Product Name | TiffinAI |
| Document Type | AI Agent Architecture Specification |
| Version | 1.0 |
| Status | Draft |
| Prepared By | Hassan Faisal |
| Last Updated | July 2026 |

---

# Table of Contents

1. Introduction
2. Purpose
3. AI Architecture Goals
4. Core Design Principles
5. AI Orchestrator Overview
6. LangGraph Workflow
7. Conversation State
8. Intent Detection and Entity Extraction
9. Planning and Decision Making
10. Tool Routing
11. Memory Architecture
12. Response Generation
13. AI Decision Boundaries
14. Failure Handling
15. Human Escalation
16. Observability
17. Future Multi-Agent Architecture
18. Architecture Summary

---

# 1. Introduction

TiffinAI uses an Agentic AI architecture to provide natural conversational experiences while preserving reliable and deterministic business operations.

The AI component is not responsible for directly managing orders, prices, menus, subscriptions, deliveries, or customer records. Instead, it operates as an orchestration layer that understands user requests, manages conversation context, selects the correct tools, and coordinates deterministic business services.

LangGraph is used to control the AI workflow, maintain state, route requests, and support reliable multi-step conversations.

---

# 2. Purpose

This document defines the architecture of the TiffinAI AI Orchestrator.

It explains:

- How customer messages are processed
- How user intent is identified
- How entities are extracted
- How tools are selected
- How conversation state is maintained
- How business services are invoked
- How RAG is used
- How failures are handled
- How the system may evolve into a multi-agent architecture

---

# 3. AI Architecture Goals

The AI architecture is designed to achieve the following goals:

- Provide natural conversational interactions
- Maintain reliable multi-turn conversations
- Separate AI reasoning from business logic
- Prevent hallucination of business-critical information
- Route requests to deterministic services
- Support English and Roman Urdu
- Handle missing information through clarification
- Recover gracefully from failures
- Support future specialized AI agents
- Maintain observability and auditability

---

# 4. Core Design Principles

## 4.1 AI as an Orchestrator

The AI coordinates workflows but does not own business data.

It may:

- Understand customer intent
- Extract relevant information
- Decide which service to call
- Request clarification
- Use RAG for business knowledge
- Format the final response

It may not:

- Invent prices
- Invent menu items
- Invent order status
- Invent rider information
- Invent subscription information
- Directly modify the database

---

## 4.2 Deterministic Tool Execution

All transactional actions are performed by deterministic tools connected to business services.

Examples include:

- Retrieving the menu
- Adding items to a cart
- Creating an order
- Cancelling an order
- Pausing a subscription
- Checking delivery status

---

## 4.3 Explicit State Management

Conversation context must be stored inside a defined LangGraph state rather than relying only on the language model prompt.

---

## 4.4 Controlled Knowledge Access

The AI must retrieve transactional information from business services and policy information from the RAG knowledge base.

---

## 4.5 Safe Failure

When the system cannot complete an operation, it should explain the issue, preserve the conversation state, and guide the user toward the next valid action.

---

# 5. AI Orchestrator Overview

The AI Orchestrator is the central intelligence layer of TiffinAI.

Its responsibilities include:

- Receiving conversation state
- Understanding the customer message
- Identifying intent
- Extracting entities
- Determining the next action
- Selecting and calling tools
- Handling tool results
- Updating conversation state
- Generating the final response
- Persisting memory

The AI Orchestrator is implemented using LangGraph.

---

# 6. LangGraph Workflow

The LangGraph workflow follows these major stages:

1. Receive Message
2. Load Conversation State
3. Detect Intent
4. Extract Entities
5. Validate Required Information
6. Plan Next Action
7. Route to Tool or RAG
8. Execute Tool
9. Process Tool Result
10. Generate Response
11. Update Memory
12. Persist State
13. Return Response

A simplified flow is shown below:

```text
Customer Message
        ↓
Load State
        ↓
Intent Detection
        ↓
Entity Extraction
        ↓
Required Data Available?
   ┌────┴────┐
   │         │
  No        Yes
   │         │
Clarify   Plan Action
             ↓
         Tool Router
        ┌────┴─────┐
        │          │
 Business Tool    RAG
        │          │
        └────┬─────┘
             ↓
       Process Result
             ↓
     Generate Response
             ↓
       Persist Memory

# 7. Conversation State

The AI maintains an explicit conversation state using LangGraph to support reliable multi-turn interactions.

Unlike traditional chatbots that rely primarily on the language model's conversational memory, TiffinAI stores structured conversation data that can be safely accessed throughout the workflow.

The conversation state contains all information required to process the current request while preserving previous context.

Typical conversation state includes:

- Conversation ID
- Customer ID
- Current user message
- Conversation history
- Detected intent
- Extracted entities
- Active cart context
- Active order context
- Subscription context
- Previous tool outputs
- Pending clarification requests
- Retrieved RAG context
- Final response

This explicit state management enables deterministic workflows, improves reliability, prevents context loss, and allows conversations to continue naturally across multiple turns.

---

# 8. Intent Detection and Entity Extraction

The first responsibility of the AI Orchestrator is understanding the customer's request.

## Intent Detection

The AI analyzes the customer's message and identifies the primary intent before performing any business operation.

Examples of supported intents include:

- View Today's Menu
- View Weekly Menu
- Search Meals
- Add Item to Cart
- Remove Item
- Update Quantity
- Place Order
- Cancel Order
- Track Order
- Subscribe to a Meal Plan
- Pause Subscription
- Resume Subscription
- Skip Meal
- Ask Business Policy
- Request Human Support

Only one primary workflow should be executed at a time unless explicitly designed as a compound workflow.

---

## Entity Extraction

After determining the customer's intent, the AI extracts all required entities from the conversation.

Examples include:

- Product name
- Meal type
- Quantity
- Date
- Day of the week
- Subscription plan
- Order number
- Delivery location
- Customer preference

If mandatory information is missing, the AI should ask a clarification question before invoking any business service.

For example:

> **Customer:** "Order Paratha."

The AI should respond:

> "Sure! For which day would you like to order the Paratha?"

This prevents incorrect assumptions while maintaining a natural conversational experience.

---

# 9. Planning and Decision Making

Once the customer's intent and entities have been identified, the AI determines the next workflow step.

Possible actions include:

- Execute a deterministic business tool
- Retrieve business knowledge using RAG
- Ask a clarification question
- Confirm a destructive operation
- Escalate the conversation to a human operator
- Inform the customer that the requested action is unsupported

The planner should always prioritize deterministic execution over language model inference.

Business validation must remain the responsibility of backend services rather than the AI.

---

# 10. Tool Routing

The Tool Router is responsible for selecting the correct backend service required to fulfill the customer's request.

Each business capability is owned by exactly one service.

| Customer Request | Selected Tool |
|------------------|---------------|
| Show today's menu | Menu Service |
| Add item to cart | Cart Service |
| Create order | Order Service |
| Pause subscription | Subscription Service |
| Track delivery | Delivery Service |
| Update customer profile | Customer Service |
| Business policy question | RAG Pipeline |

The Tool Router acts as the bridge between conversational understanding and deterministic business operations.

This separation of responsibilities simplifies maintenance and prevents overlapping business logic.

---

# 11. Memory Architecture

TiffinAI maintains multiple forms of memory to support reliable conversations.

## Short-Term Memory

Short-term memory stores information relevant to the current conversation.

Examples include:

- Active intent
- Recent messages
- Pending clarification
- Temporary workflow data
- Current cart context

---

## Long-Term Memory

Long-term memory stores persistent customer information retrieved through business services.

Examples include:

- Previous orders
- Saved delivery addresses
- Customer preferences
- Active subscriptions
- Favourite meals

The language model does not permanently store this information.

Instead, deterministic services retrieve it whenever required.

---

## Conversation History

Conversation history is stored separately to support:

- Context-aware conversations
- Customer support
- Auditing
- Analytics
- Future conversation continuation

This history enables the AI to understand follow-up requests while preserving complete interaction records.

---

# 12. Response Generation

After receiving results from business services or the RAG pipeline, the AI generates the final customer response.

The response should:

- Use natural language
- Remain concise and friendly
- Preserve conversational context
- Reflect deterministic business data accurately
- Avoid exposing internal implementation details

Business-critical values such as prices, order numbers, totals, delivery status, and subscription details must be copied directly from tool outputs without modification.

The AI is responsible for presentation rather than business computation.

---

# 13. AI Decision Boundaries

The AI operates within clearly defined boundaries.

## The AI May

- Understand customer intent
- Extract entities
- Plan workflows
- Select appropriate tools
- Retrieve business knowledge through RAG
- Summarize retrieved information
- Ask clarification questions
- Generate natural responses

---

## The AI Must Not

- Invent menu items
- Invent prices
- Invent discounts
- Invent inventory levels
- Invent order status
- Invent delivery information
- Modify database records directly
- Bypass business validation rules

All business-critical information must originate from deterministic backend services.

---

# 14. Failure Handling

Failures are expected in production systems and must be handled gracefully.

Examples include:

- Tool execution failures
- Missing customer information
- Invalid requests
- Product unavailable
- Subscription conflicts
- External API failures
- Temporary system outages

When failures occur, the AI should:

- Explain the issue clearly
- Preserve conversation state
- Suggest the next valid action
- Retry safe operations where appropriate
- Escalate when necessary

The objective is to recover from failures without losing conversation context.

---

# 15. Human Escalation

Some situations require intervention from a human operator.

Examples include:

- Customer complaints
- Payment disputes
- Refund requests
- Repeated AI failures
- Ambiguous business exceptions
- Sensitive customer issues

When escalation occurs, the AI should summarize the conversation and provide the human operator with relevant context to reduce repeated questioning and improve support efficiency.

---

# 16. Observability

The AI workflow should be fully observable for monitoring, debugging, and continuous improvement.

Important metrics include:

- Intent classification accuracy
- Tool execution success rate
- Average response time
- RAG retrieval accuracy
- Clarification frequency
- Human escalation rate
- Failed workflow rate

System logs should capture workflow execution while ensuring that sensitive customer information is protected.

---

# 17. Future Multi-Agent Architecture

The current implementation uses a single AI Orchestrator responsible for managing the complete workflow.

Future versions of TiffinAI may introduce specialized AI agents, including:

- Ordering Agent
- Subscription Agent
- Delivery Agent
- Recommendation Agent
- Customer Support Agent
- Analytics Agent

A supervisory orchestration layer may coordinate these specialized agents while ensuring that deterministic backend services remain the authoritative source of business data.

This approach improves scalability without changing the underlying business architecture.

---

# 18. Architecture Summary

TiffinAI follows an orchestration-first AI architecture in which LangGraph coordinates conversations, deterministic business services, and the RAG knowledge base.

The AI is responsible for understanding customer requests, maintaining conversation state, planning workflows, selecting tools, and generating natural responses.

All business-critical operations—including pricing, menus, orders, subscriptions, deliveries, and customer records—remain owned by dedicated backend services.

This separation of responsibilities provides a reliable, scalable, maintainable, and production-ready foundation while supporting future expansion toward a multi-agent architecture.

