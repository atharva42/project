from pydantic import BaseModel
from typing_extensions import TypedDict


###### Request/Response Models ######
class ExportRequest(BaseModel):
    results: list[dict]
    columns: list[str]


class ConversationRequest(BaseModel):
    session_id: str
    first_query: str
    messages: list

class QueryRequest(BaseModel):
    session_id: str
    question: str

class QueryResponse(BaseModel):
    sql_query: str
    results: list
    columns: list
    execution_time_ms: int

class RAGQueryRequest(BaseModel):
    session_id: str
    question: str

class RAGQueryResponse(BaseModel):
    answer: str
    context_chunks: list[str]
    sources: list[str]
    execution_time_ms: int


# will see later 

class ChatRequest(BaseModel):
    session_id: str
    question: str

# class SQLToolInput(BaseModel):
#     question: str
#     session_id: str

# class RAGToolInput(BaseModel):
#     question: str
#     session_id: str   looks redundant, can use ChatRequest for both tools

# LG state 

class GraphState(TypedDict):
    question: str
    session_id: str

    sql_result: dict | None
    rag_result: dict | None

    route: str
    final_answer: str