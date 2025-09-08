from fastapi import APIRouter, Depends, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload, selectinload
from datetime import datetime, timedelta
from typing import Optional, List

from app.database import get_db, Base, engine
from app.models import Forklift, PMJob, PMJobAssignment, User
from app.templating import templates
from app.core.authz import get_current_user, is_admin, is_assigned_to_pm

Base.metadata.create_all(bind=engine)

router = APIRouter()

# Seed dummy teknisi
@router.get("/seed_users")
def seed_users(db: Session = Depends(get_db)):
    if not db.query(User).first():
        u1 = User(name="Budi", email="budi@test.com")
        u2 = User(name="Andi", email="andi@test.com")
        u3 = User(name="Joni", email="joni@test.com")
        db.add_all([u1,u2,u3])
        db.commit()
    return {"status":"ok"}

# List PM Jobs
@router.get("/", response_class=HTMLResponse)
def list_pm_jobs(request: Request, db: Session = Depends(get_db)):
    query = db.query(PMJob).options(
        joinedload(PMJob.forklift),
        selectinload(PMJob.assigned).joinedload(PMJobAssignment.user)
    )
    jobs = query.all()
    forklifts = db.query(Forklift).all()
    # Filter out admin users from technician list
    users = db.query(User).filter(User.role != "admin").all()
    return templates.TemplateResponse("pm_jobs/list.html", {
        "request": request,
        "jobs": jobs,
        "forklifts": forklifts,
        "users": users,
        "error": None,
        "today": datetime.utcnow().strftime("%Y-%m-%d")
    })

# Create PM Job
@router.post("/tambah")
def create_pm_job(
    request: Request,
    forklift_id: int = Form(...),
    date: str = Form(...),
    technicians: List[int] = Form(...),
    report_no: str = Form(...),
    next_pm_option: Optional[str] = Form(None),
    next_pm_date: Optional[str] = Form(None),
    job_desc: str = Form(...),
    recommendation: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    if next_pm_option:
        current_date = datetime.strptime(date, "%Y-%m-%d")
        if next_pm_option == "1bulan":
            next_pm = current_date + timedelta(days=30)
        elif next_pm_option == "2bulan":
            next_pm = current_date + timedelta(days=60)
        elif next_pm_option == "3bulan":
            next_pm = current_date + timedelta(days=90)
        else:
            next_pm = None
    elif next_pm_date:
        next_pm = datetime.strptime(next_pm_date, "%Y-%m-%d")
    else:
        next_pm = None

    job = PMJob(
        forklift_id=forklift_id,
        date=datetime.strptime(date, "%Y-%m-%d"),
        report_no=report_no,
        job_desc=job_desc,
        recommendation=recommendation,
        next_pm_date=next_pm,
        created_by=1
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    for tech_id in technicians:
        assignment = PMJobAssignment(job_id=job.id, user_id=int(tech_id))
        db.add(assignment)
    db.commit()

    return RedirectResponse("/pm/", status_code=303)

# Delete PM Job (admin or assigned teknisi only)
@router.get("/delete/{id}")
def delete_pm_job(id: int, request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request)

    job = db.query(PMJob).options(
        selectinload(PMJob.assigned).joinedload(PMJobAssignment.user)
    ).filter(PMJob.id == id).first()

    if not job:
        return RedirectResponse("/pm/", status_code=303)

    if not (is_admin(current_user) or is_assigned_to_pm(current_user, job)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    db.query(PMJobAssignment).filter(PMJobAssignment.job_id == id).delete()
    db.delete(job)
    db.commit()
    return RedirectResponse("/pm/", status_code=303)


# --- Admin/Assigned Edit PM Job Endpoints ---

@router.get("/edit/{id}", response_class=HTMLResponse)
def edit_pm_job_form(id: int, request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request)

    job = db.query(PMJob).options(
        joinedload(PMJob.forklift),
        selectinload(PMJob.assigned).joinedload(PMJobAssignment.user)
    ).filter(PMJob.id == id).first()

    if not job:
        return RedirectResponse("/pm/", status_code=303)

    if not (is_admin(current_user) or is_assigned_to_pm(current_user, job)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    forklifts = db.query(Forklift).all()
    users = db.query(User).filter(User.role != "admin").all()
    selected_tech_ids = [a.user_id for a in job.assigned]

    return templates.TemplateResponse("pm_jobs/edit.html", {
        "request": request,
        "job": job,
        "forklifts": forklifts,
        "users": users,
        "selected_tech_ids": selected_tech_ids
    })


@router.post("/edit/{id}")
def update_pm_job(
    id: int,
    request: Request,
    forklift_id: int = Form(...),
    date: str = Form(...),
    technicians: Optional[List[int]] = Form(None),
    report_no: str = Form(...),
    job_desc: str = Form(...),
    recommendation: Optional[str] = Form(None),
    next_pm_option: Optional[str] = Form(None),
    next_pm_date: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(request)

    job = db.query(PMJob).options(
        selectinload(PMJob.assigned).joinedload(PMJobAssignment.user)
    ).filter(PMJob.id == id).first()

    if not job:
        return RedirectResponse("/pm/", status_code=303)

    if not (is_admin(current_user) or is_assigned_to_pm(current_user, job)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    # Update main fields
    job.forklift_id = forklift_id
    job.date = datetime.strptime(date, "%Y-%m-%d")
    job.report_no = report_no
    job.job_desc = job_desc
    job.recommendation = recommendation

    # Next PM logic - support either option-based or direct date
    computed_next_pm: Optional[datetime] = None
    if next_pm_option:
        if next_pm_option == "1bulan":
            computed_next_pm = job.date + timedelta(days=30)
        elif next_pm_option == "2bulan":
            computed_next_pm = job.date + timedelta(days=60)
        elif next_pm_option == "3bulan":
            computed_next_pm = job.date + timedelta(days=90)
        elif next_pm_option == "date" and next_pm_date:
            computed_next_pm = datetime.strptime(next_pm_date, "%Y-%m-%d")
    elif next_pm_date:
        computed_next_pm = datetime.strptime(next_pm_date, "%Y-%m-%d")

    job.next_pm_date = computed_next_pm

    # Replace technician assignments
    db.query(PMJobAssignment).filter(PMJobAssignment.job_id == job.id).delete()
    if technicians:
        for tid in technicians:
            db.add(PMJobAssignment(job_id=job.id, user_id=int(tid)))

    db.commit()
    return RedirectResponse("/pm/", status_code=303)
