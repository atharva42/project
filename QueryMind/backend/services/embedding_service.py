from chromadb.utils import embedding_functions

_embedding_function = None

def preload_embedding_model():
    global _embedding_function

    if _embedding_function is None:
        _embedding_function = (
            embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
        )

def get_embedding_function():
    global _embedding_function

    if _embedding_function is None:
        preload_embedding_model()

    return _embedding_function