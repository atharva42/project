import re
import json
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

def generate_sql_query(user_input, session_id: str = None, schema: dict = None, n_relevant_tables: int = 3):
    """Generate SQL query with semantic search for relevant tables.
    
    Args:
        user_input: Natural language question from user
        session_id: Session ID (if provided, uses semantic search)
        schema: Full schema dict (fallback if session_id not provided)
        n_relevant_tables: Number of relevant tables to include (default: 3)
    
    Returns:
        Generated SQL query string
    """
    # Use semantic search if session_id is provided
    if session_id:
        try:
            sql_handler = SQL([], session_id)
            
            # Find relevant tables using semantic search
            relevant_tables = sql_handler.find_relevant_tables(user_input, n_relevant_tables)
            
            if not relevant_tables:
                # Fallback to all tables
                all_tables = sql_handler.get_all_tables_with_embeddings()
                if not all_tables:
                    all_schemas = sql_handler.fetch_schema()
                    if not all_schemas:
                        return "No tables found in the database. Please upload CSV files first."
                    
                    # Convert schemas to table_info format
                    all_tables = []
                    for table_name, table_info in all_schemas.items():
                        if isinstance(table_info, dict) and "table_name" in table_info:
                            all_tables.append(table_info)
                        else:
                            all_tables.append({
                                "table_name": table_name,
                                "dtypes": table_info if isinstance(table_info, dict) else {},
                                "description": "",
                                "sample_rows": []
                            })
                
                relevant_tables_info = [{"table_info": table, "relevance_score": 0.0} for table in all_tables]
                print(f"[SQL GEN] Using all {len(all_tables)} tables as fallback")
            else:
                relevant_tables_info = relevant_tables
                print(f"[SQL GEN] Found {len(relevant_tables_info)} relevant tables:")
                for i, table_data in enumerate(relevant_tables_info):
                    table_info = table_data["table_info"]
                    table_name = table_info.get("table_name", "Unknown")
                    score = table_data.get("relevance_score", 0)
                    print(f"  {i+1}. {table_name} (relevance: {score:.3f})")
            
            # Build focused schema only for relevant tables
            focused_schema = {}
            for table_data in relevant_tables_info:
                table_info = table_data["table_info"]
                table_name = table_info["table_name"]
                
                focused_schema[table_name] = {
                    "columns": list(table_info["dtypes"].keys()),
                    "column_types": table_info["dtypes"],
                    "description": table_info.get("description", ""),
                    "sample_data": table_info.get("sample_rows", [])[:2]
                }
            
            schema = focused_schema
            
        except Exception as e:
            print(f"[SQL GEN] Semantic search failed: {e}. Using provided schema")
            # Continue with provided schema as fallback
    
    # Generate SQL with focused or full schema
    system_prompt = {
        "role": "system",
        "content": f"""
        You are a data assistant that generates valid SQLite SELECT queries based on user questions.

        The user may uploaded multiple datasets. Each dataset has been converted into a separate SQLite table. Below is the schema information for all tables: {json.dumps(schema, indent=2)}.

        When the user asks a question:
        - You must only generate **SELECT** queries. Do NOT generate queries that modify data such as DELETE, UPDATE, INSERT, DROP, ALTER, or TRUNCATE.
        - If the user asks to modify, delete, or alter the table or its data, politely respond: "Only read-only queries are allowed".
        - If the user asks a question **unrelated to the dataset**, politely respond: "Kindly ask a question related to the dataset. Click on 'View Database' to know about the data."
        - First, respond ONLY with a valid SQL SELECT query.
        - Always use **clear and meaningful column aliases** in the SELECT clause. For example, use `AS customer_name`, `AS total_orders`, or `AS average_spent`. Avoid raw function names like `count(*)` or `avg(...)` without aliases.
        - Respond ONLY with a valid SQL SELECT statement. Do not include any formatting or backticks.
        - Since you know all the tables and their content, you may need to perform joins or use subqueries to generate the required SQL queries.
        - When filtering for records with no matching rows in another table, prefer using `LEFT JOIN` with `IS NULL` or `NOT EXISTS` over `NOT IN` to avoid NULL-related issues.
        - When handling null values, use appropriate functions like `COALESCE()` to avoid errors or unexpected results.
        - Always check data types and handle dates with format 'yyyy-mm-dd' consistently in queries.
        - Ensure your queries handle possible nulls gracefully and avoid errors.
        - Use aliases and clear naming for readability.
        - Consider the **full schema and relationships** between tables — use appropriate JOINs and subqueries as needed.
        - If the query involves filtering "customers who never ordered", avoid `NOT IN` (which fails with NULLs). Use `LEFT JOIN ... IS NULL` or `NOT EXISTS`.
        - If you're using any derived fields (like full name with `first_name || ' ' || last_name`), make sure to include the full expression in the `GROUP BY` clause if selected.
        - Always handle possible NULLs in aggregates using `COALESCE()`.
        - Use `ROUND(..., 2)` to make numeric aggregates (like averages) user-friendly.
        - Always check the column's datatype and ensure consistent date handling using `yyyy-mm-dd` format.
        """
    }
    full_prompt = system_prompt["content"] + f"\n\nUser question: {user_input}"
    response = _client.models.generate_content(
        model=_config.get("model_name"),
        contents=full_prompt,
        config={
            "max_output_tokens": 2500,
            "temperature": 0.1
        }
    )
    raw_text = response.text.strip() if hasattr(response, "text") else response.content[0].text.strip()
    cleaned = clean_model_output(raw_text)
    print(f"[SQL GEN] Generated query: {cleaned}")
    return cleaned

def execute_sql_query(sql, query):
    return sql.sql_query(query)
