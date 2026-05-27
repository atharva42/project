from google import genai
from load_keys import load_config

config = load_config()
client = genai.Client(api_key=config.get("api_key"))


def generate_rag_answer(question: str, context_chunks: list[str]) -> str:
    """Generate answer using RAG context."""
    
    # Combine context chunks
    context = "\n\n".join([f"[Chunk {i+1}]\n{chunk}" for i, chunk in enumerate(context_chunks)])
    
    prompt = f"""You are a helpful AI assistant analyzing document content.

Context from documents:
{context}

Question: {question}

Instructions:
- Answer the question based ONLY on the provided context
- If the context doesn't contain enough information, say "I don't have enough information in the documents to answer this question."
- Be concise and specific
- Cite which chunk(s) you used if relevant

Answer:"""
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt
        )
        return response.text
    except Exception as e:
        return f"Error generating answer: {str(e)}"
