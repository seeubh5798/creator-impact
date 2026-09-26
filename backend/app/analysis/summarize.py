"""Group comment topics into the report's 'top questions' and 'main objections'."""

import json
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass

from app.analysis.classifier import _extract_json
from app.config import get_settings

log = logging.getLogger(__name__)


@dataclass
class TopicItem:
    label: str
    count: int
    example: str | None = None


MERGE_PROMPT = """You merge near-duplicate audience topics from Instagram comments into clean clusters for a brand report.
Input: a JSON list of {"i": index, "topic": text, "n": count}.
Return ONLY a JSON array of at most 6 clusters, largest first:
[{"label": "Is it good for oily skin?", "members": [0, 4, 9]}]
Labels: short, specific, written as the audience would ask it (English), no emojis. Every index belongs to at most one cluster.
Drop meaningless topics."""


def _group_exact(topics: list[tuple[str, str | None]]) -> list[TopicItem]:
    counts: Counter[str] = Counter()
    examples: dict[str, str] = {}
    for topic, example in topics:
        key = topic.strip()
        counts[key] += 1
        if example and key not in examples:
            examples[key] = example
    return [TopicItem(label, n, examples.get(label)) for label, n in counts.most_common() if label != "Other"]


def summarize_topics(topics: list[tuple[str, str | None]], limit: int = 5, use_llm: bool | None = None) -> list[TopicItem]:
    """topics: list of (topic, example_text) for each relevant comment."""
    exact = _group_exact(topics)
    if use_llm is None:
        use_llm = bool(get_settings().anthropic_api_key)
    if not use_llm or len(exact) <= 1:
        return exact[:limit]
    try:
        return _merge_with_llm(exact[:150])[:limit]
    except Exception as e:  # noqa: BLE001
        log.warning("topic merge failed (%s); using exact grouping", e)
        return exact[:limit]


def _merge_with_llm(items: list[TopicItem], client=None) -> list[TopicItem]:
    settings = get_settings()
    if client is None:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    payload = json.dumps([{"i": i, "topic": t.label, "n": t.count} for i, t in enumerate(items)], ensure_ascii=False)
    resp = client.messages.create(
        model=settings.summarize_model,
        max_tokens=1500,
        system=MERGE_PROMPT,
        messages=[{"role": "user", "content": payload}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    clusters = _extract_json(text)
    used: set[int] = set()
    merged: dict[str, TopicItem] = defaultdict(lambda: TopicItem("", 0))
    for cl in clusters:
        label = str(cl.get("label", "")).strip()[:80]
        members = [m for m in cl.get("members", []) if isinstance(m, int) and 0 <= m < len(items) and m not in used]
        if not label or not members:
            continue
        used.update(members)
        item = merged[label]
        item.label = label
        item.count += sum(items[m].count for m in members)
        item.example = item.example or next((items[m].example for m in members if items[m].example), None)
    return sorted(merged.values(), key=lambda t: t.count, reverse=True)
