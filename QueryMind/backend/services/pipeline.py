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
    question: str
):
    start = time.time()
    # Obtain per-session logger
    sess_logger = session_manager.get_session_logger(session_id)
    sess_logger.info(f"User Question Received: {question}")

    try:
        session = session_manager.get_session(session_id)

        if not session.get("db_path"):
            raise HTTPException(400, "No database uploaded for this session")

        # Reconnect to existing db file for this session
        sql_handler = SQL([], session_id)
        flag, msg = _check_length(question)
        if not flag:
            raise HTTPException(400, msg)
        
        # Load schema registry from JSON file
        schema_registry = sql_handler.load_schema_from_file()
        if not schema_registry:
            raise HTTPException(400, "Schema registry not found for this session")
        
        # 1. Generate SQL using semantic search to find relevant tables
        sql_query = generate_sql_query(question, session_id=session_id)

        # If the model returned a user-facing 'ask related to dataset' message instead of SQL,
        # return that directly instead of trying to repair.
        non_sql_messages = [
            "kindly ask a question related to the dataset",
            "kindly ask a question related",
            "only read-only queries are allowed",
            "please ask read only queries",
            "please ask a question related to the dataset",
            "ask a question related to the dataset"
        ]
        normalized = sql_query.lower().strip()
        if any(msg in normalized for msg in non_sql_messages):
            raise HTTPException(400, sql_query)

        # 2. Validate with schema registry
        is_valid, error_msg = validate_sql(sql_query, schema_registry)
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
                    schema_registry
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
        try:
            results, cols = execute_sql_query(sql_handler, sql_query)
            sess_logger.info(f"Query executed successfully: {sql_query}")
        except Exception as exec_error:
            execution_success = False
            execution_error = str(exec_error)
            sess_logger.info(f"Execution failed: {execution_error}, attempting repair...")
            repaired_query, repair_ok = repair_sql(
                question,
                sql_query,
                execution_error,
                schema_registry
            )
            if repair_ok:
                sess_logger.info(f"Repair Result (repaired SQL) for failed executed query: {repaired_query}")
                results, cols = execute_sql_query(sql_handler, repaired_query)
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

        execution_time = int((time.time() - start) * 1000)

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
        return {
            "sql_query": sql_query,
            "results": safe_results,
            "tables_used": cols,
            "execution_time_ms": execution_time
        }

    except Exception as e:
        raise HTTPException(500, str(e))

def run_rag_pipeline(session_id: str, question: str):
    start = time.time()
    try:
        session = session_manager.get_session(session_id)

        if not session.get("chroma_path"):
            raise HTTPException(400, "No PDF documents uploaded for this session")

        # Initialize PDF handler
        pdf_handler = PDFHandler(session_id)
        
        # Query ChromaDB for relevant chunks
        rag_results = pdf_handler.query(question, n_results=5)
        
        if not rag_results["documents"]:
            raise HTTPException(404, "No relevant content found in documents")
        
        # Generate answer using RAG
        answer = generate_rag_answer(question, rag_results["documents"])
        
        # Extract sources
        sources = list(set([meta["source"] for meta in rag_results["metadatas"]]))
        
        execution_time = int((time.time() - start) * 1000)

        return {
            "answer": answer,
            "context_chunks": rag_results["documents"],
            "sources": sources,
            "execution_time_ms": execution_time
        }

    except Exception as e:
        raise HTTPException(500, str(e))