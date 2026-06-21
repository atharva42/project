from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END
from langsmith import traceable
# from langchain_core.messages import HumanMessage, AIMessage
from google import genai
from google.genai import types
from load_keys import load_config
from services.pipeline import run_sql_pipeline, run_rag_pipeline
from services.session_manager import session_manager


def get_user_friendly_error(error_str: str) -> str:
    """Convert technical error messages to user-friendly messages.
    
    Only shows errors the user can actually do something about.
    System/configuration errors are hidden.
    """
    error_lower = error_str.lower()
    
    # Voyage embedding free-tier rate/token limit (no payment method added).
    # Surfaces as a 500 mentioning payment method / billing / RPM / TPM limits.
    if ("payment method" in error_lower or "billing" in error_lower
            or "rpm" in error_lower or "tpm" in error_lower
            or "rate limit" in error_lower or "429" in error_lower):
        return ("This project is running on the free tier, and the voyage-3 embedding "
                "model has a token/request limit. Please try again after some time.")
    
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
    route: Literal["sql", "rag", "both_rag_first", "both_sql_first", "both_parallel", "none"]
    condition_query: str | None   # Step-1 sub-question (the condition to evaluate)
    action_query: str | None      # Step-2 action (what to do based on the condition)
    sql_result: dict | None
    rag_result: dict | None
    final_answer: dict | None
    error: str | None

# Initialize LLM client
_config = load_config()
_client = genai.Client(api_key=_config.get("api_key"))


def _clean_sql_payload(sql_result: dict) -> str:
    """Extract only the meaningful data from a sql_result dict for LLM consumption.
    
    Strips timing metadata, execution stats, etc. — leaving just the column
    names and row data in a readable format. This avoids polluting the
    reformulator and combine prompts with noise the LLM has to ignore.
    """
    if not isinstance(sql_result, dict) or "error" in sql_result:
        return str(sql_result)

    columns = sql_result.get("tables_used") or []
    rows = sql_result.get("results") or []

    if not rows:
        return f"Query returned no rows. Columns: {columns}"

    # Format as a compact text table: header + up to 50 rows
    lines = [", ".join(str(c) for c in columns)]
    for row in rows[:50]:
        lines.append(", ".join(str(v) for v in row))
    if len(rows) > 50:
        lines.append(f"... ({len(rows) - 50} more rows)")

    return "\n".join(lines)


def reformulator_node(state: AgentState) -> AgentState:
    question = state["question"]
    # The action_query (decomposed by the router) is the step-2 task. Fall back
    # to the full question if decomposition wasn't available.
    action_query = state.get("action_query") or question
    sql_result = state.get("sql_result")
    rag_result = state.get("rag_result")
    route = state["route"]
    
    # Extract clean, noise-free payload for the LLM context.
    # RAG answer is already a plain string; SQL result needs stripping of
    # timing/metadata fields that pollute the prompt and confuse the LLM.
    if route == "both_rag_first":
        context_data = rag_result.get("answer", "") if isinstance(rag_result, dict) else str(rag_result)
        context_source = "Document Search Insights (RAG)"
    else:
        context_data = _clean_sql_payload(sql_result)
        context_source = "Database Computation Results (SQL)"

    universal_prompt = f"""You are a query reformulation assistant in a two-step pipeline.

The user's original question was: "{question}"

STEP 1 has completed. We evaluated the condition using {context_source} and got:
"{context_data}"

The remaining STEP 2 action to perform is: "{action_query}"

TASK:
1. Use the step-1 result to resolve the IF/THEN/ELSE condition (decide which branch applies).
2. Rewrite the STEP 2 action into a single, clean, direct COMMAND for the next execution engine.
3. Remove all conditional syntax, numbers, or logic blocks. The next engine should only see the final command it needs to execute.

IMPORTANT: Your output must be a REWRITTEN QUERY/COMMAND for the next engine — NOT an answer to the
user's question. Do not answer the question yourself. Only produce the instruction the next engine
should run.

CRITICAL EXAMPLES:
- SQL-first: "If sales are above 60k, return stakeholder names, else return manager names."
  Database Result: "total_sales\\n72000" (Condition met!)
  Output: "Return the names of all stakeholders."

- SQL-first: "If sales are above 60k, return stakeholder names, else return manager names."
  Database Result: "total_sales\\n45000" (Condition failed!)
  Output: "Extract the names of all managers."

- RAG-first: "Read the sales report; if sales were strong, give me the profit figures, else give me the loss figures."
  Document Insight: "The report states Q4 sales grew 20% and exceeded targets." (Condition met!)
  Output: "Return the profit figures."

- RAG-first: "Read the sales report; if sales were strong, give me the profit figures, else give me the loss figures."
  Document Insight: "The report states Q4 sales declined and missed targets." (Condition failed!)
  Output: "Return the loss figures."

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
    session_id = state["session_id"]

    # Fetch session once — used for both the fast path and context building.
    try:
        session = session_manager.get_session(session_id)
        has_sql = bool(session.get("db_path"))
        has_rag = bool(session.get("chroma_path"))
    except Exception:
        session = {}
        has_sql = has_rag = False

    # ── Fast path ──────────────────────────────────────────────────────────
    # Single-modality sessions have a deterministic route — no LLM needed.
    # CSV-only → sql, PDF-only → rag.
    # BOTH_* routes are only possible when both sources exist, so the LLM is
    # only invoked for mixed sessions.
    if has_sql != has_rag:
        forced_route = "sql" if has_sql else "rag"
        print(f"[ROUTER] Single-modality session → route={forced_route} (routing LLM skipped)")
        state["route"] = forced_route
        state["reformulated_question"] = None
        state["sql_result"] = None
        state["rag_result"] = None
        state["error"] = None
        return state

    # ── Context-aware LLM routing (both sources present) ───────
    # Build a schema/summary context block so the router can reason about
    # WHAT is actually in each source — not just question phrasing.

    context_lines = []

    # CSV context: table names + columns + LLM-generated description
    csv_schema = session.get("schema") or {}
    if csv_schema:
        context_lines.append("CSV Database tables:")
        for table_name, table_info in csv_schema.items():
            if isinstance(table_info, dict):
                cols = ", ".join(table_info.get("dtypes", {}).keys()) or "unknown columns"
                desc = table_info.get("description", "")
                context_lines.append(f"  • {table_name}: columns [{cols}]")
                if desc:
                    context_lines.append(f"    Description: {desc}")
            else:
                context_lines.append(f"  • {table_name}")

    # PDF context: filename + routing summary
    pdf_summaries = session.get("pdf_summaries") or {}
    pdf_files = session.get("pdf_files") or []
    if pdf_files:
        context_lines.append("PDF Documents:")
        for filename in pdf_files:
            summary = pdf_summaries.get(filename, "No summary available.")
            context_lines.append(f"  • {filename}: {summary}")

    context_block = "\n".join(context_lines) if context_lines else "No data sources available."

    routing_prompt = f"""You are a routing agent for a hybrid data system with two data sources: a CSV database (structured tables) and PDF documents (unstructured text).

WHAT EACH SOURCE ACTUALLY CONTAINS (use this to map each part of the question to a source):
{context_block}

────────────────────────────────────────
HOW TO DECIDE THE ROUTE — follow these steps in order:

STEP 1 — Identify if the question is conditional or independent:
  • CONDITIONAL: has an "if/then/else", "when", "depending on", or compares a value to decide what to retrieve.
    In a conditional question one part (the CONDITION) must be resolved before the other part (the ANSWER) is known.
  • PARALLEL (independent): asks for information from BOTH sources with no dependency between them.
    Both sources can be queried at the same time — neither result depends on the other.

STEP 2 — For conditional questions, map CONDITION and ANSWER to their sources:
  • CSV  → counts, sums, averages, numeric comparisons, filtering on columns, anything that is a table column.
  • PDF  → what a document says, narrative facts, names/text/policies/descriptions found in the documents.

STEP 3 — Pick the route:
  CONDITIONAL (one result depends on the other):
    • Condition in CSV, answer in PDF      → BOTH_SQL_FIRST   (compute in DB first, then fetch from PDF)
    • Condition in PDF, answer in CSV      → BOTH_RAG_FIRST   (verify in PDF first, then query DB)
    • Condition AND answer both in CSV     → SQL              (single source, even if phrased as if/then)
    • Condition AND answer both in PDF     → RAG              (single source, even if phrased as if/then)

  PARALLEL (results are independent):
    • Needs data from both CSV AND PDF     → BOTH_PARALLEL    (run both independently, combine answers)
    • Needs only CSV                       → SQL
    • Needs only PDF                       → RAG

  • Casual chatter / off-topic / unrelated → NONE

────────────────────────────────────────
EXAMPLES:

1. "If Chinese employee count > 3000, get the company's email from the document, else its description."
   → Conditional: condition=CSV, answer=PDF → BOTH_SQL_FIRST

2. "If total sales are above $60k, return the onboarding guidelines from the report."
   → Conditional: condition=CSV, answer=PDF → BOTH_SQL_FIRST

3. "Read the sales report; if sales were strong, give me the profit figures from the table, else loss."
   → Conditional: condition=PDF, answer=CSV → BOTH_RAG_FIRST

4. "If Atharva is listed in the resume, count how many users are from China."
   → Conditional: condition=PDF, answer=CSV → BOTH_RAG_FIRST

5. "If employee count > 1000 show the company name, else show the country."
   → Conditional: condition=CSV, answer=CSV → SQL  (NOT a BOTH route)

6. "If the report mentions a Q4 risk, summarize that risk section."
   → Conditional: condition=PDF, answer=PDF → RAG  (NOT a BOTH route)

7. "How many companies were founded after 2010, and what does the report say about hiring strategy?"
   → Parallel: CSV (count) + PDF (hiring strategy) — no dependency → BOTH_PARALLEL

8. "Give me the average salary from the database and also summarize the onboarding document."
   → Parallel: CSV (salary) + PDF (summary) — no dependency → BOTH_PARALLEL

9. "What does the report say about Q4 revenue?"  → RAG
10. "How many companies were founded after 2010?" → SQL

────────────────────────────────────────
CRITICAL RULES:
- Use BOTH_SQL_FIRST / BOTH_RAG_FIRST ONLY when the CONDITION and ANSWER come from DIFFERENT sources.
- Use BOTH_PARALLEL when both sources contribute independently (no if/then dependency).
- If both parts resolve from the SAME source, use that single source (SQL or RAG).
- The condition may appear BEFORE or AFTER the answer — identify which clause is the test.

User Question: {question}

Respond with exactly one of these words: SQL, RAG, BOTH_RAG_FIRST, BOTH_SQL_FIRST, BOTH_PARALLEL, or NONE."""

    try:
        response = _client.models.generate_content(
            model=_config.get("model_name", "gemini-2.5-flash"),
            contents=routing_prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="text/x.enum",
                response_schema=types.Schema(
                    type=types.Type.STRING,
                    enum=["SQL", "RAG", "BOTH_RAG_FIRST", "BOTH_SQL_FIRST", "BOTH_PARALLEL", "NONE"]
                )
            )
        )

        route_decision = response.text.strip().lower()

        # Guard against unexpected output — fall back to a safe route rather
        # than letting an unknown value hit the graph's edge mapping (which
        # would raise a KeyError with no matching edge).
        valid_routes = {"sql", "rag", "both_rag_first", "both_sql_first", "both_parallel", "none"}
        if route_decision not in valid_routes:
            print(f"[ROUTER] Unexpected route '{route_decision}', defaulting to 'none'")
            route_decision = "none"

        print(f"[ROUTER] Question: '{question[:50]}...' -> Detected Route: {route_decision}")

        state["route"] = route_decision
        state["reformulated_question"] = None
        state["condition_query"] = None
        state["action_query"] = None
        state["sql_result"] = None
        state["rag_result"] = None
        state["error"] = None

        # For conditional cross-source routes, decompose the question into:
        #   - condition_query: the sub-question the FIRST engine must answer
        #   - action_query:    what to do based on that result (FIRST engine's
        #                      source is given in the route; the action targets
        #                      the OTHER source)
        # Decomposition happens HERE because the router already has the full
        # data-source context loaded, so it knows which part belongs where.
        if route_decision in ("both_sql_first", "both_rag_first"):
            cond, action = _decompose_conditional(question, route_decision, context_block)
            state["condition_query"] = cond
            state["action_query"] = action
            print(f"[ROUTER] Decomposed → condition: '{cond}' | action: '{action}'")

        return state

    except Exception as e:
        print(f"[ROUTER] Error: {e}")
        user_msg = get_user_friendly_error(str(e))
        state["route"] = "none"
        state["error"] = user_msg
        return state


def _decompose_conditional(question: str, route: str, context_block: str) -> tuple[str, str]:
    """Split a conditional cross-source question into two sub-tasks.

    Returns (condition_query, action_query):
      - condition_query: a clean, single-purpose question for the FIRST engine
        to evaluate the condition (no IF/THEN, no references to the other source)
      - action_query: a description of what to retrieve/do once the condition is
        known, to be resolved by the reformulator after step 1 runs.

    For both_sql_first: condition is evaluated in the CSV database; action targets the PDF.
    For both_rag_first: condition is evaluated in the PDF; action targets the CSV database.
    """
    if route == "both_sql_first":
        first_source, second_source = "CSV database", "PDF documents"
    else:
        first_source, second_source = "PDF documents", "CSV database"

    prompt = f"""You are decomposing a conditional question into two steps for a two-stage data pipeline.

Available data sources:
{context_block}

User question: "{question}"

This is a conditional question. Step 1 evaluates a condition using the {first_source}.
Step 2 performs an action using the {second_source}, based on the step-1 result.

Break the question into exactly two parts:
1. CONDITION: a clean, standalone question for the {first_source} that retrieves ONLY the
   data needed to evaluate the condition. No IF/THEN wording. No references to the other source.
2. ACTION: a short description of what to retrieve from the {second_source} once the condition
   result is known (keep any if/else branches so the next step can pick the right branch).

Respond in EXACTLY this format (two lines):
CONDITION: <the condition question>
ACTION: <the action description>"""

    try:
        response = _client.models.generate_content(
            model=_config.get("model_name"),
            contents=prompt,
            config={"max_output_tokens": 200, "temperature": 0.0}
        )
        text = response.text.strip() if hasattr(response, "text") else ""
        condition_query, action_query = question, question
        for line in text.splitlines():
            s = line.strip()
            if s.upper().startswith("CONDITION:"):
                condition_query = s.split(":", 1)[1].strip()
            elif s.upper().startswith("ACTION:"):
                action_query = s.split(":", 1)[1].strip()
        return condition_query, action_query
    except Exception as e:
        print(f"[DECOMPOSE] Failed: {e} — falling back to original question")
        return question, question


def parallel_node(state: AgentState) -> AgentState:
    """Run SQL and RAG pipelines independently for parallel (non-conditional) queries."""
    session_id = state["session_id"]
    question = state["question"]
    print(f"[PARALLEL NODE] Running SQL + RAG independently for: {question[:80]}...")

    try:
        sql_result = run_sql_pipeline(session_id, question)
        state["sql_result"] = sql_result
        print(f"[PARALLEL NODE] SQL success: {len(sql_result.get('results', []))} rows")
    except Exception as e:
        user_msg = get_user_friendly_error(str(e))
        state["sql_result"] = {"error": user_msg}
        print(f"[PARALLEL NODE] SQL error: {e}")

    try:
        rag_result = run_rag_pipeline(session_id, question)
        state["rag_result"] = rag_result
        print(f"[PARALLEL NODE] RAG success: {len(rag_result.get('sources', []))} sources")
    except Exception as e:
        user_msg = get_user_friendly_error(str(e))
        state["rag_result"] = {"error": user_msg}
        print(f"[PARALLEL NODE] RAG error: {e}")

    return state


def sql_node(state: AgentState) -> AgentState:
    """Execute SQL pipeline for structured data queries."""
    
    route = state["route"]
    session_id = state["session_id"]

    # Pick the question for this step:
    #  - both_sql_first, step 1: use the decomposed condition_query (clean,
    #    single-purpose; no PDF references so the model won't hallucinate columns)
    #  - second step (after reformulator): use reformulated_question
    #  - plain sql: use the original question
    if route == "both_sql_first" and not state.get("reformulated_question"):
        pipeline_question = state.get("condition_query") or state["question"]
    else:
        pipeline_question = state.get("reformulated_question") or state["question"]

    print(f"[SQL NODE] Processing question: {pipeline_question[:80]}...")
    
    try:
        result = run_sql_pipeline(session_id, pipeline_question)
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
    route = state["route"]
    session_id = state["session_id"]

    # Pick the question for this step:
    #  - both_rag_first, step 1: use the decomposed condition_query
    #  - second step (after reformulator): use reformulated_question
    #  - plain rag: use the original question
    if route == "both_rag_first" and not state.get("reformulated_question"):
        pipeline_question = state.get("condition_query") or state["question"]
    else:
        pipeline_question = state.get("reformulated_question") or state["question"]

    print(f"[RAG NODE] Processing question: {pipeline_question[:80]}...")
    
    try:
        result = run_rag_pipeline(session_id, pipeline_question)
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
    
    # Both succeeded — combine them.
    # Use the clean payload helper so the combine LLM sees actual data rows,
    # not a noisy dict with timings, execution stats, etc.
    sql_str = _clean_sql_payload(sql_result)
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

CRITICAL — NO FABRICATION:
- Use ONLY the data provided above. Never invent, guess, or use placeholder text.
- NEVER output fill-in-the-blank templates like "[insert email here]", "[value]", or similar.
- If the specific information the user asked for is NOT present in the provided data,
  say so plainly and directly. For example: "I couldn't find the email address in the
  uploaded documents." Do not pretend a value exists.

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


def create_agent_graph():
    """Create and compile the LangGraph agent."""

    workflow = StateGraph(AgentState)

    workflow.add_node("router", router_node)
    workflow.add_node("rag", rag_node)
    workflow.add_node("reformulator", reformulator_node)
    workflow.add_node("sql", sql_node)
    workflow.add_node("parallel", parallel_node)
    workflow.add_node("combine", combine_node)
    workflow.add_node("finalize", finalize_node)

    workflow.set_entry_point("router")

    # Router → first node
    workflow.add_conditional_edges(
        "router",
        lambda state: state["route"],
        {
            "sql": "sql",
            "rag": "rag",
            "both_rag_first": "rag",      # Conditional: RAG evaluates condition first
            "both_sql_first": "sql",      # Conditional: SQL evaluates condition first
            "both_parallel": "parallel",  # Parallel: both engines run independently
            "none": "finalize"
        }
    )

    # Parallel node → always goes straight to combine (both results already in state)
    workflow.add_edge("parallel", "combine")

    # RAG node → next step depends on route
    workflow.add_conditional_edges(
        "rag",
        lambda state: (
            "reformulator" if state["route"] == "both_rag_first"  # RAG was first → reformulate for SQL
            else "combine"  if state["route"] == "both_sql_first" # RAG was second → merge
            else "finalize"                                        # Plain RAG → done
        ),
        {
            "reformulator": "reformulator",
            "combine": "combine",
            "finalize": "finalize"
        }
    )

    # SQL node → next step depends on route
    workflow.add_conditional_edges(
        "sql",
        lambda state: (
            "reformulator" if state["route"] == "both_sql_first"  # SQL was first → reformulate for RAG
            else "combine"  if state["route"] == "both_rag_first" # SQL was second → merge
            else "finalize"                                        # Plain SQL → done
        ),
        {
            "reformulator": "reformulator",
            "combine": "combine",
            "finalize": "finalize"
        }
    )

    # Reformulator → the opposite engine
    workflow.add_conditional_edges(
        "reformulator",
        lambda state: "sql" if state["route"] == "both_rag_first" else "rag",
        {
            "sql": "sql",
            "rag": "rag"
        }
    )

    workflow.add_edge("combine", "finalize")
    workflow.add_edge("finalize", END)

    return workflow.compile()


# Create the global agent instance
agent = create_agent_graph()


@traceable(name="QueryMind Agent")
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
        "reformulated_question": None,
        "condition_query": None,
        "action_query": None,
        "sql_result": None,
        "rag_result": None,
        "final_answer": None,
        "error": None
    }
    
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
        
        return final_answer
        
    except Exception as e:
        print(f"[AGENT] Error: {e}")
        user_msg = get_user_friendly_error(str(e))
        return {
            "answer": user_msg,
            "type": "error",
            "route": "none"
        }
