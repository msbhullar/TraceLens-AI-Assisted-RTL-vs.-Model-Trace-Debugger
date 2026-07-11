"""
LLM explanation layer.

Takes the already-computed, deterministic findings from detection and
localization and asks an LLM to explain them in plain English -- evidence
grounded in the structured data we hand it, nothing invented. The LLM never
decides *whether* something is a mismatch; that's already been decided
upstream by the deterministic detector/localizer. Its only job is to
translate structured facts into a readable debug summary.
"""

import os
from typing import List, Optional

from openai import OpenAI

from app.detection.detector import Finding
from app.localization.localizer import TimestampedFinding

MODEL = "gpt-4o-mini"


def _build_prompt(
    first_divergence: Optional[TimestampedFinding],
    timeline: List[TimestampedFinding],
) -> str:
    """
    Builds a prompt that hands the LLM only the structured facts we've already
    computed -- it should explain them, not re-derive or second-guess them.
    """
    if first_divergence is None:
        return (
            "The RTL and TLM traces were compared and no mismatches were found. "
            "Write one short sentence confirming the traces match, in plain English."
        )

    fd = first_divergence.finding
    other_findings = [tf for tf in timeline if tf.finding is not fd]

    lines = [
        "You are helping a hardware engineer debug a mismatch between an RTL "
        "simulation trace and a SystemC/TLM-2.0 functional model trace.",
        "",
        "The following facts were already determined by deterministic comparison "
        "logic -- do not question, reinterpret, or add mismatches beyond what is "
        "listed here. Your job is only to explain these facts clearly.",
        "",
        f"FIRST DIVERGENCE (earliest point RTL and TLM disagree, at t={first_divergence.timestamp_ns}ns):",
        f"  Type: {fd.mismatch_type}",
        f"  Transaction(s): {', '.join(fd.txn_ids)}",
        f"  Detail: {fd.description}",
        "",
    ]

    if other_findings:
        lines.append(f"OTHER FINDINGS ({len(other_findings)} additional, likely downstream):")
        for tf in other_findings[:10]:  # cap to keep the prompt bounded
            lines.append(f"  - t={tf.timestamp_ns}ns: {tf.finding.mismatch_type} -- {tf.finding.description}")
        lines.append("")

    lines.append(
        "Write a short debug summary (3-5 sentences) explaining: (1) what the "
        "first divergence means in plain English, (2) why it's likely the root "
        "cause rather than the other findings, and (3) one concrete suggestion "
        "for where to look in the RTL/TLM source to start debugging. Be direct "
        "and technical -- this is for an experienced hardware engineer, not a "
        "general audience."
    )

    return "\n".join(lines)


def explain(
    first_divergence: Optional[TimestampedFinding],
    timeline: List[TimestampedFinding],
) -> str:
    """
    Calls an LLM to generate a natural-language debug summary from the
    already-computed findings. Requires OPENAI_API_KEY to be set in the
    environment.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is not set. "
            "Get a key from https://platform.openai.com/api-keys and set it with: "
            "export OPENAI_API_KEY='your-key-here'"
        )

    client = OpenAI(api_key=api_key)
    prompt = _build_prompt(first_divergence, timeline)

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.choices[0].message.content
