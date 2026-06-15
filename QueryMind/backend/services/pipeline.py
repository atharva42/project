import time
from file_handler.sql import SQL
from file_handler.pdf import PDFHandler
from fastapi import HTTPException
from datetime import datetime
from validations.query_validation import _check_length
from validations.sql_validation import validate_sql, repair_sql
from services.session_manager import session_manager, log_query_entry
from services.sql_service import generate_sql_query, execute_sql_query
from services.rag_service import generate_rag_answer


def run_sql_pipeline(
    session_id: str,
    question: str,
    session: dict = None
):
    pipeline_start = time.time()
    # Obtain per-session logger
    sess_logger = session_manager.get_session_logger(session_id)
    sess_logger.info(f"User Question Received: {question}")

    # Initialize timing dict
    timings = {}
    
    try:
        # Reuse the session dict passed in by the caller (the router already
        # fetched it). Only hit the DB when called standalone without one.
        if session is None:
            session = session_manager.get_session(session_id)

        if not session.get("db_path"):
            raise HTTPException(400, "No database uploaded for this session")

        # Reconnect to existing db file for this session
        connection_start = time.time()
        sql_handler = SQL([], session_id)
        timings["db_connection"] = int((time.time() - connection_start) * 1000)
        
        flag, msg = _check_length(question)
        if not flag:
            raise HTTPException(400, msg)
        
        # Use schema already loaded into memory by SQL([], session_id) constructor
        # (it calls _load_schemas_from_session() which populates self.schemas from the
        # same schema.json file). Avoids a redundant disk read + JSON parse.
        schema_load_start = time.time()
        schema_registry = sql_handler.fetch_schema()
        timings["schema_load"] = int((time.time() - schema_load_start) * 1000)
        
        if not schema_registry:
            raise HTTPException(400, "Schema registry not found for this session")
        
        # 1. Generate SQL using semantic search to find relevant tables.
        # Reuse the sql_handler built above to avoid creating a second SQL
        # instance (duplicate SQLite connection + ChromaDB client + schema load).
        sql_gen_start = time.time()
        sql_query = generate_sql_query(question, session_id=session_id, timings_dict=timings, sql_handler=sql_handler)
        timings["sql_generation"] = int((time.time() - sql_gen_start) * 1000)

        # The model is instructed to return ONLY a SELECT (or a WITH/CTE) query.
        # If the output doesn't start with SELECT/WITH, it isn't SQL — it's a
        # refusal/guidance message (e.g. unrelated question or a blocked
        # modification attempt). Detect this structurally (wording-independent)
        # and return a single, controlled, user-friendly message instead of
        # feeding the text into validate_sql (which would emit a confusing
        # parser error or trigger a wasted repair attempt).
        normalized = sql_query.lower().lstrip("(").strip()
        if not normalized.startswith(("select", "with")):
            raise HTTPException(
                400,
                "I can only answer questions about your uploaded data. "
                "Please rephrase your question so it relates to the dataset "
                "(read-only questions only)."
            )

        # 2. Validate with schema registry
        validation_start = time.time()
        is_valid, error_msg = validate_sql(sql_query, schema_registry)
        timings["validation"] = int((time.time() - validation_start) * 1000)
        if not is_valid:
            # Only repair syntax errors and schema mismatches
            repaireable_errors = [
                "SQL parsing failed",  # ParseError - syntax issues
                "does not exist in uploaded data"  # Schema mismatch
            ]
            
            should_repair = any(err in error_msg for err in repaireable_errors)
            
            if should_repair:
                # Try to repair if validation failed
                sess_logger.info("Repair Triggered due to validation failure")
                repaired_query, repair_ok = repair_sql(
                    question,
                    sql_query,
                    error_msg,
                    schema_registry,
                    timings_dict=timings
                )
                
                if repair_ok:
                    sess_logger.info(f"Repair Result (repaired SQL): {repaired_query}")
                    sql_query = repaired_query
                else:
                    sess_logger.error(f"Repair failed: {error_msg}")
                    raise HTTPException(400, f"Invalid SQL after repair attempts: {error_msg}")
            else:
                print(f"error msg is: {error_msg}")
                # Don't repair: multiple statements, system table access, etc.
                raise HTTPException(400, f"Invalid query, please ask read only queries related to the dataset: {error_msg}")

        # 3. Execute
        execution_success = True
        execution_error = None
        execution_start = time.time()
        try:
            results, cols = execute_sql_query(sql_handler, sql_query)
            timings["execution"] = int((time.time() - execution_start) * 1000)
            sess_logger.info(f"Query executed successfully: {sql_query}")
        except Exception as exec_error:
            execution_success = False
            execution_error = str(exec_error)
            sess_logger.info(f"Execution failed: {execution_error}, attempting repair...")
            repaired_query, repair_ok = repair_sql(
                question,
                sql_query,
                execution_error,
                schema_registry,
                timings_dict=timings
            )
            if repair_ok:
                sess_logger.info(f"Repair Result (repaired SQL) for failed executed query: {repaired_query}")
                retry_execution_start = time.time()
                results, cols = execute_sql_query(sql_handler, repaired_query)
                timings["execution_retry"] = int((time.time() - retry_execution_start) * 1000)
                sql_query = repaired_query
                execution_success = True
                execution_error = None
            else:
                raise HTTPException(400, f"SQL execution failed: {execution_error}")

        # Approximate token count (word-based) — replace with Gemini count_tokens in Phase 4
        tokens_q = len(question.split())
        tokens_r = len(sql_query.split())
        query_id = f"{session_id}_{int(time.time()*1000)}"
        session_manager.log_token_usage(session_id, query_id, tokens_q, tokens_r)

        # 4. Generate summary
        # summary = generate_narrative_summary(question, results)
        # print(summary)

        execution_time = int((time.time() - pipeline_start) * 1000)

        # Build structured log entry
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": session_id,
            "question": question,
            "generated_sql": sql_query,
            "validation_passed": is_valid,
            "validation_error": None if is_valid else error_msg,
            "repair_triggered": not is_valid and should_repair,
            "repair_reason": error_msg if not is_valid and should_repair else None,
            "repair_sql": sql_query if not is_valid and should_repair else None,
            "execution_success": execution_success,
            "execution_error": execution_error,
            "rows_returned": len(results) if isinstance(results, list) else 0,
            "latency_sec": round(execution_time / 1000, 2)
        }
        log_query_entry(entry)

        # Ensure results is a list for the response model
        safe_results = results if isinstance(results, list) else []
        
        # Handle empty results with user-friendly message
        result_count = len(safe_results) if isinstance(safe_results, list) else 0
        
        # Add total pipeline time
        timings["total_pipeline"] = int((time.time() - pipeline_start) * 1000)
        
        # Print timing breakdown to terminal
        print(f"\n=== SQL PIPELINE TIMING BREAKDOWN ===")
        print(f"Total pipeline: {timings.get('total_pipeline', 0)}ms")
        print(f"├── Database connection: {timings.get('db_connection', 0)}ms")
        print(f"├── Schema load: {timings.get('schema_load', 0)}ms")
        print(f"├── Table semantic search: {timings.get('table_semantic_search', 0)}ms")
        print(f"├── SQL generation: {timings.get('sql_generation', 0)}ms")
        print(f"│   └── LLM call: {timings.get('llm_generation_call', 0)}ms")
        print(f"├── Validation: {timings.get('validation', 0)}ms")
        print(f"│   ├── Safety check: {timings.get('validation_safety_check', 0)}ms")
        print(f"│   └── Table check: {timings.get('validation_table_check', 0)}ms")
        print(f"├── Execution: {timings.get('execution', timings.get('execution_retry', 0))}ms")
        
        # Print repair timings if any
        repair_llm_times = sum(v for k, v in timings.items() if 'repair_attempt_' in k and '_llm' in k)
        repair_val_times = sum(v for k, v in timings.items() if 'repair_attempt_' in k and '_validation' in k)
        if repair_llm_times > 0:
            print(f"└── Repairs: {repair_llm_times + repair_val_times}ms")
            print(f"    ├── LLM calls: {repair_llm_times}ms")
            print(f"    └── Validation: {repair_val_times}ms")
            for i in range(1, 3):
                llm_key = f"repair_attempt_{i}_llm"
                val_key = f"repair_attempt_{i}_validation"
                if llm_key in timings:
                    print(f"        └── Attempt {i}: LLM={timings[llm_key]}ms, Validation={timings.get(val_key, 0)}ms")
        
        print("=" * 40)
        
        return {
            "sql_query": sql_query,
            "results": safe_results,
            "tables_used": cols,
            "execution_time_ms": execution_time,
            "result_count": result_count,
            "has_results": result_count > 0,
            "timings": timings
        }

    except Exception as e:
        raise HTTPException(500, str(e))

def run_rag_pipeline(session_id: str, question: str, session: dict = None):
    start = time.time()
    try:
        # Reuse the caller-provided session when available; only fetch when
        # called standalone.
        if session is None:
            session = session_manager.get_session(session_id)

        if not session.get("chroma_path"):
            raise HTTPException(400, "No PDF documents uploaded for this session")

        # Initialize PDF handler
        pdf_handler = PDFHandler(session_id)
        
        # Query ChromaDB for relevant chunks
        rag_results = pdf_handler.query(question, n_results=5)
        
        if not rag_results["documents"] or not any(rag_results["documents"]):
            # No relevant content found
            execution_time = int((time.time() - start) * 1000)
            return {
                "answer": "I couldn't find any relevant information in the uploaded documents to answer your question. Please try rephrasing your question or check if the information exists in your documents.",
                "context_chunks": [],
                "sources": [],
                "execution_time_ms": execution_time,
                "has_results": False
            }
        
        # Generate answer using RAG
        answer = generate_rag_answer(question, rag_results["documents"])
        
        # Extract sources
        sources = list(set([meta["source"] for meta in rag_results["metadatas"] if meta.get("source")]))
        
        execution_time = int((time.time() - start) * 1000)

        return {
            "answer": answer,
            "context_chunks": rag_results["documents"],
            "sources": sources,
            "execution_time_ms": execution_time,
            "has_results": True
        }

    except Exception as e:
        raise HTTPException(500, str(e))