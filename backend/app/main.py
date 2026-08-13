from fastapi import FastAPI
from app.api.v1.router import api_router

app = FastAPI(title="Plan Review AI Hybrid")
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def root():
    return {"app": "Plan Review AI Hybrid", "status": "ok"}
