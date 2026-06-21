# from google import genai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.uploadAPI_endpoints import router as upload_router
from routes.API_endpoints import router as query_router
from routes.auth_endpoints import router as auth_router
from routes.graph import router as graph_router
from services.embedding_service import load_embedding_model
from services.session_manager import session_manager
from contextlib import asynccontextmanager
import time
import asyncio

# Lifespan handler for startup and shutdown tasks
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown tasks."""
    print("Starting up...")
    
    # Preload embedding model on startup
    start_time = time.time()
    print("Loading embedding model...")
    load_embedding_model()
    print(f"Embedding model loaded in {time.time() - start_time:.2f} seconds")
    
    # Run initial cleanup on startup
    try:
        deleted = session_manager.cleanup_expired_sessions(max_age_days=30)
        print(f"Startup cleanup: removed {deleted} expired sessions")
    except Exception as e:
        print(f"Startup cleanup error: {e}")
    
    # Start background task for session cleanup (runs every 24 hours)
    async def cleanup_task():
        while True:
            await asyncio.sleep(86400)  # 24 hours
            try:
                deleted = session_manager.cleanup_expired_sessions(max_age_days=30)
                print(f"Session cleanup: removed {deleted} expired sessions")
            except Exception as e:
                print(f"Session cleanup error: {e}")
    
    cleanup_task_handle = asyncio.create_task(cleanup_task())
    
    yield
    
    # Shutdown
    print("Shutting down...")
    cleanup_task_handle.cancel()


app = FastAPI(title="Text-2-SQL API", lifespan=lifespan)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8001",
        "https://querymind-frontend-sx50.onrender.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],  # Only methods actually used
    allow_headers=["Content-Type", "Cookie"],  # Specific headers only
    max_age=600,  # Cache preflight for 10 minutes
)

app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(query_router)
app.include_router(graph_router)

# TEMPORARY DEMO FEATURE (remove with routes/demo.py) — preloaded datasets
from routes.demo import router as demo_router
app.include_router(demo_router)