"""
Request/response schemas for the TraceLens API.

Kept separate from the endpoint logic (app/api/routes.py) so the "shape" of
the API is documented in one place, independent of how it's implemented.
"""

from typing import List, Optional

from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    """Request body for POST /analyze."""

    rtl_log: str
    tlm_log: str
    timing_threshold_ns: int = 100


class FindingResponse(BaseModel):
    mismatch_type: str
    txn_ids: List[str]
    description: str
    timestamp_ns: Optional[int] = None


class AnalyzeResponse(BaseModel):
    """Response body for POST /analyze."""

    total_findings: int
    first_divergence: Optional[FindingResponse] = None
    timeline: List[FindingResponse]
