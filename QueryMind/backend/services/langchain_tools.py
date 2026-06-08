from langchain.tools import tool
from services.pipeline import (
    run_sql_pipeline,
    run_rag_pipeline
)

def create_tools(session_id):
    @tool
    def sql_tool(question: str):
        """
        Query structured CSV data stored in SQLite.
        Use for counts, sums, averages, filtering, tabular analysis.
        """
        return run_sql_pipeline(session_id, question)

    @tool
    def rag_tool(question: str):
        """
        Search uploaded PDF documents and answer questions from document contents.
        Use for resume, invoices, reports, contracts, policies.
        """
        return run_rag_pipeline(session_id, question)
    return [sql_tool, rag_tool]