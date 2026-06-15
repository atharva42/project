"""
Table Embeddings Service for semantic search of table descriptions.
"""
import chromadb
import json
import uuid
from pathlib import Path
from services.embedding_service import load_embedding_model


class TableEmbeddings:
    """Manages embeddings for table descriptions to enable semantic search."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.chroma_path = f"./sessions/tables_{session_id}"
        Path(self.chroma_path).mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(path=self.chroma_path)
        self.embedding_function = load_embedding_model()
        
        # Create or get collection for table descriptions
        self.collection = self.client.get_or_create_collection(
            name=f"table_descriptions_{session_id}",
            embedding_function=self.embedding_function
        )
    
    def create_table_embedding_text(self, table_info: dict) -> str:
        """Create a comprehensive text for embedding from table information.
        
        Args:
            table_info: Dictionary containing:
                - table_name: Name of the table
                - dtypes: Dictionary of column names to data types
                - description: LLM-generated description
                - sample_rows: Sample data from the table
        
        Returns:
            Formatted text for embedding
        """
        # Format columns information
        columns_text = ", ".join([f"{col} ({dtype})" for col, dtype in table_info["dtypes"].items()])
        
        # Format sample data
        sample_text = ""
        if table_info.get("sample_rows"):
            sample_rows = table_info["sample_rows"][:3]  # Use first 3 rows
            sample_text = "Sample data: "
            for i, row in enumerate(sample_rows):
                sample_text += f"Row {i+1}: {json.dumps(row)}; "
        
        # Combine all information
        embedding_text = (
            f"Table: {table_info['table_name']}. "
            f"Columns: {columns_text}. "
            f"Description: {table_info['description']}. "
            f"{sample_text}"
        )
        
        return embedding_text.strip()
    
    def add_table(self, table_info: dict):
        """Add a table description to the embeddings collection.
        
        Args:
            table_info: Dictionary containing table metadata
        """
        # Generate embedding text
        embedding_text = self.create_table_embedding_text(table_info)
        
        # Generate unique ID for this table
        table_id = f"{self.session_id}_{table_info['table_name']}_{uuid.uuid4().hex[:8]}"
        
        # Store metadata
        metadata = {
            "table_name": table_info["table_name"],
            "columns": json.dumps(list(table_info["dtypes"].keys())),
            "description": table_info["description"],
            "full_info": json.dumps(table_info)  # Store full info for retrieval
        }
        
        # Add to ChromaDB
        self.collection.add(
            documents=[embedding_text],
            ids=[table_id],
            metadatas=[metadata]
        )
        
        print(f"[TABLE EMBEDDINGS] Added table '{table_info['table_name']}' to embeddings")
    
    def find_relevant_tables(self, user_question: str, n_results: int = 3) -> list:
        """Find the most relevant tables for a user question.
        
        Args:
            user_question: Natural language question from user
            n_results: Number of tables to return
            
        Returns:
            List of table information dictionaries, sorted by relevance
        """
        # Query ChromaDB
        results = self.collection.query(
            query_texts=[user_question],
            n_results=min(n_results, self.collection.count())
        )
        
        if not results["documents"]:
            return []
        
        # Parse results
        relevant_tables = []
        for i in range(len(results["documents"][0])):
            metadata = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            
            # Parse full info from metadata
            full_info = json.loads(metadata.get("full_info", "{}"))
            
            # If full_info parsing fails, reconstruct from metadata
            if not full_info:
                full_info = {
                    "table_name": metadata.get("table_name"),
                    "dtypes": {},  # We don't store dtypes in metadata for parsing
                    "description": metadata.get("description"),
                    "sample_rows": []
                }
            
            relevant_tables.append({
                "table_info": full_info,
                "relevance_score": 1 - distance,  # Convert distance to similarity score
                "distance": distance
            })
        
        # Sort by relevance score (highest first)
        relevant_tables.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return relevant_tables
    
    def get_all_tables(self) -> list:
        """Get all tables stored in the collection.
        
        Returns:
            List of all table information dictionaries
        """
        try:
            # Get all documents from collection
            results = self.collection.get()
            
            all_tables = []
            for i in range(len(results["ids"])):
                metadata = results["metadatas"][i]
                full_info = json.loads(metadata.get("full_info", "{}"))
                
                if not full_info:
                    full_info = {
                        "table_name": metadata.get("table_name"),
                        "dtypes": {},
                        "description": metadata.get("description"),
                        "sample_rows": []
                    }
                
                all_tables.append(full_info)
            
            return all_tables
            
        except Exception as e:
            print(f"[TABLE EMBEDDINGS] Error getting all tables: {e}")
            return []
    
    def remove_table(self, table_name: str):
        """Remove a table from the embeddings collection.
        
        Args:
            table_name: Name of the table to remove
        """
        # Get all documents and find the one with matching table_name
        results = self.collection.get()
        
        for i in range(len(results["ids"])):
            metadata = results["metadatas"][i]
            if metadata.get("table_name") == table_name:
                # Delete the document
                self.collection.delete(ids=[results["ids"][i]])
                print(f"[TABLE EMBEDDINGS] Removed table '{table_name}' from embeddings")
                return
        
        print(f"[TABLE EMBEDDINGS] Table '{table_name}' not found in embeddings")