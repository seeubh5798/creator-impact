"""Impact score: buying intent + saves/shares/reach/comment rate vs the creator's own baseline.

Every sub-score is 0..100 and the final score is a weighted mean. Metrics that
are missing (no insights, no baseline) are dropped and weights re-normalised,
so a report is always produced even with partial data.
"""

import math
from dataclasses import dataclass

WEIGHTS = {"intent": 0.40, "saves": 0.20, "shares": 0.15, "reach": 0.15, "comment_rate": 0.10}

# Buying-intent rate at which the intent sub-score maxes out (15% of real comments).
INTENT_RATE_FOR_MAX = 0.15


@dataclass
class ScoreInput:
    intent_rate: float | None
    saves: float | None
    shares: float | None
    reach: float | None
    comment_rate: float | None
    base_saves: float | None
    base_shares: float | None
    base_reach: float | None
    base_comment_rate: float | None


def ratio(value: float | None, baseline: float | None) -> float | None:
    if value is None or not baseline or baseline <= 0:
        return None
    return value / baseline


def ratio_subscore(r: float | None) -> float | None:
    """0.5x -> 0, 1x -> 50, 2x -> 100 (log scale, clamped)."""
    if r is None:
        return None
    if r <= 0:
        return 0.0
    return max(0.0, min(100.0, 50.0 + 50.0 * math.log2(r)))


def intent_subscore(rate: float | None) -> float | None:
    if rate is None:
        return None
    return max(0.0, min(100.0, 100.0 * rate / INTENT_RATE_FOR_MAX))


def impact_score(inp: ScoreInput) -> tuple[int | None, dict[str, float]]:
    parts = {
        "intent": intent_subscore(inp.intent_rate),
        "saves": ratio_subscore(ratio(inp.saves, inp.base_saves)),
        "shares": ratio_subscore(ratio(inp.shares, inp.base_shares)),
        "reach": ratio_subscore(ratio(inp.reach, inp.base_reach)),
        "comment_rate": ratio_subscore(ratio(inp.comment_rate, inp.base_comment_rate)),
    }
    present = {k: v for k, v in parts.items() if v is not None}
    if not present:
        return None, {}
    total_w = sum(WEIGHTS[k] for k in present)
    score = sum(WEIGHTS[k] * v for k, v in present.items()) / total_w
    return round(score), {k: round(v, 1) for k, v in present.items()}


def verdict(score: int | None, intent_rate: float | None) -> str:
    if score is None:
        return "Not enough data yet"
    if score >= 75:
        return "Strong buying intent" if (intent_rate or 0) >= 0.08 else "Outstanding performance"
    if score >= 55:
        return "Above this creator's usual"
    if score >= 40:
        return "In line with this creator's usual"
    return "Below this creator's usual"


def percentile(value: float | None, samples: list[float]) -> int | None:
    """Share of the creator's recent posts this post beats, 0..100."""
    vals = [s for s in samples if s is not None]
    if value is None or not vals:
        return None
    below = sum(1 for s in vals if s < value)
    equal = sum(1 for s in vals if s == value)
    return round(100 * (below + 0.5 * equal) / len(vals))
