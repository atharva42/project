# QueryMind Architecture & Code Flow Analysis

## 🏗️ System Overview

QueryMind is a **hybrid data query system** that intelligently routes questions to either SQL databases or PDF documents (via RAG), or both. It uses LangGraph for orchestration, Gemini for NLP tasks, and ChromaDB for document retrieval.

---

## 📊 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                          │
│                  (localhost:3000 or 5173)                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP/REST Requests
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              BACKEND (FastAPI) - main.py                         │
│  - CORS middleware for frontend                                  │
│  - Routes included: auth, upload, query, graph                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
   ┌────────────┐    ┌──────────┐    ┌──────────────┐
   │Auth Routes │    │Upload    │    │Query Routes  │
   │            │    │Routes    │    │(Chat Handler)│
   │- Register  │    │          │    │              │
   │- Login     │    │- CSV     │    │- /chat       │
   │- Logout    │    │- PDF     │    │- /session    │
   │- Status    │    │          │    │- /schema     │
   └────────────┘    └──────────┘    └──────┬───────┘
                                             │
                                             ▼
                                    ┌─────────────────┐
                                    │  LangGraph Agent│
                                    │ (langgraph_     │
                                    │  agent.py)      │
                                    │                 │
                                    │ Routes question │
                                    │ to SQL/RAG/Both │
                                    └────────┬────────┘
                                             │
        ┌────────────────────────────────────┼────────────────────────────────┐
        │                                    │                                │
        ▼                                    ▼                                ▼
   ┌──────────────┐                    ┌──────────────┐            ┌──────────────┐
   │SQL Pipeline  │                    │RAG Pipeline  │            │Combined Flow │
   │              │                    │              │            │              │
   │1. Generate   │                    │1. Query      │            │1. Run SQL    │
   │   SQL Query  │                    │   ChromaDB   │            │2. Reformulate│
   │2. Validate   │                    │2. Generate   │            │3. Run RAG    │
   │3. Execute    │                    │   Answer     │            │4. Combine    │
   │4. Return     │                    │              │            │5. Finalize   │
   │   Results    │                    │              │            │              │
   └──────────────┘                    └──────────────┘            └──────────────┘
        │                                    │
        ▼                                    ▼
   ┌──────────────┐                    ┌──────────────┐
   │SQLite DB     │                    │ChromaDB      │
   │(session_     │                    │(vector DB)   │
   │  db.sqlite)  │                    │              │
   └──────────────┘                    └──────────────┘
```

---

## 🔐 Authentication Flow

### 1. **User Registration** (`auth_endpoints.py` → `/auth/register`)

```
POST /auth/register
{
  "username": "user@example.com",
  "password": "password123"
}
          ↓
  Create user in SQLite (users table)
  - Hash password with bcrypt
  - Assign unique user_id
  - Store in sessions.db
          ↓
  Return { message, user_id }
```

### 2. **User Login** (`auth_endpoints.py` → `/auth/login`)

```
POST /auth/login
{
  "username": "user@example.com",
  "password": "password123"
}
          ↓
  Lookup user by username
  Verify password hash with bcrypt
          ↓
  Create new session
  - session_manager.create_session(user_id=user_id)
  - Store in sessions.db
  - Set HTTP-only cookie: session_id
          ↓
  Return { message, session_id, user_id }
```

### 3. **Session Verification** (`API_endpoints.py` → `check_auth_status()`)

```
Every request checks:
  session_id = request.cookies.get("session_id")
  session = session_manager.get_session(session_id)
  user_id = session.get("user_id")
  
If valid:
  - Fetch user by user_id
  - Return { authenticated: True, user: {...} }
Else:
  - Return { authenticated: False, user: None }
  - Return HTTP 401
```

---

## 📁 Session & File Management

### 1. **Session Creation** (`API_endpoints.py` → `POST /session`)

```
Request: POST /session
Auth required: Yes
          ↓
  session_manager.create_session(user_id=authenticated_user_id)
  - Generate UUID for session_id
  - Create record in sessions table with user_id
  - Create directory: ./sessions/{session_id}/
          ↓
  Return { session_id }
```

### 2. **File Upload - CSV** (`uploadAPI_endpoints.py`)

```
POST /upload/csv
{
  "file": <CSV file>,
  "session_id": "uuid-xxx"
}
          ↓
  Verify session belongs to authenticated user
  Create SQL handler: SQL(uploaded_files=[file], session_id=session_id)
          ↓
  SQL Handler:
    1. Read CSV → pandas DataFrame
    2. Auto-detect and convert dates
    3. Create SQLite table
    4. Generate table description via Gemini (semantic understanding)
    5. Store schema in ./sessions/{session_id}/schema.json
    6. Create embeddings for semantic table search
          ↓
  Update session in DB:
    - db_path = ./sessions/{session_id}/db.sqlite
    - schema = {...}
          ↓
  Return { message, schema }
```

### 3. **File Upload - PDF** (`uploadAPI_endpoints.py`)

```
POST /upload/pdf
{
  "file": <PDF file>,
  "session_id": "uuid-xxx"
}
          ↓
  Verify session belongs to authenticated user
  PDFHandler().process(file)
          ↓
  PDFHandler:
    1. Extract text from PDF
    2. Split into chunks
    3. Create embeddings for each chunk
    4. Store in ChromaDB
    5. Save chroma_path to session
          ↓
  Update session in DB:
    - chroma_path = path to ChromaDB
    - pdf_files = [filename]
          ↓
  Return { message, files: [filename] }
```

---

## 🧠 LangGraph Agent Flow

The agent uses LangGraph for state management and conditional routing. It's defined in `langgraph_agent.py`.

### **Agent State Structure**

```python
class AgentState(TypedDict):
    session_id: str                # Session ID
    question: str                  # Original user question
    reformulated_question: str     # Question reformulated after first pipeline
    route: str                     # SQL | RAG | BOTH_RAG_FIRST | BOTH_SQL_FIRST | NONE
    sql_result: dict              # Results from SQL pipeline
    rag_result: dict              # Results from RAG pipeline
    final_answer: dict            # Final response to return
    error: str                    # Error message if any
```

### **Node Descriptions**

#### **1. Router Node** (`router_node`)

**Purpose**: Analyze question and determine which pipeline(s) to use.

**Logic**:
- Uses Gemini with enum response schema for deterministic routing
- Categories:
  - **SQL**: Pure structured data query (counts, aggregations, filtering)
  - **RAG**: Pure document/text query
  - **BOTH_RAG_FIRST**: Conditional where PDF data is needed first
  - **BOTH_SQL_FIRST**: Conditional where database results determine next action
  - **NONE**: Off-topic or unclear

**Code**:
```python
# Routes question using Gemini's enum response schema
routing_prompt = f"""Available routes:
- SQL: Structured database queries
- RAG: Document text queries
- BOTH_RAG_FIRST: Check PDF first, then query DB
- BOTH_SQL_FIRST: Query DB first, then check PDF
- NONE: Off-topic

User Question: {question}
Respond with exactly one word: ..."""

response = _client.models.generate_content(
    model=_config.get("model_name"),
    config=types.GenerateContentConfig(
        temperature=0.0,
        response_mime_type="text/x.enum",
        response_schema=types.Schema(
            type=types.Type.STRING,
            enum=["SQL", "RAG", "BOTH_RAG_FIRST", "BOTH_SQL_FIRST", "NONE"]
        )
    )
)
state["route"] = response.text.strip().lower()
```

---

#### **2. SQL Node** (`sql_node`)

**Purpose**: Execute SQL pipeline for database queries.

**Code Flow**:
```
1. Get reformulated_question or use original
2. Call run_sql_pipeline(session_id, question)
   
   Inside run_sql_pipeline:
   a. Get session and verify DB exists
   b. Load schema registry from schema.json
   c. Generate SQL query (see SQL Generation below)
   d. Validate SQL against schema
   e. Repair if needed
   f. Execute query
   g. Log results
   
3. Store result in state["sql_result"]
```

---

#### **3. RAG Node** (`rag_node`)

**Purpose**: Execute RAG pipeline for document queries.

**Code Flow**:
```
1. Get reformulated_question or use original
2. Call run_rag_pipeline(session_id, question)
   
   Inside run_rag_pipeline:
   a. Get session and verify PDFs uploaded
   b. Query ChromaDB for relevant chunks (n_results=5)
   c. Generate answer using Gemini + context chunks
   d. Extract sources
   
3. Store result in state["rag_result"]
```

---

#### **4. Reformulator Node** (`reformulator_node`)

**Purpose**: When running BOTH routes, reformulate question after first pipeline.

**Example**:
```
Original: "If sales are above $60k, return stakeholder names"

1. Route = BOTH_SQL_FIRST
2. SQL Pipeline runs → returns: total_sales = $75k (condition TRUE)
3. Reformulator changes question to:
   "Return the names of all stakeholders"
4. This clean question goes to RAG pipeline
```

---

#### **5. Combine Node** (`combine_node`)

**Purpose**: Merge SQL + RAG results into cohesive answer.

**Logic**:
- Check if either pipeline had errors
- If both succeed: prompt Gemini to synthesize both results
- Return combined answer

---

#### **6. Finalize Node** (`finalize_node`)

**Purpose**: Return appropriate response based on route.

- **SQL route**: Return SQL results directly
- **RAG route**: Return RAG answer directly
- **BOTH route**: Already handled by combine node
- **NONE route**: Return "I don't understand" message

---

### **Graph Structure & Edges**

```
START
  │
  ▼
┌─────────┐
│ router  │  ← Analyzes question, sets route
└────┬────┘
     │
     ├─→ "sql" ─────────┐
     │                   ▼
     │                ┌────────┐
     │                │ sql    │──┐
     │                └────────┘  │
     │                            ├─→ "both_rag_first" ─┐
     │                            │                     │
     ├─→ "rag" ─────────┐        │                     ▼
     │                  ▼        │                ┌──────────────┐
     │               ┌────────┐  │                │ reformulator │
     │               │ rag    │──┤                └──────┬───────┘
     │               └────────┘  │                       │
     │                           │◄──────────────────────┘
     │                           │
     │                           ├─→ "both_sql_first" ──┐
     │                           │                       │
     ├─→ "both_*" ──────────────┤                       ▼
     │                           │                  ┌────────┐
     │                           └─→ "none" ────────→│finalize│
     │                                               └────────┘
     │                                                   │
     │                                                   ▼
     └───────────────────────────────────────────────→ END
```

---

## 🔍 SQL Query Generation Flow

### **Source**: `sql_service.py` → `generate_sql_query()`

```
Input: user_question, session_id

1. Semantic Table Search (if session_id provided):
   a. Load SQL handler
   b. Find relevant tables using embeddings
   c. Limit to top N tables (default: 3)
   d. Build "focused schema" with only relevant tables
   
2. Build LLM Prompt:
   - System message with schema info
   - Instructions (SELECT only, handle nulls, use aliases, etc.)
   - User question
   
3. Call Gemini:
   - Model: gemini-2.5-flash (or configured model)
   - Temperature: 0.1 (low randomness)
   - Max tokens: 2500
   
4. Clean output (remove ANSI escape codes)

5. Return SQL query string
```

### **Schema Validation**: `pipeline.py` → `run_sql_pipeline()`

```
Generated SQL
     ↓
validate_sql(sql_query, schema_registry)
     ↓
Is Valid?
├─ YES → Execute query
└─ NO → Check if repairable
        ├─ YES (syntax/schema errors) → repair_sql()
        └─ NO (dangerous operations) → Reject with error
```

---

## 📚 RAG (Retrieval-Augmented Generation) Flow

### **Source**: `rag_service.py` → `generate_rag_answer()`

```
Input: question, context_chunks

1. Format context:
   context = "[Chunk 1]\n{chunk1}\n\n[Chunk 2]\n{chunk2}..."
   
2. Build prompt:
   - Provide all context chunks
   - User question
   - Instructions to cite chunks
   
3. Call Gemini:
   - Temperature: 0.5 (balanced)
   - Max tokens: 2000
   
4. Return generated answer with citations
```

---

## 📋 Complete Chat Flow Example

### **Scenario**: "If sales > $60k, who are our stakeholders?"

```
1. User sends request:
   POST /chat
   {
     "session_id": "uuid-123",
     "question": "If sales > $60k, who are our stakeholders?"
   }
   
2. Authentication:
   - Verify session_id cookie
   - Verify session belongs to user
   
3. Entry to Agent (run_agent):
   - Create initial state
   - Set route to "none"
   
4. Router Node:
   - Question is conditional
   - Needs to check DB first, then documents
   - Route = "both_sql_first"
   
5. SQL Node:
   - Generate: "SELECT SUM(sales) as total_sales FROM orders"
   - Validate & Execute
   - Result: total_sales = $75,000
   
6. Reformulator Node:
   - Original: "If sales > $60k, who are our stakeholders?"
   - With result: "Condition TRUE (sales=$75k)"
   - Reformulated: "List all stakeholders"
   
7. RAG Node:
   - Query ChromaDB with: "List all stakeholders"
   - Get chunks from PDF documents
   - Generate answer with references
   
8. Combine Node:
   - Merge SQL insight (sales = $75k) with RAG answer
   - Create unified response
   
9. Finalize Node:
   - Package final response
   
10. Return to Frontend:
    {
      "answer": "Based on our records...",
      "sql_result": {...},
      "rag_result": {...},
      "type": "combined"
    }
```

---

## 💾 Data Persistence

### **Session Storage**: `sessions.db`

```sql
-- users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT
);

-- sessions table
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER,
    db_path TEXT,              -- Path to session's SQLite DB
    schema TEXT,               -- JSON schema info
    chroma_path TEXT,          -- Path to ChromaDB
    pdf_files TEXT,            -- JSON list of uploaded PDFs
    created_at TEXT,
    last_accessed TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- token_usage table
CREATE TABLE token_usage (
    session_id TEXT,
    query_id TEXT,
    tokens_question INTEGER,
    tokens_response INTEGER,
    timestamp TEXT
);

-- conversations table
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    first_query TEXT,
    timestamp TEXT,
    messages TEXT,             -- JSON list
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
```

### **Session Directory Structure**

```
./sessions/
├── sessions.db                 ← Main metadata DB
├── {session_uuid}/
│   ├── db.sqlite              ← SQLite with CSV data
│   ├── schema.json            ← Table schemas & descriptions
│   ├── session.log            ← Session activity log
│   └── chroma/                ← ChromaDB (if PDFs uploaded)
│       ├── data.parquet
│       ├── index.bin
│       └── ...
```

---

## 🔄 Request/Response Flow Diagram

```
┌─────────────────────────────────┐
│   Frontend (React)              │
│   - User asks question          │
│   - Session ID from login       │
└──────────────┬──────────────────┘
               │ POST /chat
               │ { session_id, question }
               ▼
┌──────────────────────────────────┐
│  FastAPI Backend - /chat route   │
│  - Verify auth via session cookie│
│  - Extract question              │
└──────────────┬──────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│  run_agent(session_id, question) │
│  (langgraph_agent.py)            │
└──────────────┬──────────────────┘
               │
      ┌────────┴────────┐
      │                 │
      ▼                 ▼
  [Router]         [State Setup]
      │
  Route=both_sql_first
      │
      ▼
 ┌─────────┐
 │ SQL Node│
 └────┬────┘
      │
      ▼
 ┌──────────────────────┐
 │ run_sql_pipeline()   │
 │ - Generate SQL       │
 │ - Validate          │
 │ - Execute           │
 │ - Return results    │
 └────┬─────────────────┘
      │
      ▼
 ┌─────────────────┐
 │ Reformulator    │  (Clean question for RAG)
 └────┬────────────┘
      │
      ▼
 ┌─────────┐
 │ RAG Node│
 └────┬────┘
      │
      ▼
 ┌──────────────────────┐
 │ run_rag_pipeline()   │
 │ - Query ChromaDB     │
 │ - Generate answer    │
 │ - Return result      │
 └────┬─────────────────┘
      │
      ▼
 ┌────────────┐
 │ Combine    │  (Synthesize SQL + RAG)
 └────┬───────┘
      │
      ▼
 ┌────────────┐
 │ Finalize   │  (Prepare response)
 └────┬───────┘
      │
      ▼
 Return final_answer dict
      │
      ▼
┌──────────────────────────────────┐
│  API Response to Frontend        │
│  {                               │
│    "answer": "...",              │
│    "sql_result": {...},          │
│    "rag_result": {...},          │
│    "type": "combined"            │
│  }                               │
└──────────────────────────────────┘
```

---

## 🛠️ Key Technologies Used

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Backend Server | FastAPI | REST API framework |
| Database | SQLite | Session data + uploaded CSVs |
| Vector DB | ChromaDB | PDF embeddings for RAG |
| LLM | Gemini 2.5 Flash | Query generation, routing, answering |
| Agent Orchestration | LangGraph | State management, conditional routing |
| Auth | bcrypt | Password hashing |
| Frontend | React | User interface |

---

## 📊 Error Handling

### **At Each Stage**:

1. **Router**: Validation errors → Route to "none"
2. **SQL**: Query generation → Repair attempts → Fallback to error message
3. **RAG**: No documents found → Error message
4. **Combine**: Either pipeline fails → Return successful result + note
5. **Final**: All errors caught → Return error response

---

## 🔑 Key Features

✅ **Hybrid Querying**: SQL + Documents + Conditional reasoning
✅ **Semantic Search**: AI-powered table selection for SQL queries
✅ **RAG Integration**: Document retrieval with ChromaDB
✅ **User Isolation**: Each user has separate sessions
✅ **Query Logging**: Full audit trail of all queries
✅ **Error Recovery**: Automatic SQL repair and fallbacks
✅ **Authentication**: Secure user registration/login with bcrypt
✅ **Conversation History**: Store and retrieve chat history

---

## 📝 Summary

QueryMind works by:
1. **Authenticating** the user
2. **Routing** the question intelligently to SQL, RAG, or both
3. **Executing** the appropriate pipeline(s)
4. **Combining** results if needed
5. **Returning** a unified answer to the frontend

The LangGraph orchestration ensures each question takes the most efficient path through the system.
