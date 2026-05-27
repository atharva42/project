import pandas as pd
import sqlite3
import re

class SQL:
    def __init__(self, uploaded_files, session_id):
        self.db_path = f"./sessions/db_{session_id}.db"
        self.con = sqlite3.connect(self.db_path)
        self.schemas = {}  # Store schema info for each table

        for file in uploaded_files:
            filename = file.name
            table_name = self._sanitize_table_name(filename)
            df = pd.read_csv(file)

            if df.empty or df.columns.size == 0:
                raise ValueError(f"{filename} is empty or has no columns.")

            # Auto-detect and convert date columns
            df = self._convert_dates(df)

            self._create_table(table_name, df)
            self.schemas[table_name] = df.dtypes.apply(lambda x: x.name).to_dict()

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
        
        cur = self.con.cursor()
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
        self.con.commit()

    def sql_query(self, query):
        cur = self.con.cursor()
        try:
            cur.execute(query)
            result = cur.fetchall()
            if result:
                # headers = [desc[0] for desc in cur.description]
                # result_df = pd.DataFrame(result, columns=headers)
                # result_str = result_df.to_string(index=False)
                cols = [col[0] for col in cur.description]
                return (result, cols)
            else:
                return ("NO such value", [])
        except Exception as e:
            return (f"SQL Error: {e}", [])
    
    def fetch_schema(self):
        return self.schemas

    def drop_table(self, table_name):
            """Drops a table from the SQLite database."""
            cur = self.con.cursor()
            cur.execute(f"DROP TABLE IF EXISTS {table_name}")
            self.con.commit()


    def close(self):
        self.con.close()