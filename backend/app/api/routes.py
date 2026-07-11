"""
FastAPI routes for TraceLens.

Wires together the full pipeline (parse -> align -> detect -> localize)
behind a single POST /analyze endpoint.
"""

from fastapi import APIRouter, HTTPException

from app.alignment.aligner import align_events
from app.api.schemas import AnalyzeRequest, AnalyzeResponse, FindingResponse
from app.detection.detector import detect_mismatches
from app.localization.localizer import localize
from app.models import TraceSource
from app.parser.log_parser import LogParseError, parse_log_text

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Run the full TraceLens pipeline on a pair of RTL/TLM logs and return
    every detected mismatch, localized to the first point of divergence.
    """
    try:
        rtl_events = parse_log_text(request.rtl_log, TraceSource.RTL)
        tlm_events = parse_log_text(request.tlm_log, TraceSource.TLM)
    except LogParseError as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse log: {e}")

    alignment_result = align_events(rtl_events, tlm_events)
    findings = detect_mismatches(alignment_result, timing_threshold_ns=request.timing_threshold_ns)
    localization_result = localize(alignment_result, findings)

    timestamp_by_finding_id = {
        id(tf.finding): tf.timestamp_ns for tf in localization_result.timeline
    }

    def _to_response(finding) -> FindingResponse:
        return FindingResponse(
            mismatch_type=finding.mismatch_type.value
            if hasattr(finding.mismatch_type, "value")
            else str(finding.mismatch_type),
            txn_ids=finding.txn_ids,
            description=finding.description,
            timestamp_ns=timestamp_by_finding_id.get(id(finding)),
        )

    timeline_response = [_to_response(tf.finding) for tf in localization_result.timeline]

    first_divergence_response = None
    if localization_result.first_divergence is not None:
        first_divergence_response = _to_response(localization_result.first_divergence.finding)

    return AnalyzeResponse(
        total_findings=len(findings),
        first_divergence=first_divergence_response,
        timeline=timeline_response,
    )
