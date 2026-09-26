"""Keyword lexicons for the rule-based classifier (English, Hinglish, Hindi).

The rule classifier is the offline fallback and a sanity check for the LLM.
Patterns are matched against lower-cased, whitespace-normalised text.
"""

import re

BUYING_INTENT = [
    r"\bprice\b", r"\bprices\b", r"\bcost\b", r"\brate\b", r"\bkitne\b", r"\bkitna\b", r"\bkitni\b",
    r"\blink\b", r"\bbuy\b", r"\bbuying\b", r"\bbought\b", r"\bpurchase", r"\border(ed|ing)?\b",
    r"where (can|do|to) (i|we)?\s*(get|buy|find|order)", r"kah?a+n? (se|pe|par|milega|milegi|mile)",
    r"\bmilega\b", r"\bmilegi\b", r"\bchahiye\b", r"\bmangwa", r"\bneed (this|it|one)\b",
    r"\bwant (this|it|one)\b", r"\bdiscount\b", r"\bcoupon\b", r"\bcode\b", r"\bcod\b",
    r"\bavailable\b", r"\bin stock\b", r"\bshipping to\b", r"₹", r"\brs\.?\s?\d", r"\badd(ed)? to cart\b",
    r"कितने", r"कितना", r"कहाँ से", r"कहां से", r"लिंक", r"चाहिए", r"ऑर्डर", r"दाम", r"कीमत",
]

OBJECTION = [
    r"\bexpensive\b", r"\bcostly\b", r"\bmehe?nga\b", r"\boverpriced\b", r"not worth", r"\bwaste\b",
    r"\bscam\b", r"\bfake\b", r"didn'?t work", r"doesn'?t work", r"not working", r"\ballerg", r"\brash\b",
    r"side effect", r"\bbekaar\b", r"\bbekar\b", r"\bslow delivery\b", r"delivery .* slow", r"\btoo strong\b",
    r"\bpaid promotion\b", r"\bsponsored hai\b", r"\bbad quality\b", r"\bbroke\b", r"\breturn(ed)?\b",
    r"महंगा", r"महँगा", r"बेकार", r"नकली",
]

QUESTION = [
    r"\?\s*$", r"^(is|does|do|can|how|what|which|when|will|should|are|any)\b", r"\bkya\b", r"\bkaise\b",
    r"\bkab\b", r"\bkaun\b", r"\bkaunsa\b", r"\bsuitable\b", r"\bsuit (my|oily|dry|sensitive)",
    r"क्या", r"कैसे", r"कब",
]

PRAISE = [
    r"\blove", r"\bamazing\b", r"\bbeautiful\b", r"\bgorgeous\b", r"\bnice\b", r"\bsuperb\b", r"\bawesome\b",
    r"\bgreat\b", r"\bpretty\b", r"\bcute\b", r"\bqueen\b", r"\bking\b", r"\bbest\b", r"\bmast\b",
    r"\bbadhiya\b", r"\bbadiya\b", r"\bzabardast\b", r"\bkamaal\b", r"\bkhoobsurat\b", r"\baesthetic\b",
    r"\bfire\b", r"\bslay", r"\bwow\b", r"\bperfect\b", r"🔥", r"❤", r"😍", r"👑", r"💖", r"🥰", r"👏",
    r"सुंदर", r"बढ़िया", r"बहुत अच्छा",
]

SPAM = [
    r"follow (me|back|for)", r"check (my|out my) (profile|page|bio)", r"\bdm (for|me)\b.*(collab|promo)",
    r"promote (it|this|your)", r"\bearn \d", r"\bgiveaway\b.*(follow|dm)", r"\bcrypto\b", r"\bforex\b",
    r"\bf4f\b", r"\bl4l\b", r"\bsub4sub\b", r"visit my", r"https?://", r"www\.",
]

HINGLISH_MARKERS = {
    "kya", "hai", "hain", "ka", "ki", "ke", "se", "kaha", "kahan", "kitna", "kitne", "bhai", "yaar", "nahi",
    "bahut", "accha", "acha", "mujhe", "mera", "meri", "bhi", "karo", "karna", "chahiye", "milega", "ye", "yeh",
    "hoga", "thoda", "mast", "badhiya", "dedo", "kar", "wala", "wali", "abhi", "kab", "kaise",
}

_compiled: dict[str, list[re.Pattern]] = {}


def patterns(name: str) -> list[re.Pattern]:
    if name not in _compiled:
        _compiled[name] = [re.compile(p, re.IGNORECASE) for p in globals()[name]]
    return _compiled[name]


def matches(name: str, text: str) -> int:
    return sum(1 for p in patterns(name) if p.search(text))
