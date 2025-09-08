from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
from typing import Optional, Callable
from datetime import datetime

from app.routes.auth import active_sessions


async def require_auth(request: Request, call_next):
    """
    Middleware to check if user is authenticated for protected routes
    """
    # Skip auth check for public routes
    public_paths = [
        "/auth/login", 
        "/auth/logout", 
        "/auth/forgot-password", 
        "/static/"
    ]
    
    # Check if path starts with any of the public paths
    if any(request.url.path.startswith(path) for path in public_paths):
        return await call_next(request)
    
    # Check for reset-password paths which contain tokens
    if request.url.path.startswith("/auth/reset-password/"):
        return await call_next(request)
    
    # Get session token from cookies
    session_token = request.cookies.get("session_token")
    
    # If no session token or invalid session, redirect to login
    if not session_token or session_token not in active_sessions:
        return RedirectResponse(
            "/auth/login", 
            status_code=status.HTTP_303_SEE_OTHER
        )
    
    # Check if session is expired
    session = active_sessions[session_token]
    if session["expiry"] < datetime.now():
        # Remove expired session
        del active_sessions[session_token]
        return RedirectResponse(
            "/auth/login",
            status_code=status.HTTP_303_SEE_OTHER
        )
    
    # Attach current user info to request.state for templates (from cached session values, no DB hit)
    request.state.user = {
        "id": session["user_id"],
        "name": session.get("name"),
        "email": session.get("email"),
        "role": session.get("role")
    }
    
    # Continue with the request
    return await call_next(request)


async def admin_only(request: Request, call_next):
    """
    Middleware to check if user has admin role for admin-only routes
    """
    # Skip admin check for non-admin routes
    admin_paths = [
        "/users",  # User management is admin only
    ]
    
    # Check if path starts with any of the admin paths
    if not any(request.url.path.startswith(path) for path in admin_paths):
        return await call_next(request)
    
    # Get session token from cookies
    session_token = request.cookies.get("session_token")
    
    # If no session token or invalid session, redirect to login
    if not session_token or session_token not in active_sessions:
        return RedirectResponse(
            "/auth/login", 
            status_code=status.HTTP_303_SEE_OTHER
        )
    
    # Get session data
    session = active_sessions[session_token]
    
    # Check if user is admin by checking the session data
    # We can't use get_current_user here as it requires a db dependency
    if session.get("role") != "admin":
        # Not an admin, redirect to home
        return RedirectResponse(
            "/", 
            status_code=status.HTTP_303_SEE_OTHER
        )
    
    # Continue with the request
    return await call_next(request)