from typing import Any, Dict, Optional, Set, Iterable, TYPE_CHECKING

from fastapi import HTTPException
from fastapi import Request, status

if TYPE_CHECKING:
    # Imported only for type checking; avoids runtime import requirements
    from app.models import PMJob, WorkshopJob


__all__ = [
    "get_current_user",
    "is_admin",
    "is_supervisor",
    "is_user",
    "is_assigned_to_pm",
    "is_assigned_to_workshop",
]


def get_current_user(request: Request) -> Dict[str, Any]:
    """
    FastAPI dependency that returns the current authenticated user as a dict.

    Source of truth:
    - This reads request.state.user which is populated by existing auth middleware.
    - If absent, raises HTTP 401 (Unauthorized).

    Returns:
        A dictionary with at least: {"id": int, "name": str | None, "email": str | None, "role": str | None}

    Raises:
        HTTPException: 401 if the user is not present in request.state.
    """
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def is_admin(current_user: Optional[Dict[str, Any]]) -> bool:
    """
    True if the current_user has the admin role.
    Defensive: returns False if current_user is None or role is missing.
    """
    role = _normalized_role(current_user)
    return role == "admin"


def is_supervisor(current_user: Optional[Dict[str, Any]]) -> bool:
    """
    True if the current_user has the supervisor role.
    Defensive: returns False if current_user is None or role is missing.
    """
    role = _normalized_role(current_user)
    return role == "supervisor"


def is_user(current_user: Optional[Dict[str, Any]]) -> bool:
    """
    True if the current_user has a standard user role.
    Notes:
      - In this codebase, teknisi is the standard user role; we also accept 'user' for forward-compatibility.
    Defensive: returns False if current_user is None or role is missing.
    """
    role = _normalized_role(current_user)
    return role in {"user", "teknisi"}


def is_assigned_to_pm(current_user: Optional[Dict[str, Any]], job: "PMJob") -> bool:
    """
    True if:
      - current_user is admin (always allowed), OR
      - current_user.id is present among the PM job assignments.

    Defensive handling ensures it returns False if current_user or job is invalid.
    """
    if is_admin(current_user) or is_supervisor(current_user):
        return True
    user_id = _safe_user_id(current_user)
    if user_id is None or job is None:
        return False

    assigned_ids = _extract_assigned_user_ids(job)
    return user_id in assigned_ids


def is_assigned_to_workshop(current_user: Optional[Dict[str, Any]], job: "WorkshopJob") -> bool:
    """
    True if:
      - current_user is admin (always allowed), OR
      - current_user.id is present among the Workshop job assignments.

    Defensive handling ensures it returns False if current_user or job is invalid.
    """
    if is_admin(current_user) or is_supervisor(current_user):
        return True
    user_id = _safe_user_id(current_user)
    if user_id is None or job is None:
        return False

    assigned_ids = _extract_assigned_user_ids(job)
    return user_id in assigned_ids


# -----------------------
# Internal helper methods
# -----------------------

def _normalized_role(current_user: Optional[Dict[str, Any]]) -> str:
    role = ""
    if isinstance(current_user, dict):
        raw = current_user.get("role")
        if isinstance(raw, str):
            role = raw.strip().lower()
    return role


def _safe_user_id(current_user: Optional[Dict[str, Any]]) -> Optional[int]:
    if not isinstance(current_user, dict):
        return None
    cid = current_user.get("id")
    try:
        return int(cid) if cid is not None else None
    except (TypeError, ValueError):
        return None


def _extract_assigned_user_ids(job_obj: Any) -> Set[int]:
    """
    Build a set of assigned user IDs from a job object by inspecting its 'assigned' relationship.

    Supports both PMJob.assigned -> List[PMJobAssignment] and
    WorkshopJob.assigned -> List[WorkshopJobAssignment].

    Each assignment may expose:
      - assignment.user_id (preferred), or
      - assignment.user.id (if 'user' is loaded), or
      - in a very defensive fallback, if the collection contains user-like objects with 'id'.

    Returns:
        Set of int user IDs.
    """
    assigned_ids: Set[int] = set()
    assigned: Optional[Iterable[Any]] = getattr(job_obj, "assigned", None)
    if not assigned:
        return assigned_ids

    for entry in assigned:
        # Preferred: direct foreign key column
        uid = getattr(entry, "user_id", None)
        if uid is None:
            # If relationship 'user' is loaded or available, use its id
            user_rel = getattr(entry, "user", None)
            uid = getattr(user_rel, "id", None) if user_rel is not None else None

        # Extremely defensive fallback if someone passed user-like objects
        if uid is None and hasattr(entry, "id") and not hasattr(entry, "user") and not hasattr(entry, "user_id"):
            uid = getattr(entry, "id", None)

        try:
            if uid is not None:
                assigned_ids.add(int(uid))
        except (TypeError, ValueError):
            # Ignore non-castable ids
            continue

    return assigned_ids