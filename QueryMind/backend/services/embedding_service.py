import os
from chromadb.utils import embedding_functions
from load_keys import load_config

_embedding_function = None

def load_embedding_model():
    """Load and initialize the Voyage-3 embedding function."""
    global _embedding_function

    if _embedding_function is None:
        config = load_config()
        _embedding_function = embedding_functions.VoyageAIEmbeddingFunction(
            api_key=config.get("voyage_api_key"),
            model_name="voyage-3"
        )
    return _embedding_function