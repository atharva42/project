from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from services.session_manager import session_manager
import bcrypt
from datetime import datetime, timedelta

router = APIRouter()


# Request models
class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/register")
async def register(request: Request, response: Response, req: RegisterRequest):
    """Register a new user."""
    # Validate input
    if not req.username or not req.password:
        raise HTTPException(400, "Username and password are required")
    
    if len(req.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    
    # Check if user exists
    existing_user = session_manager.get_user_by_username(req.username)
    if existing_user:
        raise HTTPException(400, "Username already exists")
    
    # Hash password and create user
    try:
        password_hash = bcrypt.hashpw(req.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user_id = session_manager.create_user(req.username, password_hash)
        
        return {"message": "User registered successfully", "user_id": user_id}
    except Exception as e:
        raise HTTPException(500, f"Failed to register user: {str(e)}")


@router.post("/auth/login")
async def login(request: Request, response: Response, req: LoginRequest):
    """Login and create session."""
    # Validate input
    if not req.username or not req.password:
        raise HTTPException(400, "Username and password are required")
    
    # Find user
    user = session_manager.get_user_by_username(req.username)
    if not user:
        raise HTTPException(401, "Invalid credentials")
    
    # Verify password
    try:
        is_valid = bcrypt.checkpw(req.password.encode('utf-8'), user['password_hash'].encode('utf-8'))
        if not is_valid:
            raise HTTPException(401, "Invalid credentials")
    except Exception:
        raise HTTPException(401, "Invalid credentials")
    
    # Set session cookie
    session_id = session_manager.create_session(user_id=user['id'])
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=86400  # 24 hours
    )
    
    return {"message": "Login successful", "session_id": session_id, "user_id": user['id']}


@router.get("/auth/status")
async def get_auth_status(request: Request):
    """Check if user is logged in."""
    session_id = request.cookies.get("session_id")
    
    if not session_id:
        return {"authenticated": False, "user": None}
    
    # Get session to verify it exists and get user_id
    try:
        session = session_manager.get_session(session_id)
        if not session.get('user_id'):
            return {"authenticated": False, "user": None}
        
        user = session_manager.get_user_by_id(session['user_id'])
        return {
            "authenticated": True,
            "user": {"id": user['id'], "username": user['username']}
        }
    except Exception:
        return {"authenticated": False, "user": None}


@router.post("/auth/logout")
async def logout(request: Request, response: Response):
    """Logout and clear session."""
    session_id = request.cookies.get("session_id")
    
    if session_id:
        # Delete the session cookie
        response.delete_cookie(key="session_id")
    
    return {"message": "Logged out successfully"}
