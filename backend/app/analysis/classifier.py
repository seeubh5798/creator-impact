"""Comment classification: LLM (Claude Haiku) with a rule-based fallback."""

import json
import logging
import re
from collections.abc import Sequence
from typing import Protocol

from app.analysis import lexicon
from app.analysis.preprocess import Comment, strip_mentions
from app.analysis.topics import rule_topic
from app.config import get_settings

log = logging.getLogger(__name__)

CATEGORIES = ("buying_intent", "question", "objection", "praise", "other", "spam")


class Classifier(Protocol):
    name: str

    def classify(self, comments: Sequence[Comment]) -> None:
        """Sets category, confidence, topic (and optionally language) in place."""


class RuleClassifier:
    name = "rules"

    def classify(self, comments: Sequence[Comment]) -> None:
        for c in comments:
            c.category, c.confidence = self._one(c.clean or c.text)
            c.topic = rule_topic(c.clean or c.text, c.category)

    @staticmethod
    def _one(text: str) -> tuple[str, float]:
        t = strip_mentions(text).lower()
        if not t:
            return "other", 0.4
        if lexicon.matches("SPAM", t):
            return "spam", 0.8
        intent = lexicon.matches("BUYING_INTENT", t)
        objection = lexicon.matches("OBJECTION", t)
        question = lexicon.matches("QUESTION", t)
        praise = lexicon.matches("PRAISE", t)
        if objection and objection >= intent:
            return "objection", 0.7
        if intent:
            return "buying_intent", min(0.6 + 0.1 * intent, 0.9)
        if question:
            return "question", 0.65
        if praise:
            return "praise", 0.7
        return "other", 0.5


SYSTEM_PROMPT = """You label Instagram comments on a creator's sponsored post for a brand-impact report.
Comments may be English, Hindi (Devanagari) or Hinglish (romanised Hindi).

Categories (pick exactly one):
- buying_intent: wants to buy, asks price/link/where to buy/availability/discount code, or says they bought/ordered.
- question: asks about the product (suitability, ingredients, usage, variants, results) without clear purchase intent.
- objection: doubt or negative signal about the product: too expensive, didn't work, delivery issues, distrust of the promotion.
- praise: compliments the creator or content, emojis of appreciation.
- other: anything else (greetings, song name, tagging friends, unrelated).
- spam: self-promotion, follow-for-follow, links, scams, bot-like text.

For buying_intent, question and objection also give "t": a short English topic, max 6 words,
phrased as the underlying question or concern (e.g. "Is it good for oily skin?", "Price", "Where to buy", "Too expensive").
Return ONLY a JSON array, one object per input line, in order: [{"i":0,"c":"praise","l":"hinglish","conf":0.9,"t":null}, ...]
"l" is one of en, hi, hinglish."""


def _extract_json(text: str):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("no JSON array in model output")
    return json.loads(text[start : end + 1])


class LLMClassifier:
    name = "llm"

    def __init__(self, client=None):
        settings = get_settings()
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.client = client
        self.model = settings.classify_model
        self.batch_size = settings.classify_batch_size
        self.fallback = RuleClassifier()
        self.failed_batches = 0

    def classify(self, comments: Sequence[Comment]) -> None:
        for start in range(0, len(comments), self.batch_size):
            batch = comments[start : start + self.batch_size]
            try:
                self._classify_batch(batch)
            except Exception as e:  # noqa: BLE001 - any LLM failure falls back to rules
                self.failed_batches += 1
                log.warning("LLM batch failed (%s); using rules for %d comments", e, len(batch))
                self.fallback.classify(batch)

    def _classify_batch(self, batch: Sequence[Comment]) -> None:
        lines = "\n".join(f"{i}\t{strip_mentions(c.clean or c.text)[:300]}" for i, c in enumerate(batch))
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=40 * len(batch) + 200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Label these {len(batch)} comments:\n{lines}"}],
        )
        text = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
        rows = _extract_json(text)
        by_index = {int(r["i"]): r for r in rows if isinstance(r, dict) and "i" in r}
        missing = []
        for i, c in enumerate(batch):
            row = by_index.get(i)
            if not row or row.get("c") not in CATEGORIES:
                missing.append(c)
                continue
            c.category = row["c"]
            c.confidence = float(row.get("conf") or 0.8)
            if row.get("l") in ("en", "hi", "hinglish"):
                c.language = row["l"]
            topic = (row.get("t") or "").strip()
            c.topic = topic[:80] if topic and c.category in ("buying_intent", "question", "objection") else None
        if missing:
            self.fallback.classify(missing)


def get_classifier() -> Classifier:
    if get_settings().anthropic_api_key:
        return LLMClassifier()
    return RuleClassifier()
