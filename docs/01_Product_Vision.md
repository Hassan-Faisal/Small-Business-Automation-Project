# TiffinAI Product Vision

## Document Information

| Field | Details |
|---|---|
| Product Name | TiffinAI |
| Product Type | Agentic AI-powered food ordering and subscription platform |
| Version | 1.0 |
| Status | Draft |
| Primary Interface | WhatsApp |
| Target Market | Home-based food businesses, tiffin services, cloud kitchens, and small restaurants |

---

## 1. Product Vision

TiffinAI is an Agentic AI-powered food ordering, subscription, and customer support platform designed for food businesses that primarily communicate with customers through WhatsApp.

The platform enables customers to browse menus, place and modify orders, manage meal subscriptions, track deliveries, and ask business-related questions through natural conversations.

TiffinAI is not intended to operate as a basic question-answering chatbot. It acts as an intelligent customer service and ordering assistant that understands customer requests, maintains conversation context, coordinates backend services, validates business rules, and completes operational tasks.

The AI acts as an orchestrator, while deterministic backend services remain responsible for business-critical information and actions such as product availability, pricing, order totals, subscription status, delivery schedules, and order creation.

---

## 2. Product Mission

The mission of TiffinAI is to reduce the manual workload of food business owners by automating repetitive customer conversations and operational workflows without compromising accuracy, reliability, or customer experience.

The platform should allow small food businesses to serve more customers without requiring additional staff to manually answer every WhatsApp message.

---

## 3. Problem Statement

Many home-based food businesses, tiffin services, and small restaurants depend heavily on WhatsApp for customer communication.

Customers frequently ask questions such as:

- What is available today?
- What is included in the weekly menu?
- Is a specific meal available tomorrow?
- Can I place an order for breakfast?
- When will my order arrive?
- Can I skip tomorrow's subscribed meal?
- Do you deliver to my area?
- Which payment methods are supported?
- Can I repeat my previous order?

These requests are often handled manually by the business owner or staff.

As the number of customers increases, this creates several problems:

- Slow response times
- Missed customer messages
- Incorrect or incomplete orders
- Repetitive administrative work
- Difficulty managing subscriptions
- Poor visibility into order and delivery status
- Limited ability to scale business operations

TiffinAI addresses these problems by providing an AI-powered conversational interface connected to reliable business services and databases.

---

## 4. Proposed Solution

TiffinAI provides a conversational ordering experience through WhatsApp.

A typical customer interaction may look like this:

1. The customer asks for today's or the weekly menu.
2. The assistant retrieves the correct menu from the database.
3. The customer asks to order a specific item for a particular day and meal.
4. The assistant extracts the requested product, quantity, day, and meal type.
5. The system validates whether the item is available.
6. The item is added to the customer's cart.
7. The customer confirms the order.
8. The Order Service creates the order and stores it in the database.
9. The assistant provides the confirmed order details.
10. The customer can later ask about the order status or expected delivery.
11. The system retrieves the actual order status and combines it with approved delivery guidance.
12. When the order is dispatched, the customer is informed that the rider may call before delivery.

The AI must never invent business information. It must retrieve or execute business-critical information through deterministic services.

---

## 5. Target Users

### 5.1 Customers

Customers use WhatsApp to:

- Browse today's menu
- Browse the weekly menu
- Search meals by day or meal type
- Place immediate or scheduled orders
- Add, remove, or update cart items
- Confirm or cancel orders
- Track order status
- Repeat previous orders
- Manage subscriptions
- Skip subscribed meals
- Pause or resume subscriptions
- Ask about delivery, payment, and business policies
- Receive order and delivery notifications

### 5.2 Business Owners

Business owners use the platform to:

- Manage menus and pricing
- Update item availability
- Manage inventory and daily limits
- Review and update orders
- Manage subscriptions
- Configure delivery areas and windows
- Manage riders
- Review customer conversations
- Send broadcast messages
- View business analytics
- Escalate exceptional customer cases
- Ask the AI assistant for operational insights

### 5.3 Riders

Riders use the system to:

- View assigned deliveries
- Access customer delivery information
- Update delivery status
- Contact customers when required
- Mark orders as delivered
- Report delivery problems

### 5.4 Platform Administrators

Platform administrators are a future user group responsible for:

- Managing multiple businesses
- Monitoring system health
- Managing platform users and permissions
- Reviewing AI performance
- Managing billing and subscriptions
- Handling platform-wide support cases

---

## 6. Product Goals

TiffinAI should:

- Automate the majority of routine customer conversations
- Enable natural English, Roman Urdu, and mixed-language communication
- Support complete menu-to-delivery customer journeys
- Maintain context across multiple conversation turns
- Prevent hallucination of business-critical information
- Reduce order-entry mistakes
- Improve response speed
- Make subscription management simple
- Provide accurate order and delivery status
- Escalate complaints and exceptional cases to humans
- Help small food businesses scale their operations

---

## 7. Product Principles

### 7.1 AI as an Orchestrator

The AI determines the customer's intent and decides which tool or service should handle the request.

It does not act as the source of truth for business data.

### 7.2 Deterministic Business Logic

The following information must always come from the database or deterministic services:

- Menu items
- Product availability
- Prices
- Quantities
- Order totals
- Order IDs
- Order statuses
- Subscription plans
- Subscription states
- Payment methods
- Delivery windows
- Delivery charges
- Rider assignments

### 7.3 Context-Aware Conversations

The assistant should understand follow-up messages such as:

- Order the first one
- Make it two
- Remove one
- Add the same item for tomorrow
- Repeat my last order
- Skip tomorrow's meal

The assistant should use conversation memory and previously displayed results to resolve such requests safely.

### 7.4 Human-Like Customer Experience

Customers should be able to speak naturally rather than memorizing fixed commands.

Example:

> Monday ka nashta mein Aloo Paratha order kar do.

The system should understand:

- Intent: Add item
- Day: Monday
- Meal type: Breakfast
- Product: Aloo Paratha
- Quantity: One

### 7.5 Safe Failure and Clarification

When a request is ambiguous, the assistant should ask a focused clarification question rather than guessing.

When a business exception occurs, the system should escalate the conversation to a human.

### 7.6 Modular Architecture

Each business capability should remain independently maintainable through services such as:

- Menu Service
- Inventory Service
- Cart Service
- Order Service
- Subscription Service
- Customer Service
- Delivery Service
- Rider Service
- Notification Service
- RAG Knowledge Service

---

## 8. Core Product Capabilities

### Customer Conversation

- Natural-language understanding
- English and Roman Urdu support
- Intent classification
- Entity extraction
- Conversation memory
- Contextual follow-ups
- Human escalation

### Menu and Availability

- Today's menu
- Tomorrow's menu
- Weekly menu
- Day-specific menu
- Meal-specific menu
- Item availability validation
- Alternative suggestions

### Cart and Ordering

- Add item
- Remove item
- Update quantity
- Replace item
- View cart
- Clear cart
- Confirm order
- Cancel order
- Schedule future order
- Repeat previous order

### Subscriptions

- Weekly subscriptions
- Monthly subscriptions
- Subscription status
- Skip meal
- Pause subscription
- Resume subscription
- Subscription reminders

### Delivery

- Delivery window
- Rider assignment
- Preparing status
- Ready status
- Out-for-delivery status
- Delivered status
- Customer delivery notifications
- Rider-call reminder

### Business Knowledge

The RAG pipeline may answer approved non-transactional questions regarding:

- Delivery policies
- Payment policies
- Refund policies
- Opening hours
- Delivery areas
- Meal preparation guidance
- General FAQs

Transactional information must come from deterministic services.

---

## 9. Product Boundaries

### Included in the Initial Product

- WhatsApp-based customer interaction
- Menu retrieval
- Cart management
- Order placement
- Order tracking
- Subscription management
- RAG-based policy answers
- Conversation memory
- English and Roman Urdu support
- Human escalation
- Basic delivery lifecycle
- Business owner management APIs

### Not Included Initially

- Native Android or iOS applications
- Live GPS rider tracking
- Automatic online payment settlement
- Loyalty points
- Coupons and promotional campaigns
- Voice-note understanding
- Advanced demand forecasting
- Multi-business SaaS billing
- Fully automated rider route optimization

These features may be introduced in later versions.

---

## 10. Long-Term Vision

TiffinAI should evolve from a WhatsApp ordering assistant into a complete AI-powered operating platform for food businesses.

The long-term platform may include:

- Customer ordering through WhatsApp, web, and mobile
- Automated subscriptions and recurring meal delivery
- Rider assignment and live delivery tracking
- Inventory forecasting
- Personalized meal recommendations
- Customer segmentation
- Business analytics
- Automated customer retention campaigns
- AI-powered owner assistant
- Multi-business SaaS support

The owner should eventually be able to ask questions such as:

- How many orders did we receive today?
- Which meal generated the most revenue this week?
- Which customers have not ordered in the last 30 days?
- How many meals should we prepare tomorrow?
- Which subscription plan has the highest retention?
- Which rider has the fastest delivery time?

---

## 11. Product Success Criteria

The product will be considered successful when:

- Customers can complete an order without human assistance
- Explicit menu requests return accurate results
- Requested products are validated before ordering
- Prices and totals are always deterministic
- The assistant remembers relevant conversation context
- Customers receive accurate order status
- Subscription actions follow configured business rules
- Exceptional cases are escalated correctly
- Duplicate WhatsApp messages do not create duplicate actions
- The system supports reliable English and Roman Urdu interactions
- Business owners experience a measurable reduction in manual WhatsApp workload

---

## 12. Product Positioning

TiffinAI is not positioned as a generic chatbot.

It is positioned as:

> An Agentic AI-powered food ordering, subscription, delivery, and customer operations platform for WhatsApp-first food businesses.

The platform combines:

- Conversational AI
- LangGraph orchestration
- Deterministic business services
- Retrieval-augmented generation
- Conversation memory
- Order management
- Subscription management
- Delivery operations
- Business analytics

This combination enables a reliable, scalable, and human-like customer experience while preserving operational accuracy.