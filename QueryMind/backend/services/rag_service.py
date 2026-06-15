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
- Answer the question based ONLY on the provided context. 
- If the context doesn't contain enough information, say "The document does not contain enough information to answer the question." and In that case
don't give the cite/chunk information.
- Be concise and specific and interactive in your answer, and if you can give a more detailed answer, do so.
- Do NOT add follow-up questions, suggestions, or offers to provide more information (e.g. "Would you like to know more about...", "Let me know if...", "I can also explain..."). End your response once the question is answered.
- Cite which chunk(s) you used if relevant along with the filename from which the chunk was extracted.

Answer:"""
    
    try:
        response = client.models.generate_content(
            model=config.get("model_name"),
            contents=prompt,
            config={
                "max_output_tokens": 2000,
                "temperature": 0.5
            }
        )
        return response.text
    except Exception as e:
        return f"Error generating answer: {str(e)}"
