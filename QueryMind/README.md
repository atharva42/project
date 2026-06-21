# QueryMind — Multi-Source Agentic AI Analytics Platform

**🔗 [Live Demo](https://querymind-frontend-sx50.onrender.com)**

> ⚠️ The public demo is currently unavailable due to free-tier hosting limitations. The project remains actively maintained, and the source code is fully available in this repository.

Natural language to SQL and RAG over uploaded data. Unified LangGraph agent with dynamic routing, session persistence, and production-ready multi-modal query processing.

---
## Observability

<p align="center">
  <img src="ss/Screenshot from 2026-06-18 21-21-40.png" width="900">
  <br>
  <em>Main chat interface</em>
</p>

## What It Does

- **Natural language to SQL**: Upload CSV files, ask questions in plain English, get SQL results with zero schema knowledge required
- **Contextual document Q&A**: Upload PDFs, query semantically with RAG pipeline returning source-cited answers
- **Intelligent multi-source routing**: Single agent automatically routes queries to SQL, RAG, or both pipelines based on question semantics
- **Conditional query handling**: Processes IF/THEN questions by sequential pipeline execution with query reformulation
- **Session-based persistence**: Multi-turn conversations with data isolation, authentication, and automatic cleanup

---

## ⚠️ Disclaimer: Free-Tier Resources

This project is running on **free-tier resources**:
- **Embeddings**: Google Gemini Embedding (free tier) — limited to 3 requests per minute and 10K tokens per minute
- **LLM Calls**: Google Gemini 2.5 Flash API (free tier) — subject to quota and rate limits
- **Hosting**: Frontend and backend on free-tier cloud platforms with CPU/memory throttling

If you experience timeouts, "rate limit exceeded" errors, or degraded performance, **please try again after a few minutes**. The system will recover as the rate-limit window resets.

---

## How We Handle Complex Multi-Source Queries

When your question requires data from both CSV and PDF sources (e.g., "If Chinese employees > 3000, give me the email from the document"), QueryMind tackles this using **query decomposition**:

1. **Router** determines the order: which source provides the condition, which provides the answer
2. **First Pipeline** (SQL or RAG) executes the condition query and returns a result
3. **Reformulator** injects that result into the original question, resolving the IF/THEN logic
4. **Second Pipeline** (the opposite source) executes the refined action query with condition context
5. **Combine** node synthesizes both results into a unified answer

This two-stage approach with **query decomposition** avoids the need for complex multi-hop reasoning — the LLM sees the condition result as context, making the second step deterministic and accurate.

---

## Known Limitations & Edge Cases

- **API rate limiting**: Free tier limits to 3 embedding requests/min. Heavy usage or parallel sessions will hit rate limits.
- **Single-source misclassification**: In some occasional events the Router may misclassify multi-source questions, routing to SQL-only or RAG-only when both are needed. This may happen if the question is vague. In that case Rephrase the question to clarify which data sources should be used.
- **SQL hallucination**: Generated SQL may reference non-existent columns or use incorrect logic. Review generated SQL in the "Database Query Details" section.
---


## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        React Frontend                        │
│             (Auth Context + Session Management)              │
└──────────────────────────────┬───────────────────────────────┘
                               │ HTTP/Cookie Auth
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                       FastAPI Backend                        │
│              (CORS + Cookie Session + User Isolation)        │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                LangGraph State Machine Agent                 │
│                        (StateGraph)                          │
│                                                              │
│  ┌──────────────┐                                            │
│  │    ROUTER    │──── Analyzes question semantics            │
│  │     NODE     │                                            │
│  └──────┬───────┘                                            │
│         │                                                    │
│    ┌────┼────────────┬──────────────┬──────────────┬────┐    │
│    │    │            │              │              │    │    │
│    ▼    ▼            ▼              ▼              ▼    │    │
│  ┌────┐┌────┐   ┌──────────┐   ┌──────────┐   ┌────┐    │    │
│  │SQL ││RAG │   │both_rag  │   │both_sql  │   │none│    │    │
│  │NODE││NODE│   │_first    │   │_first    │   │    │    │    │
│  └─┬──┘└─┬──┘   └────┬─────┘   └────┬─────┘   └─┬──┘    │    │
│    │     │           │              │           │       │    │
│    └─────┼───────────┼──────────────┼───────────┘       │    │
│          │           ▼              │                   │    │
│          │    ┌──────────────┐      │                   │    │
│          │    │ REFORMULATOR │      │                   │    │
│          │    │     NODE     │      │                   │    │
│          │    └──────┬───────┘      │                   │    │
│          │           │              │                   │    │
│          │           ▼              │                   │    │
│          │    ┌──────────────┐      │                   │    │
│          └───►│   COMBINE    │◄─────┘                   │    │
│               │     NODE     │                          │    │
│               └──────┬───────┘                          │    │
│                      │                                  │    │
│                      ▼                                  ▼    │
│               ┌──────────────┐                   ┌───────────┐
│               │   FINALIZE   │◄──────────────────│   none    │
│               │     NODE     │                   └───────────┘
│               └──────┬───────┘                               │
└──────────────────────┼───────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │              │              │
        ▼              ▼              ▼
┌──────────────┐┌──────────────┐┌──────────────┐
│    SQLite    ││   ChromaDB   ││   Sessions   │
│   (CSV→DB)   ││  (PDF→Vec)   ││ (Users+DB)   │
└──────────────┘└──────────────┘└──────────────┘
       │               │               │
       ▼               ▼               ▼
  Per-session     Per-session     Shared SQLite
  db.sqlite       chroma/         sessions.db
                  embeddings
```

**Pipeline Flow:**
- **`none`** → **FINALIZE** (direct path, returns error message for unrecognized questions)
- **`sql`** → **FINALIZE** (direct path, returns SQL result)
- **`rag`** → **FINALIZE** (direct path, returns RAG answer)
- **`both_parallel`**: parallel → combine → **FINALIZE** (both SQL and RAG execute independently on same question, results merged)
- **`both_rag_first`**: rag → reformulator → sql → combine → **FINALIZE** (RAG evaluates condition first, SQL retrieves final answer)
- **`both_sql_first`**: sql → reformulator → rag → combine → **FINALIZE** (SQL evaluates condition first, RAG retrieves final answer)
- **Reformulator** resolves conditional logic (IF/THEN) by injecting first pipeline's results into query rewrite
- **Combine** synthesizes results from both pipelines into unified answer

---

## Tech Stack

**Agent & Orchestration**
- LangGraph — StateGraph with typed state and conditional edges for stateful agent workflow
- LangSmith — optional observability and tracing (auto-instruments all LangGraph nodes)

**LLM**
- Google Gemini Flash (direct API via `google-genai` SDK, no LangChain wrapper)
- Supports both `gemini-2.5-flash` and `gemini-flash-lite-latest` (currently using lite due to 2.5 Flash hard API limits on free tier)

**Backend**
- FastAPI, Python 3.x, Pydantic validation, Uvicorn ASGI server

**Data & Storage**
- SQLite — session-isolated databases for CSV→table storage
- ChromaDB — persistent vector store for PDF embeddings and table description semantic search (per-session isolation)
- Google Gemini Embedding (`gemini-embedding-001`) — embedding generation for both PDF chunks and table descriptions
- sqlglot — SQL parsing and validation

**Frontend**
- React 18, JavaScript, Vite, TailwindCSS, React Router, Axios

**Security**
- HTTPOnly secure cookies, bcrypt password hashing, session invalidation, CORS middleware, SQL injection prevention (parameterized queries + validation)

---

## Key Engineering Decisions

**1. Custom pipelines over LangChain abstractions**  
Built SQL and RAG pipelines directly using source libraries (ChromaDB, Sentence Transformers, Gemini API) instead of LangChain wrappers. LangGraph used purely for agent orchestration (StateGraph, conditional routing). Result: full control over pipeline behavior, no black-box abstractions, easier debugging, faster execution without middleware overhead.

**2. Dynamic routing with conditional query decomposition**  
Router node uses Gemini with structured output validation (enum schema enforcement) to classify queries into 5 routes. Multi-source routes (`both_rag_first`/`both_sql_first`) use **query decomposition**: the router splits the original question into a CONDITION (the IF part) and an ACTION (the THEN part), annotating which source each belongs to. The CONDITION executes first; its result is injected into the original question and passed to a reformulator node, which rewrites it into a clean ACTION query for the second pipeline. This two-stage execution with context injection enables complex conditional logic (e.g., "If sales > 60k, return stakeholder names from PDFs") without multi-hop reasoning—the LLM sees the condition result as deterministic context.

**3. Semantic table search with dual-level embeddings**  
CSV tables get LLM-generated descriptions embedded in separate ChromaDB collection (`table_embeddings.py`). Query generation uses semantic search to find top-N relevant tables before generating SQL, reducing context size and improving accuracy for multi-table databases.

**4. Session-based isolation with per-session file storage**  
Each session gets isolated directory (`./sessions/{session_id}/`) containing SQLite DB, ChromaDB vector store, and schema JSON. Sessions link to authenticated users via foreign key. Background cleanup task removes expired sessions (30+ days). Enables multi-user data isolation without complex permission systems.

**5. SQL validation and self-repair pipeline**  
Generated SQL passes through 3-stage validation: safety check (SELECT-only), schema validation (table/column existence), execution. Failures trigger LLM-based repair with schema context. Prevents system table access, multi-statement injection, and gracefully handles schema mismatches.

---

## Repository Structure

```
QueryMind/
├── backend/                 # FastAPI server with LangGraph agent
│   ├── services/           # Core AI pipelines (SQL, RAG, routing logic)
│   ├── routes/             # REST API endpoints
│   ├── file_handler/       # CSV & PDF processing
│   ├── dependencies/       # Auth middleware
│   └── validations/        # SQL safety & repair
├── frontend/               # React chat interface
│   └── src/
│       ├── components/     # Reusable UI components
│       ├── context/        # Auth & session state
│       └── pages/          # Login, register screens
└── README.md
```

---

## Local Setup

**Environment Variables** (create `.env` in `backend/`):
```bash
GOOGLE_API_KEY=your_gemini_api_key
MODEL_NAME=gemini-flash-lite-latest
ENVIRONMENT=development  # or production

# LangSmith Tracing (optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key
LANGCHAIN_PROJECT=QueryMind
```

**Backend**:
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend**:
```bash
cd frontend
npm install
npm run dev
```

---
