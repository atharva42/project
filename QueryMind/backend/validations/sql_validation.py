import sqlglot
from sqlglot import exp
from google import genai
from load_keys import load_config

_config = load_config()
_client = genai.Client(api_key=_config.get("api_key"))

SYSTEM_TABLES = {"sqlite_master", "sqlite_sequence", "sqlite_stat1"}

REPAIR_SYSTEM_PROMPT = """You are an expert SQLite query repair assistant.
You will be given a broken SQL query, the error it produced, and the database schema.
Your job is to fix the query and return ONLY the corrected raw SQL.
No explanations. No markdown. No code blocks. Just the raw SQL query."""


def _get_cte_names(parsed) -> set[str]:
    return {cte.alias.lower() for cte in parsed.find_all(exp.CTE)}

def validate_tables(
    sql: str,
    schema_registry: dict
) -> tuple[bool, str]:

    try:
        parsed = sqlglot.parse_one(sql, dialect="sqlite")
    except sqlglot.errors.ParseError as e:
        return False, f"SQL parsing failed: {e}"

    allowed_tables = {table.lower() for table in schema_registry.keys()}
    cte_names = _get_cte_names(parsed)

    for table in parsed.find_all(exp.Table):
        table_name = table.name.lower()

        if table_name in cte_names:
            continue

        if table_name in SYSTEM_TABLES:
            return False, f"Access to system table '{table_name}' is not allowed."

        if table_name not in allowed_tables:
            return False, f"Table '{table_name}' does not exist in uploaded data."

    return True, "OK"

def validate_sql_safety(sql: str) -> tuple[bool, str]:
    try:
        statements = sqlglot.parse(sql, dialect="sqlite")
    except sqlglot.errors.ParseError as e:
        return False, f"Invalid SQL syntax: {e}"
    
    if not statements:
        return False, "Empty query."
    if len(statements) > 1:
        return False, "Multiple statements are not allowed."

    stmt = statements[0]
    if not isinstance(stmt, exp.Select):
        return False, "Only SELECT queries are permitted."
    return True, "OK"

# Actual function to call 

def validate_sql(
    sql: str,
    schema_registry: dict
) -> tuple[bool, str]:

    ok, msg = validate_sql_safety(sql)
    
    if not ok:
        return False, msg

    ok, msg = validate_tables(sql, schema_registry)

    if not ok:
        return False, msg

    return True, "OK"


def repair_sql(
    original_question: str,
    broken_sql: str,
    error_message: str,
    schema_registry: dict,
    max_attempts: int = 2
) -> tuple[str, bool]:
    """
    Attempt to repair broken SQL using Gemini.
    
    Args:
        original_question: The user's original question
        broken_sql: The SQL query that failed
        error_message: The error message from execution or validation
        schema_registry: Dict with table names as keys
        max_attempts: Max repair attempts
    
    Returns:
        (repaired_sql, success) - Returns repaired SQL and whether it's valid, or (broken_sql, False) if all repairs fail
    """
    schema_str = "\n".join([f"- {table}: {', '.join(info.get('columns', []))}" for table, info in schema_registry.items()])
    
    repair_prompt = f"""
    {REPAIR_SYSTEM_PROMPT}
    
    User Question: {original_question}
    
    Schema:
    {schema_str}
    
    Broken SQL: {broken_sql}
    
    Error: {error_message}
    """
    
    for attempt in range(max_attempts):
        try:
            response = _client.models.generate_content(
                model=_config.get("model_name"),
                contents=repair_prompt,
                config={
                    "max_output_tokens": 1000,
                    "temperature": 0.2
                }
            )
            
            repaired = response.text.strip() if hasattr(response, 'text') else response.content[0].text.strip()
            
            # Validate the repaired query
            ok, msg = validate_sql(repaired, schema_registry)
            
            if ok:
                print(f"[REPAIR] Attempt {attempt + 1}: Successfully repaired SQL")
                return repaired, True
            else:
                print(f"[REPAIR] Attempt {attempt + 1}: Repaired query still invalid: {msg}")
        except Exception as e:
            print(f"[REPAIR] Attempt {attempt + 1} failed with exception: {e}")
    
    print(f"[REPAIR] All {max_attempts} repair attempts failed")
    return broken_sql, False
