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

- Admin dashboard
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
