import chromadb
from pypdf import PdfReader
import uuid
import time
from pathlib import Path
from services.embedding_service import get_embedding_function


class PDFHandler:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.chroma_path = f"./sessions/chroma_{session_id}"
        Path(self.chroma_path).mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB with local embeddings
        self.client = chromadb.PersistentClient(path=self.chroma_path)
        
        # Use sentence-transformers for local embeddings
        start = time.time()
        self.embedding_function = get_embedding_function()
        print(f"the time taken to initialize embedding function: {time.time() - start}")
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=f"pdf_docs_{session_id}",
            embedding_function=self.embedding_function
        )
    
    def extract_text_from_pdf(self, pdf_file) -> str:
        """Extract text from PDF file."""
        reader = PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        """Split text into overlapping chunks."""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk.strip():
                chunks.append(chunk)
        
        return chunks
    
    def add_pdf(self, pdf_file, filename: str):
        """Process PDF and add to ChromaDB."""
        # Extract text
        text = self.extract_text_from_pdf(pdf_file)
        
        # Chunk text
        chunks = self.chunk_text(text)
        
        # Generate IDs and metadata
        ids = [f"{filename}_{i}_{uuid.uuid4().hex[:8]}" for i in range(len(chunks))]
        metadatas = [{"source": filename, "chunk_index": i} for i in range(len(chunks))]
        
        # Add to ChromaDB
        self.collection.add(
            documents=chunks,
            ids=ids,
            metadatas=metadatas
        )
        
        return len(chunks)
    
    def query(self, question: str, n_results: int = 5) -> dict:
        """Query the PDF collection."""
        results = self.collection.query(
            query_texts=[question],
            n_results=n_results
        )
        
        return {
            "documents": results["documents"][0] if results["documents"] else [],
            "metadatas": results["metadatas"][0] if results["metadatas"] else [],
            "distances": results["distances"][0] if results["distances"] else []
        }
    
    def get_collection_count(self) -> int:
        """Get number of chunks in collection."""
        return self.collection.count()
