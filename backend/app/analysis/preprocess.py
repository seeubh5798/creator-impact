"""Cleaning, spam rules and language detection. No LLM cost here."""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

from app.analysis import lexicon

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
MENTION = re.compile(r"@[\w.]+")
WORD = re.compile(r"[a-zA-Zऀ-ॿ]+")


@dataclass
class Comment:
    comment_id: str
    text: str
    username: str | None = None
    like_count: int = 0
    timestamp: datetime | None = None
    # Filled in by preprocessing / classification
    clean: str = ""
    language: str = "en"
    category: str | None = None
    confidence: float | None = None
    topic: str | None = None
    extra: dict = field(default_factory=dict)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def strip_mentions(text: str) -> str:
    return normalize(MENTION.sub("", text))


def detect_language(text: str) -> str:
    """'hi' (Devanagari), 'hinglish' (romanised Hindi) or 'en'."""
    if DEVANAGARI.search(text):
        return "hi"
    words = [w.lower() for w in WORD.findall(text)]
    if not words:
        return "und"
    hits = sum(1 for w in words if w in lexicon.HINGLISH_MARKERS)
    if hits >= 2 or (hits == 1 and len(words) <= 4):
        return "hinglish"
    return "en"


def is_emoji_only(text: str) -> bool:
    return not WORD.search(text)


def is_spam(text: str) -> bool:
    lowered = text.lower()
    if lexicon.matches("SPAM", lowered):
        return True
    # Repeated-character noise like "😍😍😍😍😍😍😍😍" is praise, but "aaaaaaaa" or
    # a lone "💯💯💯" chain from growth pods is treated as spam.
    if re.fullmatch(r"(💯\s*)+", text.strip()):
        return True
    return False


def preprocess(comments: list[Comment], creator_username: str | None) -> tuple[list[Comment], dict]:
    """Returns (comments to classify, stats). Sets category for spam / own / dupes."""
    seen: set[tuple[str | None, str]] = set()
    out: list[Comment] = []
    stats = {"spam": 0, "own": 0, "duplicates": 0}
    creator = (creator_username or "").lower()
    for c in comments:
        c.clean = normalize(c.text)
        c.language = detect_language(c.clean)
        if creator and (c.username or "").lower() == creator:
            c.category, c.confidence = "own", 1.0
            stats["own"] += 1
            out.append(c)
            continue
        key = ((c.username or "").lower(), c.clean.lower())
        if c.username and key in seen:
            c.category, c.confidence = "spam", 0.9
            stats["duplicates"] += 1
            out.append(c)
            continue
        seen.add(key)
        if not c.clean or is_spam(c.clean):
            c.category, c.confidence = "spam", 0.9
            stats["spam"] += 1
        out.append(c)
    return out, stats
