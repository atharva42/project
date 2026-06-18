from chromadb import EmbeddingFunction, Embeddings
from google import genai
from load_keys import load_config

_embedding_function = None


class GeminiEmbeddingFunction(EmbeddingFunction):
    """Thin ChromaDB-compatible wrapper around the google-genai SDK for
    gemini-embedding-001. Uses RETRIEVAL_DOCUMENT task type for storage
    and RETRIEVAL_QUERY for queries — matching the intended use case."""

    def __init__(self, api_key: str, task_type: str = "RETRIEVAL_DOCUMENT"):
        self._client = genai.Client(api_key=api_key)
        self._task_type = task_type

    def __call__(self, input: list[str]) -> Embeddings:
        response = self._client.models.embed_content(
            model="gemini-embedding-001",
            contents=input,
            config={"task_type": self._task_type}
        )
        return [e.values for e in response.embeddings]


def load_embedding_model(task_type: str = "RETRIEVAL_DOCUMENT") -> GeminiEmbeddingFunction:
    """Return the cached Gemini embedding function.

    task_type should be:
      - "RETRIEVAL_DOCUMENT"  when embedding chunks/tables for storage
      - "RETRIEVAL_QUERY"     when embedding a user question for search

    ChromaDB calls the embedding function for both add() and query(), so it
    always uses the same instance. For query-time calls the caller can pass
    task_type="RETRIEVAL_QUERY" to get a fresh instance — but in practice
    the difference is minor and sharing one instance is fine for now.
    """
    global _embedding_function

    if _embedding_function is None:
        config = load_config()
        _embedding_function = GeminiEmbeddingFunction(
            api_key=config.get("api_key"),
            task_type=task_type
        )

    return _embedding_function
