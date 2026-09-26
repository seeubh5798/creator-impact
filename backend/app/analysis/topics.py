"""Rule-based topic tagging for questions, objections and buying-intent comments."""

import re

TOPICS: list[tuple[str, list[str]]] = [
    ("Price", [r"price", r"kitn[aei]", r"cost", r"rate", r"mehe?nga", r"expensive", r"costly", r"overpriced",
               r"worth", r"₹", r"कितन", r"दाम", r"कीमत", r"महं?ँ?गा"]),
    ("Where to buy", [r"link", r"kah?a+n?", r"where", r"available", r"amazon", r"nykaa", r"flipkart", r"myntra",
                      r"order", r"buy", r"milega", r"milegi", r"store", r"shop", r"लिंक", r"कहा"]),
    ("Discount codes", [r"discount", r"code", r"coupon", r"offer", r"sale"]),
    ("Delivery & COD", [r"deliver", r"shipping", r"\bcod\b", r"dispatch", r"courier", r"city", r"pincode"]),
    ("Skin & hair type", [r"oily", r"dry skin", r"sensitive", r"acne", r"skin type", r"combination", r"hair type",
                          r"frizzy", r"dandruff"]),
    ("Shade, size & variants", [r"shade", r"size", r"colou?r", r"variant", r"flavou?r", r"\bfit\b"]),
    ("Ingredients & safety", [r"vegan", r"fragrance", r"ingredient", r"safe", r"chemical", r"side effect",
                              r"allerg", r"rash", r"paraben", r"organic", r"cruelty"]),
    ("Results & durability", [r"work", r"result", r"last", r"effective", r"long", r"days", r"difference"]),
    ("How to use", [r"how to", r"daily", r"\buse\b", r"kaise", r"apply", r"routine", r"कैसे"]),
    ("Authenticity", [r"paid", r"sponsored", r"promotion", r"genuine", r"honest", r"fake", r"real review"]),
]

_compiled = [(name, [re.compile(p, re.IGNORECASE) for p in pats]) for name, pats in TOPICS]


def rule_topic(text: str, category: str) -> str | None:
    if category not in ("question", "objection", "buying_intent"):
        return None
    best, best_hits = None, 0
    for name, pats in _compiled:
        hits = sum(1 for p in pats if p.search(text))
        if hits > best_hits:
            best, best_hits = name, hits
    return best or "Other"
