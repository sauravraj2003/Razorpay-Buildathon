# Autonomous Agentic Commerce Platform
### Razorpay Buildathon | Multi-Agent E-Commerce with LangGraph, Groq, and Human-in-the-Loop

An autonomous multi-agent commerce engine built on **LangGraph StateGraph**, **FastAPI**, **Groq (LLaMA 3.3)**, **SQLite**, and **Razorpay Payment Links**.

---

## 🌟 Key Features

1. **4 Autonomous Agents**:
   - 🧠 **Orchestrator Agent**: Routes user intent, maintains state handoffs, prevents downstream confusion, and monitors HITL triggers.
   - 🔍 **Buyer Agent**: High-precision catalog search over SQLite, top-3 ranked products with 1-line justification, and strict anti-hallucination fallback.
   - 💳 **Checkout Agent**: Validates cart, surfaces exact financial details prior to transaction, triggers Human-in-the-Loop (HITL) approval, and creates Razorpay payment links.
   - ✨ **Upsell Agent**: Post-cart complementary recommendations (max 2 items) with relevance justifications; respects user decline signals and protects active checkout flows.
2. **LangGraph StateGraph Architecture**:
   - `AgenticCommerceState` TypedDict maintaining session, cart, payment, and memory.
   - Thread persistence via `MemorySaver`.
3. **Razorpay Integration**:
   - Native payment link generation (`razorpay.Client`) with automated mock mode fallback for local builds and offline evaluation.
   - Explicit zero-retry policy without user consent.
4. **20-Scenario LLM-as-a-Judge Eval Harness**:
   - Automated scoring across **Correctness**, **Groundedness**, **Tool Appropriateness**, and **State Integrity**.
   - Per-agent metrics (Buyer precision, Checkout completion, Upsell timing accuracy, Orchestrator routing accuracy).
5. **Interactive Web Demonstration UI**:
   - Live visual multi-agent flow tracker, real-time cart state inspector, and interactive payment modals.

---

## 🏗️ Folder Structure

```
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py    # Intent classifier & context dispatcher
│   ├── buyer.py           # Catalog search & top-3 ranked recommendation
│   ├── checkout.py        # Cart validation & Razorpay payment link generation
│   ├── upsell.py          # Post-cart complementary product targeting
│   └── llm_client.py      # Groq LLaMA 3.3 client with fallback
├── tools/
│   ├── __init__.py
│   ├── db.py              # SQLite schema, seed catalog, & order persistence
│   ├── catalog_search.py  # Ranked retrieval with anti-hallucination threshold
│   ├── cart_ops.py        # Cart mutations, stock validation, and tax calculations
│   └── razorpay_tool.py   # Razorpay API client & mock payment link creator
├── graph/
│   ├── __init__.py
│   ├── state.py           # AgenticCommerceState TypedDict schema
│   ├── edges.py           # Conditional edge routing logic
│   ├── graph.py           # StateGraph compilation & checkpointer
│   └── runner.py          # Interactive session & HITL manager
├── api/
│   ├── __init__.py
│   ├── main.py            # FastAPI backend (/chat, /chat/stream, /chat/approve)
│   └── static/
│       └── index.html     # Real-time web demonstration interface
├── eval/
│   ├── __init__.py
│   ├── scenarios.json     # 20 benchmark scenarios with edge cases
│   └── harness.py         # LLM-as-a-judge evaluation suite
├── .env.example
├── run.sh
└── README.md
```

---

## 🚀 Quick Start

### 1. Run Server
```bash
./run.sh
```
Or with uvicorn:
```bash
.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser at **`http://localhost:8000`** to access the interactive web dashboard.

### 2. Run the 20-Scenario Evaluation Harness
```bash
.venv/bin/python eval/harness.py
```

Expected benchmark output:
```text
============================================================
EVALUATION COMPLETE: 20/20 passed (100.0%)
Overall Benchmark Score: 100/100 | Avg Judge Score: 5.0/5.0
Buyer Retrieval Precision: 100.0% | Fallback Rate: 100.0%
Checkout Completion: 100.0%
Upsell Timing Accuracy: 100.0%
Orchestrator Routing Accuracy: 100.0%
============================================================
```

---

## 📊 Evaluation Harness Scenarios

The test suite covers:
1. **Exact Product Search**: Ranked top-3 retrieval with 1-line justification.
2. **Ambiguous Query**: Broad inquiry handling without fictional specs.
3. **Non-Existent Query**: Strict catalog fallback (zero hallucination).
4. **Filtered Search**: Price and category boundary checks.
5. **Multi-Intent**: Handling "find X and buy Y" cleanly.
6. **Zero-Item Cart**: Validation error on empty cart checkout attempt.
7. **HITL Surfacing**: Itemized summary and user confirmation prompt before payment.
8. **HITL Approval**: Seamless Razorpay payment link generation.
9. **HITL Cancellation**: Order paused with cart preserved.
10. **Mid-Checkout Upsell Guard**: Suppressing interruptions during checkout.
11. **Empty Cart Upsell**: Suppressing upsell when no base items exist.
12. **Complementary Upsell**: Recommending at most 2 complementary items.
13. **Decline Preference**: Respecting "no upsell" signal.
14. **No-Spam Policy**: Suppressing repeated upsell offers.
15. **Gateway Error Classification**: Classifying gateway timeout vs user error.
16. **Zero-Retry Policy**: Requiring explicit consent before re-attempting failed payments.
17. **Chit-chat & Help**: Conversational intro without false routing.
18. **Stock Boundary Validation**: Preventing orders that exceed warehouse inventory.
19. **End-to-End Happy Path**: Full multi-turn buying journey.
20. **Context Integrity**: Preserving cart snapshots across agent handoffs.

---

## 📡 API Endpoints

- `POST /chat` — Multi-agent conversation turn
- `POST /chat/stream` — Real-time Server-Sent Events (SSE) token and agent status stream
- `POST /chat/approve` — Human-in-the-Loop payment confirmation/rejection
- `GET /products` — Product catalog
- `POST /cart/add` — Add product to cart
- `POST /cart/remove` — Remove product from cart
- `POST /eval/run` — Run live benchmark evaluation suite
- `GET /orders` — Order history from SQLite
