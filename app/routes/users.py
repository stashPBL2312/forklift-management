from fastapi import APIRouter, Depends, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db, Base, engine
from app.models import User
from app.routes.auth import hash_password
from app.templating import templates

from app.core.authz import get_current_user, is_admin

def require_admin(current_user = Depends(get_current_user)):
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")

Base.metadata.create_all(bind=engine)
router = APIRouter(dependencies=[Depends(require_admin)])

# LIST USER
@router.get("/", response_class=HTMLResponse)
def list_users(request: Request, db: Session = Depends(get_db)):
    users = db.query(User).all()
    return templates.TemplateResponse("users/list.html", {"request": request, "users": users})

# CREATE USER
@router.post("/tambah")
def create_user(
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db)
):
    # Hash the password before storing
    hashed_password = hash_password(password)
    user = User(name=name, email=email, password=hashed_password, role=role)
    db.add(user)
    db.commit()
    return RedirectResponse("/users/", status_code=303)

# DELETE USER
@router.get("/delete/{id}")
def delete_user(id: int, db: Session = Depends(get_db)):
    user = db.query(User).get(id)
    if user:
        db.delete(user)
        db.commit()
    return RedirectResponse("/users/", status_code=303)

# EDIT USER FORM
@router.get("/edit/{id}", response_class=HTMLResponse)
def edit_form(id: int, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).get(id)
    return templates.TemplateResponse("users/edit.html", {"request": request, "user": user})

# UPDATE USER
@router.post("/edit/{id}")
def update_user(
    id: int,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).get(id)
    if user:
        user.name = name
        user.email = email
        # Hash the password before storing
        user.password = hash_password(password)
        user.role = role
        db.commit()
    return RedirectResponse("/users/", status_code=303)
