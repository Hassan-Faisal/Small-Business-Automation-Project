# Product Requirements Document (PRD)

## Document Information

| Field | Details |
|------|---------|
| Product Name | TiffinAI |
| Document Type | Product Requirements Document (PRD) |
| Version | 1.0 |
| Status | Draft |
| Prepared By | Hassan Faisal |
| Last Updated | July 2026 |

---

# 1. Introduction

## Overview

TiffinAI is an Agentic AI-powered food ordering and subscription platform designed to automate customer interactions for food businesses operating primarily through WhatsApp.

The platform enables customers to browse menus, place and manage orders, subscribe to meal plans, track deliveries, and receive support through natural conversations while ensuring that all business-critical operations remain deterministic and reliable.

Unlike traditional chatbots, TiffinAI uses AI as an orchestration layer that coordinates backend services rather than generating business information.

---

# 2. Business Objectives

The primary objectives of TiffinAI are:

- Reduce manual customer support workload
- Improve response times
- Automate food ordering workflows
- Simplify subscription management
- Improve customer satisfaction
- Increase operational efficiency
- Minimize ordering mistakes
- Provide scalable customer support
- Build a production-ready AI-powered business platform

---

# 3. Stakeholders

## Business Owner

Responsible for:

- Managing business operations
- Menus
- Pricing
- Inventory
- Orders
- Delivery
- Customers
- Analytics

---

## Customer

Uses the system to:

- Browse menus
- Place orders
- Modify orders
- Track deliveries
- Manage subscriptions
- Receive notifications

---

## Rider

Responsible for:

- Viewing assigned deliveries
- Updating delivery status
- Contacting customers
- Completing deliveries

---

## Platform Administrator (Future)

Responsible for:

- Platform maintenance
- Business onboarding
- Monitoring AI
- Billing
- User management

---

# 4. User Personas

## Persona 1 — Customer

### Goals

- Order food quickly
- Ask questions naturally
- Receive accurate responses
- Track deliveries
- Manage subscriptions

### Pain Points

- Slow WhatsApp replies
- Confusing menus
- Incorrect orders
- No delivery updates

---

## Persona 2 — Business Owner

### Goals

- Save time
- Reduce repetitive conversations
- Increase sales
- Improve customer experience
- Automate operations

### Pain Points

- Hundreds of WhatsApp messages
- Manual order taking
- Subscription management
- Delivery coordination

---

# 5. Product Scope

## In Scope

### Customer Features

- View today's menu
- View tomorrow's menu
- Weekly menu
- Browse meals
- Search meals
- Place orders
- Modify orders
- Cancel orders
- Repeat previous orders
- View cart
- Confirm orders
- Order tracking
- Subscription management
- Pause subscriptions
- Resume subscriptions
- Skip meals
- FAQs
- Delivery information
- Payment information

---

### Business Features

- Menu management
- Pricing
- Inventory management
- Order management
- Customer management
- Delivery management
- Subscription management
- Notifications
- Analytics

---

### AI Features

- Intent detection
- Entity extraction
- Conversation memory
- Multi-turn conversations
- Tool orchestration
- RAG
- Human escalation
- Recommendation engine

---

# 6. Out of Scope (Version 1)

The following features will not be included in the initial release:

- Mobile applications
- Live GPS tracking
- Online payment gateway
- Loyalty rewards
- Coupons
- Referral system
- Voice ordering
- AI-generated menus
- Multi-business SaaS billing

---

# 7. Functional Requirements

---

## FR-1 Menu Management

The system shall:

- Retrieve today's menu
- Retrieve weekly menu
- Retrieve meal-specific menus
- Retrieve day-specific menus
- Validate product availability
- Suggest alternatives when unavailable

---

## FR-2 Order Management

The system shall allow customers to:

- Add items
- Remove items
- Update quantities
- Replace products
- View cart
- Confirm order
- Cancel order
- Repeat previous order
- Schedule future orders

---

## FR-3 Cart Management

The cart shall:

- Maintain quantities
- Prevent duplicates
- Calculate totals
- Validate availability
- Update dynamically

---

## FR-4 Subscription Management

The system shall support:

- Weekly subscriptions
- Monthly subscriptions
- Pause subscription
- Resume subscription
- Skip meal
- Subscription reminders
- Subscription status

---

## FR-5 Delivery Management

The system shall:

- Track order status
- Assign riders
- Notify customers
- Update delivery stages
- Mark deliveries complete

---

## FR-6 Customer Management

The system shall maintain:

- Customer profile
- Addresses
- Preferences
- Favorites
- Previous orders
- Active subscriptions

---

## FR-7 Knowledge Management

The RAG pipeline shall answer:

- Business policies
- Refund policies
- Delivery policies
- Payment policies
- FAQs
- Business hours

It shall not answer:

- Prices
- Menu
- Availability
- Order status
- Totals

These must come from deterministic services.

---

## FR-8 Notifications

The system shall notify customers when:

- Order confirmed
- Order preparing
- Rider assigned
- Out for delivery
- Delivered
- Subscription reminder
- Meal skipped

---

# 8. Non-Functional Requirements

## Performance

- Average response time < 3 seconds
- Tool execution < 2 seconds
- Menu retrieval < 1 second

---

## Scalability

Support:

- Thousands of customers
- Multiple businesses (future)
- Concurrent conversations

---

## Reliability

- No duplicate order creation
- Idempotent message handling
- Automatic retries
- Graceful failures

---

## Security

- Secure APIs
- Environment variables
- Role-based access
- Data validation
- Input sanitization

---

## Maintainability

Architecture shall remain:

- Modular
- Service-oriented
- Extensible
- Testable

---

# 9. Business Rules

The AI shall never invent:

- Menu
- Prices
- Discounts
- Totals
- Order IDs
- Rider names
- Delivery times
- Inventory
- Subscription details

---

All business-critical information shall come from:

- Database
- Business services
- Deterministic calculations

---

# 10. Customer Journey

## Journey 1 — Menu to Order

Customer

↓

Today's menu

↓

AI retrieves menu

↓

Customer selects meal

↓

Availability validation

↓

Cart updated

↓

Order confirmed

↓

Database

↓

Confirmation

---

## Journey 2 — Subscription

Customer

↓

Weekly plans

↓

Plan selected

↓

Subscription created

↓

Future reminders

↓

Skip / Pause / Resume

---

## Journey 3 — Order Tracking

Customer

↓

Where is my order?

↓

Order Service

↓

Current status

↓

Delivery information

↓

Response

---

# 11. Acceptance Criteria

The product shall be considered complete when:

✓ Customers can browse menus naturally

✓ Customers can order naturally

✓ Customers can modify orders

✓ Customers can track deliveries

✓ Context-aware conversations work

✓ Conversation memory works

✓ Business rules are enforced

✓ Duplicate WhatsApp messages do not create duplicate actions

✓ AI never hallucinates business data

✓ Human escalation works

✓ English supported

✓ Roman Urdu supported

---

# 12. Future Enhancements

Future releases may include:

- Mobile applications
- Live GPS rider tracking
- AI demand forecasting
- Inventory prediction
- Smart recommendations
- Loyalty program
- Coupons
- Customer segmentation
- Owner AI assistant
- Multi-business SaaS support

---

# 13. Risks

Potential risks include:

- Incorrect intent classification
- Hallucination
- Poor conversation context
- Inventory inconsistency
- Delayed delivery updates
- WhatsApp API limitations
- LLM latency

Mitigation strategies include:

- Deterministic services
- Regression testing
- Conversation memory
- Tool validation
- Human escalation
- Monitoring

---

# 14. Success Metrics

The success of TiffinAI will be measured using:

### Customer Metrics

- Successful order completion rate
- Average conversation duration
- Customer satisfaction
- Repeat orders

### Business Metrics

- Reduction in manual conversations
- Order accuracy
- Subscription retention
- Average response time
- Revenue growth

### Technical Metrics

- Intent classification accuracy
- Tool execution success
- RAG retrieval accuracy
- API uptime
- Test coverage