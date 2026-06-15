from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dependencies.auth import CurrentUser, AuthUser, verify_session_ownership
from services.langgraph_agent import run_agent

router = APIRouter()


class AgentQueryRequest(BaseModel):
    session_id: str
    question: str


class AgentQueryResponse(BaseModel):
    answer: str | dict
    type: str
    sql_result: dict | None = None
    rag_result: dict | None = None
    error: str | None = None


@router.post("/agent/query", response_model=AgentQueryResponse)
async def agent_query(agent_request: AgentQueryRequest, user: AuthUser = CurrentUser):
    """Query endpoint using LangGraph agent for intelligent routing.
    
    The agent will:
    1. Analyze the question
    2. Route to SQL, RAG, or both pipelines
    3. Combine results if needed
    4. Return a comprehensive answer
    
    Requires authentication and session ownership verification.
    """
    # Verify session ownership (reuse the returned session downstream)
    session = verify_session_ownership(agent_request.session_id, user)
    
    # Execute agent query
    try:
        result = run_agent(agent_request.session_id, agent_request.question, session=session)
        
        return AgentQueryResponse(
            answer=result.get("answer", result),
            type=result.get("type", "unknown"),
            sql_result=result.get("sql_result"),
            rag_result=result.get("rag_result"),
            error=result.get("error")
        )
        
    except Exception as e:
        raise HTTPException(500, f"Agent error: {str(e)}")