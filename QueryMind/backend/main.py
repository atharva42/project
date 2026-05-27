from google import genai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from load_keys import load_config
from routes.uploadAPI_endpoints import router as upload_router
from routes.API_endpoints import router as query_router
from routes.auth_endpoints import router as auth_router

app = FastAPI(title="Text-2-SQL API")

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

config = load_config()
client = genai.Client(api_key=config.get("api_key"))

