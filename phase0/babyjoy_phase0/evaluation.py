"""Human rating statistics; does not process or publish private image/video data."""
from __future__ import annotations

import json
from math import sqrt
from pathlib import Path

from .harness import CASE_ID, GateError

RATINGS = ("identity", "motion", "lip_sync", "continuity", "emotion")
WEIGHTS = {"identity": 0.30, "motion": 0.20, "lip_sync": 0.20,
           "continuity": 0.15, "emotion": 0.15}
# 'emotion' includes appearance of affection; cost stays a separate objective measure.


def wilson(success: int, total: int, z: float = 1.96) -> tuple[float, float] | None:
    if total == 0:
        return None
    p = success / total
    denom = 1 + z * z / total
    middle = (p + z * z / (2 * total)) / denom
    delta = z * sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return max(0.0, middle - delta), min(1.0, middle + delta)


def summarize_ratings(ratings_file: Path) -> dict:
    """Aggregate manually-entered blind ratings; enforce independent severe-artifact veto."""
    if not ratings_file.is_file():
        return {"status": "NOT_RUN", "rated_outputs": 0}
    records: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for line in ratings_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise GateError("Invalid rating JSONL") from exc
        if not isinstance(record, dict):
            raise GateError("Rating must be JSON object")
        if not CASE_ID.fullmatch(str(record.get("case_id", ""))):
            raise GateError("Invalid anonymized case_id")
        if not CASE_ID.fullmatch(str(record.get("model_id", ""))):
            raise GateError("Invalid model_id")
        if not CASE_ID.fullmatch(str(record.get("reviewer_id", ""))):
            raise GateError("Reviewer must have pseudonymous reviewer_id")
        key = record["case_id"], record["model_id"], record["reviewer_id"]
        if key in seen:
            raise GateError("Duplicate blind rating by same reviewer")
        seen.add(key)
        for metric in RATINGS:
            value = record.get(metric)
            if type(value) is not int or not 1 <= value <= 5:
                raise GateError("Ratings must be integers 1..5")
        if type(record.get("severe_artifact")) is not bool:
            raise GateError("severe_artifact must be explicitly true/false")
        if record.get("identity") < 4 or record["severe_artifact"]:
            record["accepted"] = False
        else:
            record["accepted"] = sum(record[k] * WEIGHTS[k] for k in RATINGS) >= 3.8
        records.append(record)
    if not records:
        return {"status": "NOT_RUN", "rated_outputs": 0}
    accepted = sum(r["accepted"] for r in records)
    # A small blind rating set is useful for debugging, NOT evidence of product readiness.
    unique_cases = len({r["case_id"] for r in records})
    return {
        "status": "OBSERVED" if unique_cases >= 30 else "INSUFFICIENT_EVIDENCE",
        "rated_outputs": len(records),
        "unique_cases": unique_cases,
        "accepted_ratings": accepted,
        "rating_acceptance": round(accepted / len(records), 4),
        "rating_acceptance_wilson95": [round(x, 4) for x in wilson(accepted, len(records))],
        "severe_artifact_ratings": sum(r["severe_artifact"] for r in records),
        "mean_scores": {
            metric: round(sum(r[metric] for r in records) / len(records), 3)
            for metric in RATINGS
        },
        "warning": "Ratings are NOT independent when multiple reviewers rate the same case. "
                   "Do not use this estimate as an independent family-level confidence interval.",
    }
