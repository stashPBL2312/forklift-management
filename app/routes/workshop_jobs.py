from fastapi import APIRouter, Depends, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload, selectinload
from datetime import datetime
from typing import List, Optional

from app.database import get_db
from app.models import Forklift, User, WorkshopJob, WorkshopJobAssignment, WorkshopJobItem
from app.templating import templates
from app.core.authz import get_current_user, is_admin, is_assigned_to_workshop

router = APIRouter()

# List Workshop Jobs
@router.get("/", response_class=HTMLResponse)
def list_workshop_jobs(request: Request, db: Session = Depends(get_db), page: int = 1, size: int = 20):
    # Clamp params
    page = max(page, 1)
    size = min(max(size, 1), 100)

    # Query with eager loading
    query = db.query(WorkshopJob).options(
        joinedload(WorkshopJob.forklift),
        selectinload(WorkshopJob.assigned).joinedload(WorkshopJobAssignment.user),
        selectinload(WorkshopJob.items)
    )

    total = query.count()
    total_pages = (total + size - 1) // size
    jobs = query.offset((page - 1) * size).limit(size).all()

    forklifts = db.query(Forklift).all()
    users = db.query(User).filter(User.role != "admin").all()
    success = request.query_params.get("success")

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

    return templates.TemplateResponse("workshop_jobs/list.html", {
        "request": request,
        "jobs": jobs,
        "forklifts": forklifts,
        "users": users,
        "today": datetime.utcnow().strftime("%Y-%m-%d"),
        "success": success,
        "pagination": pagination
    })


# Create Workshop Job
@router.post("/tambah")
def create_workshop_job(
    request: Request,
    forklift_id: int = Form(...),
    date: str = Form(...),
    technicians: Optional[List[int]] = Form(None),
    report_no: str = Form(...),
    job_desc: str = Form(...),
    notes: Optional[str] = Form(None),
    item_name: Optional[List[str]] = Form(None),
    qty: Optional[List[int]] = Form(None),
    db: Session = Depends(get_db)
):
    # Validate technicians field
    if not technicians:
        # Get form data for re-rendering the form with error
        forklifts = db.query(Forklift).all()
        users = db.query(User).filter(User.role != "admin").all()
        jobs = db.query(WorkshopJob).all()
        
        return templates.TemplateResponse("workshop_jobs/list.html", {
            "request": request,
            "jobs": jobs,
            "forklifts": forklifts,
            "users": users,
            "today": date,  # Preserve the date input
            "error": "Pilih minimal satu teknisi",
            "form_data": {
                "forklift_id": forklift_id,
                "report_no": report_no,
                "job_desc": job_desc,
                "notes": notes,
                "item_names": item_name,
                "qtys": qty
            }
        })
    
    job = WorkshopJob(
        forklift_id=forklift_id,
        date=datetime.strptime(date, "%Y-%m-%d"),
        report_no=report_no,
        job_desc=job_desc,
        notes=notes
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    for tech_id in technicians:
        assign = WorkshopJobAssignment(job_id=job.id, user_id=tech_id)
        db.add(assign)

    if item_name and qty:
        for name, q in zip(item_name, qty):
            if name.strip():
                item = WorkshopJobItem(job_id=job.id, item_name=name, qty=q)
                db.add(item)

    db.commit()
    return RedirectResponse("/workshop/?success=1", status_code=303)


# Delete Workshop Job
@router.get("/delete/{id}")
def delete_workshop_job(id: int, request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request)

    job = db.query(WorkshopJob).options(
        selectinload(WorkshopJob.assigned).joinedload(WorkshopJobAssignment.user)
    ).filter(WorkshopJob.id == id).first()

    if not job:
        return RedirectResponse("/workshop/", status_code=303)

    if not (is_admin(current_user) or is_assigned_to_workshop(current_user, job)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    db.query(WorkshopJobAssignment).filter(WorkshopJobAssignment.job_id == id).delete()
    db.query(WorkshopJobItem).filter(WorkshopJobItem.job_id == id).delete()
    db.delete(job)
    db.commit()
    return RedirectResponse("/workshop/", status_code=303)


# --------------------------
# Edit Workshop Job (GET)
# --------------------------
@router.get("/edit/{id}", response_class=HTMLResponse)
def edit_workshop_job_form(id: int, request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request)

    job = (
        db.query(WorkshopJob)
        .options(
            joinedload(WorkshopJob.forklift),
            selectinload(WorkshopJob.assigned).joinedload(WorkshopJobAssignment.user),
            selectinload(WorkshopJob.items),
        )
        .filter(WorkshopJob.id == id)
        .first()
    )

    if not job:
        return RedirectResponse("/workshop/", status_code=303)

    if not (is_admin(current_user) or is_assigned_to_workshop(current_user, job)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    forklifts = db.query(Forklift).all()
    users = db.query(User).filter(User.role != "admin").all()
    selected_tech_ids = [a.user_id for a in job.assigned]

    return templates.TemplateResponse(
        "workshop_jobs/edit.html",
        {
            "request": request,
            "job": job,
            "forklifts": forklifts,
            "users": users,
            "selected_tech_ids": selected_tech_ids,
        },
    )


# --------------------------
# Edit Workshop Job (POST)
# --------------------------
@router.post("/edit/{id}")
def update_workshop_job(
    id: int,
    request: Request,
    forklift_id: int = Form(...),
    date: str = Form(...),
    technicians: Optional[List[int]] = Form(None),
    report_no: str = Form(...),
    job_desc: str = Form(...),
    notes: Optional[str] = Form(None),
    item_name: Optional[List[str]] = Form(None),
    qty: Optional[List[int]] = Form(None),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request)

    job = (
        db.query(WorkshopJob)
        .options(
            selectinload(WorkshopJob.assigned).joinedload(WorkshopJobAssignment.user),
            selectinload(WorkshopJob.items),
        )
        .filter(WorkshopJob.id == id)
        .first()
    )

    if not job:
        return RedirectResponse("/workshop/", status_code=303)

    if not (is_admin(current_user) or is_assigned_to_workshop(current_user, job)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    if not technicians:
        forklifts = db.query(Forklift).all()
        users = db.query(User).filter(User.role != "admin").all()
        selected_tech_ids = [a.user_id for a in job.assigned]
        return templates.TemplateResponse(
            "workshop_jobs/edit.html",
            {
                "request": request,
                "job": job,
                "forklifts": forklifts,
                "users": users,
                "selected_tech_ids": selected_tech_ids,
                "error": "Pilih minimal satu teknisi",
            },
        )

    # Update core fields
    job.forklift_id = forklift_id
    job.date = datetime.strptime(date, "%Y-%m-%d")
    job.report_no = report_no
    job.job_desc = job_desc
    job.notes = notes

    # Replace assignments
    db.query(WorkshopJobAssignment).filter(WorkshopJobAssignment.job_id == job.id).delete()
    for tech_id in technicians:
        db.add(WorkshopJobAssignment(job_id=job.id, user_id=tech_id))

    # Replace items
    db.query(WorkshopJobItem).filter(WorkshopJobItem.job_id == job.id).delete()
    if item_name and qty:
        for name, q in zip(item_name, qty):
            if name and str(name).strip():
                try:
                    q_int = int(q)
                except (TypeError, ValueError):
                    q_int = 0
                db.add(WorkshopJobItem(job_id=job.id, item_name=name, qty=q_int))

    db.commit()
    return RedirectResponse("/workshop/", status_code=303)
