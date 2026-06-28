import uuid, os, sys
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlalchemy.orm import Session

sys.path.insert(0, "/shared")   # ← changed from /worker
sys.path.insert(0, "/app")

from database import get_db
from models import Job, Transaction, JobSummary
from schemas import JobCreateResponse, JobStatusResponse, JobResultsResponse, JobListItem
from celery_app import celery_app

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/upload", response_model=JobCreateResponse)
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files accepted.")

    contents = await file.read()
    rows = [l for l in contents.decode("utf-8").splitlines() if l.strip()]
    row_count = max(0, len(rows) - 1)  # subtract header

    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id,
        filename=file.filename,
        status="pending",
        row_count_raw=row_count,
    )
    db.add(job)
    db.commit()

    # Enqueue the task
    celery_app.send_task("tasks.process_job", args=[job_id, contents.decode("utf-8")])

    return JobCreateResponse(job_id=job_id, status="pending", message="Job enqueued.")


@router.get("", response_model=list[JobListItem])
def list_jobs(status: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(Job)
    if status:
        q = q.filter(Job.status == status)
    jobs = q.order_by(Job.created_at.desc()).all()
    return [JobListItem(
        job_id=j.id, filename=j.filename, status=j.status,
        row_count_raw=j.row_count_raw, created_at=j.created_at
    ) for j in jobs]


@router.get("/{job_id}/status", response_model=JobStatusResponse)
def job_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    summary = None
    if job.status == "completed" and job.summary:
        s = job.summary
        summary = {
            "total_spend_inr": s.total_spend_inr,
            "total_spend_usd": s.total_spend_usd,
            "anomaly_count": s.anomaly_count,
            "risk_level": s.risk_level,
            "narrative": s.narrative,
        }
    return JobStatusResponse(job_id=job_id, status=job.status, summary=summary)


@router.get("/{job_id}/results", response_model=JobResultsResponse)
def job_results(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Job status is '{job.status}', not completed.")

    txns = db.query(Transaction).filter(Transaction.job_id == job_id).all()
    anomalies = [t for t in txns if t.is_anomaly]

    # Per-category spend
    category_spend = {}
    for t in txns:
        cat = t.llm_category or t.category or "Uncategorised"
        category_spend[cat] = round(category_spend.get(cat, 0) + (t.amount or 0), 2)

    summary = None
    if job.summary:
        s = job.summary
        summary = {
            "total_spend_inr": s.total_spend_inr,
            "total_spend_usd": s.total_spend_usd,
            "top_merchants": s.top_merchants,
            "anomaly_count": s.anomaly_count,
            "narrative": s.narrative,
            "risk_level": s.risk_level,
        }

    return JobResultsResponse(
        job_id=job_id,
        transactions=txns,
        anomalies=anomalies,
        category_spend=category_spend,
        summary=summary,
    )