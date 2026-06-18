import chromadb
from pypdf import PdfReader
import uuid
import time
from pathlib import Path
from google import genai
from load_keys import load_config
from services.embedding_service import load_embedding_model

_config = load_config()
_client = genai.Client(api_key=_config.get("api_key"))


class PDFHandler:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.chroma_path = f"./sessions/chroma_{session_id}"
        Path(self.chroma_path).mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB with local embeddings
        self.client = chromadb.PersistentClient(path=self.chroma_path)
        
        # Use sentence-transformers for local embeddings
        start = time.time()
        self.embedding_function = load_embedding_model()
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
    
    def add_pdf(self, pdf_file, filename: str) -> tuple[int, str]:
        """Process PDF and add to ChromaDB.
        
        Returns:
            (num_chunks, extracted_text) — text is returned so the caller can
            pass it to generate_summary without reading the file a second time.
        """
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
        
        return len(chunks), text
    
    def generate_summary(self, text: str, filename: str) -> str:
        """Generate a routing-optimized summary of the document using an LLM.

        The summary is designed to help the routing agent decide whether to
        search this document for a given user question — without the agent
        seeing the document itself. It is generated once at upload time so
        there is zero cost at query time.

        Args:
            text: Full extracted text of the PDF.
            filename: Original filename (used as context in the prompt).

        Returns:
            A concise routing-oriented summary string, or an empty string if
            generation fails (so a missing summary never breaks routing).
        """
        # Use first ~3000 words + last ~500 words to cover intro and conclusion
        # without blowing the token budget.
        words = text.split()
        if len(words) > 3500:
            sample_words = words[:3000] + words[-500:]
        else:
            sample_words = words
        text_sample = " ".join(sample_words)

        prompt = f"""You are creating a routing summary for a document retrieval system.
A routing agent will read this summary to decide whether to search this document
to answer a user's question — without seeing the document itself.

Document filename: {filename}

Your task: write a summary that maximizes routing accuracy for ANY kind of question
a user might ask about this document. The summary must enable the routing agent to
confidently answer: "Is the answer to this question likely to be in this document?"

To do this, your summary MUST cover:
1. What this document is fundamentally about (domain, subject, scope)
2. The main topics, concepts, and themes covered
3. The types of information present (e.g. definitions, statistics, procedures,
   narratives, data tables, timelines, arguments, instructions)
4. Any notable specifics that would appear in user questions (names, terms,
   time periods, categories — whatever is significant for THIS document)
5. What this document does NOT cover, so the router avoids false positives

Keep the summary under 200 words. Be concrete and specific to this document.
Do not use generic filler phrases. Every sentence should help distinguish
whether a question belongs to this document or not.

Document content:
{text_sample}"""

        try:
            response = _client.models.generate_content(
                model=_config.get("model_name"),
                contents=prompt,
                config={
                    "max_output_tokens": 400,
                    "temperature": 0.2
                }
            )
            summary = response.text.strip() if hasattr(response, "text") else ""
            print(f"[PDF SUMMARY] Generated summary for '{filename}' ({len(summary)} chars)")
            return summary
        except Exception as e:
            print(f"[PDF SUMMARY] Failed to generate summary for '{filename}': {e}")
            return ""

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
