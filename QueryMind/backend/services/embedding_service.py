import os
from chromadb.utils import embedding_functions
from load_keys import load_config

_embedding_function = None

def preload_embedding_model():
    global _embedding_function

    if _embedding_function is None:
        config = load_config()
        _embedding_function = (
             embedding_functions.VoyageAIEmbeddingFunction(
                api_key=config.get("voyage_api_key"),
                model_name="voyage-3"
            )
        )

def get_embedding_function():
    global _embedding_function

    if _embedding_function is None:
        preload_embedding_model()

    return _embedding_function