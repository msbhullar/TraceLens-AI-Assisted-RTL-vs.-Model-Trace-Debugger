"""
TraceLens FastAPI application entry point.

Run locally with:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(
    title="TraceLens",
    description="AI-assisted RTL vs. TLM simulation trace debugger",
    version="0.1.0",
)

app.include_router(router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
