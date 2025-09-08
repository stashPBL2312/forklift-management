from fastapi import FastAPI, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.database import Base, engine
from fastapi.staticfiles import StaticFiles
from datetime import datetime

# Import semua router
from app.routes import forklifts, pm_jobs, users, workshop_jobs, auth
from app.middleware import require_auth, admin_only
from app.templating import templates

# Inisialisasi FastAPI
app = FastAPI(title="Forklift Repair Logging System")

# Centralized DB initialization
@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

# Mount static file
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Setup templates with global context
@app.middleware("http")
async def add_global_context(request: Request, call_next):
    request.state.current_year = datetime.now().year
    response = await call_next(request)
    return response

# Add compression middleware
app.add_middleware(GZipMiddleware, minimum_size=500)

# Add cache headers for static files
class StaticCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if request.url.path.startswith("/static/"):
            if "cache-control" not in response.headers:
                response.headers["Cache-Control"] = "public, max-age=604800, immutable"
        return response

# Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if "Content-Security-Policy" not in response.headers:
            response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; font-src 'self' data:"
        if "X-Frame-Options" not in response.headers:
            response.headers["X-Frame-Options"] = "DENY"
        if "Referrer-Policy" not in response.headers:
            response.headers["Referrer-Policy"] = "no-referrer"
        if "X-Content-Type-Options" not in response.headers:
            response.headers["X-Content-Type-Options"] = "nosniff"
        if "Strict-Transport-Security" not in response.headers:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(StaticCacheMiddleware)

app.add_middleware(SecurityHeadersMiddleware)

# Authentication middleware remains
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    return await require_auth(request, call_next)

# Admin-only middleware remains
@app.middleware("http")
async def admin_middleware(request: Request, call_next):
    return await admin_only(request, call_next)

# Tambahkan semua router
app.include_router(forklifts.router)
app.include_router(pm_jobs.router, prefix="/pm", tags=["pm"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(workshop_jobs.router, prefix="/workshop", tags=["workshop"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])

# Root redirect ke forklift list (opsional)
@app.get("/")
def root():
    return {"message": "Akses halaman utama di http://127.0.0.1:8080/ untuk Forklift"}

from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

# Mount static files with cache control
app.mount(
    "/static",
    StaticFiles(directory="app/static", html=False),
    name="static"
)

@app.middleware("http")
async def cache_headers(request, call_next):
    response: Response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        response.headers["Cache-Control"] = "public, max-age=60, stale-while-revalidate=600"
    return response

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
