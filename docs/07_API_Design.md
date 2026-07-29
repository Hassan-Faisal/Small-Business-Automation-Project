# API Design

## Document Information

| Field | Details |
|---|---|
| Product Name | TiffinAI |
| Document Type | API Design Specification |
| Version | 1.0 |
| Status | Draft |
| Prepared By | Hassan Faisal |
| Last Updated | July 2026 |

---

# Table of Contents

1. Introduction
2. Purpose
3. API Design Goals
4. API Design Principles
5. API Architecture
6. Base URL and Versioning
7. Authentication and Authorization
8. Standard Request Format
9. Standard Response Format
10. Error Handling
11. Resource Groups
12. Customer APIs
13. Menu APIs
14. Cart APIs
15. Order APIs
16. Subscription APIs
17. Delivery APIs
18. Conversation APIs
19. Notification APIs
20. Webhook APIs
21. Health and Monitoring APIs
22. Idempotency
23. Pagination, Filtering, and Sorting
24. Rate Limiting
25. Validation
26. Security Considerations
27. Logging and Observability
28. API Lifecycle
29. Future Improvements
30. API Summary

---

# 1. Introduction

TiffinAI exposes a structured set of APIs that connect customer channels, internal services, administrative interfaces, and external integrations.

FastAPI serves as the central API layer of the platform.

The API layer is responsible for:

- Receiving requests
- Validating input
- Performing authentication and authorization
- Invoking deterministic business services
- Returning standardized responses

The AI Orchestrator interacts with business services through registered tools rather than directly manipulating database records.

---

# 2. Purpose

This document defines the API design standards for TiffinAI.

It specifies:

- API architecture
- Naming conventions
- Endpoint organization
- Request and response formats
- Authentication
- Authorization
- Validation
- Error handling
- Versioning
- Idempotency
- Security
- Logging
- Future evolution

This document serves as the API contract for backend services, customer applications, dashboards, and external integrations.

---

# 3. API Design Goals

The API layer is designed to:

- Provide a consistent developer experience
- Support WhatsApp and future client applications
- Maintain deterministic business operations
- Separate transport logic from business logic
- Support safe retries
- Prevent duplicate operations
- Standardize request and response structures
- Support future API versions
- Enable secure integrations
- Simplify testing and maintenance

---

# 4. API Design Principles

## 4.1 Resource-Oriented Design

Endpoints represent business resources instead of implementation details.

Examples:

GET /api/v1/menus/today

POST /api/v1/orders

GET /api/v1/orders/{order_id}

Avoid action-based endpoint names such as:

POST /api/v1/create-order

---

## 4.2 Appropriate HTTP Methods

| Method | Purpose |
|---|---|
| GET | Retrieve data |
| POST | Create a resource |
| PUT | Replace a complete resource |
| PATCH | Partially update a resource |
| DELETE | Remove or deactivate a resource |

---

## 4.3 Stateless Communication

Every request contains sufficient information to be processed independently.

Conversation state is loaded using identifiers rather than relying on server-side HTTP sessions.

---

## 4.4 Separation of Concerns

FastAPI routes are responsible for:

- Request validation
- Dependency injection
- Authentication
- Authorization
- Response serialization

Business logic remains inside dedicated services.

---

## 4.5 Consistent Contracts

All APIs should follow consistent standards for:

- Naming
- Validation
- Responses
- Error handling
- Pagination
- Status codes

---

# 5. API Architecture

The standard request flow is:

Client

↓

FastAPI Router

↓

Authentication

↓

Validation

↓

Business Service

↓

Repository / External Integration

↓

Response Serializer

↓

Client

For conversational requests:

WhatsApp

↓

Webhook

↓

Conversation Manager

↓

AI Orchestrator

↓

Business Tool

↓

Business Service

↓

Response

---

# 6. Base URL and Versioning

Base URL:

/api/v1

Examples:

GET /api/v1/products

POST /api/v1/orders

GET /api/v1/customers/{customer_id}

Future breaking changes will use:

/api/v2

---

# 7. Authentication and Authorization

Current implementation:

- Webhook verification
- Internal service authentication
- Environment-based secrets

Future implementation:

- JWT
- OAuth2
- API Keys

Role-based authorization:

| Role | Permissions |
|---|---|
| Customer | Personal resources |
| Rider | Assigned deliveries |
| Business Owner | Business management |
| Administrator | Platform management |
| Internal Services | Service communication |

---

# 8. Standard Request Format

Requests use JSON.

Example:

{
  "customer_id": "cus_001",
  "address_id": "addr_001",
  "items": [
    {
      "product_id": "prd_001",
      "quantity": 2
    }
  ]
}

Validation is performed using Pydantic models.

---

# 9. Standard Response Format

Successful responses:

{
  "success": true,
  "message": "Order created successfully.",
  "data": {},
  "metadata": {
    "request_id": "req_123"
  }
}

---

# 10. Error Handling

Error responses follow a consistent structure:

{
  "success": false,
  "error": {
    "code": "ORDER_NOT_FOUND",
    "message": "The requested order could not be found."
  },
  "metadata": {
    "request_id": "req_123"
  }
}

Standard HTTP status codes include:

- 400 Bad Request
- 401 Unauthorized
- 403 Forbidden
- 404 Not Found
- 409 Conflict
- 422 Validation Error
- 429 Too Many Requests
- 500 Internal Server Error
- 503 Service Unavailable


---

# 11. Resource Groups

The TiffinAI API is organized into resource-based groups that reflect the platform's business domains.

Each resource group owns a specific set of endpoints and is responsible for a well-defined business capability.

The primary resource groups include:

- Customer APIs
- Menu APIs
- Cart APIs
- Order APIs
- Subscription APIs
- Delivery APIs
- Conversation APIs
- Notification APIs
- Webhook APIs
- Health and Monitoring APIs

This organization simplifies maintenance, improves discoverability, and aligns the API structure with the service-oriented architecture.

The recommended FastAPI project structure is shown below:

```text
app/
├── api/
│   ├── customers.py
│   ├── menus.py
│   ├── carts.py
│   ├── orders.py
│   ├── subscriptions.py
│   ├── deliveries.py
│   ├── conversations.py
│   ├── notifications.py
│   ├── webhooks.py
│   └── health.py
│
├── services/
├── repositories/
├── schemas/
├── models/
└── core/
```

Each router should remain lightweight and delegate business logic to its corresponding service layer.

---

# 12. Customer APIs

Customer APIs manage customer profiles, delivery addresses, and personal preferences.

## Responsibilities

- Create customer profiles
- Retrieve customer information
- Update customer details
- Manage customer addresses
- Retrieve customer preferences
- View previous orders
- Manage saved information

---

## Example Endpoints

| Method | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/v1/customers` | Create a customer |
| GET | `/api/v1/customers/{customer_id}` | Retrieve customer details |
| PATCH | `/api/v1/customers/{customer_id}` | Update customer profile |
| DELETE | `/api/v1/customers/{customer_id}` | Deactivate customer |
| GET | `/api/v1/customers/{customer_id}/addresses` | Retrieve customer addresses |
| POST | `/api/v1/customers/{customer_id}/addresses` | Add a delivery address |

---

## Business Rules

Customer APIs must:

- Validate customer identity
- Prevent duplicate customer records
- Validate phone numbers
- Protect personal information
- Return standardized responses

---

# 13. Menu APIs

Menu APIs provide access to available meals and menu information.

The Menu Service remains the authoritative source for all menu-related data.

---

## Responsibilities

- Retrieve today's menu
- Retrieve tomorrow's menu
- Retrieve weekly menu
- Search menu items
- Retrieve meal-specific menus
- Validate product availability

---

## Example Endpoints

| Method | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/v1/menus/today` | Retrieve today's menu |
| GET | `/api/v1/menus/tomorrow` | Retrieve tomorrow's menu |
| GET | `/api/v1/menus/weekly` | Retrieve weekly menu |
| GET | `/api/v1/products` | List products |
| GET | `/api/v1/products/{product_id}` | Retrieve product details |

---

## Business Rules

Menu APIs must:

- Return only available products
- Support filtering by meal type
- Support filtering by date
- Never expose unpublished menus
- Return deterministic pricing

Menu information should always originate from the Menu Service rather than the AI.

---

# 14. Cart APIs

Cart APIs manage a customer's active shopping cart.

These APIs support incremental updates while maintaining deterministic cart calculations.

---

## Responsibilities

- Create cart
- Retrieve cart
- Add items
- Remove items
- Update quantities
- Clear cart
- Calculate totals

---

## Example Endpoints

| Method | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/v1/cart` | Retrieve active cart |
| POST | `/api/v1/cart/items` | Add item to cart |
| PATCH | `/api/v1/cart/items/{item_id}` | Update cart item |
| DELETE | `/api/v1/cart/items/{item_id}` | Remove cart item |
| DELETE | `/api/v1/cart` | Clear cart |

---

## Business Rules

Cart APIs must:

- Validate product availability
- Prevent duplicate cart items
- Update quantities correctly
- Calculate totals deterministically
- Reject unavailable products

The AI Orchestrator may request cart operations but must never calculate totals itself.

---

# 15. Order APIs

Order APIs manage the complete customer ordering lifecycle.

The Order Service is responsible for validating, creating, updating, and tracking customer orders.

---

## Responsibilities

- Create orders
- Confirm orders
- Retrieve order details
- Retrieve order history
- Cancel orders
- Track order status

---

## Example Endpoints

| Method | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/v1/orders` | Create a new order |
| GET | `/api/v1/orders/{order_id}` | Retrieve order details |
| GET | `/api/v1/orders` | Retrieve customer orders |
| PATCH | `/api/v1/orders/{order_id}/cancel` | Cancel an order |
| GET | `/api/v1/orders/{order_id}/status` | Retrieve order status |

---

## Business Rules

Order APIs must:

- Validate customer identity
- Validate product availability before order creation
- Prevent duplicate order creation
- Generate unique order numbers
- Preserve transactional consistency
- Support idempotent order creation

Once an order has been successfully created, all subsequent updates should follow the defined business workflow managed by the Order Service.


---

# 16. Subscription APIs

Subscription APIs manage recurring meal plans and customer subscriptions.

The Subscription Service is responsible for creating, updating, pausing, resuming, and cancelling subscriptions while enforcing all business rules.

---

## Responsibilities

- Create subscriptions
- Retrieve subscription details
- Pause subscriptions
- Resume subscriptions
- Skip scheduled meals
- Cancel subscriptions
- Retrieve subscription history

---

## Example Endpoints

| Method | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/v1/subscriptions` | Create a subscription |
| GET | `/api/v1/subscriptions/{subscription_id}` | Retrieve subscription details |
| GET | `/api/v1/subscriptions` | Retrieve customer subscriptions |
| PATCH | `/api/v1/subscriptions/{subscription_id}/pause` | Pause a subscription |
| PATCH | `/api/v1/subscriptions/{subscription_id}/resume` | Resume a subscription |
| PATCH | `/api/v1/subscriptions/{subscription_id}/skip` | Skip the next scheduled meal |
| DELETE | `/api/v1/subscriptions/{subscription_id}` | Cancel a subscription |

---

## Business Rules

Subscription APIs must:

- Validate the selected subscription plan
- Prevent duplicate active subscriptions for the same plan where business rules prohibit them
- Prevent skipping meals outside the allowed time window
- Preserve subscription history
- Generate reminders through the Notification Service

All subscription decisions remain deterministic and are handled by the Subscription Service.

---

# 17. Delivery APIs

Delivery APIs manage delivery assignments, tracking, and completion.

The Delivery Service owns all delivery-related operations and communicates with rider management when required.

---

## Responsibilities

- Assign riders
- Retrieve delivery status
- Update delivery progress
- Mark deliveries as completed
- Retrieve delivery history

---

## Example Endpoints

| Method | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/v1/deliveries/{delivery_id}` | Retrieve delivery details |
| GET | `/api/v1/deliveries/{delivery_id}/status` | Retrieve current delivery status |
| PATCH | `/api/v1/deliveries/{delivery_id}` | Update delivery status |
| POST | `/api/v1/deliveries/{delivery_id}/assign-rider` | Assign a rider |
| PATCH | `/api/v1/deliveries/{delivery_id}/complete` | Mark delivery as completed |

---

## Business Rules

Delivery APIs must:

- Validate rider availability before assignment
- Preserve delivery history
- Prevent invalid status transitions
- Notify customers when delivery status changes
- Record delivery timestamps for auditing

Delivery status should always be retrieved from the Delivery Service and never inferred by the AI.

---

# 18. Conversation APIs

Conversation APIs manage customer conversations and conversation history.

These APIs support conversational continuity, auditing, analytics, and customer support.

---

## Responsibilities

- Create conversation sessions
- Retrieve conversation history
- Retrieve conversation state
- Persist conversation messages
- Support human escalation

---

## Example Endpoints

| Method | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/v1/conversations/{conversation_id}` | Retrieve conversation details |
| GET | `/api/v1/conversations/{conversation_id}/messages` | Retrieve conversation messages |
| POST | `/api/v1/conversations` | Create a conversation session |
| PATCH | `/api/v1/conversations/{conversation_id}` | Update conversation metadata |

---

## Business Rules

Conversation APIs must:

- Preserve chronological message history
- Maintain conversation identifiers
- Support AI and human interactions
- Prevent message duplication
- Protect sensitive customer information

Conversation storage should remain independent from AI prompts to ensure reliable state management.

---

# 19. Notification APIs

Notification APIs manage outgoing customer notifications generated by business events.

The Notification Service is responsible for message creation, scheduling, delivery tracking, and retry handling.

---

## Responsibilities

- Send order notifications
- Send subscription reminders
- Send delivery updates
- Schedule notifications
- Retrieve notification history

---

## Example Endpoints

| Method | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/v1/notifications` | Create a notification |
| GET | `/api/v1/notifications/{notification_id}` | Retrieve notification details |
| GET | `/api/v1/notifications` | Retrieve notification history |
| PATCH | `/api/v1/notifications/{notification_id}` | Update notification status |

---

## Business Rules

Notification APIs must:

- Prevent duplicate notifications
- Retry failed deliveries when appropriate
- Record delivery status
- Support multiple communication channels
- Maintain complete notification history

Future notification channels may include:

- WhatsApp
- SMS
- Email
- Push Notifications

---

# 20. Webhook APIs

Webhook APIs provide integration points for external services.

The initial implementation focuses on WhatsApp Cloud API webhooks, while the architecture allows additional integrations in future releases.

---

## Responsibilities

- Receive incoming WhatsApp messages
- Verify webhook authenticity
- Process webhook events
- Trigger conversation workflows
- Return acknowledgement responses

---

## Example Endpoints

| Method | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/v1/webhooks/whatsapp` | Verify webhook |
| POST | `/api/v1/webhooks/whatsapp` | Receive incoming WhatsApp events |

---

## Business Rules

Webhook APIs must:

- Verify request authenticity
- Reject invalid webhook requests
- Process duplicate events safely using idempotency
- Log webhook activity
- Respond within the required timeout limits

Webhook endpoints should remain lightweight and delegate business processing to the appropriate services to ensure reliability and scalability.

---

# 21. Health and Monitoring APIs

Health and Monitoring APIs provide operational visibility into the platform and support system monitoring, diagnostics, and maintenance.

These endpoints are primarily intended for internal services, administrators, and infrastructure monitoring tools.

---

## Responsibilities

- Verify API availability
- Monitor service health
- Report dependency status
- Provide readiness information
- Provide liveness information
- Expose application metrics

---

## Example Endpoints

| Method | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/v1/health` | General system health |
| GET | `/api/v1/health/live` | Liveness check |
| GET | `/api/v1/health/ready` | Readiness check |
| GET | `/api/v1/metrics` | Application metrics |

---

## Business Rules

Health APIs should:

- Respond quickly without expensive database operations
- Avoid exposing sensitive infrastructure details
- Return standardized health responses
- Be suitable for automated monitoring systems
- Distinguish between healthy, degraded, and unavailable services

---

# 22. Idempotency

Certain API operations must be idempotent to prevent duplicate processing caused by retries or repeated client requests.

Idempotency is especially important for operations that create or modify business resources.

Examples include:

- Order creation
- Subscription creation
- Payment processing
- Webhook event processing

Clients should include an **Idempotency-Key** header when performing operations that require safe retries.

Example:

```http
Idempotency-Key: 6d6ab2fa-2a18-4d79-aef7-9b18a57d25d8
```

The server should:

- Detect duplicate requests
- Return the previously generated response when appropriate
- Prevent duplicate business operations
- Maintain request history for a configurable period

This approach ensures reliable processing even when network interruptions occur.

---

# 23. Pagination, Filtering, and Sorting

Collection endpoints should support standardized pagination, filtering, and sorting to improve scalability and client usability.

---

## Pagination

Paginated endpoints should support the following query parameters:

| Parameter | Description |
|-----------|-------------|
| `page` | Page number |
| `page_size` | Number of records per page |

Example:

```http
GET /api/v1/orders?page=2&page_size=20
```

---

## Filtering

Collection resources may support filtering by business attributes.

Examples:

```http
GET /api/v1/orders?status=completed
```

```http
GET /api/v1/products?meal_type=breakfast
```

```http
GET /api/v1/subscriptions?status=active
```

---

## Sorting

Sorting should be supported using a consistent parameter.

Example:

```http
GET /api/v1/orders?sort=-created_at
```

Where:

- `created_at` → ascending
- `-created_at` → descending

Consistent pagination and filtering simplify API consumption and improve performance for large datasets.

---

# 24. Rate Limiting

Rate limiting protects the platform from abuse, accidental overload, and denial-of-service scenarios.

Different API consumers may have different limits depending on their role.

Example policy:

| Consumer | Example Limit |
|----------|---------------|
| Customer | 100 requests per minute |
| Business Owner | 300 requests per minute |
| Internal Services | Configurable |
| Administrator | Configurable |

When limits are exceeded, the API should return:

```http
429 Too Many Requests
```

Responses should include appropriate headers indicating:

- Remaining requests
- Reset time
- Configured limit

Rate limiting should be configurable and centrally managed.

---

# 25. Validation

Input validation is performed before business logic is executed.

FastAPI uses Pydantic models to validate incoming requests.

Validation includes:

- Required fields
- Data types
- Length constraints
- Value ranges
- Enumeration validation
- Format validation
- Business rule validation

Examples include:

- Valid phone numbers
- Valid email addresses
- Positive quantities
- Existing product identifiers
- Valid subscription plans
- Supported delivery dates

Invalid requests should return standardized validation errors without executing any business operations.

Validation should occur as early as possible within the request lifecycle to reduce unnecessary processing and maintain API reliability.

---

# 26. Security Considerations

Security is a fundamental design principle of the TiffinAI API. Every endpoint should follow secure-by-default practices to protect customer data, business operations, and external integrations.

---

## Authentication

Current implementation supports:

- Webhook verification
- Internal service authentication
- Environment-based secrets

Future enhancements may include:

- JWT Authentication
- OAuth 2.0
- API Keys
- Multi-Factor Authentication (MFA)

---

## Authorization

Authorization should be enforced using Role-Based Access Control (RBAC).

| Role | Access Level |
|------|--------------|
| Customer | Personal resources only |
| Rider | Assigned deliveries |
| Business Owner | Business operations |
| Administrator | Platform management |
| Internal Services | Service-to-service communication |

Every request should verify that the authenticated user has permission to access the requested resource.

---

## Data Protection

Sensitive information should be protected through:

- HTTPS encryption
- Password hashing
- Secure secret management
- Encryption of sensitive fields where required
- Least-privilege access policies

Personally identifiable information (PII) should only be exposed to authorized users.

---

## API Security Best Practices

The API should:

- Validate all incoming requests
- Sanitize user input
- Prevent SQL injection
- Prevent NoSQL injection
- Prevent command injection
- Prevent cross-site scripting (XSS)
- Protect against CSRF where applicable
- Apply rate limiting
- Log security-relevant events
- Return generic error messages without exposing internal implementation details

Security should be continuously reviewed as the platform evolves.

---

# 27. Logging and Observability

Comprehensive logging improves debugging, monitoring, auditing, and operational reliability.

---

## Request Logging

Each request should record:

- Request ID
- Timestamp
- Endpoint
- HTTP method
- Response status
- Processing time
- Authenticated user (when applicable)

---

## Error Logging

Errors should include:

- Error code
- Exception details
- Stack trace (internal only)
- Request ID
- Service name
- Timestamp

Sensitive information such as passwords, authentication tokens, and personal customer data must never be written to application logs.

---

## Metrics

Operational metrics may include:

- Request volume
- Response latency
- Error rates
- Success rates
- Webhook processing time
- AI tool execution time
- Database query performance

These metrics help identify performance bottlenecks and maintain service reliability.

---

# 28. API Lifecycle

The API follows a structured lifecycle to ensure stability while allowing continuous improvement.

---

## Versioning Strategy

Breaking changes should be introduced through new API versions.

Example:

```text
/api/v1
/api/v2
```

Existing versions should remain supported for a defined transition period before deprecation.

---

## Deprecation Policy

When an endpoint is scheduled for removal:

- Mark it as deprecated in the documentation
- Notify API consumers in advance
- Provide migration guidance
- Continue supporting the endpoint during the deprecation window

This approach minimizes disruption for client applications.

---

## Backward Compatibility

Whenever possible, new features should be introduced without breaking existing integrations.

Examples include:

- Adding optional request fields
- Introducing new response attributes
- Creating new endpoints instead of modifying existing contracts

---

# 29. Future Improvements

The API architecture is designed to evolve alongside the platform.

Potential future enhancements include:

- GraphQL support for flexible data retrieval
- Public developer APIs
- API gateway integration
- Advanced analytics endpoints
- Bulk import and export operations
- WebSocket support for real-time updates
- Enhanced webhook management
- API usage dashboards
- Fine-grained permission management
- Multi-tenant API support

These improvements can be introduced incrementally without requiring major architectural changes.

---

# 30. API Summary

The TiffinAI API is designed around RESTful principles, deterministic business services, and a clear separation of concerns.

FastAPI serves as the primary interface between client applications, AI components, business services, and external integrations.

Key characteristics of the API include:

- Resource-oriented endpoint design
- Consistent request and response formats
- Standardized error handling
- Secure authentication and authorization
- Deterministic business operations
- Scalable versioning strategy
- Robust validation and rate limiting
- Comprehensive logging and observability
- Support for conversational workflows through the AI Orchestrator

By following these principles, the API provides a reliable foundation for current functionality while remaining flexible enough to support future capabilities as the TiffinAI platform grows.