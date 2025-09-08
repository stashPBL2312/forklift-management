from fastapi import APIRouter, Depends, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.models import Forklift
from datetime import datetime
from typing import List, Optional
from app.templating import templates
from app.core.authz import is_admin, is_supervisor

router = APIRouter()

# LIST
@router.get("/", response_class=HTMLResponse)
def list_forklifts(request: Request, db: Session = Depends(get_db), page: int = 1, size: int = 20):
    page = max(page, 1)
    size = min(max(size, 1), 100)
    query = db.query(Forklift)
    total = query.count()
    total_pages = (total + size - 1) // size
    forklifts = query.offset((page - 1) * size).limit(size).all()
    current_year = datetime.now().year
    pagination = {
        "page": page,
        "size": size,
        "total": total,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
        "next_page": page + 1 if page < total_pages else None,
        "prev_page": page - 1 if page > 1 else None,
        "query": f"&size={size}"
    }
    return templates.TemplateResponse("forklifts/list.html", {
        "request": request,
        "forklifts": forklifts,
        "error": None,
        "current_year": current_year,
        "pagination": pagination
    })

# CREATE
@router.post("/tambah", response_class=HTMLResponse)
def create_forklift(request: Request, brand: str = Form(...), type: str = Form(...),
                    eq_no: str = Form(...), serial_number: str = Form(...),
                    location: str = Form(...), powertrain: str = Form(...),
                    owner: str = Form(...), mfg_year: int = Form(...),
                    status: str = Form(...), db: Session = Depends(get_db)):
    forklift = Forklift(brand=brand, type=type, eq_no=eq_no, serial_number=serial_number,
                        location=location, powertrain=powertrain, owner=owner,
                        mfg_year=mfg_year, status=status)
    db.add(forklift)
    try:
        db.commit()
        return RedirectResponse("/", status_code=303)
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse("forklifts/list.html", {
            "request": request,
            "forklifts": db.query(Forklift).all(),
            "error": "EQ No atau Serial Number sudah ada!",
            "current_year": datetime.now().year,
            "pagination": {"page": 1, "size": 20, "total": 1, "total_pages": 1}
        })

# UPDATE
@router.post("/edit/{id}")
def update_forklift(id: int, request: Request,
                    brand: str = Form(...), type: str = Form(...),
                    eq_no: str = Form(...), serial_number: str = Form(...),
                    location: str = Form(...), powertrain: str = Form(...),
                    owner: str = Form(...), mfg_year: int = Form(...),
                    status: str = Form(...), db: Session = Depends(get_db)):
    forklift = db.get(Forklift, id)
    if forklift:
        forklift.brand = brand
        forklift.type = type
        forklift.eq_no = eq_no
        forklift.serial_number = serial_number
        forklift.location = location
        forklift.powertrain = powertrain
        forklift.owner = owner
        forklift.mfg_year = mfg_year
        forklift.status = status
        db.commit()
    return RedirectResponse("/", status_code=303)

# DELETE one -> now POST
@router.post("/delete/{id}")
def delete_one(id: int, request: Request, db: Session = Depends(get_db)):
    current_user = getattr(request.state, "user", None)
    if not (is_admin(current_user) or is_supervisor(current_user)):
        return Response(status_code=status.HTTP_403_FORBIDDEN)
    forklift = db.get(Forklift, id)
    if forklift:
        db.delete(forklift)
        db.commit()
    return RedirectResponse("/", status_code=303)

# BULK DELETE
@router.post("/delete_bulk")
def delete_bulk(request: Request, ids: Optional[List[int]] = Form(None), db: Session = Depends(get_db)):
    current_user = getattr(request.state, "user", None)
    if not (is_admin(current_user) or is_supervisor(current_user)):
        return Response(status_code=status.HTTP_403_FORBIDDEN)
    if ids:
        for id in ids:
            forklift = db.get(Forklift, id)
            if forklift:
                db.delete(forklift)
        db.commit()
    return RedirectResponse("/", status_code=303)
