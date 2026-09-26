import httpx
import respx

from app.instagram.client import GraphInstagramClient, exchange_code

BASE = "https://graph.instagram.com/v23.0"


@respx.mock
def test_insights_fall_back_to_single_metrics():
    def insights(request):
        metric = request.url.params["metric"]
        if "," in metric or metric == "shares":
            return httpx.Response(400, json={"error": {"message": "unsupported metric", "code": 100}})
        return httpx.Response(200, json={"data": [{"name": metric, "values": [{"value": 10}]}]})

    respx.get(f"{BASE}/m1/insights").mock(side_effect=insights)
    out = GraphInstagramClient("tok").get_media_insights("m1")
    assert out == {"reach": 10, "views": 10, "likes": 10, "comments": 10, "saves": 10, "shares": None}


@respx.mock
def test_comments_paginate_and_flatten_replies():
    def comments(request):
        if request.url.params.get("after") == "abc":
            return httpx.Response(200, json={"data": [{"id": "3", "text": "c"}]})
        return httpx.Response(200, json={
            "data": [{"id": "1", "text": "a", "replies": {"data": [{"id": "1r", "text": "reply"}]}},
                     {"id": "2", "text": "b"}],
            "paging": {"next": f"{BASE}/m1/comments?after=abc&access_token=tok"},
        })

    respx.get(url__startswith=f"{BASE}/m1/comments").mock(side_effect=comments)
    out = GraphInstagramClient("tok").list_comments("m1", 100)
    assert [c["id"] for c in out] == ["1", "1r", "2", "3"]


@respx.mock
def test_auth_error_is_detected():
    respx.get(f"{BASE}/me").mock(return_value=httpx.Response(400, json={"error": {"message": "expired", "code": 190}}))
    try:
        GraphInstagramClient("tok").get_profile()
    except Exception as e:
        assert e.is_auth_error
    else:
        raise AssertionError("expected error")


@respx.mock
def test_exchange_code_handles_new_response_shape():
    respx.post("https://api.instagram.com/oauth/access_token").mock(return_value=httpx.Response(
        200, json={"data": [{"access_token": "short", "user_id": 42, "permissions": "x"}]}))
    respx.get("https://graph.instagram.com/access_token").mock(return_value=httpx.Response(
        200, json={"access_token": "long", "token_type": "bearer", "expires_in": 5183944}))
    result = exchange_code("abc#_")
    assert result.access_token == "long" and result.user_id == "42" and result.expires_at is not None
