# TiffinAI — Product Scenarios & User Journey Document

> This document explains the complete product vision, user journeys, RAG implementation,
> LangGraph workflow, and AI decision-making logic for TiffinAI.
> Written to guide the development team and AI coding tools (Codex, Cursor, Claude Code).

---

## Table of Contents

1. [Product Vision](#1-product-vision)
2. [Actors in the System](#2-actors-in-the-system)
3. [Complete User Journey Map](#3-complete-user-journey-map)
4. [Scenario 1 — New Customer First Contact](#scenario-1--new-customer-first-contact)
5. [Scenario 2 — Menu & Pricing Inquiry](#scenario-2--menu--pricing-inquiry)
6. [Scenario 3 — Placing a Meal Order](#scenario-3--placing-a-meal-order)
7. [Scenario 4 — Weekly Subscription](#scenario-4--weekly-subscription)
8. [Scenario 5 — Order Status Check](#scenario-5--order-status-check)
9. [Scenario 6 — Cancellation or Modification](#scenario-6--cancellation-or-modification)
10. [Scenario 7 — FAQ Handling](#scenario-7--faq-handling)
11. [Scenario 8 — Escalation to Human Owner](#scenario-8--escalation-to-human-owner)
12. [Scenario 9 — Owner Daily Summary](#scenario-9--owner-daily-summary)
13. [Language Detection & Switching](#13-language-detection--switching)
14. [RAG Implementation](#14-rag-implementation)
15. [LangGraph Workflow](#15-langgraph-workflow)
16. [AI Tools Design](#16-ai-tools-design)
17. [Conversation Memory Design](#17-conversation-memory-design)
18. [Escalation Logic](#18-escalation-logic)
19. [What AI Does vs What Python Does](#19-what-ai-does-vs-what-python-does)
20. [Edge Cases & Guardrails](#20-edge-cases--guardrails)

---

## 1. Product Vision

**TiffinAI** is a WhatsApp-native AI assistant for a home kitchen that provides tiffin (meal) services to bachelors and working professionals in Pakistan.

The owner currently answers 50–100+ WhatsApp messages every day manually:
- "Aaj ka menu kya hai?"
- "Lunch delivery kab hogi?"
- "Weekly subscription kitne ki hai?"
- "Mera order cancel karna hai"
- "Kal se start karna hai subscription"

TiffinAI handles all of these automatically — in Urdu or English — so the owner can focus on cooking, not messaging.

### What the Customer Gets
- Instant replies 24/7 on WhatsApp
- Menu information, pricing, delivery timings
- Easy order placement and subscription signup
- Real-time order status updates
- Human escalation when needed

### What the Owner Gets
- Zero time spent on repetitive questions
- All orders logged automatically
- Daily summary every evening
- Notification only when a human is truly needed

---

## 2. Actors in the System

| Actor | Who They Are | How They Interact |
|---|---|---|
| **Customer** | Bachelor or working professional | WhatsApp messages |
| **AI Agent** | TiffinAI brain | Processes messages, calls tools, sends replies |
| **Owner** | Home kitchen owner | Receives escalations + daily summary on WhatsApp |
| **System** | Backend + database | Stores orders, subscriptions, conversations |

---

## 3. Complete User Journey Map

```
Customer sends WhatsApp message
            ↓
    ┌───────────────────────┐
    │  Is this a new        │
    │  customer?            │
    └───────────────────────┘
         Yes ↓        No ↓
    Register &      Load existing
    greet them      profile & history
            ↓
    ┌───────────────────────────────────────────┐
    │           What does the customer want?    │
    └───────────────────────────────────────────┘
         ↓            ↓           ↓          ↓
    View Menu    Place Order   Subscription  FAQ
         ↓            ↓           ↓          ↓
    RAG search   Collect      Collect     RAG search
    menu docs    order info   plan info   policy docs
         ↓            ↓           ↓          ↓
    Reply with   Confirm &    Confirm &   Answer from
    menu+prices  save order   save sub    knowledge base
                      ↓
              ┌──────────────┐
              │  Can AI      │
              │  handle it?  │
              └──────────────┘
               Yes ↓    No ↓
           Reply to   Escalate
           customer   to owner
                          ↓
                   Owner notified
                   on WhatsApp
```

---

## Scenario 1 — New Customer First Contact

### Trigger
A person messages the tiffin service WhatsApp number for the very first time.

### What Happens

**Customer:**
> "Hello, tiffin service available hai?"

**System (behind the scenes):**
1. Webhook receives message
2. System checks database — no record for this phone number
3. New customer profile created
4. New conversation session started
5. Agent generates welcome response

**AI Response (Urdu detected):**
> "Assalam o Alaikum! 🍱 TiffinAI mein khush aamdeed!
> Hum ghar ka khana bachelors aur working professionals ko deliver karte hain.
>
> Aap kya jaanna chahte hain?
> 1️⃣ Aaj ka menu
> 2️⃣ Prices aur subscription plans
> 3️⃣ Delivery timings
> 4️⃣ Order karna hai"

### Data Saved
```
customers table:
- phone: +923001234567
- first_seen: 2024-01-15 10:30:00
- language_preference: ur

conversations table:
- customer_phone: +923001234567
- started_at: 2024-01-15 10:30:00
- status: active
```

---

## Scenario 2 — Menu & Pricing Inquiry

### Trigger
Customer asks about today's menu or prices.

### Conversation Flow

**Customer:**
> "Aaj lunch mein kya hai?"

**AI (RAG search on today's menu):**
> "Aaj ka lunch menu 🍽️
>
> • Daal Chawal + Salad — Rs. 180
> • Chicken Karahi + 2 Roti — Rs. 250
> • Vegetable Pulao + Raita — Rs. 200
>
> Delivery time: 12:30 PM – 1:30 PM
> Order karne ki last time: 11:00 AM
>
> Order karna chahte hain? 😊"

**Customer:**
> "Chicken karahi wala le lena hai, price thori zyada nahi?"

**AI:**
> "Hum samajhte hain! Lekin is mein ghar ka masala, fresh chicken aur 2 roti shamil hain.
> Agar aap weekly subscription lete hain toh har meal sirf Rs. 220 mein milti hai — Rs. 30 ki bachat!
>
> Subscription ke baare mein jaanna chahte hain?"

### RAG Used For
- Today's menu (uploaded daily by owner as a simple text/image)
- Pricing details
- Delivery timings

### Tools Called
- `search_knowledge(query="aaj ka lunch menu prices")`

---

## Scenario 3 — Placing a Meal Order

### Trigger
Customer wants to order a single meal (breakfast, lunch, or dinner).

### Conversation Flow

**Customer:**
> "Lunch order karna hai"

**AI:**
> "Zaroor! Konsa meal chahiye?
>
> 🍽️ Aaj ka lunch:
> 1. Daal Chawal + Salad — Rs. 180
> 2. Chicken Karahi + 2 Roti — Rs. 250
> 3. Vegetable Pulao + Raita — Rs. 200"

**Customer:**
> "2 number wala"

**AI:**
> "Chicken Karahi + 2 Roti — Rs. 250 ✅
>
> Delivery address kya hai?"

**Customer:**
> "Gulberg Block C, House 45"

**AI:**
> "Delivery area check kar raha hoon..."
> *(tool: check_delivery_area)*
>
> "Bilkul! Hum Gulberg deliver karte hain 🚀
>
> Order confirm karein?
> 🍽️ Chicken Karahi + 2 Roti
> 📍 Gulberg Block C, House 45
> 💰 Rs. 250 (Cash on Delivery)
> 🕐 Delivery: 12:30 PM – 1:30 PM
>
> Confirm karne ke liye 'YES' likhein"

**Customer:**
> "YES"

**AI:**
> "Order confirm ho gaya! 🎉
>
> Order ID: #TF-2024-089
> Aapko delivery se pehle notify kar diya jaega.
> Shukriya! 😊"

### Behind the Scenes (Tool Calls)
```
1. search_knowledge("delivery areas")     → confirms Gulberg is in zone
2. check_menu_availability("lunch", 2)    → confirms item available
3. create_order({                         → saves to DB
     customer_phone: "+923001234567",
     meal: "Chicken Karahi + 2 Roti",
     meal_type: "lunch",
     price: 250,
     address: "Gulberg Block C, House 45",
     status: "confirmed"
   })
4. generate_order_id()                    → returns TF-2024-089
```

### Data Saved
```
orders table:
- id: TF-2024-089
- customer_phone: +923001234567
- meal_name: Chicken Karahi + 2 Roti
- meal_type: lunch
- price: 250
- address: Gulberg Block C, House 45
- status: confirmed
- order_date: 2024-01-15
- created_at: 10:45:00
```

---

## Scenario 4 — Weekly Subscription

### Trigger
Customer wants to subscribe to daily meals for a week or month.

### Subscription Plans (Defined in DB, NOT by LLM)

| Plan | Meals Included | Price/Day | Total |
|---|---|---|---|
| Lunch Only | 1 meal/day × 7 days | Rs. 220 | Rs. 1,540/week |
| Lunch + Dinner | 2 meals/day × 7 days | Rs. 400 | Rs. 2,800/week |
| Full Day (3 meals) | 3 meals/day × 7 days | Rs. 550 | Rs. 3,850/week |
| Monthly Lunch | 1 meal/day × 30 days | Rs. 200 | Rs. 6,000/month |

### Conversation Flow

**Customer:**
> "Weekly subscription lena hai lunch ka"

**AI:**
> "Bohat acha! 😊 Hamare subscription plans:
>
> 🥗 Lunch Only (7 din)
> • Rs. 220/din = Rs. 1,540 total
> • Delivery: 12:30 PM – 1:30 PM daily
>
> 🍱 Lunch + Dinner (7 din)
> • Rs. 400/din = Rs. 2,800 total
>
> 🌟 Full Day — 3 meals (7 din)
> • Rs. 550/din = Rs. 3,850 total
>
> Konsa plan chahiye?"

**Customer:**
> "Lunch only"

**AI:**
> "Lunch Only plan — Rs. 1,540/week ✅
>
> Subscription kab se start karein?
> (Example: 'kal se' ya '20 January se')"

**Customer:**
> "Kal se"

**AI:**
> "Delivery address?"

**Customer:**
> "Same address hai jo pehle diya tha"

**AI (loads from customer profile):**
> "Gulberg Block C, House 45 — theek hai? ✅"

**Customer:**
> "Haan"

**AI:**
> "Subscription confirm! 🎉
>
> 📋 Plan: Lunch Only
> 📅 Start: 16 January 2024
> 📅 End: 22 January 2024
> 💰 Total: Rs. 1,540
> 📍 Gulberg Block C, House 45
>
> Payment aaj shaam tak kar dein:
> 🏦 Easypaisa: 0300-1234567
>
> Payment confirm hone ke baad subscription activate ho jaegi. 😊"

### Behind the Scenes
```
1. get_subscription_plans()              → returns all plans from DB
2. calculate_subscription_dates(         → Python calculates start/end
     start="tomorrow",
     duration=7
   )
3. get_customer_address(phone)           → retrieves saved address
4. create_subscription({                 → saves to DB
     plan: "lunch_only",
     start_date: "2024-01-16",
     end_date: "2024-01-22",
     price: 1540,
     status: "pending_payment"
   })
```

---

## Scenario 5 — Order Status Check

### Trigger
Customer wants to know where their order is.

### Conversation Flow

**Customer:**
> "Mera order kab aayega?"

**AI (fetches latest order from DB):**
> "Aapka order #TF-2024-089 check kar raha hoon...
>
> 🍽️ Chicken Karahi + 2 Roti
> 📍 Gulberg Block C, House 45
> 🚀 Status: On the way
> ⏰ Expected: 12:30 PM – 1:30 PM
>
> Thodi der mein pohonch jaega! 😊"

### Tool Called
```
get_order_status(customer_phone="+923001234567", order_id="latest")
→ returns: { status: "on_the_way", eta: "12:30-1:30 PM" }
```

---

## Scenario 6 — Cancellation or Modification

### Trigger
Customer wants to cancel or change their order.

### Conversation Flow — Cancellation

**Customer:**
> "Order cancel karna hai"

**AI:**
> "Aapka latest order:
> #TF-2024-089 — Chicken Karahi + 2 Roti — Rs. 250
>
> Cancel karna chahte hain?"

**Customer:**
> "Haan"

**AI (checks cancellation policy via RAG + Python rule):**

**If order is more than 1 hour before delivery:**
> "Order cancel ho gaya ✅
> Order #TF-2024-089 cancel kar diya gaya hai.
> Agar dobara order karna ho toh bata dein! 😊"

**If order is less than 1 hour before delivery:**
> "Maafi chahte hain, lekin delivery se 1 ghante se kam time mein order cancel nahi ho sakta.
> Koi aur madad chahiye?"

### Important Rule
The 1-hour cancellation rule is enforced by Python in `order_service.py` — NOT by the LLM.

---

## Scenario 7 — FAQ Handling

### Common FAQs the RAG System Handles

| Question | Source |
|---|---|
| "Delivery charges kya hain?" | Policy document |
| "Kaunse areas mein deliver karte hain?" | Delivery zones document |
| "Khana halal hai?" | FAQ document |
| "Khana ghar ka bana hua hai?" | FAQ document |
| "Payment kaise karein?" | Payment policy document |
| "Subscription pause ho sakti hai?" | Subscription policy |
| "Delivery late kyun hai?" | → Escalate to human |

### Flow for FAQ

**Customer:**
> "Kya home delivery free hai?"

**AI (RAG search):**
> "Delivery charges:
> • 5km tak: Free delivery 🎉
> • 5–10km: Rs. 50
> • 10km se zyada: Available nahi
>
> Aap ka area check karna chahte hain?"

---

## Scenario 8 — Escalation to Human Owner

### When AI Escalates (Python rules, not LLM decision)

| Trigger | Example |
|---|---|
| Customer frustrated or complaining | "Ye kya bakwaas service hai" |
| AI fails to answer after 2 attempts | Question not in knowledge base |
| Payment dispute | "Maine payment ki thi lekin order nahi aaya" |
| Custom request outside menu | "Kya aap biryani bana sakte hain?" |
| Customer explicitly asks for human | "Owner se baat karni hai" |
| Subscription modification edge case | Partial refund request |

### Conversation Flow

**Customer:**
> "Maine kal payment ki thi lekin abhi tak koi response nahi mila"

**AI:**
> "Hum aapki problem samajhte hain aur maafi chahte hain 🙏
>
> Yeh matter owner ke paas forward kar diya gaya hai.
> Aap ko 15–30 minutes mein reply milega.
>
> Aapka reference number: ESC-2024-012"

**Owner receives (on their WhatsApp):**
> "⚠️ Escalation Alert — ESC-2024-012
>
> Customer: +923001234567
> Issue: Payment made yesterday, no response received
> Time: 11:45 AM
>
> [View conversation history in dashboard]"

### Data Saved
```
escalations table:
- id: ESC-2024-012
- conversation_id: ...
- customer_phone: +923001234567
- reason: payment_dispute
- status: pending
- created_at: 11:45:00
```

---

## Scenario 9 — Owner Daily Summary

### When
Every evening at 9:00 PM (scheduled job — not triggered by customer).

### Owner Receives on WhatsApp

> "📊 TiffinAI Daily Summary — 15 January 2024
>
> 📦 Orders Today: 23
> ✅ Delivered: 21
> ❌ Cancelled: 2
> 💰 Revenue: Rs. 5,450
>
> 📋 Subscriptions Active: 8
> 🆕 New Subscribers Today: 2
>
> ❓ Top Questions Asked:
> 1. Delivery charges (asked 7 times)
> 2. Tomorrow's menu (asked 5 times)
> 3. Payment methods (asked 4 times)
>
> ⚠️ Escalations: 1 (resolved)
>
> 🤖 AI handled: 94% of conversations
> 👤 Human needed: 6%"

---

## 13. Language Detection & Switching

### How it Works

The system detects language on every incoming message and matches the response language accordingly.

| Customer writes in | AI responds in |
|---|---|
| Urdu (Roman or script) | Urdu (Roman) |
| English | English |
| Mix of both | Match the dominant language |

### Language Detection (Python, not LLM)

```python
def detect_language(text: str) -> str:
    # Use langdetect library
    # Roman Urdu patterns detected via keyword matching
    # Falls back to English if unclear
    urdu_keywords = ["kya", "hai", "mera", "aap", "nahi", "karo", "chahiye", "wala"]
    if any(word in text.lower() for word in urdu_keywords):
        return "ur"
    return detect(text)  # langdetect for English/Urdu script
```

### Language stored in customer profile
Once detected, the customer's language preference is saved. All future messages use that language unless the customer switches.

---

## 14. RAG Implementation

### 14.1 What Goes Into RAG

| Document | Content | Updated |
|---|---|---|
| `daily_menu.txt` | Today's breakfast, lunch, dinner + prices | Daily by owner |
| `subscription_plans.txt` | All plans, prices, duration | When plans change |
| `delivery_zones.txt` | Areas covered, delivery charges | When zones change |
| `faq.txt` | Common questions and answers | As needed |
| `payment_policy.txt` | Payment methods, Easypaisa/JazzCash numbers | When changed |
| `cancellation_policy.txt` | Rules for cancellation, modification | When changed |

### 14.2 What Does NOT Go Into RAG

| Data | Why | Where Instead |
|---|---|---|
| Order status | Changes in real-time | PostgreSQL via tool |
| Subscription status | Live data | PostgreSQL via tool |
| Customer payment status | Sensitive, live | PostgreSQL via tool |
| Prices (for calculation) | Must be exact | PostgreSQL via tool |
| Delivery time for specific order | Order-specific | PostgreSQL via tool |

### 14.3 Ingestion Pipeline

```
Owner uploads/updates document
            ↓
FastAPI /knowledge/upload endpoint receives file
            ↓
knowledge_service.ingest(file)
            ↓
Text extracted (plain text / PDF / image via OCR)
            ↓
Text split into chunks
  • chunk_size = 400 tokens
  • chunk_overlap = 50 tokens
  • metadata = { business_id, document_type, updated_at }
            ↓
Each chunk → OpenAI text-embedding-3-small → vector
            ↓
Vectors stored in Qdrant
  • collection = "tiffin_knowledge"
  • filter field = business_id
            ↓
Document record saved in PostgreSQL
  • filename, type, status: active, ingested_at
```

### 14.4 Retrieval Flow

```
Customer asks: "Delivery charges kya hain?"
            ↓
Query embedded → vector
            ↓
Qdrant similarity search
  • top_k = 3
  • filter: business_id = current_business
  • minimum_score = 0.75
            ↓
Retrieved chunks passed to LLM as context
            ↓
LLM generates answer ONLY from context
            ↓
If no chunk scores above 0.75:
  → "Mujhe is baare mein sure nahi, owner se confirm karein"
  → Escalation flagged
```

### 14.5 Daily Menu Update Flow

Owner sends today's menu every morning (simple WhatsApp message or text file):

```
Owner sends: "Aaj ka lunch: Daal Chawal 180, Chicken Karahi 250"
            ↓
Special owner command detected
            ↓
Old menu chunk deleted from Qdrant
            ↓
New menu ingested and embedded
            ↓
Confirmation sent to owner: "✅ Menu updated!"
```

### 14.6 Hallucination Prevention Rules

```
System Prompt (non-negotiable):
"Answer ONLY from the context provided below.
If the answer is not in the context, say:
'Mujhe is baare mein sure nahi, please owner se confirm karein.'
NEVER invent prices, delivery areas, or timings.
NEVER guess an answer."
```

---

## 15. LangGraph Workflow

### 15.1 Overview

LangGraph manages the conversation flow as a stateful graph. Each node does one thing. Edges decide which node runs next.

### 15.2 Conversation State

```python
class TiffinConversationState(TypedDict):
    # Identity
    business_id: str
    customer_phone: str
    conversation_id: str
    language: str                    # "en" or "ur"

    # Current turn
    incoming_message: str            # Raw customer message
    message_type: str                # "text", "image", "audio"

    # Context
    conversation_history: list       # Last 10 messages
    retrieved_context: str           # RAG result for this turn
    customer_profile: dict           # Name, address, language pref

    # Agent output
    tool_calls_made: list            # Tools called this turn
    agent_response: str              # Final response to send

    # Routing flags
    should_escalate: bool            # True = hand to human
    is_new_customer: bool            # True = show welcome message
    needs_rag: bool                  # True = retrieve from knowledge base
    order_in_progress: dict          # Stores partial order during collection
```

### 15.3 Graph Nodes

```
┌─────────────────────────────────────────────────────────┐
│                   LANGGRAPH NODES                        │
└─────────────────────────────────────────────────────────┘

Node 1: receive_and_parse
  - Parse incoming WhatsApp webhook payload
  - Extract: phone number, message text, timestamp
  - Detect language (Python — not LLM)
  - Load or create customer profile
  - Load last 10 messages from conversation history

Node 2: classify_intent
  - LLM classifies intent into one of:
    [ menu_inquiry | place_order | subscription |
      order_status | cancellation | faq | escalation | greeting ]
  - Returns: { intent: "place_order", confidence: 0.95 }

Node 3: retrieve_context  (runs only if needs_rag = True)
  - Embeds customer query
  - Searches Qdrant (filtered by business_id)
  - Returns top 3 chunks if score > 0.75
  - Sets retrieved_context in state

Node 4: run_agent
  - LLM receives:
    • System prompt
    • Conversation history
    • Retrieved context (if any)
    • Available tools
  - LLM decides: answer directly OR call a tool

Node 5: execute_tools
  - Executes whatever tool the LLM selected
  - Tool calls Python service (never DB directly)
  - Returns structured result to agent
  - Agent generates final response

Node 6: check_escalation
  - Python checks escalation conditions (not LLM)
  - Sets should_escalate = True if triggered
  - Creates escalation record in DB

Node 7: send_response
  - Calls Meta WhatsApp Cloud API
  - Sends response to customer
  - Logs message to DB

Node 8: notify_owner  (runs only if should_escalate = True)
  - Sends escalation alert to owner's WhatsApp
  - Includes customer phone + issue summary
```

### 15.4 Graph Edges (Decision Flow)

```
receive_and_parse
        ↓
  [is_new_customer?]
    Yes → send welcome → classify_intent
    No  → classify_intent
        ↓
  [intent needs RAG?]
    Yes → retrieve_context → run_agent
    No  → run_agent
        ↓
  [agent needs tool?]
    Yes → execute_tools → run_agent (with tool result)
    No  → check_escalation
        ↓
  [should_escalate?]
    Yes → send_response → notify_owner → END
    No  → send_response → END
```

### 15.5 Intent → Node Routing

| Intent Detected | RAG Needed | Tools Needed |
|---|---|---|
| `greeting` | No | No |
| `menu_inquiry` | Yes (menu doc) | No |
| `faq` | Yes (faq/policy docs) | No |
| `place_order` | Yes (menu doc) | Yes (create_order) |
| `subscription` | Yes (plans doc) | Yes (create_subscription) |
| `order_status` | No | Yes (get_order_status) |
| `cancellation` | Yes (policy doc) | Yes (cancel_order) |
| `escalation` | No | Yes (escalate_to_human) |

---

## 16. AI Tools Design

Each tool is a thin bridge between the LLM and a Python service. Tools never touch the database directly.

### Tool 1: `search_menu`
```
Purpose: Get today's menu and prices
Input:   { meal_type: "lunch" | "breakfast" | "dinner" | "all" }
Calls:   knowledge_service.get_menu(meal_type)
Returns: { items: [...], prices: [...], delivery_time: "..." }
Used when: Customer asks about menu or prices
```

### Tool 2: `create_order`
```
Purpose: Place a new meal order
Input:   { meal_name, meal_type, price, address, customer_phone }
Calls:   order_service.create(order_data)
Returns: { order_id, status, estimated_delivery }
Used when: Customer confirms an order
```

### Tool 3: `get_order_status`
```
Purpose: Check status of customer's latest or specific order
Input:   { customer_phone, order_id (optional) }
Calls:   order_service.get_status(phone, order_id)
Returns: { order_id, meal, status, eta }
Used when: Customer asks "order kab aayega?"
```

### Tool 4: `create_subscription`
```
Purpose: Register a new weekly/monthly subscription
Input:   { plan_name, start_date, address, customer_phone }
Calls:   subscription_service.create(data)
Returns: { subscription_id, plan, start_date, end_date, total_price }
Used when: Customer wants to subscribe
```

### Tool 5: `cancel_order`
```
Purpose: Cancel an existing order
Input:   { order_id, customer_phone }
Calls:   order_service.cancel(order_id, phone)
Returns: { success: bool, message, reason_if_failed }
Note:    Cancellation policy enforced in Python, not LLM
```

### Tool 6: `check_delivery_area`
```
Purpose: Check if a given address is in delivery zone
Input:   { address: "Gulberg Block C" }
Calls:   knowledge_service.check_zone(address)
Returns: { is_deliverable: bool, charge: 0 | 50, zone: "..." }
```

### Tool 7: `escalate_to_human`
```
Purpose: Flag conversation for human takeover
Input:   { customer_phone, reason, conversation_id }
Calls:   escalation_service.create(data)
Returns: { escalation_id, owner_notified: bool }
Used when: Python escalation rules trigger
```

### Tool 8: `get_subscription_plans`
```
Purpose: Return all available subscription plans
Input:   { } (no input needed)
Calls:   subscription_service.get_plans()
Returns: { plans: [...with prices and details...] }
Note:    Prices come from DB, not RAG
```

---

## 17. Conversation Memory Design

### Short-Term Memory (Within Session)

- Last 10 messages of the current conversation are always passed to the LLM
- Stored in `messages` table, retrieved by `conversation_id`
- If conversation exceeds 10 turns, older messages are summarized into one context block

### What Gets Remembered Across Sessions

| Data | Where Stored | Example |
|---|---|---|
| Customer name | `customers.name` | "Ahmed" |
| Preferred address | `customers.default_address` | "Gulberg Block C" |
| Language preference | `customers.language` | "ur" |
| Last order | `orders` table (latest) | Retrieved on demand |
| Active subscription | `subscriptions` table | Retrieved on demand |

### Order Collection Memory (Mid-Conversation)

When a customer is placing an order, partial order data is stored in `ConversationState.order_in_progress`:

```python
order_in_progress = {
    "meal_name": "Chicken Karahi",   # Collected ✅
    "meal_type": "lunch",            # Collected ✅
    "address": None,                 # Still needed ❌
    "confirmed": False               # Not confirmed yet ❌
}
```

This prevents the AI from losing track of what has already been collected.

---

## 18. Escalation Logic

### Rules Checked in Python (escalation_service.py)

```python
def should_escalate(message: str, conversation: Conversation) -> tuple[bool, str]:

    # Rule 1: Customer explicitly asks for human
    human_keywords = ["owner", "human", "banda", "aap se", "manager", "baat karni hai"]
    if any(kw in message.lower() for kw in human_keywords):
        return True, "customer_requested_human"

    # Rule 2: Frustration or complaint detected
    frustration_keywords = ["bakwaas", "worst", "ganda", "cheating", "fraud", "complaint"]
    if any(kw in message.lower() for kw in frustration_keywords):
        return True, "customer_frustrated"

    # Rule 3: AI failed to answer twice in a row
    if conversation.consecutive_rag_failures >= 2:
        return True, "ai_cannot_answer"

    # Rule 4: Payment dispute
    payment_dispute_keywords = ["payment ki thi", "paid", "paise gaye", "refund"]
    if any(kw in message.lower() for kw in payment_dispute_keywords):
        return True, "payment_dispute"

    # Rule 5: Conversation too long without resolution
    if conversation.message_count > 15 and not conversation.order_placed:
        return True, "unresolved_long_conversation"

    return False, None
```

---

## 19. What AI Does vs What Python Does

This is the most important rule in the entire system.

| Task | AI (LLM) | Python Service |
|---|---|---|
| Understand "Chicken wala de do" as an order | ✅ | ❌ |
| Calculate price of Chicken Karahi | ❌ | ✅ |
| Check if slot/meal is available | ❌ | ✅ |
| Generate friendly Urdu response | ✅ | ❌ |
| Decide if cancellation is allowed | ❌ | ✅ |
| Write order to database | ❌ | ✅ |
| Detect customer language | ❌ | ✅ |
| Decide if escalation needed | ❌ | ✅ |
| Generate daily summary content | ✅ | ❌ |
| Calculate subscription end date | ❌ | ✅ |
| Choose which tool to call | ✅ | ❌ |
| Execute the tool | ❌ | ✅ |

---

## 20. Edge Cases & Guardrails

### Edge Case 1: Customer sends voice note
```
Action: AI replies → "Voice notes abhi support nahi hote.
Please text mein likhein ya owner se directly baat karein."
Escalation: Optional (depends on message content if transcribed)
```

### Edge Case 2: Customer sends image (e.g. screenshot of order)
```
Action: AI replies → "Image receive ho gayi.
Owner ko forward kar di gayi hai. Thodi der mein reply milega."
Escalation: Always escalate image messages
```

### Edge Case 3: Customer asks something completely off-topic
```
Customer: "Bhai Python programming sikhao"
AI: "Hum sirf tiffin service ke liye yahan hain 😄
Kya aap menu ya subscription ke baare mein jaanna chahte hain?"
```

### Edge Case 4: Customer gives incomplete address
```
AI: "Thodi aur detail chahiye — kaunsa block aur ghar number?
Hum confirm kar lein ke aapke area mein deliver karte hain."
```

### Edge Case 5: Owner accidentally messages the bot number
```
System detects owner's phone number
→ Route to owner dashboard flow (not customer flow)
→ Allow: menu update, check today's orders, view escalations
```

### Edge Case 6: Duplicate order attempt
```
Customer places same order twice within 10 minutes
→ Python detects duplicate (same meal, same address, < 10 min gap)
→ AI: "Aapka order pehle se place ho chuka hai! (Order #TF-2024-089)
Kya aap duplicate order chahte hain?"
```

### Edge Case 7: Order placed after cutoff time
```
Customer tries to order lunch at 12:45 PM (cutoff was 11:00 AM)
→ Python checks: current_time > meal_cutoff_time
→ AI: "Lunch orders 11:00 AM tak accept hote hain.
Kya aap dinner order karna chahte hain? (Order by 6:00 PM)"
```

---

*This document covers the complete product scenarios for TiffinAI.*
*Use this as the reference for all AI, backend, and integration implementation decisions.*
*Last updated: Week 1 — Product Definition Phase*