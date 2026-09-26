"""Deterministic fake Instagram account so the whole product works without Meta approval.

Used when DEMO_MODE=true and a user signs in with "Try the demo". Everything is
generated from a seed, so the same demo account always returns the same data.
"""

import random
from datetime import datetime, timedelta, timezone

DEMO_USERNAME = "demo.creator"

BRANDS = ["GlowLab", "Snackify", "UrbanThread"]

TEMPLATES = {
    "buying_intent": [
        "Price kya hai?", "price please", "Link do please", "Where can I buy this?", "kahan se milega ye?",
        "Ordered yesterday!", "Just ordered mine", "Need this asap", "Isko kaha se order karein?",
        "Link in bio?", "Mujhe bhi chahiye", "Is there a discount code?", "कितने का है?", "Is it available on Amazon?",
        "Want this so bad, link?", "COD available hai?", "Kitne ka hai bhai?", "Buying this today",
    ],
    "question": [
        "Is it good for oily skin?", "Does it suit sensitive skin?", "Kya ye daily use kar sakte hain?",
        "How long does it last?", "Is it vegan?", "Which shade are you wearing?", "Does it work for men too?",
        "Kya isme fragrance hai?", "Size chart kaisa hai?", "How is the delivery time?",
    ],
    "objection": [
        "Too expensive yaar", "Bahut mehenga hai", "Delivery to smaller cities is so slow",
        "The fragrance is too strong for me", "Didn't work for me honestly", "Not worth the price",
        "Paid promotion obviously", "Mehenga hai thoda",
    ],
    "praise": [
        "You look amazing!", "Love this 😍", "Superb video", "🔥🔥🔥", "Bahut badhiya", "So pretty ❤️",
        "Mast hai", "Your editing is top notch", "Queen 👑", "Beautiful", "This is so aesthetic", "Loved it",
    ],
    "other": [
        "First comment", "Hi from Pune", "Where is this location?", "Song name?", "Waiting for next video",
        "@friend look at this", "Good morning", "Nice background",
    ],
    "spam": [
        "Follow me for more", "Check my profile 💯", "DM for collab", "Promote it on @growthpage",
        "💯💯💯", "Nice pic follow back", "Earn 5000 daily, check bio",
    ],
}

ORGANIC_MIX = {"buying_intent": 0.02, "question": 0.06, "objection": 0.02, "praise": 0.55, "other": 0.25, "spam": 0.10}
SPONSORED_MIX = {"buying_intent": 0.15, "question": 0.20, "objection": 0.06, "praise": 0.37, "other": 0.15, "spam": 0.07}


class DemoInstagramClient:
    def __init__(self, ig_user_id: str = "demo-0001"):
        self.ig_user_id = ig_user_id
        self.seed = sum(ord(c) for c in ig_user_id)
        self._media = self._build_media()

    def get_profile(self) -> dict:
        return {
            "user_id": self.ig_user_id,
            "username": DEMO_USERNAME,
            "account_type": "MEDIA_CREATOR",
            "profile_picture_url": None,
            "followers_count": 184_000,
            "media_count": len(self._media),
        }

    def _build_media(self) -> list[dict]:
        rng = random.Random(self.seed)
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        media = []
        for i in range(24):
            sponsored = i in (1, 6, 13)
            posted = now - timedelta(days=2 + i * 3, hours=rng.randint(0, 12))
            brand = BRANDS[[1, 6, 13].index(i)] if sponsored else None
            caption = (
                f"Trying the new {brand} launch 💫 #ad #collab @{brand.lower()}" if sponsored
                else rng.choice(["Sunday vibes", "Get ready with me", "Weekend in Goa", "My morning routine",
                                 "Outfit of the day", "Q&A time!", "Street food tour", "Skincare shelf tour"])
            )
            media.append({
                "id": f"{self.ig_user_id}-m{i:02d}",
                "caption": caption,
                "media_type": "VIDEO" if i % 3 != 2 else "IMAGE",
                "media_product_type": "REELS" if i % 3 != 2 else "FEED",
                "permalink": f"https://www.instagram.com/reel/DEMO{i:02d}/",
                "thumbnail_url": None,
                "timestamp": posted.strftime("%Y-%m-%dT%H:%M:%S+0000"),
                "_sponsored": sponsored,
            })
        return media

    def list_media(self, limit: int = 50) -> list[dict]:
        out = []
        for m in self._media[:limit]:
            ins = self.get_media_insights(m["id"])
            out.append({k: v for k, v in m.items() if not k.startswith("_")} |
                       {"like_count": ins["likes"], "comments_count": ins["comments"]})
        return out

    def _media_by_id(self, media_id: str) -> dict:
        for m in self._media:
            if m["id"] == media_id:
                return m
        raise KeyError(media_id)

    def get_media_insights(self, media_id: str) -> dict:
        m = self._media_by_id(media_id)
        rng = random.Random(f"{self.seed}-{media_id}")
        reach = rng.randint(90_000, 160_000)
        boost = 1.3 if m["_sponsored"] else 1.0
        reach = int(reach * boost)
        comments = len(self._comment_plan(media_id))
        return {
            "reach": reach,
            "views": int(reach * rng.uniform(1.4, 2.2)),
            "likes": int(reach * rng.uniform(0.04, 0.07)),
            "comments": comments,
            "saves": int(reach * rng.uniform(0.008, 0.014) * (2.0 if m["_sponsored"] else 1.0)),
            "shares": int(reach * rng.uniform(0.005, 0.009) * (1.6 if m["_sponsored"] else 1.0)),
        }

    def _comment_plan(self, media_id: str) -> list[tuple[str, str]]:
        m = self._media_by_id(media_id)
        rng = random.Random(f"{self.seed}-{media_id}-c")
        n = rng.randint(400, 700) if m["_sponsored"] else rng.randint(120, 300)
        mix = SPONSORED_MIX if m["_sponsored"] else ORGANIC_MIX
        cats, weights = zip(*mix.items())
        return [(c, rng.choice(TEMPLATES[c])) for c in rng.choices(cats, weights=weights, k=n)]

    def list_comments(self, media_id: str, max_comments: int) -> list[dict]:
        m = self._media_by_id(media_id)
        posted = datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
        rng = random.Random(f"{self.seed}-{media_id}-t")
        out = []
        for idx, (_, text) in enumerate(self._comment_plan(media_id)[:max_comments]):
            out.append({
                "id": f"{media_id}-c{idx:04d}",
                "text": text,
                "username": f"viewer_{rng.randint(1, 9999)}",
                "like_count": rng.choices([0, 1, 2, 5, 20], weights=[60, 20, 10, 7, 3])[0],
                "timestamp": (posted + timedelta(minutes=rng.randint(1, 60 * 72))).strftime("%Y-%m-%dT%H:%M:%S+0000"),
            })
        return out
