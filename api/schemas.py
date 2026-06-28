from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

class JobCreateResponse(BaseModel):
    job_id: str
    status: str
    message: str

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    summary: Optional[dict] = None

class TransactionOut(BaseModel):
    id: int
    txn_id: Optional[str]
    date: Optional[str]
    merchant: Optional[str]
    amount: Optional[float]
    currency: Optional[str]
    status: Optional[str]
    category: Optional[str]
    account_id: Optional[str]
    notes: Optional[str]
    is_anomaly: bool
    anomaly_reason: Optional[str]
    llm_category: Optional[str]

    class Config:
        from_attributes = True

class JobResultsResponse(BaseModel):
    job_id: str
    transactions: List[TransactionOut]
    anomalies: List[TransactionOut]
    category_spend: dict
    summary: Optional[dict]

class JobListItem(BaseModel):
    job_id: str
    filename: Optional[str]
    status: str
    row_count_raw: int
    created_at: datetime

    class Config:
        from_attributes = True