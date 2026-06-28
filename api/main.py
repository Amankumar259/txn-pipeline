from fastapi import FastAPI
from database import engine, Base
from routers.jobs import router as jobs_router

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Transaction Processing Pipeline")
app.include_router(jobs_router)

@app.get("/")
def root():
    return {"message": "Transaction Pipeline API is running."}