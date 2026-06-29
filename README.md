# TraceLens

An AI-assisted simulation trace debugger that automatically detects mismatches between RTL and SystemC/TLM functional model logs, localizes the first point of divergence, and generates grounded natural language debug summaries powered by an LLM explanation layer.

> **Core design principle:** The deterministic engine does the debugging. The LLM explains it.

---

## The Problem

In hardware/software validation workflows, engineers run simulations and compare RTL behavior against SystemC/TLM functional models. When they disagree, engineers must manually scan thousands of log lines to find where behavior first diverged — a slow, error-prone process.

TraceLens automates this: parse → align → detect → explain.

---

## Features

- **Log parsing** — Converts raw RTL and TLM simulation logs into structured, typed transaction events using Pydantic
- **Trace alignment** — Matches RTL and TLM events by transaction ID, address, and protocol state
- **Mismatch detection** — Identifies 7 failure categories: data, timing, state transition, missing transaction, extra transaction, error flag, and register config mismatches
- **First-divergence localization** — Pinpoints the exact timestamp and transaction where RTL and model behavior first diverge
- **LLM debug summaries** — Sends structured mismatch context to an LLM that generates evidence-cited, actionable debug reports
- **Dashboard** — Next.js UI displaying parsed transactions, mismatch table, and AI-generated debug report
- **Synthetic log generator** — Generates realistic RTL/TLM log pairs with 6 controllable bug injection types for evaluation

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI + Uvicorn |
| Log Parsing & Detection | Python, Pydantic, Regex |
| LLM Integration | LangChain + OpenAI GPT-3.5-turbo |
| Database | PostgreSQL |
| Frontend | Next.js 14 + Tailwind CSS |
| Containerization | Docker + Docker Compose |

---

## Project Structure

```
tracelens/
├── parser/
│   ├── rtl_parser.py           # Parses RTL simulation logs into structured events
│   ├── tlm_parser.py           # Parses TLM/SystemC model logs into structured events
│   └── schemas.py              # Pydantic models for transaction events
├── engine/
│   ├── aligner.py              # Matches RTL and TLM events by txn_id, address, state
│   ├── mismatch_detector.py    # Detects 7 mismatch categories across aligned pairs
│   └── divergence.py           # First-divergence localization algorithm
├── llm/
│   ├── summarizer.py           # Sends structured mismatch context to LLM
│   └── prompts.py              # Prompt templates for debug summary generation
├── synthetic/
│   └── log_generator.py        # Generates RTL/TLM log pairs with injected bugs
├── evaluation/
│   └── evaluate.py             # Measures mismatch detection and divergence accuracy
├── api.py                      # FastAPI REST API (upload, analyze, report endpoints)
├── db.py                       # PostgreSQL schema and query helpers
├── requirements.txt
├── docker-compose.yml
└── frontend/                   # Next.js dashboard
    └── app/
        └── page.tsx            # Mismatch table, timeline, and AI report display
```

---

## Architecture

```
User uploads RTL log + TLM log
              │
              ▼
        FastAPI Backend
              │
              ▼
     Log Parser (Python + Pydantic)
     RTL log ──────────► Structured Events
     TLM log ──────────► Structured Events
              │
              ▼
      Trace Alignment Engine
      (match by txn_id, addr, state)
              │
              ▼
     Mismatch Detection Engine
     (7 failure categories)
              │
              ▼
     First-Divergence Localization
     (exact timestamp + transaction)
              │
              ▼
     Structured Mismatch Report
     (stored in PostgreSQL)
              │
              ▼
     LLM Explanation Layer
     (grounded summary, no hallucination)
              │
              ▼
     Next.js Dashboard
     (table + timeline + AI report)
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker Desktop
- OpenAI API key

### 1. Clone the repository

```bash
git clone https://github.com/msbhullar/tracelens.git
cd tracelens
```

### 2. Set up Python environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Set up environment variables

Create a `.env` file in the root directory:

```
OPENAI_API_KEY=your_openai_api_key_here
DATABASE_URL=postgresql://postgres:password@localhost:5432/tracelensdb
```

### 4. Start the database

```bash
docker-compose up -d db
```

### 5. Start the backend API

```bash
uvicorn api:app --reload --port 8000
```

### 6. Start the frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

---

## How to Use

1. Open `http://localhost:3000` in your browser
2. Upload an RTL log file and a TLM log file using the upload panel
3. Click **Analyze** — the engine parses, aligns, and detects mismatches automatically
4. View the mismatch table, first-divergence marker, and AI-generated debug report
5. To test with synthetic logs, run the generator first (see below)

---

## Synthetic Log Generation

Since real simulation logs are proprietary, TraceLens includes a synthetic log generator that models a realistic protocol:

**Protocol states:** `RESET → CONFIG → IDLE → TX_ACTIVE / RX_ACTIVE → ERROR`

**Transaction types:** `READ, WRITE, FRAME_TX, FRAME_RX, INTERRUPT`

**Injected bug types:**
- Wrong register value (data mismatch)
- Missing interrupt (missing transaction)
- Delayed transaction (timing mismatch)
- Wrong state transition (state mismatch)
- Extra frame emitted by model (extra transaction)
- Error flag mismatch after invalid frame

```bash
python synthetic/log_generator.py --num_logs 50 --output_dir data/synthetic/
```

This generates 50 RTL/TLM log pairs with ground-truth mismatch labels for evaluation.

---

## Mismatch Categories

| Category | Example |
|---|---|
| Data mismatch | RTL writes `0x01`, model writes `0x00` to same address |
| Timing mismatch | RTL event at `100ns`, model event at `180ns` |
| Missing transaction | RTL has txn `id=42`, model does not |
| Extra transaction | Model emits txn not present in RTL |
| State mismatch | RTL state is `ACTIVE`, model state is `IDLE` |
| Error flag mismatch | RTL raises error flag, model does not |
| Register config mismatch | Different register value after same operation |

---

## LLM Debug Summary

The LLM explanation layer receives structured mismatch context — not raw logs — and produces grounded, evidence-cited debug reports:

```
First divergence detected at transaction id=88, timestamp=240ns.

RTL transitions: IDLE → ERROR_PASSIVE
TLM model transitions: IDLE → ACTIVE

Both transitions occur immediately after an invalid frame event at 235ns.

Recommended checks:
1. Verify error-frame handling in the model state machine.
2. Confirm whether the ERROR_PASSIVE transition condition is implemented.
3. Compare register configuration at address 0x104 before transaction 88.
```

The LLM only uses evidence from the mismatch detection engine — it never infers or hallucinate details not present in the structured report.

---

## Evaluation

```bash
python evaluation/evaluate.py --data_dir data/synthetic/
```

Outputs:

| Metric | Score |
|---|---|
| Mismatch detection accuracy | 94% |
| First-divergence localization accuracy | 90% |
| Parser success rate | 100% |

Evaluated on 50 synthetic regression logs with 6 injected failure types.

---

## Restarting the Project

```bash
# 1. Start the database
docker-compose up -d db

# 2. Activate Python environment
source venv/bin/activate

# 3. Start the backend
uvicorn api:app --reload --port 8000

# 4. Start the frontend (new terminal)
cd frontend && npm run dev
```

---

## Future Improvements

- Failure clustering across multiple regression runs using embeddings
- Vector search over historical failures (pgvector + semantic similarity)
- Timeline visualization of RTL vs TLM event sequences
- Support for additional log formats (UVM, VCD, FSDB)
- Export debug report as PDF or Markdown
- Background job queue (Celery + Redis) for large log files

---

## Author

Maninderjit Bhullar
Master of Computer Science — Arizona State University
