# 🍱 Small Business Automation Project

An AI-powered WhatsApp assistant that enables customers to order meals, manage subscriptions, track orders, and receive instant business support through natural conversations.

The project combines **FastAPI**, **LangGraph**, **Retrieval-Augmented Generation (RAG)**, **PostgreSQL**, **OpenAI**, and **Twilio WhatsApp** to automate customer interactions for a small food business.

---

## Features

### 🤖 AI-Powered WhatsApp Assistant
- Natural language conversations
- Context-aware responses
- Multi-turn conversation handling
- Conversation memory using LangGraph

### 🍛 Meal Ordering
- View today's menu
- Add meals to cart
- View cart
- Checkout
- Address collection
- Order confirmation
- Order tracking

### 📅 Subscription Plans
- Browse available subscription plans
- View pricing and descriptions
- Subscribe through chat

### 📚 Knowledge Base (RAG)
Answer customer questions such as:
- Delivery areas
- Refund policy
- Business information
- General FAQs

Powered using Retrieval-Augmented Generation (RAG) with ChromaDB.

### 📦 Order Management
- Cart management
- Order creation
- Order status tracking
- Customer conversation history

---

# Tech Stack

| Category | Technology |
|----------|------------|
| Backend | FastAPI |
| AI Workflow | LangGraph |
| LLM | OpenAI GPT |
| Embeddings | OpenAI Embeddings |
| Vector Database | ChromaDB |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| Messaging | Twilio WhatsApp API |
| Validation | Pydantic |
| Testing | Pytest |
| Deployment | Railway |

---

# Project Structure

```text
.
├── alembic/
├── app/
│   ├── api/
│   ├── core/
│   ├── data/
│   ├── langgraph/
│   ├── models/
│   ├── rag/
│   ├── services/
│   ├── schemas/
│   └── main.py
│
├── docs/
├── scripts/
├── tests/
├── alembic.ini
├── requirements.txt
└── README.md
```

---

# Architecture

```
Customer
      │
      ▼
WhatsApp
      │
      ▼
Twilio Webhook
      │
      ▼
FastAPI
      │
      ▼
LangGraph Workflow
      │
 ┌────┴────────────┐
 │                 │
 ▼                 ▼
Business Logic    RAG
 │                 │
 ▼                 ▼
PostgreSQL      ChromaDB
 │
 ▼
OpenAI
```

---

# Conversation Flow

```
User
   │
   ▼
Twilio Webhook
   │
   ▼
Intent Detection
   │
   ▼
LangGraph Workflow
   │
   ├── Greeting
   ├── Menu
   ├── Cart
   ├── Checkout
   ├── Subscription
   ├── Tracking
   └── RAG
```

---

# Environment Variables

Create a `.env` file with the following variables:

```env
OPENAI_API_KEY=

OPENAI_MODEL=gpt-4.1-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

DATABASE_URL=

TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_NUMBER=

TWILIO_SIGNATURE_VERIFICATION_ENABLED=true
TWILIO_TRUST_FORWARDED_HEADERS=true
```

---

# Installation

Clone the repository:

```bash
git clone https://github.com/Hassan-Faisal/Small-Business-Automation-Project.git

cd Small-Business-Automation-Project
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it:

### Windows

```bash
.venv\Scripts\activate
```

### Linux / macOS

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# Database Setup

Run database migrations:

```bash
alembic upgrade head
```

Seed the demo data (if required):

```bash
python -m app.data.tiffin_seed
```

---

# Run the Application

```bash
uvicorn app.main:app --reload
```

Application:

```
http://localhost:8000
```

Swagger Documentation:

```
http://localhost:8000/docs
```

---

# Railway Deployment

1. Connect the GitHub repository to Railway.
2. Add a PostgreSQL service.
3. Configure the required environment variables.
4. Set the start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

5. Run database migrations before deployment:

```bash
alembic upgrade head
```

---

# Testing

Run the complete test suite:

```bash
pytest
```

Run specific tests:

```bash
pytest tests/test_menu_conversation.py
```

Run the smoke demo:

```bash
python scripts/smoke_tiffin_demo.py
```

---

# Key Capabilities

- AI-powered WhatsApp conversations
- Multi-turn conversational workflow
- Meal ordering
- Cart management
- Subscription management
- Order tracking
- RAG-powered FAQ support
- PostgreSQL persistence
- Railway deployment
- Twilio integration
- Automated database migrations
- Comprehensive automated testing

---

# Future Improvements

- Admin order, menu, customer, and subscription management
- Payment gateway integration
- Real-time delivery tracking
- Voice message support
- Multi-language conversations
- Analytics dashboard
- Customer notifications
- Inventory management

---

# License

This project is intended for educational and portfolio purposes.
## Admin owner authentication (Phase 1)

Admin authentication uses an HttpOnly, signed cookie. Add these variables to `.env`; use a long random secret in production and never commit real values:

```env
ADMIN_AUTH_SECRET=replace-with-a-long-random-production-secret
ADMIN_TOKEN_EXPIRE_MINUTES=60
ADMIN_COOKIE_SECURE=true
ADMIN_COOKIE_NAME=tiffinai_admin
ADMIN_COOKIE_SAMESITE=lax
```

For a frontend hosted on a different site from the backend (including local
`http://localhost:5173` calling a Railway HTTPS backend), set
`ADMIN_COOKIE_SAMESITE=none` together with `ADMIN_COOKIE_SECURE=true`. Keep
`lax` for a same-site local setup where the backend is served locally.

Apply the schema and create the first owner:

```bash
alembic upgrade head
python -m app.commands.create_admin
```

For local HTTP development only, set `ADMIN_COOKIE_SECURE=false`; keep it `true` in production. Open `/docs` and use `POST /admin/auth/login`; Swagger will retain the authentication cookie for `/admin/auth/me` and `/admin/protected-check`. Use `POST /admin/auth/logout` to clear it. Passwords and authentication secrets must not appear in source control, logs, or documentation.


---

# Admin Dashboard Frontend (Phase 2B)

The owner dashboard is a separate React application in `frontend/`. It uses the FastAPI HttpOnly admin cookie and never reads or stores authentication tokens in JavaScript.

## Frontend Setup

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Set the backend URL in `frontend/.env`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Run FastAPI separately from the repository root:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Vite serves the dashboard at `http://localhost:5173`. Sign in at `/login`; authenticated owners are redirected to `/dashboard`. Session checks, dashboard requests, and logout include credentials so the browser can send the HttpOnly cookie. Refreshing a protected route restores the session through `GET /admin/auth/me`.

## Admin CORS Configuration

Configure exact frontend origins on the API. Wildcards are rejected because credentialed CORS requires explicit origins.

```env
ADMIN_FRONTEND_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
ADMIN_COOKIE_SECURE=false
```

Use `ADMIN_COOKIE_SECURE=false` only for local HTTP development. In production, use HTTPS, `ADMIN_COOKIE_SECURE=true`, and add the deployed frontend origin to `ADMIN_FRONTEND_ORIGINS`. If the frontend and API are on different sites, configure the existing cookie setting as `ADMIN_COOKIE_SAMESITE=none`; same-site deployments can retain `lax`.

## Frontend Validation

```bash
cd frontend
npm run build
npm run lint
npm test
```

## Frontend Deployment

Build with `VITE_API_BASE_URL` set to the public FastAPI URL and publish `frontend/dist/` through a static host. Configure that exact HTTPS frontend origin in the backend `ADMIN_FRONTEND_ORIGINS`, then redeploy the API. The initial dashboard includes login, protected navigation, the dashboard summary, recent orders, logout, and placeholder pages only; order, menu, customer, subscription, analytics, and settings management are intentionally not implemented.

---

# Admin Menu Management API (Phase 3A)

`MealOffering` remains the authoritative scheduled menu record: it controls the day, meal type, menu description, availability, and active state shown to customers. `Product` remains the globally named orderable record used by carts and `OrderItem.product_id`.

The existing catalog associates these records by normalized name rather than a foreign key. Admin menu writes preserve that contract atomically:

- creating a new offering creates or reuses a same-name `Product`;
- a product name has one current orderable price, so explicit price changes update the product and all same-name scheduled offerings;
- product availability is true while at least one same-name offering is active and available;
- renaming an item with peer schedules or historical orders creates a new product instead of repurposing the old product;
- deletion is a soft deactivation of the offering;
- historical `OrderItem.unit_price`, `subtotal`, and `product_id` values are never modified.

Protected endpoints are available under `/admin/menu-items`. List results are paginated with a maximum page size of 100. The React menu-management page is intentionally not implemented in this phase.
