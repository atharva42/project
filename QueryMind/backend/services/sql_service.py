import re
import json
import time
from google import genai
from load_keys import load_config
from file_handler.sql import SQL

_config = load_config()
_client = genai.Client(api_key=_config.get("api_key"))

ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

def clean_model_output(text: str) -> str:
    if not isinstance(text, str):
        return ""
    return ANSI_ESCAPE_RE.sub("", text).strip()

def generate_sql_query(user_input, session_id: str = None, schema: dict = None, n_relevant_tables: int = 3, timings_dict: dict = None, sql_handler=None):
    """Generate SQL query with semantic search for relevant tables.
    
    Args:
        user_input: Natural language question from user
        session_id: Session ID (if provided, uses semantic search)
        schema: Full schema dict (fallback if session_id not provided)
        n_relevant_tables: Number of relevant tables to include (default: 3)
        timings_dict: Optional dict to store timing metrics
        sql_handler: Optional pre-built SQL handler to reuse. If the caller
            (e.g. the pipeline) already created a SQL([], session_id) instance,
            passing it here avoids creating a second one — which would open
            another SQLite connection, another ChromaDB client/collection, and
            re-read schema.json.
    
    Returns:
        Generated SQL query string
    """
    # Use semantic search if session_id is provided
    if session_id:
        try:
            # Reuse the caller's SQL handler when provided; only build a new one
            # if called standalone without an existing handler.
            if sql_handler is None:
                sql_handler = SQL([], session_id)
            
            # Load the in-memory schema first (cheap — already populated by the
            # constructor). Only run the semantic-search network call when there
            # are MORE tables than we'd include anyway. With <= n_relevant_tables
            # tables there is nothing to filter down to, so we skip the Voyage
            # embedding round-trip entirely and just use all tables.
            all_schemas = sql_handler.fetch_schema()

            if not all_schemas:
                return "No tables found in the database. Please upload CSV files first."

            if len(all_schemas) <= n_relevant_tables:
                relevant_tables = None  # fast path: use all tables, no semantic search
                print(f"[SQL GEN] {len(all_schemas)} table(s) <= n_relevant_tables ({n_relevant_tables}); skipping semantic search")
            else:
                table_search_start = time.time()
                relevant_tables = sql_handler.find_relevant_tables(user_input, n_relevant_tables)
                if timings_dict is not None:
                    timings_dict["table_semantic_search"] = int((time.time() - table_search_start) * 1000)

            if not relevant_tables:
                relevant_tables_info = []
                for table_name, table_info in all_schemas.items():
                    if not (isinstance(table_info, dict) and "table_name" in table_info):
                        table_info = {
                            "table_name": table_name,
                            "dtypes": table_info if isinstance(table_info, dict) else {},
                            "description": "",
                            "sample_rows": []
                        }
                    relevant_tables_info.append({"table_info": table_info, "relevance_score": 0.0})
                print(f"[SQL GEN] Using all {len(relevant_tables_info)} tables")
            else:
                relevant_tables_info = relevant_tables
                print(f"[SQL GEN] Found {len(relevant_tables_info)} relevant tables:")

            # Build focused schema and log each table in a single pass.
            focused_schema = {}
            for i, table_data in enumerate(relevant_tables_info):
                table_info = table_data["table_info"]
                table_name = table_info["table_name"]

                focused_schema[table_name] = {
                    "columns": list(table_info["dtypes"].keys()),
                    "column_types": table_info["dtypes"],
                    "description": table_info.get("description", ""),
                    "sample_data": table_info.get("sample_rows", [])[:2]
                }

                score = table_data.get("relevance_score", 0)
                print(f"  {i+1}. {table_name} (relevance: {score:.3f})")
            
            schema = focused_schema
            
        except Exception as e:
            print(f"[SQL GEN] Semantic search failed: {e}. Using provided schema")

    system_prompt = f"""You are a SQLite SELECT query generator. Generate accurate SELECT queries based on the schema and user question.

            Schema: {json.dumps(schema, indent=2)}

            Rules:
            - Generate SELECT queries ONLY. Refuse INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE.
            - If question is unrelated to the dataset, respond: "Kindly ask a question related to the dataset."
            - Use meaningful column aliases (AS customer_name, AS total_sales, AS average_spent)
            - For multi-table queries, use appropriate JOINs and subqueries based on relationships
            - Use LEFT JOIN + IS NULL instead of NOT IN for exclusions (avoids NULL issues)
            - Use COALESCE() to handle NULL values in aggregates
            - Use ROUND(x, 2) for numeric/average aggregates
            - If using derived fields (e.g. first_name || ' ' || last_name), include full expression in GROUP BY
            - Dates must follow yyyy-mm-dd format
            - Return ONLY the raw SQL query — no backticks, no explanation, no formatting

            User question: {user_input}
        """

    llm_call_start = time.time()
    response = _client.models.generate_content(
        model=_config.get("model_name"),
        contents=system_prompt,
        config={
            "max_output_tokens": 2500,
            "temperature": 0.1
        }
    )
    if timings_dict is not None:
        timings_dict["llm_generation_call"] = int((time.time() - llm_call_start) * 1000)
    
    raw_text = response.text.strip() if hasattr(response, "text") else response.content[0].text.strip()
    cleaned = clean_model_output(raw_text)
    print(f"[SQL GEN] Generated query: {cleaned}")
    return cleaned

def execute_sql_query(sql, query):
    return sql.sql_query(query)
