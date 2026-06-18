from google import genai
from load_keys import load_config

config = load_config()
client = genai.Client(api_key=config.get("api_key"))


def generate_rag_answer(question: str, context_chunks: list[str], metadatas: list[dict] = None) -> str:
    """Generate answer using RAG context."""
    
    # Combine context chunks, including the source filename for each so the
    # LLM can cite accurately. Metadatas come from ChromaDB chunk metadata.
    parts = []
    for i, chunk in enumerate(context_chunks):
        filename = ""
        if metadatas and i < len(metadatas):
            filename = metadatas[i].get("source", "")
        header = f"[Chunk {i+1} | File: {filename}]" if filename else f"[Chunk {i+1}]"
        parts.append(f"{header}\n{chunk}")
    context = "\n\n".join(parts)
    
    prompt = f"""You are a helpful AI assistant analyzing document content.

Context from documents:
{context}

Question: {question}

Instructions:
- Answer the question based ONLY on the provided context.
- If the context doesn't contain enough information, say "The document does not contain enough information to answer the question."
- Be concise and specific.
- Do NOT ask follow-up questions or suggest further actions.

Answer:"""
    
    try:
        response = client.models.generate_content(
            model=config.get("model_name"),
            contents=prompt,
            config={
                "max_output_tokens": 2000,
                "temperature": 0.3
            }
        )
        return response.text
    except Exception as e:
        return f"Error generating answer: {str(e)}"
