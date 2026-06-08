import pandas as pd
import sqlite3
import re
import json
import os
from pathlib import Path
# LLM client for generating table descriptions
from google import genai
from load_keys import load_config
from services.table_embeddings import TableEmbeddings

class SQL:
    def __init__(self, uploaded_files, session_id):
        self.session_id = session_id
        self.session_dir = f"./sessions/{session_id}"
        self.db_path = f"{self.session_dir}/db.sqlite"
        self.schema_path = f"{self.session_dir}/schema.json"
        
        # Create session directory if it doesn't exist
        Path(self.session_dir).mkdir(parents=True, exist_ok=True)
        
        self.con = sqlite3.connect(self.db_path)
        self.schemas = {}  # Store schema info for each table
        # Initialize table embeddings for semantic search
        self.table_embeddings = TableEmbeddings(session_id)
        # Initialize LLM client for description generation
        self._config = load_config()
        
        if uploaded_files:
            # New session - process uploaded files
            _client = genai.Client(api_key=self._config.get("api_key"))
            
            for file in uploaded_files:
                filename = file.name
                table_name = self._sanitize_table_name(filename)
                df = pd.read_csv(file)

                if df.empty or df.columns.size == 0:
                    raise ValueError(f"{filename} is empty or has no columns.")

                # Auto-detect and convert date columns
                df = self._convert_dates(df)

                self._create_table(table_name, df)
                # Generate a semantic description via LLM using table name, columns and sample rows
                description = self._generate_table_description(_client, table_name, df)
                
                # Create table info dictionary
                table_info = {
                    "table_name": table_name,
                    "dtypes": df.dtypes.apply(lambda x: x.name).to_dict(),
                    "description": description,
                    "sample_rows": df.head(5).to_dict(orient="records")
                }
                
                self.schemas[table_name] = table_info
                
                # Store table description in embeddings for semantic search
                self.table_embeddings.add_table(table_info)
                
                # Save schema to file
                self._save_schema_to_file(table_info)
        else:
            # Reconnecting to existing session - load schemas from file
            self._load_schemas_from_session()

    def _sanitize_table_name(self, filename):
        # Remove extension and non-alphanumeric characters
        name = re.sub(r'\W+', '_', filename.split('.')[0])
        return name.lower()

    def _convert_dates(self, df):
        for col in df.columns:
            try:
                converted = pd.to_datetime(df[col], format="%m/%d/%Y", errors='coerce')
                if converted.notna().sum() > 0 and converted.notna().sum() / len(df) > 0.5:
                    df[col] = converted.dt.strftime('%Y-%m-%d')
            except Exception:
                continue
        return df

    def _map_dtype_to_sqlite(self, dtype):
        if dtype.startswith('int'):
            return 'INTEGER'
        elif dtype.startswith('float'):
            return 'REAL'
        elif dtype == 'datetime64[ns]':
            return 'DATE'
        else:
            return 'TEXT'

    def _create_table(self, table_name, df):
        with self.con:
            cur = self.con.cursor()
            try:
                col_defs = ", ".join([
                    f'"{col}" {self._map_dtype_to_sqlite(str(df[col].dtype))}'
                    for col in df.columns
                ])
                cur.execute(f"DROP TABLE IF EXISTS {table_name}")
                cur.execute(f"CREATE TABLE {table_name} ({col_defs})")

                placeholders = ", ".join(["?" for _ in df.columns])
                cur.executemany(
                    f"INSERT INTO {table_name} VALUES ({placeholders})",
                    df.where(pd.notnull(df), None).values.tolist()
                )
            finally:
                cur.close()

    def sql_query(self, query):
        cur = self.con.cursor()
        try:
            cur.execute(query)
            result = cur.fetchall()
            if result:
                cols = [col[0] for col in cur.description]
                return (result, cols)
            else:
                return ("NO such value", [])
        except Exception as e:
            return (f"SQL Error: {e}", [])
        finally:
            cur.close()
        

    def _save_schema_to_file(self, table_info: dict):
        """Save individual table schema to JSON file in session directory."""
        schema_registry = self.load_schema_from_file() or {}
        
        # Save the full table info for this table
        schema_registry[table_info["table_name"]] = table_info

        with open(self.schema_path, 'w') as f:
            json.dump(schema_registry, f, indent=2)
    
    def _load_schemas_from_session(self):
        """Load schemas from session JSON file when reconnecting."""
        schema_registry = self.load_schema_from_file()
        
        if schema_registry:
            for table_name, table_info in schema_registry.items():
                # Store in schemas dict
                self.schemas[table_name] = table_info
                
                # Add to embeddings (if not already there)
                try:
                    # Check if table already exists in embeddings
                    all_tables = self.table_embeddings.get_all_tables()
                    table_names = [t.get("table_name") for t in all_tables]
                    
                    if table_name not in table_names:
                        self.table_embeddings.add_table(table_info)
                except Exception as e:
                    print(f"[SQL] Error adding table to embeddings: {e}")
                    # Continue without embeddings for this table
            
            print(f"[SQL] Loaded {len(self.schemas)} tables from session file")
    
    def load_schema_from_file(self):
        """Load schema registry from JSON file."""
        if os.path.exists(self.schema_path):
            with open(self.schema_path, 'r') as f:
                return json.load(f)
        return None

    def _generate_table_description(self, client, table_name: str, df: pd.DataFrame) -> str:
        """Ask the LLM to produce a concise, semantically‑rich description of a table.

        The prompt provides the table name, column names and a few example rows.
        The model is expected to return a short paragraph suitable for documentation.
        """
        columns = ", ".join(df.columns.tolist())
        sample = df.head(5).to_dict(orient="records")
        prompt = f"""
            "You are a data assistant. Given the following information about a table, "
            "write a clear, concise description of what the table represents. Only Return the description and no other text."
            "Include any obvious semantics you can infer from column names and sample data.\n\n"
            "Table name: {table_name}\n"
            "Columns: {columns}\n"
            "Sample rows (JSON): {json.dumps(sample, ensure_ascii=False)}\n"
            "Description:" 
            """
        response = client.models.generate_content(
            model=self._config.get("model_name", "gemini-flash-lite-latest"),
            contents=prompt,
            config={
                "max_output_tokens": 500,
                "temperature": 0.3
            }
        )
        # Extract text safely
        return response.text.strip() if hasattr(response, "text") else response.content[0].text.strip()
    
    # def build_schema_registry(self):
    #     """
    #     Build schema registry from current schemas dict.
    #     Returns dict with table names and their columns.
        
    #     Returns:
    #         {
    #             "orders": {"columns": ["id", "amount", "customer_id"]},
    #             "customers": {"columns": ["id", "name", "email"]}
    #         }
    #     """
    #     registry = {}
    #     for table_name, dtypes in self.schemas.items():
    #         registry[table_name] = {
    #             "columns": list(dtypes.keys())
    #         }
    #     return registry


    
    def fetch_schema(self):
        return self.schemas
    
    def find_relevant_tables(self, user_question: str, n_results: int = 3) -> list:
        """Find the most relevant tables for a user question using semantic search.
        
        Args:
            user_question: Natural language question from user
            n_results: Number of tables to return
            
        Returns:
            List of relevant table information dictionaries
        """
        return self.table_embeddings.find_relevant_tables(user_question, n_results)
    
    def get_all_tables_with_embeddings(self) -> list:
        """Get all tables stored in the embeddings collection.
        
        Returns:
            List of all table information dictionaries inside the code
        """
        return self.table_embeddings.get_all_tables()

    def drop_table(self, table_name):
        """Drops a table from the SQLite database."""
        cur = self.con.cursor()
        try:
            cur.execute(f"DROP TABLE IF EXISTS {table_name}")
            self.con.commit()
        finally:
            cur.close()


    def close(self):
        self.con.close()