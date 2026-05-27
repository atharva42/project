# routes/query.py
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from services.sql_service import (
    generate_sql_query,
    validate_sql,
    execute_sql_query,
    generate_narrative_summary,
    # generate_visualization_code
)
from services.rag_service import generate_rag_answer
from services.session_manager import session_manager
from services.health_service import get_full_health_status
from file_handler.sql import SQL
from file_handler.pdf import PDFHandler
import time
import uuid
from datetime import datetime


###### Request/Response Models ######
class ExportRequest(BaseModel):
    results: list[dict]
    columns: list[str]

class QueryRequest(BaseModel):
    session_id: str
    question: str

class QueryResponse(BaseModel):
    sql_query: str
    results: list
    columns: list
    summary: str
    execution_time_ms: int

class RAGQueryRequest(BaseModel):
    session_id: str
    question: str

class RAGQueryResponse(BaseModel):
    answer: str
    context_chunks: list[str]
    sources: list[str]
    execution_time_ms: int

class ConversationRequest(BaseModel):
    session_id: str
    first_query: str
    messages: list


###### All instances are created here ######
router = APIRouter()


# <----------------Endpoints are defined below ---------------->

@router.post("/session")
async def create_session():
    """Create a new session and return its ID.

    The front‑end should call this endpoint when a user starts a new
    interaction (e.g., after uploading a CSV).  The returned ``session_id``
    is then used in subsequent requests to ``/query`` and ``/schema``.
    """
    session_id = session_manager.create_session()
    return {"session_id": session_id}


@router.get("/schema/{session_id}")
async def get_schema(session_id: str):
    """Return the database schema for a given session.

    The schema is stored in the session record as a JSON string.  When a CSV
    file is uploaded, the schema is extracted and persisted via
    :func:`session_manager.update_session`.  This endpoint simply retrieves
    that stored schema.
    """
    session = session_manager.get_session(session_id)
    if not session.get("schema"):
        raise HTTPException(404, "Schema not found for this session")
    return session["schema"]

@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Execute a natural language question and return SQL results.
    
    Takes a user's natural language question and the associated session ID,
    generates SQL using Gemini API, validates it, executes against the session's
    database, and returns results with execution time. Logs token usage for the session.
    
    Args:
        request: QueryRequest with session_id and question.
    
    Returns:
        QueryResponse with sql_query, results, columns, summary, and execution_time_ms.
    
    Raises:
        HTTPException: If session not found, no database uploaded, or SQL validation fails.
    """
    start = time.time()

    try:
        session = session_manager.get_session(request.session_id)

        if not session.get("db_path"):
            raise HTTPException(400, "No database uploaded for this session")

        # Reconnect to existing db file for this session
        sql_handler = SQL([], request.session_id)

        # 1. Generate SQL
        sql_query = generate_sql_query(request.question, session["schema"])

        # 2. Validate
        is_valid, errors = validate_sql(sql_query)
        if not is_valid:
            raise HTTPException(400, f"Invalid SQL: {', '.join(errors)}")

        # 3. Execute
        results, cols = execute_sql_query(sql_handler, sql_query)
        # print(results)

        # Approximate token count (word-based) — replace with Gemini count_tokens in Phase 4
        tokens_q = len(request.question.split())
        tokens_r = len(sql_query.split())
        query_id = f"{request.session_id}_{int(time.time()*1000)}"
        session_manager.log_token_usage(request.session_id, query_id, tokens_q, tokens_r)

        # 4. Generate summary
        summary = generate_narrative_summary(request.question, results)
        print(summary)

        execution_time = int((time.time() - start) * 1000)

        return QueryResponse(
            sql_query=sql_query,
            results=results,
            columns=cols,
            summary=summary,
            execution_time_ms=execution_time
        )

    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/query/rag", response_model=RAGQueryResponse)
async def query_rag(request: RAGQueryRequest):
    """Execute a RAG query against PDF documents.
    
    Takes a user's question and retrieves relevant context from PDF documents,
    then generates an answer using Gemini.
    
    Args:
        request: RAGQueryRequest with session_id and question.
    
    Returns:
        RAGQueryResponse with answer, context_chunks, sources, and execution_time_ms.
    
    Raises:
        HTTPException: If session not found or no PDFs uploaded.
    """
    start = time.time()

    try:
        session = session_manager.get_session(request.session_id)

        if not session.get("chroma_path"):
            raise HTTPException(400, "No PDF documents uploaded for this session")

        # Initialize PDF handler
        pdf_handler = PDFHandler(request.session_id)
        
        # Query ChromaDB for relevant chunks
        rag_results = pdf_handler.query(request.question, n_results=5)
        
        if not rag_results["documents"]:
            raise HTTPException(404, "No relevant content found in documents")
        
        # Generate answer using RAG
        answer = generate_rag_answer(request.question, rag_results["documents"])
        
        # Extract sources
        sources = list(set([meta["source"] for meta in rag_results["metadatas"]]))
        
        execution_time = int((time.time() - start) * 1000)

        return RAGQueryResponse(
            answer=answer,
            context_chunks=rag_results["documents"],
            sources=sources,
            execution_time_ms=execution_time
        )

    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/usage_tokens")
async def usage_tokens(session_id: str):
    """Return token usage statistics for a given session."""
    return session_manager.get_token_usage(session_id)


@router.get("/get_system_health")
async def health():
    """Comprehensive health check for all system components"""
    health_status = await get_full_health_status()
    # Use a more human‑readable timestamp (e.g., 2026-05-25 18:22:04)
    health_status["timestamp"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    
    # Return appropriate HTTP status code
    status_code = 200
    if health_status["status"] == "unhealthy":
        status_code = 503  # Service Unavailable
    elif health_status["status"] == "degraded":
        status_code = 200  # Still operational but with warnings
    
    return health_status

#implemet this after frontend
@router.post("/export/results")
async def export_results(request: ExportRequest):
    """Export query results to a CSV file.
    
    Accepts results and column names from the frontend (avoiding a duplicate DB query),
    writes them to a CSV file, and returns the file for download.
    
    Args:
        request: ExportRequest with results (list of dicts) and columns (list of str).
    
    Returns:
        FileResponse: CSV file containing the query results.
    """
    import csv, os, uuid
    from fastapi.responses import FileResponse
    
    file_path = f"backend/sessions/export_{uuid.uuid4().hex}.csv"
    
    with open(file_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=request.columns)
        writer.writeheader()
        writer.writerows(request.results)
    
    return FileResponse(file_path, filename="results.csv", media_type="text/csv")


# Helper function to check auth status
def check_auth_status(request: Request):
    """Check if user is authenticated."""
    session_id = request.cookies.get("session_id")
    
    if not session_id:
        return {"authenticated": False, "user": None}
    
    try:
        session = session_manager.get_session(session_id)
        if not session.get('user_id'):
            return {"authenticated": False, "user": None}
        
        user = session_manager.get_user_by_id(session['user_id'])
        return {
            "authenticated": True,
            "user": {"id": user['id'], "username": user['username']}
        }
    except Exception:
        return {"authenticated": False, "user": None}


@router.get("/conversations")
async def get_conversations(request: Request, session_id: str = None):
    """Get conversations for a session or all conversations."""
    # Check auth status
    auth_status = check_auth_status(request)
    if not auth_status["authenticated"]:
        raise HTTPException(401, "Not authenticated")
    
    if session_id:
        return session_manager.get_conversations(session_id)
    # Return all conversations from all sessions (filtered by user in session_manager)
    return session_manager.get_all_conversations()


@router.post("/conversations/save")
async def save_conversation(request: Request, conversation: ConversationRequest):
    """Save a conversation."""
    # Check auth status
    auth_status = check_auth_status(request)
    if not auth_status["authenticated"]:
        raise HTTPException(401, "Not authenticated")
    
    conv_id = f"conv_{uuid.uuid4().hex}"
    session_manager.save_conversation(
        conversation.session_id,
        conv_id,
        conversation.first_query,
        conversation.messages
    )
    return {"conv_id": conv_id}