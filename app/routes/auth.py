from fastapi import APIRouter, Depends, Request, Form, HTTPException, Response, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional

from app.database import get_db
from app.models import User
from app.templating import templates

router = APIRouter()

# In-memory storage for password reset tokens (in production, use a database)
reset_tokens = {}

# In-memory session storage (in production, use a proper session backend)
active_sessions = {}

# Helper functions
def hash_password(password: str) -> str:
    """Create a SHA-256 hash of the password"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return hash_password(plain_password) == hashed_password

def create_session(user_id: int, role: str, name: str, email: str) -> str:
    """Create a new session for a user, store minimal cached info"""
    session_token = secrets.token_hex(16)
    expiry = datetime.now() + timedelta(days=1)  # 1 day session
    active_sessions[session_token] = {
        "user_id": user_id,
        "role": role,
        "name": name,
        "email": email,
        "expiry": expiry
    }
    return session_token

def get_current_user(session_token: Optional[str] = Cookie(None), db: Session = Depends(get_db)):
    """Get the current user from the session token"""
    if not session_token or session_token not in active_sessions:
        return None
    
    session = active_sessions[session_token]
    if session["expiry"] < datetime.now():
        # Session expired
        del active_sessions[session_token]
        return None
    
    return db.query(User).filter(User.id == session["user_id"]).first()

# Routes
@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = None):
    return templates.TemplateResponse("auth/login.html", {"request": request, "error": error})

@router.post("/login")
def login(request: Request, response: Response, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    # Find user by email
    user = db.query(User).filter(User.email == email).first()
    
    # Check if user exists and password is correct
    if not user or not verify_password(password, user.password):
        return templates.TemplateResponse(
            "auth/login.html", 
            {"request": request, "error": "Invalid email or password"}
        )
    
    # Create session
    session_token = create_session(user.id, user.role, user.name, user.email)
    
    # Set cookie and redirect
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        key="session_token", 
        value=session_token,
        httponly=True,
        max_age=86400,  # 1 day in seconds
        samesite="lax"
    )
    
    return response

@router.get("/logout")
def logout(response: Response, session_token: Optional[str] = Cookie(None)):
    # Remove session if it exists
    if session_token and session_token in active_sessions:
        del active_sessions[session_token]
    
    # Clear cookie and redirect to login
    response = RedirectResponse("/auth/login", status_code=303)
    response.delete_cookie(key="session_token")
    
    return response

@router.get("/user-info")
def user_info(user: User = Depends(get_current_user)):
    """Return information about the currently logged in user"""
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role
    }

@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request, error: str = None, success: str = None):
    return templates.TemplateResponse(
        "auth/forgot_password.html", 
        {"request": request, "error": error, "success": success}
    )

@router.post("/forgot-password")
def send_password_reset(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    # Find user by email
    user = db.query(User).filter(User.email == email).first()
    
    # Always show success even if email doesn't exist (security best practice)
    if not user:
        return templates.TemplateResponse(
            "auth/forgot_password.html", 
            {
                "request": request, 
                "success": "If your email is registered, you will receive a password reset link shortly."
            }
        )
    
    # Generate token
    token = secrets.token_urlsafe(32)
    expiry = datetime.now() + timedelta(hours=1)  # 1 hour expiry
    reset_tokens[token] = {"user_id": user.id, "expiry": expiry}
    
    # In a real app, send an email with the reset link
    # For demo purposes, just show the link
    reset_link = f"/auth/reset-password/{token}"
    
    return templates.TemplateResponse(
        "auth/forgot_password.html", 
        {
            "request": request, 
            "success": f"Password reset link: {reset_link} (In a real app, this would be emailed to you)"
        }
    )

@router.get("/reset-password/{token}", response_class=HTMLResponse)
def reset_password_page(request: Request, token: str, error: str = None):
    # Check if token exists and is valid
    if token not in reset_tokens or reset_tokens[token]["expiry"] < datetime.now():
        return templates.TemplateResponse(
            "auth/reset_password.html", 
            {"request": request, "error": "Invalid or expired reset link. Please request a new one."}
        )
    
    return templates.TemplateResponse(
        "auth/reset_password.html", 
        {"request": request, "token": token, "error": error}
    )

@router.post("/reset-password/{token}")
def reset_password(request: Request, token: str, password: str = Form(...), confirm_password: str = Form(...), db: Session = Depends(get_db)):
    # Check if token exists and is valid
    if token not in reset_tokens or reset_tokens[token]["expiry"] < datetime.now():
        return templates.TemplateResponse(
            "auth/reset_password.html", 
            {"request": request, "error": "Invalid or expired reset link. Please request a new one."}
        )
    
    # Check if passwords match
    if password != confirm_password:
        return templates.TemplateResponse(
            "auth/reset_password.html", 
            {"request": request, "token": token, "error": "Passwords do not match."}
        )
    
    # Update user's password
    user_id = reset_tokens[token]["user_id"]
    user = db.query(User).filter(User.id == user_id).first()
    
    if user:
        user.password = hash_password(password)
        db.commit()
    
    # Remove used token
    del reset_tokens[token]
    
    return templates.TemplateResponse(
        "auth/reset_password.html", 
        {"request": request, "success": "Your password has been reset successfully. You can now login with your new password."}
    )