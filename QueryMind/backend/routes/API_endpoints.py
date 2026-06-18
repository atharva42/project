# routes/query.py
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException
from dependencies.auth import CurrentUser, AuthUser, verify_session_ownership
from models.pydantic_schema import (
    ConversationRequest,
    ChatRequest,
)
from services.session_manager import session_manager
from services.health_service import get_full_health_status
from services.langgraph_agent import run_agent as chat_graph


###### All instances are created here ######
router = APIRouter()


# <----------------Endpoints are defined below ---------------->

@router.post("/session")
async def create_session(user: AuthUser = CurrentUser):
    """Create a new session and return its ID.

    The front‑end should call this endpoint when a user starts a new
    interaction (e.g., after uploading a CSV).  The returned ``session_id``
    is then used in subsequent requests to ``/query`` and ``/schema``.
    
    Requires authentication - session will be linked to the authenticated user.
    """
    session_id = session_manager.create_session(user_id=user.id)
    return {"session_id": session_id}


@router.get("/schema/{session_id}")
async def get_schema(session_id: str, user: AuthUser = CurrentUser):
    """Return the schema and/or loaded files for a given session.

    CSV sessions return schema information, PDF sessions return uploaded file
    names, and mixed sessions return both.
    """
    # Verify session ownership
    session = verify_session_ownership(session_id, user)
    
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
async def chat(chat_request: ChatRequest, user: AuthUser = CurrentUser):
    """Handle chat requests from the frontend."""
    verify_session_ownership(chat_request.session_id, user)

    result = chat_graph(chat_request.session_id, chat_request.question)

    # Inject execution_time_ms if the route didn't already set it.
    # For combined routes, sum the individual pipeline times already recorded
    # inside sql_result / rag_result — this excludes routing and LLM overhead
    # and gives the actual data-fetching latency the user should see.
    if isinstance(result, dict) and "execution_time_ms" not in result:
        sql_ms = (result.get("sql_result") or {}).get("execution_time_ms", 0) or 0
        rag_ms = (result.get("rag_result") or {}).get("execution_time_ms", 0) or 0
        if sql_ms or rag_ms:
            result["execution_time_ms"] = sql_ms + rag_ms

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
async def usage_tokens(session_id: str, user: AuthUser = CurrentUser):
    """Return token usage statistics for a given session."""
    # Verify session ownership
    verify_session_ownership(session_id, user)
    
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


@router.get("/conversations")
async def get_conversations(session_id: str = None, user: AuthUser = CurrentUser):
    """Get conversations for a session or all conversations for the authenticated user."""
    if session_id:
        # Verify the session belongs to this user before returning conversations
        verify_session_ownership(session_id, user)
        return session_manager.get_conversations(session_id)
    
    # Return all conversations for this user only
    return session_manager.get_user_conversations(user.id)


@router.post("/conversations/save")
async def save_conversation(conversation: ConversationRequest, user: AuthUser = CurrentUser):
    """Save a conversation."""
    # Verify session belongs to this user
    verify_session_ownership(conversation.session_id, user)
    
    conv_id = f"conv_{uuid.uuid4().hex}"
    session_manager.save_conversation(
        conversation.session_id,
        conv_id,
        conversation.first_query,
        conversation.messages
    )
    return {"conv_id": conv_id}


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str, session_id: str = None, user: AuthUser = CurrentUser):
    """Delete conversation(s).
    
    If session_id query parameter is provided, deletes ALL conversations for that session.
    Otherwise, deletes a single conversation by conv_id (legacy behavior).
    """
    # If session_id is provided, delete all conversations for that session
    if session_id:
        # Verify session belongs to this user
        verify_session_ownership(session_id, user)
        
        session_manager.delete_all_conversations(session_id)
        return {"message": f"All conversations for session {session_id} deleted successfully"}
    
    # Otherwise, delete single conversation by conv_id (legacy)
    if not conv_id.startswith("conv_"):
        raise HTTPException(400, "Invalid conversation ID")
    if not conv_id:
        raise HTTPException(400, "Invalid conversation selected")
    
    # Verify the conversation belongs to this user by checking its session
    conversations = session_manager.get_user_conversations(user.id)
    conv_belongs_to_user = any(c["id"] == conv_id for c in conversations)
    
    if not conv_belongs_to_user:
        raise HTTPException(403, "Access denied: Conversation belongs to another user")
    
    session_manager.delete_conversation(conv_id)
    return {"message": "Conversation deleted successfully"}