"""
TraceLens FastAPI application entry point.

Run locally with:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

app = FastAPI(
    title="TraceLens",
    description="AI-assisted RTL vs. TLM simulation trace debugger",
    version="0.1.0",
)

# Allow the Next.js dev server (localhost:3000) to call this API directly
# from the browser. In production this should be locked down to the actual
# deployed frontend domain instead of allowing all origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
