import os
from fastapi.templating import Jinja2Templates
from jinja2 import FileSystemBytecodeCache
from app.core.authz import is_admin, is_supervisor, is_assigned_to_pm, is_assigned_to_workshop

# Ensure cache directory exists
os.makedirs("app/.jinja_cache", exist_ok=True)

# Create shared Jinja2Templates instance
templates = Jinja2Templates(directory="app/templates")

# Configure bytecode cache
templates.env.bytecode_cache = FileSystemBytecodeCache(
    directory="app/.jinja_cache",
    pattern="__bytecode__.%s.cache"
)
# Register helpful globals for templates
templates.env.globals["is_admin"] = is_admin
# Register assignment helper for templates
templates.env.globals["is_assigned_to_pm"] = is_assigned_to_pm
# Register assignment helper for Workshop templates
templates.env.globals["is_assigned_to_workshop"] = is_assigned_to_workshop
templates.env.globals["is_supervisor"] = is_supervisor
# Expose supervisor role check to templates
