import sqlglot
import time
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
    schema_registry: dict,
    parsed=None
) -> tuple[bool, str]:

    # Reuse a pre-parsed statement if provided (avoids re-parsing the same SQL).
    if parsed is None:
        try:
            parsed = sqlglot.parse_one(sql, dialect="sqlite")
        except sqlglot.errors.ParseError as e:
            return False, f"SQL parsing failed: {e}"

    allowed_tables = {table.lower() for table in schema_registry.keys()}
    cte_names = _get_cte_names(parsed)

    # Build alias → real table name map for column validation
    alias_to_table = {}
    for table in parsed.find_all(exp.Table):
        tname = table.name.lower()
        alias = table.alias.lower() if table.alias else tname
        alias_to_table[alias] = tname

    for table in parsed.find_all(exp.Table):
        table_name = table.name.lower()

        if table_name in cte_names:
            continue

        if table_name in SYSTEM_TABLES:
            return False, f"Access to system table '{table_name}' is not allowed."

        if table_name not in allowed_tables:
            return False, f"Table '{table_name}' does not exist in uploaded data."

    # Validate column names against the schema.
    # Only check when binding is unambiguous: qualified columns (table.col)
    # or single-table queries. Multi-table unqualified columns are skipped
    # (SQLite will catch them at execution time).
    tables_in_query = [
        t.name.lower() for t in parsed.find_all(exp.Table)
        if t.name.lower() not in cte_names
    ]

    for col in parsed.find_all(exp.Column):
        col_name = col.name.lower()
        if col_name == "*":
            continue

        col_table = col.table.lower() if col.table else None

        if col_table:
            real_table = alias_to_table.get(col_table, col_table)
            if real_table in cte_names:
                continue
        elif len(tables_in_query) == 1:
            real_table = tables_in_query[0]
        else:
            continue  # ambiguous — skip

        table_info = schema_registry.get(real_table) or schema_registry.get(real_table.lower())
        if not table_info:
            continue

        allowed_cols = {c.lower() for c in (table_info.get("dtypes") or table_info.get("columns") or {}).keys()}
        if allowed_cols and col_name not in allowed_cols:
            return False, (
                f"Column '{col.name}' does not exist in table '{real_table}'. "
                f"Available columns: {', '.join(sorted(allowed_cols))}"
            )

    return True, "OK"

def validate_sql_safety(sql: str) -> tuple[bool, str, object]:
    """Validate SQL is a single SELECT statement.

    Returns (ok, message, parsed_statement). The parsed statement is returned
    so callers can reuse it without re-parsing the same SQL.
    """
    try:
        statements = sqlglot.parse(sql, dialect="sqlite")
    except sqlglot.errors.ParseError as e:
        return False, f"Invalid SQL syntax: {e}", None
    
    if not statements:
        return False, "Empty query.", None
    if len(statements) > 1:
        return False, "Multiple statements are not allowed.", None

    stmt = statements[0]
    if not isinstance(stmt, exp.Select):
        return False, "Only SELECT queries are permitted.", None
    return True, "OK", stmt

# Actual function to call 

def validate_sql(
    sql: str,
    schema_registry: dict,
    timings_dict: dict = None
) -> tuple[bool, str]:

    safety_start = time.time()
    ok, msg, parsed = validate_sql_safety(sql)
    if timings_dict is not None:
        timings_dict["validation_safety_check"] = int((time.time() - safety_start) * 1000)

    if not ok:
        return False, msg

    table_start = time.time()
    # Reuse the statement already parsed during the safety check
    ok, msg = validate_tables(sql, schema_registry, parsed=parsed)
    if timings_dict is not None:
        timings_dict["validation_table_check"] = int((time.time() - table_start) * 1000)

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
