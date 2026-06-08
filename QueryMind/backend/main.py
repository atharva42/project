# from google import genai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# from load_keys import load_config
# Import routers using absolute package paths to avoid circular import and
# module‑not‑found errors when the application is started with
# ``uvicorn backend.main:app``. The ``backend`` directory is a package, so we
# reference sub‑modules with the full package name.
from routes.uploadAPI_endpoints import router as upload_router
from routes.API_endpoints import router as query_router
from routes.auth_endpoints import router as auth_router
from routes.graph import router as graph_router
from services.embedding_service import preload_embedding_model
from contextlib import asynccontextmanager
import time

# pre-load the model
@asynccontextmanager
async def lifespan(app: FastAPI):
    start_time = time.time()
    print("Loading embedding model...")
    preload_embedding_model()
    print("Embedding model loaded")
    end_time = time.time()
    print(f"Time taken to load embedding model: {end_time - start_time:.2f} seconds")

    yield

    print("Shutting down...")


app = FastAPI(title="Text-2-SQL API", lifespan=lifespan)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(query_router)
app.include_router(graph_router)
# config = load_config()
# client = genai.Client(api_key=config.get("api_key"))


# Langchain tools pre-loaded here for agent

# print(config.get("model_name"))


