# routes/query.py
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from models.pydantic_schema import (
    ConversationRequest,
    ChatRequest,
)
from services.session_manager import session_manager
from services.health_service import get_full_health_status
# Import the agent runner without causing a circular import.
# ``chat_graph`` was previously imported from ``main`` which also imports this
# module, leading to the circular import error. The actual agent execution
# function lives in ``services.langgraph_agent`` as ``run_agent``. We alias it
# to ``chat_graph`` to keep the existing variable name used in the endpoint.
from services.langgraph_agent import run_agent as chat_graph


###### All instances are created here ######
router = APIRouter()


# <----------------Endpoints are defined below ---------------->

@router.post("/session")
async def create_session(request: Request):
    """Create a new session and return its ID.

    The front‑end should call this endpoint when a user starts a new
    interaction (e.g., after uploading a CSV).  The returned ``session_id``
    is then used in subsequent requests to ``/query`` and ``/schema``.
    
    Requires authentication - session will be linked to the authenticated user.
    """
    # Authenticate user
    auth_status = check_auth_status(request)
    if not auth_status["authenticated"]:
        raise HTTPException(401, "Not authenticated")
    
    # Create session linked to this user
    user_id = auth_status["user"]["id"]
    session_id = session_manager.create_session(user_id=user_id)
    return {"session_id": session_id}


@router.get("/schema/{session_id}")
async def get_schema(request: Request, session_id: str):
    """Return the schema and/or loaded files for a given session.

    CSV sessions return schema information, PDF sessions return uploaded file
    names, and mixed sessions return both.
    """
    # Check auth status and verify session ownership
    auth_status = check_auth_status(request)
    if not auth_status["authenticated"]:
        raise HTTPException(401, "Not authenticated")
    
    session = session_manager.get_session(session_id)
    
    # Verify session belongs to this user
    if session.get("user_id") and session.get("user_id") != auth_status["user"]["id"]:
        raise HTTPException(403, "Access denied: Session belongs to another user")
    
    response = {}
    if session.get("schema"):
        response["schema"] = session["schema"]
    if session.get("pdf_files"):
        response["files"] = session["pdf_files"]
    elif session.get("chroma_path"):
        response["files"] = []
    if not response:
        raise HTTPException(404, "Schema not found for this session")
    response["file_type"] = (
        "csv" if response.get("schema") and not response.get("files")
        else "pdf" if response.get("files") and not response.get("schema")
        else "csv & pdf"
    )
    return response

@router.post("/chat")
async def chat(request: Request, chat_request: ChatRequest):
    """Handle chat requests from the frontend.

    The original implementation incorrectly used ``ConversationRequest`` which
    expects ``first_query`` and ``messages`` fields, causing a 422 validation
    error when the frontend sent only ``session_id`` and ``question``. We now
    accept the lightweight ``ChatRequest`` model that matches the frontend
    payload.
    """
    # Check auth status and verify session ownership
    auth_status = check_auth_status(request)
    if not auth_status["authenticated"]:
        raise HTTPException(401, "Not authenticated")
    
    # Verify session belongs to this user
    try:
        session = session_manager.get_session(chat_request.session_id)
        if session.get("user_id") and session.get("user_id") != auth_status["user"]["id"]:
            raise HTTPException(403, "Access denied: Session belongs to another user")
    except ValueError:
        raise HTTPException(404, "Session not found")
    
    # ``chat_graph`` is the ``run_agent`` function which returns the final answer dict.
    print("I entered the chat endpoint with request")
    result = chat_graph(chat_request.session_id, chat_request.question)
    print("I exited successfully!")

    # The agent returns the final_answer dict directly - return it without extra nesting
    # This ensures SQL results have sql_query, results, columns at top level
    # RAG results have answer, context_chunks, sources at top level
    # Combined results have answer, sql_result, rag_result at top level
    return result

# @router.post("/query", response_model=QueryResponse)
# async def query(request: QueryRequest):
#     """Execute a natural language question and return SQL results.
    
#     Takes a user's natural language question and the associated session ID,
#     generates SQL using Gemini API, validates it, executes against the session's
#     database, and returns results with execution time. Logs token usage for the session.
    
#     Args:
#         request: QueryRequest with session_id and question.
    
#     Returns:
#         QueryResponse with sql_query, results, columns, summary, and execution_time_ms.
    
#     Raises:
#         HTTPException: If session not found, no database uploaded, or SQL validation fails.
#     """
#     result = run_sql_pipeline(request.session_id, request.question)
#     return QueryResponse(**result)


# @router.post("/query/rag", response_model=RAGQueryResponse)
# async def query_rag(request: RAGQueryRequest):
#     """Execute a RAG query against PDF documents.
    
#     Takes a user's question and retrieves relevant context from PDF documents,
#     then generates an answer using Gemini.
    
#     Args:
#         request: RAGQueryRequest with session_id and question.
    
#     Returns:
#         RAGQueryResponse with answer, context_chunks, sources, and execution_time_ms.
    
#     Raises:
#         HTTPException: If session not found or no PDFs uploaded.
#     """
#     result = run_rag_pipeline(request.session_id, request.question)
#     return RAGQueryResponse(**result)


@router.get("/usage_tokens")
async def usage_tokens(request: Request, session_id: str):
    """Return token usage statistics for a given session."""
    # Check auth status and verify session ownership
    auth_status = check_auth_status(request)
    if not auth_status["authenticated"]:
        raise HTTPException(401, "Not authenticated")
    
    # Verify session belongs to this user
    try:
        session = session_manager.get_session(session_id)
        if session.get("user_id") and session.get("user_id") != auth_status["user"]["id"]:
            raise HTTPException(403, "Access denied: Session belongs to another user")
    except ValueError:
        raise HTTPException(404, "Session not found")
    
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
# @router.post("/export/results")
# async def export_results(request: ExportRequest):
#     """Export query results to a CSV file.
    
#     Accepts results and column names from the frontend (avoiding a duplicate DB query),
#     writes them to a CSV file, and returns the file for download.
    
#     Args:
#         request: ExportRequest with results (list of dicts) and columns (list of str).
    
#     Returns:
#         FileResponse: CSV file containing the query results.
#     """
#     import csv, os, uuid
#     from fastapi.responses import FileResponse
    
#     file_path = f"backend/sessions/export_{uuid.uuid4().hex}.csv"
    
#     with open(file_path, "w", newline="") as f:
#         writer = csv.DictWriter(f, fieldnames=request.columns)
#         writer.writeheader()
#         writer.writerows(request.results)
    
#     return FileResponse(file_path, filename="results.csv", media_type="text/csv")


# Helper function to check auth status
def check_auth_status(request: Request):
    """Check if user is authenticated."""
    print("COOKIES:", request.cookies)

    session_id = request.cookies.get("session_id")
    print("AUTH SESSION:", session_id)
    
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
    """Get conversations for a session or all conversations for the authenticated user."""
    # Check auth status
    auth_status = check_auth_status(request)
    if not auth_status["authenticated"]:
        raise HTTPException(401, "Not authenticated")
    
    user_id = auth_status["user"]["id"]
    
    if session_id:
        # Verify the session belongs to this user before returning conversations
        try:
            session = session_manager.get_session(session_id)
            if session.get("user_id") != user_id:
                raise HTTPException(403, "Access denied: Session belongs to another user")
        except ValueError:
            raise HTTPException(404, "Session not found")
        
        return session_manager.get_conversations(session_id)
    
    # Return all conversations for this user only
    return session_manager.get_user_conversations(user_id)


@router.post("/conversations/save")
async def save_conversation(request: Request, conversation: ConversationRequest):
    """Save a conversation."""
    # Check auth status
    auth_status = check_auth_status(request)
    if not auth_status["authenticated"]:
        raise HTTPException(401, "Not authenticated")
    
    # Verify session belongs to this user
    try:
        session = session_manager.get_session(conversation.session_id)
        if session.get("user_id") and session.get("user_id") != auth_status["user"]["id"]:
            raise HTTPException(403, "Access denied: Session belongs to another user")
    except ValueError:
        raise HTTPException(404, "Session not found")
    
    conv_id = f"conv_{uuid.uuid4().hex}"
    session_manager.save_conversation(
        conversation.session_id,
        conv_id,
        conversation.first_query,
        conversation.messages
    )
    return {"conv_id": conv_id}


@router.delete("/conversations/{conv_id}")
async def delete_conversation(request: Request, conv_id: str, session_id: str = None):
    """Delete conversation(s).
    
    If session_id query parameter is provided, deletes ALL conversations for that session.
    Otherwise, deletes a single conversation by conv_id (legacy behavior).
    """
    # Check auth status
    auth_status = check_auth_status(request)
    if not auth_status["authenticated"]:
        raise HTTPException(401, "Not authenticated")
    
    user_id = auth_status["user"]["id"]
    
    # If session_id is provided, delete all conversations for that session
    if session_id:
        # Verify session belongs to this user
        try:
            session = session_manager.get_session(session_id)
            if session.get("user_id") != user_id:
                raise HTTPException(403, "Access denied: Session belongs to another user")
        except ValueError:
            raise HTTPException(404, "Session not found")
        
        session_manager.delete_all_conversations(session_id)
        return {"message": f"All conversations for session {session_id} deleted successfully"}
    
    # Otherwise, delete single conversation by conv_id (legacy)
    if not conv_id.startswith("conv_"):
        raise HTTPException(400, "Invalid conversation ID")
    if not conv_id:
        raise HTTPException(400, "Invalid conversation selected")
    
    # Verify the conversation belongs to this user by checking its session
    conversations = session_manager.get_user_conversations(user_id)
    conv_belongs_to_user = any(c["id"] == conv_id for c in conversations)
    
    if not conv_belongs_to_user:
        raise HTTPException(403, "Access denied: Conversation belongs to another user")
    
    session_manager.delete_conversation(conv_id)
    return {"message": "Conversation deleted successfully"}