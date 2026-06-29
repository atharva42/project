from typing import TypedDict, Literal, Annotated
from langgraph.graph import StateGraph, END
# from langchain_core.messages import HumanMessage, AIMessage
from google import genai
from google.genai import types
from load_keys import load_config
from services.pipeline import run_sql_pipeline, run_rag_pipeline
import time
from datetime import datetime
from services.session_manager import log_query_entry



def get_user_friendly_error(error_str: str) -> str:
    """Convert technical error messages to user-friendly messages.
    
    Only shows errors the user can actually do something about.
    System/configuration errors are hidden.
    """
    error_lower = error_str.lower()
    
    # Network/Service errors - user can check connection or wait
    if "connection" in error_lower or "network" in error_lower or "timeout" in error_lower:
        return "Unable to connect. Please check your internet connection and try again."
    
    if "503" in error_lower or "service unavailable" in error_lower or "unavailable" in error_lower:
        return "Service is temporarily unavailable. Please try again in a few moments."
    
    # Database/Data errors - user can fix these
    if "no database uploaded" in error_lower or "no pdf" in error_lower:
        return "No data found. Please upload a CSV or PDF file first."
    
    if "session not found" in error_lower or "session expired" in error_lower:
        return "Session expired. Please upload your data again."
    
    if "sql" in error_lower and ("syntax" in error_lower or "invalid" in error_lower):
        return "I couldn't understand your question. Please try rephrasing it."
    
    if "context length" in error_lower or "token limit" in error_lower or "too long" in error_lower:
        return "Your question is too complex. Please try breaking it into smaller parts."
    
    # Generic fallback for all other errors (API key, config, auth, etc.)
    # Don't expose technical details the user can't fix
    return "I'm having trouble processing your request right now. Please try again or rephrase your question."


# Define the state schema
class AgentState(TypedDict):
    session_id: str
    question: str
    reformulated_question: str | None
    route: Literal["sql", "rag", "both_rag_first", "both_sql_first", "none"] # Updated
    sql_result: dict | None
    rag_result: dict | None
    final_answer: dict | None
    error: str | None

# Initialize LLM client
_config = load_config()
_client = genai.Client(api_key=_config.get("api_key"))


def reformulator_node(state: AgentState) -> AgentState:
    question = state["question"]
    sql_result = state.get("sql_result")
    rag_result = state.get("rag_result")
    route = state["route"]
    
    # Dynamically pick what information we are using as our factual "anchor"
    if route == "both_rag_first":
        context_data = rag_result.get("answer", "") if isinstance(rag_result, dict) else str(rag_result)
        context_source = "Document Search Insights (RAG)"
    else:
        context_data = str(sql_result)
        context_source = "Database Computation Results (SQL)"

    universal_prompt = f"""You are an advanced query reformulation assistant.
The user asked a complex conditional question: "{question}"
We ran the first phase of processing and gathered this data from the {context_source}: "{context_data}"

TASK:
1. Use the data metrics or factual insights provided to completely resolve the IF/THEN/ELSE conditional logic.
2. Rewrite the query into a single, clean, highly direct request for the next execution engine.
3. Remove all conditional syntax, numbers, or logic blocks. The next engine should only see the final command it needs to execute.
4. Just answer the question in clean & crisp way, make sure the answer is relavant, dont ask for futher details.

CRITICAL EXAMPLES:
- If route is SQL-first: "If sales are above 60k, return stakeholder names, else return manager names."
  Database Result: "[{{'total_sales': 72000}}]" (Condition met!)
  Output: "Return the names of all stakeholders."

- If route is SQL-first: "If sales are above 60k, return stakeholder names, else return manager names."
  Database Result: "[{{'total_sales': 45000}}]" (Condition failed!)
  Output: "Extract the names of all managers."

Respond with ONLY the final rewritten command:"""

    try:
        response = _client.models.generate_content(
            model=_config.get("model_name", "gemini-flash-lite-latest"),
            contents=universal_prompt,
            config={"temperature": 0.0}
        )
        state["reformulated_question"] = response.text.strip()
    except Exception:
        state["reformulated_question"] = question
        
    return state



def router_node(state: AgentState) -> AgentState:
    """Route the question to appropriate pipeline(s) based on content analysis.
    
    Analyzes the user's question and determines whether it should go to:
    - SQL: For structured data queries (counts, aggregations, filtering)
    - RAG: For document-based questions (PDFs, text search)
    - Both: When the question needs both sources
    - None: When the question is unclear or off-topic
    """
    question = state["question"]
    # session_id = state["session_id"]
    
    # Prompt for routing decision
    routing_prompt = f"""You are an advanced routing agent for a hybrid data system.
Analyze the user's question and decide the correct execution route based on data dependencies.

Available routes:
- SQL: The question only asks about structured CSV database metrics (counts, sums, averages, sorting).
- RAG: The question only asks about text contents inside uploaded PDF documents or reports.
- BOTH_RAG_FIRST: A conditional question where you must look up information in the PDF documents FIRST before you can build the database query.
  Example: "If Atharva works at Axtria, count Chinese users." (You must verify employment in the PDF first to know whether to count).
- BOTH_SQL_FIRST: A conditional question where you must calculate numbers in the database FIRST before you can extract data from the PDFs.
  Example: "If sales are above $60k, return the names of stakeholders." (You must calculate sales first to know whether to pull the names from the PDF).
- NONE: The question is casual chatter, off-topic, or unclear.

User Question: {question}

Respond with exactly one of these words: SQL, RAG, BOTH_RAG_FIRST, BOTH_SQL_FIRST, or NONE."""

    try:
        # 2. Call Gemini using strict validation configuration
        response = _client.models.generate_content(
            model=_config.get("model_name", "gemini-2.5-flash"),
            contents=routing_prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,  # Forces deterministic routing
                # These two lines force Gemini to ONLY output one of your exact route words
                response_mime_type="text/x.enum",
                response_schema=types.Schema(
                    type=types.Type.STRING,
                    enum=["SQL", "RAG", "BOTH_RAG_FIRST", "BOTH_SQL_FIRST", "NONE"]
                )
            )
        )
        
        # 3. Read the clean output and normalize it to lowercase for LangGraph matching
        route_decision = response.text.strip().lower()
        print(f"[ROUTER] Question: '{question[:50]}...' -> Detected Route: {route_decision}")
        
        # 4. Save the route AND clear out any old data fields from previous turns
        state["route"] = route_decision
        state["reformulated_question"] = None
        state["sql_result"] = None
        state["rag_result"] = None
        state["error"] = None
        
        return state
        
    except Exception as e:
        print(f"[ROUTER] Error: {e}")
        user_msg = get_user_friendly_error(str(e))
        state["route"] = "none"
        state["error"] = user_msg
        return state


def sql_node(state: AgentState) -> AgentState:
    """Execute SQL pipeline for structured data queries."""
    
    question = state.get("reformulated_question") or state["question"]
    session_id = state["session_id"]
    
    print(f"[SQL NODE] Processing question: {question[:50]}...")
    
    try:
        result = run_sql_pipeline(session_id, question)
        state["sql_result"] = result
        print(f"[SQL NODE] Success: {len(result.get('results', []))} rows returned")
    except Exception as e:
        print(f"[SQL NODE] Error: {e}")
        user_msg = get_user_friendly_error(str(e))
        state["sql_result"] = {"error": user_msg}
        state["error"] = user_msg
    
    return state


def rag_node(state: AgentState) -> AgentState:
    """Execute RAG pipeline for document-based queries."""
    question = state.get("reformulated_question") or state["question"]
    session_id = state["session_id"]
    
    print(f"[RAG NODE] Processing question: {question[:50]}...")
    
    try:
        result = run_rag_pipeline(session_id, question)
        state["rag_result"] = result
        print(f"[RAG NODE] Success: Answer generated from {len(result.get('sources', []))} sources")
    except Exception as e:
        print(f"[RAG NODE] Error: {e}")
        user_msg = get_user_friendly_error(str(e))
        state["rag_result"] = {"error": user_msg}
        state["error"] = user_msg
    
    return state


def combine_node(state: AgentState) -> AgentState:
    """Combines results from SQL and RAG dynamically based on execution flow."""
    question = state["question"]
    sql_result = state.get("sql_result")
    rag_result = state.get("rag_result")
    route = state["route"]
    
    print(f"[COMBINE NODE] Finalizing cross-source answer for route: {route}")
    
    # Check if either pipeline has an error
    sql_has_error = sql_result and "error" in sql_result
    rag_has_error = rag_result and "error" in rag_result
    
    if sql_has_error and rag_has_error:
        # Both failed
        state["final_answer"] = {
            "error": f"Both pipelines failed. SQL: {sql_result.get('error')}. RAG: {rag_result.get('error')}",
            "type": "error"
        }
        return state
    elif sql_has_error:
        # SQL failed, but RAG succeeded - return RAG result
        state["final_answer"] = {
            **rag_result,
            "type": "rag",
            "note": f"SQL pipeline failed: {sql_result.get('error')}"
        }
        return state
    elif rag_has_error:
        # RAG failed, but SQL succeeded - return SQL result
        state["final_answer"] = {
            **sql_result,
            "type": "sql",
            "note": f"RAG pipeline failed: {rag_result.get('error')}"
        }
        return state
    
    # Both succeeded - combine them
    sql_str = str(sql_result)
    rag_str = rag_result.get("answer", "") if isinstance(rag_result, dict) else str(rag_result)
    
    combined_prompt = f"""You are a master data analyst and synthesis engine. 
The user asked a multi-source question: "{question}"

We processed this request using a specialized workflow (Route: {route}). Here is the data collected:

1. SQL Database Output: {sql_str}
2. Document Search (RAG) Output: {rag_str}

TASK:
Formulate a clean, direct final answer to the user's question. 
- If the question was conditional (e.g., IF/THEN), focus heavily on delivering the final target information that was requested. 
- Do not mention inner mechanical routing details like "the SQL pipeline found" or "the RAG node returned" unless explicitly asked.
- Present the final takeaway clearly and concisely.

Final Answer:"""

    try:
        response = _client.models.generate_content(
            model=_config.get("model_name", "gemini-flash-lite-latest"),
            contents=combined_prompt,
            config={
                "max_output_tokens": 2000,
                "temperature": 0.3
            }
        )
        
        state["final_answer"] = {
            "answer": response.text.strip(),
            "sql_result": sql_result,
            "rag_result": rag_result,
            "type": "combined"
        }
        print(f"[COMBINE NODE] Clean response generated.")
        
    except Exception as e:
        print(f"[COMBINE NODE] Error: {e}")
        user_msg = get_user_friendly_error(str(e))
        state["final_answer"] = {
            "error": user_msg,
            "sql_result": sql_result,
            "rag_result": rag_result,
            "type": "error"
        }
    
    return state



def finalize_node(state: AgentState) -> AgentState:
    """Finalize the response based on the route and available results."""
    route = state["route"]
    
    # Check if there's an error in the state
    if state.get("error"):
        state["final_answer"] = {
            "error": state["error"],
            "type": "error"
        }
        return state
    
    if route == "none":
        state["final_answer"] = {
            "answer": "I couldn't understand your question or it's not related to the uploaded data. Please ask a question about your CSV data or PDF documents.",
            "type": "error"
        }
    elif route == "sql":
        # Check if SQL result has an error
        if state["sql_result"] and "error" in state["sql_result"]:
            state["final_answer"] = {
                "error": state["sql_result"]["error"],
                "type": "error"
            }
        else:
            state["final_answer"] = {
                **state["sql_result"],
                "type": "sql"
            }
    elif route == "rag":
        # Check if RAG result has an error
        if state["rag_result"] and "error" in state["rag_result"]:
            state["final_answer"] = {
                "error": state["rag_result"]["error"],
                "type": "error"
            }
        else:
            state["final_answer"] = {
                **state["rag_result"],
                "type": "rag"
            }
    # "both" route is already handled by combine_node
    return state


def should_run_sql(state: AgentState) -> bool:
    """Conditional edge: should we run SQL?"""
    return state["route"] in ["sql", "both"]


def should_run_rag(state: AgentState) -> bool:
    """Conditional edge: should we run RAG?"""
    return state["route"] in ["rag", "both"]


def should_combine(state: AgentState) -> bool:
    """Conditional edge: should we combine results?"""
    return state["route"] == "both"


def create_agent_graph():
    """Create and compile the LangGraph agent."""
    
    # Create the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("router", router_node)
    workflow.add_node("rag", rag_node)
    workflow.add_node("reformulator", reformulator_node)
    workflow.add_node("sql", sql_node)
    workflow.add_node("combine", combine_node)
    workflow.add_node("finalize", finalize_node)
    
    # Set entry point
    workflow.set_entry_point("router")
    
    # Add conditional edges from router
    workflow.add_conditional_edges(
        "router",
        lambda state: state["route"],
        {
            "sql": "sql",
            "rag": "rag",
            "both_rag_first": "rag", # Document verification first
            "both_sql_first": "sql", # Calculation metrics first
            "none": "finalize"
        }
    )
    
    workflow.add_conditional_edges(
        "rag",
        lambda state: "reformulator" if state["route"] == "both_rag_first" else ("combine" if state["route"] == "both_sql_first" else "finalize"),
        {
            "reformulator": "reformulator", # If RAG was first, go clean the query for SQL
            "combine": "combine",           # If RAG was second, we are done! Go combine
            "finalize": "finalize"
        }
    )
    
    # 3. Outbound from SQL Node
    workflow.add_conditional_edges(
        "sql",
        lambda state: "reformulator" if state["route"] == "both_sql_first" else ("combine" if state["route"] == "both_rag_first" else "finalize"),
        {
            "reformulator": "reformulator", # If SQL was first, go clean the query for RAG
            "combine": "combine",           # If SQL was second, we are done! Go combine
            "finalize": "finalize"
        }
    )
    
    # 4. Outbound from Reformulator Node (Direct Routing to the opposite node)
    workflow.add_conditional_edges(
        "reformulator",
        lambda state: "sql" if state["route"] == "both_rag_first" else "rag",
        {
            "sql": "sql",
            "rag": "rag"
        }
    )
    
    # From combine and finalize to END
    workflow.add_edge("combine", "finalize")
    workflow.add_edge("finalize", END)
    
    # Compile the graph
    return workflow.compile()


# Create the global agent instance
agent = create_agent_graph()


def run_agent(session_id: str, question: str) -> dict:
    """Run the agent for a given question.
    
    Args:
        session_id: Session ID for the user
        question: User's natural language question
        
    Returns:
        Final answer dictionary with results and route information
    """

    initial_state = {
        "session_id": session_id,
        "question": question,
        "route": "none",
        "sql_result": None,
        "rag_result": None,
        "final_answer": None,
        "error": None
    }
    
    agent_start = time.time()

    try:
        # Run the agent
        final_state = agent.invoke(initial_state)
        
        # Add route information to the final response
        final_answer = final_state["final_answer"]
        if isinstance(final_answer, dict):
            final_answer["route"] = final_state["route"]
        else:
            # Fallback if final_answer is not a dict
            final_answer = {
                "answer": str(final_answer),
                "route": final_state["route"],
                "type": "error"
            }

        # Log metrics for combined + rag routes
        latency = round(time.time() - agent_start, 2)
        route = final_state["route"]
        if route in ("both_sql_first", "both_rag_first", "both_parallel"):
            sql_r = final_state.get("sql_result") or {}
            rag_r = final_state.get("rag_result") or {}
            log_query_entry({
                "timestamp": datetime.utcnow().isoformat(),
                "session_id": session_id,
                "question": question,
                "pipeline_type": route,
                "execution_success": "error" not in final_answer,
                "sql_rows_returned": len(sql_r.get("results") or []),
                "rag_sources_found": len(rag_r.get("sources") or []),
                "latency_sec": latency
            })

        return final_answer
        
    except Exception as e:
        print(f"[AGENT] Error: {e}")
        user_msg = get_user_friendly_error(str(e))
        return {
            "answer": user_msg,
            "type": "error",
            "route": "none"
        }
