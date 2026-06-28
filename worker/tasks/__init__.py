from celery_app import celery_app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os, sys, traceback, math
from datetime import datetime, timezone

sys.path.insert(0, "/app")
sys.path.insert(0, "/shared")
from models import Base, Job, Transaction, JobSummary

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def get_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@celery_app.task(name="tasks.process_job")
def process_job(job_id: str, csv_text: str):
    db = SessionLocal()
    Base.metadata.create_all(bind=engine)
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        job.status = "processing"
        db.commit()

        from tasks.cleaning import clean_csv
        from tasks.anomaly import detect_anomalies
        from tasks.llm import classify_and_summarise

        df = clean_csv(csv_text)
        df = detect_anomalies(df)
        df, summary_data = classify_and_summarise(df)

        # Persist transactions
        def _clean_value(val):
            if val is None:
                return None
            try:
                if pd.isna(val):
                    return None
            except Exception:
                pass
            if hasattr(val, "item") and not isinstance(val, (str, bytes)):
                try:
                    val = val.item()
                except Exception:
                    pass
            if isinstance(val, bool):
                return val
            text = str(val).strip()
            return text if text != "" else None

        for _, row in df.iterrows():
            row_data = row.to_dict()

            amount_value = row_data.get("amount")
            amount = None
            if amount_value is not None and str(amount_value).strip() != "":
                try:
                    amount = float(amount_value)
                    if math.isnan(amount):
                        amount = None
                except (ValueError, TypeError):
                    amount = None

            txn = Transaction(
                job_id=str(job_id),
                txn_id=_clean_value(row_data.get("txn_id")),
                date=_clean_value(row_data.get("date")),
                merchant=_clean_value(row_data.get("merchant")),
                amount=amount,
                currency=_clean_value(row_data.get("currency")),
                status=_clean_value(row_data.get("status")),
                category=_clean_value(row_data.get("category")),
                account_id=_clean_value(row_data.get("account_id")),
                notes=_clean_value(row_data.get("notes")),
                is_anomaly=bool(row_data.get("is_anomaly", False)),
                anomaly_reason=_clean_value(row_data.get("anomaly_reason")),
                llm_category=_clean_value(row_data.get("llm_category")),
                llm_failed=bool(row_data.get("llm_failed", False)),
            )
            db.add(txn)

        # Persist summary
        js = JobSummary(
            job_id=job_id,
            total_spend_inr=float(summary_data.get("total_spend_inr", 0)),
            total_spend_usd=float(summary_data.get("total_spend_usd", 0)),
            top_merchants=list(summary_data.get("top_merchants", [])),
            anomaly_count=int(summary_data.get("anomaly_count", 0)),
            narrative=summary_data.get("narrative", ""),
            risk_level=summary_data.get("risk_level", "low"),
        )
        db.add(js)

        job.status = "completed"
        job.row_count_clean = len(df)
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as e:
        db.rollback()
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = traceback.format_exc()
            db.commit()
    finally:
        db.close()