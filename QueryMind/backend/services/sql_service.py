import pandas as pd
from google import genai
from load_keys import load_config

_config = load_config()
_client = genai.Client(api_key=_config.get("api_key"))


def generate_sql_query(user_input, schema):
    system_prompt = {
        "role": "system",
        "content": f"""
        You are a data assistant you can also give general answers covesation that:
        1. Generates valid SQLite SELECT queries based on user questions.
        2. After the query is executed, you will be given the result.
        3. Based on the result, generate Streamlit code to visualize it clearly.

        The user may uploaded multiple datasets. Each dataset has been converted into a separate SQLite table. Below is the schema information for all tables: {schema}.

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


        After the result is returned, respond ONLY with matplotlib code to visualize it using up to **two different charts** that best represent the data.
        - The result of sql query is stored in variable called sql_result
        - Only generate visualizations if the data is suitable (e.g., contains numeric columns, multiple rows, or categorical groupings).
        - If the SQL result contains only one row and one column, or if the data is non-numeric, respond with: "Cannot visualize the result".
        - If only one meaningful chart can be generated, return that chart and then the message: "Only one visualization is possible".
        - There might be null values in the any row or column. So make sure to account for poosible errors that may arise. Generate the Sql query by accounting these things. 
        - Use matplotlib for visualizations.
        - Please return only matplotlib code that visualizes this result using a chart (e.g., bar_chart, line_chart, or matplotlib).
        - Do not use st.table or st.dataframe. Do not include any explanation or text — only return valid Python code. Remove fomatting or backticks as well.
        - You may use `matplotlib` if needed, but assume `st` and `pd` are already imported.
        - If the SQL result contains only one row and one column, or if the data is non-numeric, respond with: "Cannot visualize the result".
        - If the result is a list of tuples like `[('HCP_2995',), ('HCP_1439',)]`, convert it to a DataFrame before displaying.
        - Do not include `import streamlit` or `import pandas` or better don't include import or any other backticks of formatting — assume they are already imported.
        - Do not explain the code. Just return the code block.
        """
    }
    full_prompt = system_prompt["content"] + f"\n\nUser question: {user_input}"
    response = _client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=full_prompt
    )
    print(f"[SQL GEN] Generated query {response.text.strip()}")
    return response.text.strip()

def execute_sql_query(sql, query):
    return sql.sql_query(query)

def validate_sql(query):
    """
    Validate SQL query with guardrails
    Your EXISTING validation logic
    """
    errors = []
    sql_upper = query.upper()
    
    # Forbidden operations
    forbidden = ['DELETE', 'DROP', 'UPDATE', 'ALTER', 'INSERT', 'TRUNCATE']
    for op in forbidden:
        if op in sql_upper:
            errors.append(f"Forbidden operation: {op}")
    
    # Basic syntax check
    if not sql_upper.strip().startswith('SELECT'):
        errors.append("Query must start with SELECT")
    
    # Check for semicolons (SQL injection prevention)
    if query.count(';') > 1:
        errors.append("Multiple statements not allowed")
    
    return (len(errors) == 0, errors)

# def generate_visualization_code(messages, sql_result):
#     prompt = messages[0]["content"] + f"\n\nThe result of the query is: {sql_result}"
#     response = _client.models.generate_content(
#         model="gemini-2.0-flash",
#         contents=prompt
#     )
#     print(f"[VISUALIZATION] Generated viz code")
#     return response.text.strip()

# def display_sql_result(sql_result, columnss):
#     st.markdown("#### 📋 SQL Result Table")
#     try:
#         df = pd.DataFrame(sql_result, columns=columnss)
#         st.table(df)
#         return df
#     except Exception as e:
#         st.warning(f"Could not display SQL result as table: {e}")
#         return None

def generate_narrative_summary(user_query, sql_result):  # noqa
    narrative_prompt = f"""
You are a data analyst assistant. Based on the user's question and the SQL query result, generate a concise, human-readable narrative summary.

User Question:
{user_query}

SQL Query Result:
{sql_result}

Instructions:
- Summarize the key insights from the data in the context of the user's question.
- Be clear, concise, and avoid repeating the table verbatim.
- Highlight trends, comparisons, or notable values if applicable.
- The summary needs to be explained in brief to a "non-technical" user. So tell the result in a story form.
"""
    response = _client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=narrative_prompt
    )
    print(f"[SUMMARY] Generated summary")
    return response.text.strip()


# def handle_user_input(user_input, client, deployment, temperature, sql, schema):
#     if not user_input:
#         return

    # Store user message
    # st.session_state.messages.append({"role": "user", "content": user_input})

    # with st.spinner("Generating SQL..."):
    #     sql_query, messages = generate_sql_query(user_input, client, deployment, temperature, schema)

    # Handle restricted or irrelevant queries
    # if sql_query.startswith("Only"):
    #     st.session_state.messages.append({
    #         "role": "assistant",
    #         "content": "🚨 Altering/modification not allowed",
    #         "query": sql_query,
    #         "res": [],
    #         "summa": "",
    #         "viz_code": "",
    #         "columns": []
    #     })

    #     return

    # if sql_query.startswith("Kindly"):
    #     final_message = "Kindly ask a question related to the dataset. Click on 'View Database' to know about the data."
    #     st.session_state.messages.append({
    #         "role": "assistant",
    #         "content": "🚨 " + final_message.capitalize(),
    #         "query": final_message,
    #         "res": [],
    #         "summa": "",
    #         "viz_code": "",
    #         "columns": []
    #     })
    
    #     return

    # Run SQL
    # sql_result, columnss = execute_sql_query(sql, sql_query)
    # if sql_result == "NO such value":
    #     st.warning("⚠️ No results found for your query.")
    #     return

    # Generate summary
    # summary = generate_narrative_summary(client, deployment, temperature, user_input, sql_result)

    # # Generate visualization code
    # viz_code = generate_visualization_code(client, deployment, temperature, messages, sql_result)
    # viz_code = viz_code.strip().replace("```python", "").replace("```", "")

