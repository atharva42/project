"""Authentication dependencies for FastAPI endpoints."""

from fastapi import Request, HTTPException, Depends
from typing import Optional
from services.session_manager import session_manager


class AuthUser:
    """Represents an authenticated user."""
    def __init__(self, user_id: int, username: str):
        self.id = user_id
        self.username = username


async def get_current_user_optional(request: Request) -> Optional[AuthUser]:
    """Get the current authenticated user, or None if not authenticated.
    
    Use this for endpoints that work with or without authentication.
    """
    session_id = request.cookies.get("session_id")
    
    if not session_id:
        return None
    
    try:
        session = session_manager.get_session(session_id)
        if not session.get('user_id'):
            return None
        
        user = session_manager.get_user_by_id(session['user_id'])
        return AuthUser(user_id=user['id'], username=user['username'])
    except Exception:
        return None


async def get_current_user(request: Request) -> AuthUser:
    """Get the current authenticated user, or raise 401 if not authenticated.
    
    Use this for endpoints that require authentication.
    """
    user = await get_current_user_optional(request)
    
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return user


def verify_session_ownership(session_id: str, user: AuthUser) -> dict:
    """Verify that a session belongs to the authenticated user.
    
    Args:
        session_id: The session ID to verify
        user: The authenticated user
        
    Returns:
        The session dict if ownership verified
        
    Raises:
        HTTPException: 404 if session not found, 403 if not owned by user
    """
    try:
        session = session_manager.get_session(session_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Verify ownership
    if session.get("user_id") and session.get("user_id") != user.id:
        raise HTTPException(
            status_code=403, 
            detail="Access denied: Session belongs to another user"
        )
    
    return session


# FastAPI dependency shortcuts
CurrentUser = Depends(get_current_user)
OptionalUser = Depends(get_current_user_optional)
