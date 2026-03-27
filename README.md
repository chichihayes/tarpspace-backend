# TarpSpace — Phase 1 Backend

Semantic mandate matching engine. Connects people based on what they need and offer — using sentence embeddings for fast retrieval and an LLM for intelligent validation.

---

## Architecture

```
POST /match  →  [BAAI/bge-large-en-v1.5 embed]
             →  [Cosine similarity → top-K agents]
             →  [Gemini LLM validate + reason]
             →  Ranked results with scores + explanations
```

**Stack:**
- `FastAPI` — API layer
- `sentence-transformers` (BAAI/bge-large-en-v1.5) — semantic embeddings
- `numpy` — cosine similarity (in-memory, no Pinecone needed for 50-agent dataset)
- `Gemini Flash` via OpenRouter — LLM validation
- `SQLite` — agent store + match logs

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

> First run will download the `BAAI/bge-large-en-v1.5` model (~1.3GB). Cached after that.

### 2. Set your OpenRouter API key (optional but recommended)

```bash
export OPENROUTER_API_KEY=sk-or-your-key-here
```

Get a free key at [openrouter.ai](https://openrouter.ai). Without a key, you still get vector-similarity results.

---

## Running

### Option A: CLI (fastest for testing)

```bash
# Single query (vector only if no API key set)
python test_match.py "I need a React developer for a fintech project"

# With LLM validation
OPENROUTER_API_KEY=sk-or-... python test_match.py "machine learning study partner"

# Run all demo queries
python test_match.py --demo

# Raw JSON output
python test_match.py "need a co-founder for logistics startup" --json

# Adjust top-K candidates
python test_match.py "need an investor" --top-k 10
```

### Option B: API server

```bash
uvicorn api.app:app --reload --port 8000
```

Then open http://localhost:8000/docs for interactive Swagger UI.

---

## API Endpoints

### `POST /match`

Run a mandate through the full matching pipeline.

**Request:**
```json
{
  "mandate": "I need a React developer for a 3-month fintech contract",
  "top_k": 8,
  "api_key": "sk-or-..."   // optional, falls back to env var
}
```

**Response:**
```json
{
  "query": "I need a React developer...",
  "top_k_retrieved": [
    {"id": "AGT-002", "score": 0.912},
    ...
  ],
  "validated": [
    {
      "id": "AGT-002",
      "name": "Chidi Eze",
      "category": "Tech & Work",
      "mandate": "I am a frontend engineer with 4 years...",
      "match": true,
      "score": 0.92,
      "vector_score": 0.912,
      "reason": "AGT-002 is a React/TypeScript developer available for remote freelance — direct match.",
      "caveat": null
    },
    ...
  ],
  "latency_ms": 1240
}
```

### `GET /agents`

List all 50 agents. Filter by category:

```
GET /agents?category=Tech%20%26%20Work
GET /agents?category=Learning
GET /agents?category=Business%20%26%20Money
GET /agents?category=Creative
GET /agents?category=Lifestyle
```

### `GET /agents/{id}`

Get a single agent by ID (e.g. `AGT-001`).

### `GET /logs`

View recent match logs from SQLite. Add `?limit=50` for more.

### `GET /health`

Basic health check.

---

## Example Queries to Test

These are designed to hit the complementary pairs in the seed data:

| Query | Expected match |
|-------|---------------|
| "I need a React developer for fintech" | AGT-002 (Chidi Eze) |
| "Machine learning study partner, struggling with backpropagation" | AGT-022 (Chiamaka Obi) |
| "Angel investor interested in African healthtech" | AGT-036 (Obinna Nwachukwu) |
| "Looking for a co-founder for logistics startup, I do tech" | AGT-043 (Bola Adesanya) |
| "Need a Python tutor, complete beginner" | AGT-024 (Nkechi Odum) |
| "Afrobeats vocalist looking for a producer" | AGT-051 (Damilola Ogunleye) |
| "Need help with Nigerian tax and bookkeeping" | AGT-045 (Biodun Ojo) |
| "Looking for a running partner in Victoria Island" | AGT-062 (Kunle Abiodun) |

---

## Next Steps (Phase 2)

- [ ] Add Pinecone for scalable vector storage (swap `EmbeddingStore` for `PineconeStore`)
- [ ] Add real user accounts + mandate storage
- [ ] Add agent negotiation loop (LLM asks clarifying questions before connecting)
- [ ] Add `POST /agents` to register new agents dynamically
- [ ] Add match request / connection flow (accept/decline)
- [ ] Webhook or notification when a match is found
