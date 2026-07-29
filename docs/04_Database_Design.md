# Database Design

## Document Information

| Field | Details |
|------|---------|
| Product Name | TiffinAI |
| Document Type | Database Design Specification |
| Version | 1.0 |
| Status | Draft |
| Prepared By | Hassan Faisal |
| Last Updated | July 2026 |

---

# Table of Contents

1. Introduction
2. Database Goals
3. Design Principles
4. Database Architecture
5. Entity Overview
6. Entity Specifications
7. Entity Relationships
8. Service Ownership
9. Transaction Strategy
10. Indexing Strategy
11. Security Considerations
12. Future Expansion
13. Database Summary

---

# 1. Introduction

The database serves as the single source of truth for all business-critical information within TiffinAI.

Unlike conversational AI systems that rely heavily on generated responses, TiffinAI separates conversational intelligence from business data. Every transaction, order, subscription, menu, inventory item, and customer record is stored and managed within the database.

Business services retrieve and update this information through deterministic operations, while the AI layer orchestrates workflows without owning or modifying business logic directly.

---

# 2. Database Goals

The database has been designed to achieve the following goals:

- Maintain a single source of truth
- Ensure transactional consistency
- Support high-volume customer interactions
- Enable modular service ownership
- Maintain referential integrity
- Simplify future scalability
- Support auditability
- Minimize redundant data
- Enable analytics
- Support future multi-business architecture

---

# 3. Design Principles

## 3.1 Single Source of Truth

Every business entity should exist only once.

Examples include:

- Customer
- Product
- Menu
- Order
- Subscription

No duplicated business information should exist across services.

---

## 3.2 Normalization

The schema follows relational database normalization principles to reduce redundancy while maintaining efficient querying.

---

## 3.3 Referential Integrity

Relationships between entities are enforced through foreign keys to maintain data consistency.

Examples:

- Every Order belongs to one Customer.
- Every Order Item belongs to one Order.
- Every Subscription belongs to one Customer.

---

## 3.4 Auditability

Every major business entity includes audit fields to track lifecycle events.

---

## 3.5 Scalability

The schema is designed so that additional services can be introduced without redesigning existing tables.

---

# 4. Database Architecture

The data flow within the platform follows the architecture below:

Customer Request

↓

FastAPI

↓

Business Service

↓

SQLAlchemy ORM

↓

PostgreSQL Database

↓

Business Service

↓

LangGraph

↓

Customer Response

Business services communicate directly with the database.

The AI layer never performs direct database operations.

---

# 5. Entity Overview

The platform consists of the following primary entities:

## Customer Domain

- Customer
- Address

---

## Menu Domain

- Menu
- Product
- MenuItem

---

## Cart Domain

- Cart
- CartItem

---

## Order Domain

- Order
- OrderItem

---

## Subscription Domain

- Subscription
- SubscriptionPlan

---

## Delivery Domain

- Rider
- Delivery

---

## Conversation Domain

- Conversation
- ConversationMessage

---

## Notification Domain

- Notification

---

# 6. Entity Specifications

## Customer

### Purpose

Stores customer profile information.

### Key Fields

- id
- full_name
- whatsapp_number
- email
- status
- created_at
- updated_at

### Relationships

- One Customer has many Orders.
- One Customer has many Addresses.
- One Customer has many Subscriptions.
- One Customer has one Cart.

### Owned By

Customer Service

---

## Address

### Purpose

Stores customer delivery addresses.

### Relationships

- Many Addresses belong to one Customer.

### Owned By

Customer Service

---

## Product

### Purpose

Stores all available food items.

### Key Fields

- id
- name
- description
- category
- price
- availability
- meal_type

### Owned By

Menu Service

---

## Menu

### Purpose

Represents menus for specific dates and meal sessions.

### Relationships

- One Menu contains many Menu Items.

### Owned By

Menu Service

---

## MenuItem

### Purpose

Maps Products to Menus.

### Relationships

- Many Menu Items belong to one Menu.
- Many Menu Items reference one Product.

### Owned By

Menu Service

---

## Cart

### Purpose

Stores a customer's active shopping cart.

### Relationships

- One Cart belongs to one Customer.
- One Cart contains many Cart Items.

### Owned By

Cart Service

---

## CartItem

### Purpose

Represents individual products inside the cart.

### Relationships

- Many Cart Items belong to one Cart.
- Each Cart Item references one Product.

### Owned By

Cart Service

---

## Order

### Purpose

Stores confirmed customer orders.

### Key Fields

- id
- order_number
- customer_id
- status
- total_amount
- payment_status
- scheduled_date

### Relationships

- One Order belongs to one Customer.
- One Order contains many Order Items.

### Owned By

Order Service

---

## OrderItem

### Purpose

Stores individual products within an order.

### Relationships

- Many Order Items belong to one Order.
- Each Order Item references one Product.

### Owned By

Order Service

---

## SubscriptionPlan

### Purpose

Defines available subscription packages.

### Examples

- Weekly Plan
- Monthly Plan
- Breakfast Plan
- Lunch Plan

### Owned By

Subscription Service

---

## Subscription

### Purpose

Stores customer subscription details.

### Relationships

- Many Subscriptions belong to one Customer.
- Each Subscription references one Subscription Plan.

### Owned By

Subscription Service

---

## Rider

### Purpose

Stores rider information.

### Owned By

Delivery Service

---

## Delivery

### Purpose

Stores delivery assignments and statuses.

### Relationships

- One Delivery belongs to one Order.
- One Delivery references one Rider.

### Owned By

Delivery Service

---

## Conversation

### Purpose

Stores conversation sessions between customers and the assistant.

### Owned By

Conversation Service

---

## ConversationMessage

### Purpose

Stores every exchanged message.

### Owned By

Conversation Service

---

## Notification

### Purpose

Stores outgoing notifications.

Examples:

- Order confirmed
- Rider assigned
- Subscription reminder

### Owned By

Notification Service

---

# 7. Entity Relationships

The primary relationships are:

Customer

├── Address

├── Cart

│ └── CartItem

├── Order

│ └── OrderItem

├── Subscription

└── Conversation

Order

├── Delivery

└── Notification

Menu

└── MenuItem

Product

├── MenuItem

├── CartItem

└── OrderItem

---

# 8. Service Ownership

Each service owns a specific subset of the database.

| Service | Owned Entities |
|---------|----------------|
| Customer Service | Customer, Address |
| Menu Service | Menu, Product, MenuItem |
| Cart Service | Cart, CartItem |
| Order Service | Order, OrderItem |
| Subscription Service | Subscription, SubscriptionPlan |
| Delivery Service | Rider, Delivery |
| Conversation Service | Conversation, ConversationMessage |
| Notification Service | Notification |

This ownership model prevents overlapping responsibilities and simplifies future maintenance.

---

# 9. Transaction Strategy

Critical business operations execute within database transactions.

Examples include:

## Order Creation

1. Create Order
2. Create Order Items
3. Validate Inventory
4. Update Inventory
5. Commit Transaction

If any step fails, the transaction is rolled back.

---

## Subscription Creation

1. Validate Customer
2. Validate Plan
3. Create Subscription
4. Schedule Notifications
5. Commit Transaction

---

# 10. Indexing Strategy

Indexes should be created for frequently queried fields.

Examples include:

Customer

- whatsapp_number
- email

Order

- order_number
- customer_id
- status

Product

- name
- availability

Subscription

- customer_id
- status

Delivery

- rider_id
- status

These indexes improve query performance as the platform scales.

---

# 11. Security Considerations

The database design incorporates the following security measures:

- Foreign key constraints
- Input validation
- Parameterized queries through SQLAlchemy
- Role-based data access
- Audit logging
- Soft deletion where appropriate
- Secure credential management

Sensitive information should never be exposed directly to the AI layer.

---

# 12. Future Expansion

The schema has been designed to support future features, including:

- Multi-business support
- Inventory management
- Coupon system
- Payment gateway integration
- Loyalty programs
- Customer segmentation
- Analytics
- AI recommendations
- Kitchen management
- Multi-region deployment

These features can be introduced through additional tables without major schema redesign.

---

# 13. Database Summary

The TiffinAI database is designed as the authoritative source of business data.

Business services own their respective entities and communicate with PostgreSQL through SQLAlchemy. The AI layer never manipulates business data directly but instead orchestrates deterministic services that operate on the database.

This separation of responsibilities enables a scalable, maintainable, and production-ready architecture capable of supporting future product growth.