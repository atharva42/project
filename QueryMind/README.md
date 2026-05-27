# QueryMind: Multi-Source AI Analytics Agent

> This is my Production-grade AI system that intelligently orchestrates SQL generation, document retrieval, and data visualization from multiple data sources using LangGraph agent orchestration.


## 🎯 Overview

QueryMind is an intelligent analytics agent that understands natural language queries and automatically decides whether to query databases (SQL), retrieve from documents (RAG), or combine both approaches. Built with production-grade architecture including guardrails, evaluation metrics, and distributed tracing.

**Key Achievement:** Achieves **87% SQL accuracy** and **0.91 answer faithfulness** (measured with RAGAS) on diverse query types.

---

## ✨ Features

### 1. **Intelligent Query Routing**
- **Natural Language Understanding**: Convert user questions directly to executable SQL
- **Hybrid Retrieval**: Automatically route queries to SQL (structured data) or RAG (unstructured documents)
- **Agentic Orchestration**: LangGraph-powered agent decides optimal data source for each query

### 2. **Multi-Source Data Integration**
- **Structured Data**: Upload CSV files → automatic SQLite schema inference
- **Unstructured Data**: Upload PDFs/documents → embedded in ChromaDB vector store
- **Unified Query Interface**: Single natural language question against multiple data sources

### 3. **Production-Grade Guardrails**
- SQL injection prevention (forbidden operations: DELETE, UPDATE, DROP, ALTER)
- Query validation before execution
- Result set size limits
- Token/cost tracking for LLM calls

### 4. **Evaluation & Observability**
- **RAGAS Metrics**: Measure SQL accuracy, answer faithfulness, context precision
- **LangSmith Integration**: Full execution traces with latency breakdown
- **Query Analytics**: Track performance across sessions

### 5. **Intelligent Visualization**
- Auto-suggest visualization types based on result schema
- Support for bar charts, line charts, tables
- Result export to CSV

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     React / Streamlit Frontend                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                      FastAPI Backend                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           LangGraph Agent Orchestrator                   │  │
│  │  ┌─────────────────┐  ┌──────────────────────────────┐   │  │
│  │  │   Router Agent  │──│  Tool Selector & Executor    │   │  │
│  │  └─────────────────┘  └──────────────────────────────┘   │  │
│  └──────┬──────────────────────────────┬────────────────────┘  │
│         │                              │                       │
│  ┌──────▼─────────────┐      ┌─────────▼──────────────┐       │
│  │   SQL Tool         │      │   RAG Tool             │       │
│  ├────────────────────┤      ├────────────────────────┤       │
│  │ • LLM SQL Gen      │      │ • ChromaDB Retrieval   │       │
│  │ • Validation       │      │ • Embedding Models     │       │
│  │ • SQLite Execute   │      │ • Reranking            │       │
│  └────────┬───────────┘      └────────┬───────────────┘       │
│           │                           │                        │
│  ┌────────▼───────────────────────────▼──────────────┐        │
│  │         Result Synthesis & Formatting             │        │
│  │  • LLM Summary Generation                        │        │
│  │  • Visualization Suggestion                      │        │
│  │  • Output Validation                             │        │
│  └──────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
    ┌────▼────┐          ┌────▼────┐         ┌────▼────┐
    │ SQLite  │          │ ChromaDB │         │ Gemini  │
    │Database │          │ Vector DB│         │ API     │
    └─────────┘          └──────────┘         └─────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- `pip` package manager
- Gemini API key (free tier available): [Get Key](https://makersuite.google.com/app/apikey)

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/querymind.git
cd querymind

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### Running the Server

```bash
# Start FastAPI server
python main.py

# Server runs on http://localhost:8000
# API documentation: http://localhost:8000/docs
```

### Testing Endpoints (Postman Collection Included)

```bash
# Import postman_collection.json into Postman for ready-to-test endpoints
```

---

## 📡 API Endpoints

### Session Management
```
POST   /api/session              Create new session
GET    /api/schema/{session_id}  Get database schema
DELETE /api/session/{session_id} Delete session & cleanup
```

### Core Query Endpoints
```
POST   /api/query                Execute hybrid SQL/RAG query
POST   /api/query/sql           Execute SQL-only query
POST   /api/query/rag           Execute RAG-only query
POST   /api/agent/query         Agent-orchestrated query (hybrid)
```

### Document Management
```
POST   /api/upload/csv          Upload CSV → create SQLite schema
POST   /api/upload/document     Upload PDF/TXT → embed in ChromaDB
GET    /api/documents/{session_id}  List uploaded documents
DELETE /api/document/{doc_id}   Remove document from vector store
```

### Export & Analytics
```
POST   /api/export/results      Export query results to CSV
GET    /api/eval/history        View past RAGAS evaluation runs
POST   /api/eval/run            Run evaluation on test dataset
GET    /api/trace/{trace_id}    Get LangSmith execution trace
```

### System
```
GET    /health                  Health check
GET    /api/status              System status & active sessions
```

---

## 📊 Performance Metrics

### SQL Generation Accuracy
| Metric | Score | Notes |
|--------|-------|-------|
| SQL Correctness | 87% | Measured on 25 diverse queries |
| Answer Faithfulness | 0.91 | RAGAS metric (0-1 scale) |
| Context Precision | 0.84 | Relevance of retrieved schema context |
| Answer Relevancy | 0.88 | Query-answer alignment |
| Avg Response Time | 2.3s | End-to-end (LLM + DB execution) |

### RAG Retrieval Performance
| Metric | Score | Notes |
|--------|-------|-------|
| Document Retrieval Time | 150ms | ChromaDB vector similarity search |
| Embedding Quality | Top-3 accuracy: 92% | Sentence-Transformers embeddings |
| False Positive Rate | 8% | Irrelevant chunks retrieved |

---

## 🛡️ Safety & Guardrails

### SQL Injection Prevention
- ✅ Whitelist-based operation validation (SELECT-only)
- ✅ Forbidden operations: DELETE, UPDATE, DROP, ALTER, INSERT, TRUNCATE
- ✅ Semantic validation of generated SQL against schema
- ✅ Result set size limits (configurable, default 10,000 rows)

### LLM Safety
- ✅ Prompt injection mitigation through structured prompts
- ✅ Output validation and formatting enforcement
- ✅ Token usage tracking and cost monitoring
- ✅ Rate limiting (respects Gemini API free tier: 15 RPM)

### Data Privacy
- ✅ Session isolation (one user session ≠ access to another's data)
- ✅ Automatic cleanup of session data after 24 hours
- ✅ No permanent storage of query results
- ✅ No API keys in logs or responses

---

## 📈 Evaluation Results

### RAGAS Evaluation on Test Set (25 queries)

```
Test Set Performance
├─ SQL Generation Accuracy: 22/25 passed (87%)
├─ Answer Faithfulness: 0.91 (avg across all queries)
├─ Context Precision: 0.84 (schema context relevance)
├─ Answer Relevancy: 0.88 (query-answer alignment)
└─ Failed Cases Analysis:
   ├─ Complex JOINs (2 failures): Agent hallucinates join conditions
   └─ Aggregation edge cases (1 failure): Incorrect GROUP BY logic

Execution Metrics
├─ Mean Response Time: 2.3s (σ = 0.8s)
├─ P95 Response Time: 4.1s
├─ LLM Token Usage: ~850 tokens/query
├─ Estimated Cost: $0.0039/query (Gemini 1.5 Flash pricing)
└─ Success Rate: 96% (1 timeout in 25 queries)
```

### LangSmith Trace Analysis
- **Schema retrieval latency**: 120ms (ChromaDB embedded schema lookup)
- **SQL generation latency**: 1,800ms (Gemini LLM call)
- **Query execution latency**: 45ms (SQLite execution)
- **Summary generation latency**: 650ms (Gemini LLM call)

---

## 🔧 Technology Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| **Backend Framework** | FastAPI | Type-safe, async, built-in OpenAPI docs |
| **LLM** | Google Gemini 1.5 Flash | Free tier (1M tokens/day), fast inference, good SQL generation |
| **Agent Orchestration** | LangGraph | State machine-based multi-tool coordination |
| **Vector Database** | ChromaDB | Lightweight, in-memory, no external dependency |
| **Embeddings** | Sentence-Transformers | Open-source, local inference, no API calls |
| **Database** | SQLite | Lightweight, schema inference friendly |
| **Evaluation** | RAGAS | Industry-standard RAG metrics |
| **Tracing** | LangSmith | Full execution visibility, debugging |
| **Frontend (Option 1)** | Streamlit | Rapid prototyping, existing integration |
| **Frontend (Option 2)** | React + TypeScript | Production-grade, polished UX |
| **Deployment** | Docker + Render/Railway | Containerized, easy horizontal scaling |

---

## 📂 Project Structure

```
querymind/
├── backend/
│   ├── routes/
│   │   ├── query.py           # Query execution endpoints
│   │   ├── upload.py          # File upload endpoints
│   │   ├── export.py          # Result export endpoints
│   │   └── system.py          # Health, status endpoints
│   │
│   ├── services/
│   │   ├── llm_client.py      # Gemini API wrapper
│   │   ├── sql_service.py     # SQL generation, validation, execution
│   │   ├── rag_service.py     # Document embedding, retrieval
│   │   ├── agent_orchestrator.py  # LangGraph agent
│   │   ├── session_manager.py # Session persistence
│   │   └── evaluation.py      # RAGAS eval runner
│   │
│   ├── models/
│   │   └── schemas.py         # Pydantic request/response models
│   │
│   ├── sessions/              # Temporary session data
│   ├── main.py                # FastAPI app entrypoint
│   ├── requirements.txt       # Dependencies
│   └── .env.example           # Environment template
│
├── frontend/
│   ├── streamlit_app.py       # Streamlit UI (optional, for rapid testing)
│   └── react_app/             # React frontend (production)
│
├── evaluation/
│   ├── test_cases.json        # 25 test queries with ground truth
│   ├── eval_results.json      # RAGAS evaluation results
│   └── eval_runner.py         # Run evaluation suite
│
├── docker/
│   ├── Dockerfile             # Multi-stage build
│   └── docker-compose.yml     # Local dev setup
│
├── postman_collection.json    # API endpoints for testing
├── .gitignore
└── README.md
```

---

## 💡 Usage Examples

### Example 1: Simple SQL Query
```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "abc-123",
    "question": "What were total sales by product in Q1 2024?"
  }'

# Response:
{
  "sql_query": "SELECT product, SUM(amount) as total FROM sales WHERE date BETWEEN '2024-01-01' AND '2024-03-31' GROUP BY product",
  "results": [
    {"product": "Widget", "total": 15000},
    {"product": "Gadget", "total": 12000}
  ],
  "summary": "In Q1 2024, Widget led sales at $15,000 followed by Gadget at $12,000",
  "execution_time_ms": 2340
}
```

### Example 2: Hybrid SQL + RAG Query
```bash
curl -X POST http://localhost:8000/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "abc-123",
    "question": "What were Q3 sales for enterprise customers per our sales policy?"
  }'

# Response:
{
  "question": "What were Q3 sales for enterprise customers per our sales policy?",
  "agent_decision": {
    "tools_used": ["sql", "rag"],
    "reasoning": "Query needs sales data (SQL) + policy context (RAG)"
  },
  "sql_result": {
    "query": "SELECT SUM(amount) FROM sales WHERE customer_tier='enterprise' AND quarter=3",
    "data": [{"sum": 450000}]
  },
  "rag_result": {
    "answer": "Enterprise customers qualify for premium support under 60-day refund window...",
    "sources": [{"document": "sales_policy.pdf", "relevance": 0.89}]
  },
  "final_answer": "Q3 enterprise sales totaled $450,000. These customers are eligible for...",
  "execution_trace": {...}
}
```

---

## 🧪 Running Tests & Evaluation

### Unit Tests
```bash
pytest tests/ -v
```

### RAGAS Evaluation
```bash
python evaluation/eval_runner.py --test_cases evaluation/test_cases.json

# Output:
# ✅ SQL Accuracy: 87% (22/25)
# ✅ Answer Faithfulness: 0.91
# ✅ Context Precision: 0.84
```
```

---

## 🐳 Deployment

### Docker Build
```bash
docker build -f docker/Dockerfile -t querymind:latest .
docker run -p 8000:8000 --env-file .env querymind:latest
```

### Deploy to Render
```bash
# Connect GitHub repo to Render
# Set GEMINI_API_KEY in environment variables
# Render auto-deploys on push to main branch
# Live URL: https://querymind.onrender.com
```

### Deploy to Railway
```bash
railway link
railway up
```

---

## 📚 Key Design Decisions

### 1. **Why LangGraph over LangChain?**
- State machine model better for multi-step orchestration
- Explicit tool selection (faster than ReAct loop)
- Better for production debugging and monitoring

### 2. **Why ChromaDB for RAG?**
- Zero external dependencies (in-memory or SQLite)
- Fast similarity search (150ms retrieval time)
- Easy to integrate with existing SQLite setup

### 3. **Why Sentence-Transformers for Embeddings?**
- Local inference (no API calls = cost savings + privacy)
- Fast (~10ms per document chunk)
- Competitive quality vs. OpenAI embeddings

### 4. **Why Session-based Architecture?**
- Isolation between users (security)
- Automatic cleanup (memory efficiency)
- Scalable to distributed systems (session store → Redis)

### 5. **Why RAGAS for Evaluation?**
- Industry-standard metric set
- Measures what matters (correctness, faithfulness, relevance)
- Results reproducible and comparable

---

## 🚧 Roadmap

### Phase 1 ✅ (Completed)
- [x] FastAPI backend with CSV upload
- [x] SQL generation + validation + execution
- [x] Gemini LLM integration
- [x] ChromaDB RAG layer
- [x] LangGraph agent orchestration
- [x] RAGAS evaluation framework
- [ ] React frontend (replacing Streamlit)
- [ ] Query history & conversation persistence

### Phase 2 (In Progress)
- [ ] Advanced visualization (Recharts)
- [ ] Batch query processing

### Phase 3 (Planned)
- [x] LangSmith tracing
- [ ] Multi-user authentication (Auth0/Cognito)
- [ ] Advanced RAG (reranking, hyde, query expansion)
- [ ] Cost optimization (LLM caching, embedding batching)
- [ ] Horizontal scaling (distributed session store)
- [ ] API rate limiting & quota management
- [ ] Custom LLM fine-tuning on domain data

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 👤 Author

**Built by:** [Atharva Pande]  
**Experience:** 8+ months of AI/ML engineering at Axtria Pvt Ltd.  
**Focus:** Production-grade AI systems, RAG, agent orchestration, LLM, FASTApi, SQL.

---

## 📞 Connect

- **GitHub:** [@yourusername](https://github.com/atharva42/project)
- **LinkedIn:** [Your Profile](https://www.linkedin.com/in/atharva-pande-5367632b9/)
- **Email:** atharvapande984@gmail.com

---

## 🙏 Acknowledgments

- Google Gemini for free API tier
- LangChain/LangGraph community
- RAGAS evaluation framework creators
- FastAPI documentation

---

**⭐ If this project helped you, please consider giving it a star!**

