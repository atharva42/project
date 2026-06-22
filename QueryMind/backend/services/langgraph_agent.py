from typing import TypedDict, Literal
import json
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
    condition_query: str | None      # Step-1 sub-question (gets the data to test)
    condition_predicate: str | None  # The test applied to step-1 data (true/false statement)
    then_action: str | None          # Step-2 command if condition is TRUE
    else_action: str | None          # Step-2 command if condition is FALSE (None if unspecified)
    condition_met: bool | None       # Resolved condition outcome
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


def _evaluate_condition(predicate: str, context_data: str, context_source: str) -> bool:
    """Evaluate whether a condition holds, given the step-1 evidence.

    A narrow, deterministic LLM call with structured (enum) output — it answers
    ONE thing: does the predicate hold against the evidence? The agent's control
    flow uses this boolean to pick a branch; the decision logic lives in code.
    """
    prompt = f"""Evidence gathered from {context_source}:
"{context_data}"

Based ONLY on the evidence above, does the following statement hold true?
Statement: "{predicate}"

Answer with exactly TRUE or FALSE."""
    try:
        response = _client.models.generate_content(
            model=_config.get("model_name", "gemini-flash-lite-latest"),
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="text/x.enum",
                response_schema=types.Schema(
                    type=types.Type.STRING,
                    enum=["TRUE", "FALSE"]
                )
            )
        )
        return response.text.strip().upper() == "TRUE"
    except Exception as e:
        print(f"[CONDITION EVAL] Failed: {e} — assuming TRUE to attempt the action")
        return True


def _build_conclusion(question: str, condition_met: bool, context_data: str) -> str:
    """Generate a short, factual answer when no branch action applies.

    Used only after the agent has STRUCTURALLY decided to conclude (the chosen
    branch has no action). The LLM only handles wording, not the decision.
    """
    prompt = f"""The user asked: "{question}"

We evaluated the condition and it was {'TRUE' if condition_met else 'FALSE'}.
Evidence: "{context_data}"

The question specifies no action to take for this outcome. Write a short, direct answer
that states the condition result and explains that the requested action does not apply.
Use only the evidence above. Do not invent data."""
    try:
        response = _client.models.generate_content(
            model=_config.get("model_name", "gemini-flash-lite-latest"),
            contents=prompt,
            config={"temperature": 0.2, "max_output_tokens": 300}
        )
        return response.text.strip()
    except Exception:
        return ("The condition in your question was not met, and no alternative action "
                "was specified, so there is nothing further to return.")


def reformulator_node(state: AgentState) -> AgentState:
    """Resolve the conditional branch after step 1.

    All decisions here are structural, driven by the decomposed branches — not
    by prompt examples:
      1. Evaluate the condition to a boolean against step-1 evidence.
      2. Select the branch action: then_action if TRUE, else_action if FALSE.
      3. If the selected branch has NO action -> conclude directly (skip engine 2).
         Otherwise -> hand the action to the second engine.
    """
    question = state["question"]
    route = state["route"]
    sql_result = state.get("sql_result")
    rag_result = state.get("rag_result")

    # Extract clean, noise-free evidence from step 1 for the condition check.
    if route == "both_rag_first":
        context_data = rag_result.get("answer", "") if isinstance(rag_result, dict) else str(rag_result)
        context_source = "Document Search Insights (RAG)"
    else:
        context_data = _clean_sql_payload(sql_result)
        context_source = "Database Computation Results (SQL)"

    predicate = state.get("condition_predicate") or question
    then_action = state.get("then_action")
    else_action = state.get("else_action")

    # 1. Evaluate the condition -> boolean.
    condition_met = _evaluate_condition(predicate, context_data, context_source)
    state["condition_met"] = condition_met

    # 2. Pick the branch — pure structural logic, no prompt-specific examples.
    selected_action = then_action if condition_met else else_action
    print(f"[REFORMULATOR] Condition '{predicate}' -> {condition_met}; "
          f"selected action: {selected_action!r}")

    # 3. No action defined for this outcome -> conclude. The decision to stop is
    #    the agent's, based on the branch structure (a missing branch), not on
    #    any wording baked into a prompt.
    if not selected_action:
        state["final_answer"] = {
            "answer": _build_conclusion(question, condition_met, context_data),
            "sql_result": sql_result,
            "rag_result": rag_result,
            "type": "combined",
        }
        state["reformulated_question"] = None
        print("[REFORMULATOR] No action for this branch -> concluding directly.")
        return state

    # 4. Action exists -> it becomes the command for the second engine.
    state["reformulated_question"] = selected_action
    return state


def _retrieval_evidence(session_id: str, question: str, n: int = 3) -> str:
    """Probe the PDF vector store with the question to ground routing in real content.

    Returns the top semantically-matching PDF passages (with similarity distance)
    so the router can SEE whether the answer to this specific question actually
    lives in the documents — rather than guessing from a static summary or from
    attribute keywords. Lower distance = closer match. On any failure it returns
    a neutral note so routing never breaks.
    """
    try:
        from file_handler.pdf import PDFHandler
        handler = PDFHandler(session_id)
        res = handler.query(question, n_results=n)
        docs = res.get("documents", []) or []
        dists = res.get("distances", []) or []
        if not docs:
            return "PDF semantic search returned no matching passages for this question."

        lines = []
        for i, doc in enumerate(docs):
            snippet = " ".join(str(doc).split())[:300]
            dist = dists[i] if i < len(dists) else None
            score = f"(distance {dist:.3f}) " if isinstance(dist, (int, float)) else ""
            lines.append(f"  [{i + 1}] {score}{snippet}")
        return ("Most relevant PDF passages (lower distance = stronger match):\n"
                + "\n".join(lines))
    except Exception as e:
        print(f"[ROUTER] PDF retrieval probe failed: {e}")
        return "PDF semantic search unavailable for this question."


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

    # ── Retrieval grounding ──────────────────────────────────────────────────
    # A static summary can't tell the router whether a SPECIFIC entity asked
    # about (e.g. a particular person) actually lives in the PDF or the CSV.
    # So we probe the PDF vector store with the real question and show the router
    # the top matching passages. Now the routing decision is grounded in actual
    # content the model can read and reason over — not a guess from keywords.
    if pdf_files:
        evidence = _retrieval_evidence(session_id, question)
        context_lines.append("")
        context_lines.append("RETRIEVAL EVIDENCE — live PDF semantic search for THIS exact question:")
        context_lines.append(evidence)

    context_block = "\n".join(context_lines) if context_lines else "No data sources available."

    routing_prompt = f"""You are a routing agent for a hybrid data system with two data sources: a CSV database (structured tables) and PDF documents (unstructured text).

WHAT EACH SOURCE ACTUALLY CONTAINS (use this to map each part of the question to a source):
{context_block}

────────────────────────────────────────
HOW TO DECIDE THE ROUTE — follow these steps in order:

STEP 1 — Can ONE source answer the ENTIRE question by itself?
  Use the RETRIEVAL EVIDENCE and source contents above to see which source actually holds what the
  question asks for.
  • Everything needed is in the CSV tables only  → SQL
  • Everything needed is in the PDF documents only → RAG
  A plain retrieval like "give me the <attribute> of <entity>" is SINGLE-source whenever one source
  contains both the entity and that attribute. Only move past this step if the question genuinely
  cannot be answered without BOTH sources.

STEP 2 — The question truly needs BOTH sources. Decide if there is a dependency:
  • CONDITIONAL: the question contains an explicit conditional construct ("if/then/else", "when",
    "depending on", "only if", "in case"), OR one part's result must be known before you can tell
    what to retrieve for the other part. The CONDITION must be resolved before the ANSWER is known.
  • PARALLEL (independent): both parts are separate retrievals; neither result depends on the other.
    Both sources can be queried at the same time.

STEP 3 — For conditional questions, map CONDITION and ANSWER to their sources:
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
EXAMPLES (abstract patterns — focus on the structure, not the words):

A. "<single attribute> of <entity>"  (one source has both the entity and the attribute)
   → SINGLE source → SQL or RAG (whichever source holds it)

B. "<fact A from one source> and <fact B from the other source>"  (two independent asks)
   → no dependency → BOTH_PARALLEL

C. "if <numeric/column test on CSV> then <retrieve narrative from PDF> [else <other PDF info>]"
   → condition in CSV, answer in PDF → BOTH_SQL_FIRST

D. "based on what the document says about <X>, return <CSV metric/rows>"
   → condition in PDF, answer in CSV → BOTH_RAG_FIRST

E. "if <CSV test> then <CSV value> else <other CSV value>"
   → condition and answer BOTH in CSV → SQL  (single source, even though it says "if")

F. "if the document mentions <X>, summarize <that document section>"
   → condition and answer BOTH in PDF → RAG  (single source, even though it says "if")

G. "what does the document say about <X>?"        → RAG
H. "<count/sum/average/filter over CSV columns>"   → SQL


────────────────────────────────────────
CRITICAL RULES:
- ALWAYS try STEP 1 first: if one source can answer the whole question, use that single source (SQL or RAG). Prefer a single source over any BOTH route.
- A simple "give me the X of Y" is single-source retrieval, NOT a cross-source dependency. Finding an entity and returning one of its attributes is one lookup, not a condition.
- Use BOTH_SQL_FIRST / BOTH_RAG_FIRST ONLY when there is a genuine conditional dependency AND the CONDITION and ANSWER come from DIFFERENT sources.
- Use BOTH_PARALLEL when both sources contribute independent pieces (no if/then dependency).
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
        state["condition_predicate"] = None
        state["then_action"] = None
        state["else_action"] = None
        state["condition_met"] = None
        state["sql_result"] = None
        state["rag_result"] = None
        state["error"] = None

        # For conditional cross-source routes, decompose the question into a
        # structured branch plan:
        #   - condition_query:     sub-question the FIRST engine answers (gets data)
        #   - condition_predicate: the test applied to that data (true/false)
        #   - then_action:         what the SECOND engine should do if TRUE
        #   - else_action:         what the SECOND engine should do if FALSE (or None)
        # Decomposition happens HERE because the router already has the full
        # data-source context loaded. The agent's control flow (not a prompt)
        # later decides whether to run the second engine or conclude, based on
        # whether the selected branch has an action.
        if route_decision in ("both_sql_first", "both_rag_first"):
            decomp = _decompose_conditional(question, route_decision, context_block)
            state["condition_query"] = decomp["condition_query"]
            state["condition_predicate"] = decomp["condition_predicate"]
            state["then_action"] = decomp["then_action"]
            state["else_action"] = decomp["else_action"]
            print(f"[ROUTER] Decomposed -> condition_query: '{decomp['condition_query']}' | "
                  f"predicate: '{decomp['condition_predicate']}' | "
                  f"then: '{decomp['then_action']}' | else: '{decomp['else_action']}'")

        return state

    except Exception as e:
        print(f"[ROUTER] Error: {e}")
        user_msg = get_user_friendly_error(str(e))
        state["route"] = "none"
        state["error"] = user_msg
        return state


def _decompose_conditional(question: str, route: str, context_block: str) -> dict:
    """Decompose a conditional cross-source question into a structured branch plan.

    Returns a dict with:
      - condition_query:     clean, standalone question for the FIRST engine to
                             retrieve the data needed to test the condition.
      - condition_predicate: the test applied to that data, phrased as a
                             true/false statement (e.g. "the count is above 1000").
      - then_action:         standalone command for the SECOND engine if the
                             condition is TRUE.
      - else_action:         standalone command for the SECOND engine if the
                             condition is FALSE — None when the question gives no
                             alternative for the false case.

    The LLM only produces this structured breakdown. Whether the second engine
    runs at all is decided later by the agent's control flow (in the
    reformulator) based on which branch is selected — not by any prompt wording.

    For both_sql_first: condition is tested in the CSV database; action targets the PDF.
    For both_rag_first: condition is tested in the PDF; action targets the CSV database.
    """
    if route == "both_sql_first":
        first_source, second_source = "CSV database", "PDF documents"
    else:
        first_source, second_source = "PDF documents", "CSV database"

    prompt = f"""Decompose a conditional question into a structured plan for a two-stage pipeline.

Available data sources:
{context_block}

User question: "{question}"

Step 1 tests a condition using the {first_source}.
Step 2 performs an action using the {second_source}, depending on the condition outcome.

Produce these fields:
- condition_query: a clean, standalone question for the {first_source} that retrieves ONLY
  the data needed to test the condition. No if/then wording, no reference to the other source.
- condition_predicate: the test applied to that data, written as a statement that is either
  true or false (e.g. "the count is greater than 1000", "the report mentions strong growth").
- then_action: a standalone command for the {second_source} to run if the condition is TRUE.
- else_action: a standalone command for the {second_source} to run if the condition is FALSE.
  Leave this empty if the question specifies no alternative for the false case."""

    schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "condition_query": types.Schema(type=types.Type.STRING),
            "condition_predicate": types.Schema(type=types.Type.STRING),
            "then_action": types.Schema(type=types.Type.STRING),
            "else_action": types.Schema(type=types.Type.STRING),
        },
        required=["condition_query", "condition_predicate", "then_action"],
    )

    fallback = {
        "condition_query": question,
        "condition_predicate": question,
        "then_action": question,
        "else_action": None,
    }

    try:
        response = _client.models.generate_content(
            model=_config.get("model_name"),
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=400,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        data = json.loads(response.text)
        # Normalize an empty/blank else_action to None so the agent treats it as
        # "no branch" rather than an empty command.
        else_action = (data.get("else_action") or "").strip() or None
        return {
            "condition_query": data.get("condition_query") or question,
            "condition_predicate": data.get("condition_predicate") or question,
            "then_action": (data.get("then_action") or "").strip() or None,
            "else_action": else_action,
        }
    except Exception as e:
        print(f"[DECOMPOSE] Failed: {e} — falling back to original question")
        return fallback


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

    # Reformulator → the opposite engine, UNLESS the condition resolved with no
    # meaningful follow-up (final_answer already set) → go straight to finalize.
    workflow.add_conditional_edges(
        "reformulator",
        lambda state: (
            "finalize" if state.get("final_answer") is not None
            else "sql" if state["route"] == "both_rag_first"
            else "rag"
        ),
        {
            "sql": "sql",
            "rag": "rag",
            "finalize": "finalize"
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
        "condition_predicate": None,
        "then_action": None,
        "else_action": None,
        "condition_met": None,
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
