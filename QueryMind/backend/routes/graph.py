from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
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
async def agent_query(request: AgentQueryRequest):
    """Query endpoint using LangGraph agent for intelligent routing.
    
    The agent will:
    1. Analyze the question
    2. Route to SQL, RAG, or both pipelines
    3. Combine results if needed
    4. Return a comprehensive answer
    """
    try:
        result = run_agent(request.session_id, request.question)
        
        return AgentQueryResponse(
            answer=result.get("answer", result),
            type=result.get("type", "unknown"),
            sql_result=result.get("sql_result"),
            rag_result=result.get("rag_result"),
            error=result.get("error")
        )
        
    except Exception as e:
        raise HTTPException(500, f"Agent error: {str(e)}")