from types import SimpleNamespace

import pytest

from app.analysis.classifier import LLMClassifier, RuleClassifier
from app.analysis.preprocess import Comment, detect_language, preprocess
from app.analysis.scoring import ScoreInput, impact_score, percentile, ratio_subscore, verdict
from app.analysis.summarize import summarize_topics
from app.analysis.topics import rule_topic


@pytest.mark.parametrize("text,lang", [
    ("Price kya hai?", "hinglish"),
    ("कितने का है?", "hi"),
    ("Is it good for oily skin?", "en"),
    ("🔥🔥🔥", "und"),
    ("bhai link do", "hinglish"),
])
def test_detect_language(text, lang):
    assert detect_language(text) == lang


@pytest.mark.parametrize("text,category", [
    ("Price kya hai?", "buying_intent"),
    ("price please", "buying_intent"),
    ("Link do please", "buying_intent"),
    ("kahan se milega ye?", "buying_intent"),
    ("Ordered yesterday!", "buying_intent"),
    ("कितने का है?", "buying_intent"),
    ("Is there a discount code?", "buying_intent"),
    ("Is it good for oily skin?", "question"),
    ("Kya ye daily use kar sakte hain?", "question"),
    ("Too expensive yaar", "objection"),
    ("Bahut mehenga hai", "objection"),
    ("Didn't work for me honestly", "objection"),
    ("You look amazing!", "praise"),
    ("🔥🔥🔥", "praise"),
    ("Bahut badhiya", "praise"),
    ("Good morning", "other"),
    ("Follow me for more", "spam"),
])
def test_rule_classifier(text, category):
    c = Comment(comment_id="x", text=text, clean=text)
    RuleClassifier().classify([c])
    assert c.category == category, (text, c.category)


def test_preprocess_marks_spam_own_and_duplicates():
    comments = [
        Comment("1", "Check my profile 💯", username="bot1"),
        Comment("2", "Thank you all!", username="Creator"),
        Comment("3", "Price?", username="fan"),
        Comment("4", "Price?", username="fan"),
        Comment("5", "Price?", username="other_fan"),
        Comment("6", "💯💯💯", username="pod"),
    ]
    out, stats = preprocess(comments, "creator")
    cats = {c.comment_id: c.category for c in out}
    assert cats == {"1": "spam", "2": "own", "3": None, "4": "spam", "5": None, "6": "spam"}
    assert stats == {"spam": 2, "own": 1, "duplicates": 1}


def test_rule_topics():
    assert rule_topic("Price kitna hai?", "buying_intent") == "Price"
    assert rule_topic("Is it good for oily skin?", "question") == "Skin & hair type"
    assert rule_topic("Delivery to smaller cities is so slow", "objection") == "Delivery & COD"
    assert rule_topic("Love it", "praise") is None


def test_ratio_subscore_curve():
    assert ratio_subscore(1.0) == 50
    assert ratio_subscore(2.0) == 100
    assert ratio_subscore(0.5) == 0
    assert ratio_subscore(4.0) == 100
    assert ratio_subscore(None) is None


def test_impact_score_renormalises_missing_metrics():
    full, parts = impact_score(ScoreInput(0.15, 200, 100, 1000, 0.01, 100, 50, 1000, 0.01))
    # intent 100, saves 100, shares 100, reach 50, comment_rate 50
    assert abs(full - 87.5) <= 0.5
    only_intent, parts = impact_score(ScoreInput(0.075, None, None, None, None, None, None, None, None))
    assert only_intent == 50 and set(parts) == {"intent"}
    none, _ = impact_score(ScoreInput(None, None, None, None, None, None, None, None, None))
    assert none is None


def test_verdict_and_percentile():
    assert verdict(None, None) == "Not enough data yet"
    assert verdict(80, 0.14) == "Strong buying intent"
    assert verdict(80, 0.01) == "Outstanding performance"
    assert verdict(30, 0.01) == "Below this creator's usual"
    assert percentile(5, [1, 2, 3, 4, 10]) == 80
    assert percentile(None, [1]) is None
    assert percentile(1, []) is None


def test_summarize_exact_grouping():
    topics = [("Price", "price?")] * 5 + [("Where to buy", "link?")] * 3 + [("Other", "hmm")] * 9
    out = summarize_topics(topics, use_llm=False)
    assert [(t.label, t.count) for t in out] == [("Price", 5), ("Where to buy", 3)]


class FakeAnthropic:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0
        self.messages = self

    def create(self, **kwargs):
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=reply)])


def test_llm_classifier_parses_and_falls_back(monkeypatch):
    comments = [Comment(str(i), t, clean=t) for i, t in enumerate(["price?", "so pretty", "Is it vegan"])]
    reply = '```json\n[{"i":0,"c":"buying_intent","l":"en","conf":0.95,"t":"Price"},' \
            '{"i":1,"c":"praise","l":"en","conf":0.9,"t":null}]\n```'
    clf = LLMClassifier(client=FakeAnthropic([reply]))
    clf.classify(comments)
    assert [c.category for c in comments] == ["buying_intent", "praise", "question"]  # #2 missing -> rules
    assert comments[0].topic == "Price" and comments[1].topic is None

    broken = [Comment("9", "Too expensive", clean="Too expensive")]
    clf = LLMClassifier(client=FakeAnthropic([RuntimeError("overloaded")]))
    clf.classify(broken)
    assert broken[0].category == "objection" and clf.failed_batches == 1
