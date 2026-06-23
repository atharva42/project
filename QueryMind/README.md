# QueryMind

A full-stack AI agent platform built solo to solve a core problem in multi-hop RAG: **resolving complex user queries that require querying both structured data (CSV/SQLite) and unstructured files (PDFs/ChromaDB) in a guaranteed execution sequence without model hallucinations.**

[🔗Live Demo](https://querymind-frontend-sx50.onrender.com)

> Demo runs on free-tier infrastructure (rate-limited embeddings, throttled CPU/RAM). If it times out, that's the hosting tier — see [Known Limitations](#known-limitations--why-the-demo-might-misbehave).

<p align="center">
  <img src="ss/Screenshot from 2026-06-18 21-21-40.png" width="850">
</p>

<p align="center">
  <img src="ss/Screenshot from 2026-06-21 13-16-29.png" width="850">
</p>

---

## Why I Built This

Most Text-to-SQL or RAG side projects pick one lane and stop there. I wanted to find out what actually breaks when a question needs *both* — e.g. **"If Q3 sales exceeded $60K, pull the stakeholder names from the contract."** That needs a database lookup and a PDF lookup, in a specific order, with the first answer feeding the second.

The naive approach — handing both sources to one LLM call and asking it to reason across them — fails in a specific way: the model guesses whether sales exceeded $60K instead of actually checking. I wanted to fix that properly instead of prompt-engineering around it, so the core of this project is a routing layer that **resolves the condition against real data first**, then acts on it.

---

## How It Works

A single [LangGraph](https://langchain-ai.github.io/langgraph/) agent classifies every incoming question into one of five routes:

- **`sql`** — only needs structured data → straight to the SQL pipeline
- **`rag`** — only needs document content → straight to the RAG pipeline
- **`both_parallel`** — needs both, but they're independent → run concurrently, merge
- **`both_sql_first`** — a SQL result determines what to look up in the PDF
- **`both_rag_first`** — a PDF fact determines what to query in SQL

The **reformulator** node is what makes the conditional routes actually work: it takes the first pipeline's real result and rewrites the original question into a clean, unconditional instruction for the second pipeline. The second model call never sees "if X then Y" — it sees the resolved instruction, because the condition was already checked against real data, not guessed.

Route direction is decided by **where the condition lives**, not where the final answer comes from — so "if sales > 60K, get names from the PDF" and "if the PDF says sales were strong, get the profit from the table" both go through the same mechanism, just mirrored.

The router is fed live context (table structures and column descriptions dynamically retrieved via vector search instead of matching keywords), so it's reasoning about what's actually in each source.

```
                         ┌─────────────┐
                         │   ROUTER    │  (context-aware, schema + doc summaries)
                         └──────┬──────┘
              ┌────────┬────────┼────────┬────────┐
              ▼        ▼        ▼        ▼        ▼
            sql      rag   both_sql   both_rag  parallel
              │        │    _first    _first       │
              │        │       │         │      ┌───┴────┐
              │        │       ▼         ▼      │  sql   │
              │        │  ┌─────────┐┌─────────┐ │  rag   │
              │        │  │REFORMULATE│REFORMULATE│ (concurrent)
              │        │  └────┬────┘└────┬────┘ └───┬────┘
              │        │       ▼         ▼          │
              │        │     [rag]    [sql]          │
              └────┬───┴───────┴─────────┴───────────┘
                   ▼
              ┌─────────┐
              │ COMBINE │  → synthesizes final answer
              └─────────┘
```

---

## What I Actually Measured

No fabricated accuracy scores here — what I instrumented and logged while building this:

- **SQL-only route**: ~1.7s end-to-end (generation + validation + execution)
- **RAG-only route**: ~2.3s end-to-end (retrieval + generation)
- **Combined routes** (`both_*`, running both pipelines + reformulation + combine): 4–7s — the added latency is the cost of running two pipelines sequentially/concurrently and synthesizing one answer, and it's the main thing I'd optimize next if this went further (caching, parallelizing what's safe to parallelize).
- **Token usage per query**, logged per session, as a foundation for cost tracking.
- **SQL self-repair trigger rate** — how often generated SQL fails validation/execution and gets auto-corrected vs. fails outright.

These came from per-stage timing instrumentation (DB connect, schema load, semantic table search, LLM call, validation, execution, repair) added specifically to find the bottleneck — which turned out to be SQL generation; switching to a faster Gemini Flash variant cut that stage roughly 3x.

A proper RAGAS evaluation (faithfulness, context precision, answer relevancy) on a labeled test set is the next thing I want to add — see [Roadmap](#roadmap).

---

## Key Engineering Decisions

**No LangChain abstraction layer.** SQL and RAG pipelines call ChromaDB and the Gemini SDK directly — LangGraph is used purely for orchestration (`StateGraph`, conditional edges, typed state), not as a wrapper around every LLM call. Fewer layers between me and the actual API response, easier to debug, no hidden prompt templates.

**Query decomposition over single-shot multi-hop reasoning.** Instead of trusting one LLM call to juggle two data sources and a conditional, the condition is resolved against real data first, then injected back into the question. The second model call is deterministic, not a guess.

**Semantic table selection.** To handle dynamic multi-table CSV uploads without bloating the LLM context window, table schemas and column descriptions are embedded into ChromaDB alongside the PDF content. The system runs a semantic pre-search against these schemas before generating SQL, injecting only the relevant table definitions into the prompt—completely bypassing this step for simple single-table sessions to save latency.

**Structured output enforcement on routing.** The router uses Gemini's enum-constrained schema (`response_mime_type="text/x.enum"`) so the route decision is always one of five valid values — no parsing free-text output and hoping it matches.

**Three-stage SQL safety.** Every generated query passes safety check (SELECT-only) → schema validation (do these tables/columns exist) → execution, with LLM-based self-repair on schema mismatches and syntax errors. Multi-statement injection and system-table access are blocked syntactically, not repaired.

**Session isolation without a permissions system.** Each session gets its own directory (`SQLite` + `ChromaDB` + schema JSON), tied to an authenticated user. A background job expires sessions after 30 days. Good enough for multi-user isolation without building real RBAC.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Agent orchestration | LangGraph (StateGraph, typed state, conditional routing) |
| Observability | LangSmith (auto-traces every node) |
| LLM | Gemini Flash, direct via `google-genai` SDK |
| Embeddings | Gemini `embedding-001` (PDF chunks + table descriptions) |
| Backend | FastAPI, Pydantic, Uvicorn |
| Structured store | SQLite (Per-session isolation; dynamically parses and stores CSV datasets into relational tables) |
| Vector store | ChromaDB (Per-session isolation; stores chunked PDF document vectors *and* embeds SQL table/column brief descriptions for semantic schema discovery) |
| SQL parsing | sqlglot |
| Frontend | React 18, Vite, TailwindCSS, Axios |
| Auth | HTTPOnly cookies, bcrypt, CORS, parameterized queries |

---

## Known Limitations & Why the Demo Might Misbehave

Documenting these because hitting one of them shouldn't read as a bug in the code:

- **Embedding rate limits (3 req/min, free tier)** — heavy use or concurrent sessions will trigger 429s. The system recovers once the window resets; it's not a crash.
- **Occasional router misclassification** — vague multi-source questions can get routed to a single pipeline when they needed both. Rephrasing to make the data dependency explicit fixes it. This is a known model-reasoning edge case, not a routing bug.
- **SQL hallucination on ambiguous schemas** — generated SQL can occasionally reference a column that doesn't exist. Caught by the validation stage most of the time; visible in the "Database Query Details" panel when it isn't.
- **Free-tier hosting** — both frontend and backend can cold-start or throttle under load.

---

## Repository Structure

```
QueryMind/
├── backend/
│   ├── services/        # SQL pipeline, RAG pipeline, LangGraph routing logic
│   ├── routes/          # REST endpoints
│   ├── file_handler/    # CSV & PDF ingestion
│   ├── dependencies/    # Auth middleware
│   └── validations/     # SQL safety & self-repair
├── frontend/
│   └── src/
│       ├── components/
│       ├── context/      # Auth & session state
│       └── pages/
└── README.md
```

---

## Setup (for reviewing the code)

```bash
# backend
cd backend
pip install -r requirements.txt
# .env needs: GOOGLE_API_KEY, MODEL_NAME=gemini-flash-lite-latest, ENVIRONMENT=development
uvicorn main:app --reload --port 8000

# frontend
cd frontend
npm install
npm run dev
```

Optional LangSmith tracing: set `LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT` in the backend `.env`.

---

## Roadmap

What I'd build next if I kept going:

- [ ] RAGAS evaluation suite (faithfulness, context precision, answer relevancy) on a labeled test set
- [ ] Redis caching for repeated embedding/query lookups
- [ ] Swap free-tier embeddings for a model with no per-minute cap
- [ ] Cost-per-query dashboard (token logging is already in place, just needs a UI)

---

Built solo, end to end — backend, agent logic, and frontend. Happy to walk through any part of the design, especially the routing/reformulation logic, in more depth.