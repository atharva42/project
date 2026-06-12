# QueryMind — Multi-Source Agentic AI Analytics Platform

**🔗[Live Demo](SITE WILL GO LIVE SOON.....)**

Natural language to SQL and RAG over uploaded data. Unified LangGraph agent with dynamic routing, session persistence, and production-ready multi-modal query processing.

---

## What It Does

- **Natural language to SQL**: Upload CSV files, ask questions in plain English, get SQL results with zero schema knowledge required
- **Contextual document Q&A**: Upload PDFs, query semantically with RAG pipeline returning source-cited answers
- **Intelligent multi-source routing**: Single agent automatically routes queries to SQL, RAG, or both pipelines based on question semantics
- **Conditional query handling**: Processes IF/THEN questions by sequential pipeline execution with query reformulation
- **Session-based persistence**: Multi-turn conversations with data isolation, authentication, and automatic cleanup

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
- **`both_rag_first`**: rag → reformulator → sql → combine → **FINALIZE**
- **`both_sql_first`**: sql → reformulator → rag → combine → **FINALIZE**
- **Reformulator** resolves conditional logic (IF/THEN) by injecting first pipeline's results into query rewrite

---

## Tech Stack

**Agent & Orchestration**
- LangGraph — StateGraph with typed state and conditional edges for stateful agent workflow

**LLM**
- Google Gemini 2.5 Flash (direct API via `google-genai` SDK, no LangChain wrapper)

**Backend**
- FastAPI, Python 3.x, Pydantic validation, Uvicorn ASGI server

**Data & Storage**
- SQLite — session-isolated databases for CSV→table storage
- ChromaDB — persistent vector store for PDF embeddings (per-session isolation)
- Sentence Transformers (`all-MiniLM-L6-v2`) — local embedding generation
- sqlglot — SQL parsing and validation

**Frontend**
- React 18, JavaScript, Vite, TailwindCSS, React Router, Axios

**Security**
- HTTPOnly secure cookies, bcrypt password hashing, session invalidation, CORS middleware, SQL injection prevention (parameterized queries + validation)

---

## Key Engineering Decisions

**1. Custom pipelines over LangChain abstractions**  
Built SQL and RAG pipelines directly using source libraries (ChromaDB, Sentence Transformers, Gemini API) instead of LangChain wrappers. LangGraph used purely for agent orchestration (StateGraph, conditional routing). Result: full control over pipeline behavior, no black-box abstractions, easier debugging, faster execution without middleware overhead.

**2. Dynamic routing with conditional query reformulation**  
Router node uses Gemini with structured output validation (enum schema enforcement) to classify queries into 5 routes. Multi-source routes (`both_rag_first`/`both_sql_first`) execute pipelines sequentially with a reformulator node that rewrites the original question by injecting results from the first pipeline, enabling complex conditional logic handling (e.g., "If sales > 60k, return stakeholder names from PDFs").

**3. Semantic table search with dual-level embeddings**  
CSV tables get LLM-generated descriptions embedded in separate ChromaDB collection (`table_embeddings.py`). Query generation uses semantic search to find top-N relevant tables before generating SQL, reducing context size and improving accuracy for multi-table databases.

**4. Session-based isolation with per-session file storage**  
Each session gets isolated directory (`./sessions/{session_id}/`) containing SQLite DB, ChromaDB vector store, and schema JSON. Sessions link to authenticated users via foreign key. Background cleanup task removes expired sessions (30+ days). Enables multi-user data isolation without complex permission systems.

**5. SQL validation and self-repair pipeline**  
Generated SQL passes through 3-stage validation: safety check (SELECT-only), schema validation (table/column existence), execution. Failures trigger LLM-based repair with schema context. Prevents system table access, multi-statement injection, and gracefully handles schema mismatches.

---

## Known Limitations

- Multi-source synthesis (SQL + RAG combined) can degrade on complex conditional queries with nested logic — refactoring to multi-hop ReAct agent planned for v2
- Table semantic search may fail to retrieve relevant tables if descriptions are too generic — future improvement: include sample queries in embedding text
- ChromaDB implementation is not modular — switching to Pinecone/Weaviate would require refactoring `PDFHandler` and `TableEmbeddings` classes (not just import changes)

---

## Project Structure

```
QueryMind/
├── backend/
│   ├── dependencies/        # Auth middleware (session verification)
│   ├── file_handler/        # CSV→SQLite, PDF→ChromaDB processors
│   ├── models/              # Pydantic schemas
│   ├── routes/              # FastAPI endpoints (auth, upload, query, graph)
│   ├── services/            # Core logic (pipelines, embeddings, session manager, LangGraph agent)
│   ├── validations/         # SQL validation and repair
│   ├── main.py              # FastAPI app entry point
│   └── load_keys.py         # Environment config loader
├── frontend/
│   ├── src/
│   │   ├── components/      # UploadForm
│   │   ├── context/         # AuthContext
│   │   ├── pages/           # Login, Register
│   │   ├── App.jsx          # Main chat interface
│   │   └── main.jsx         # React entry point
│   └── package.json
└── sessions/                # Runtime: per-session data (gitignored)
```

---

## Local Setup

**Environment Variables** (create `.env` in `backend/`):
```bash
GOOGLE_API_KEY=your_gemini_api_key
MODEL_NAME=gemini-2.5-flash
ENVIRONMENT=development  # or production
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
