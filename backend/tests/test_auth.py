import time

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth import get_verifier


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "malformed",
        "signature",
        "expired",
        "issuer",
        "client",
        "id",
        "empty-sub",
        "unknown-key",
        "algorithm",
        "basic",
    ]
    + ["missing-" + name for name in ("exp", "iss", "sub", "client_id", "token_use")],
)
async def test_invalid_tokens_are_401(client, tokens, case):
    token = tokens()
    if case == "missing":
        client.headers.clear()
    elif case == "malformed":
        token = "not-a-jwt"
    elif case == "signature":
        token = tokens(key=rsa.generate_private_key(public_exponent=65537, key_size=2048))
    elif case == "expired":
        token = tokens(changes={"exp": int(time.time()) - 1})
    elif case == "issuer":
        token = tokens(changes={"iss": "https://untrusted.example"})
    elif case == "client":
        token = tokens(changes={"client_id": "other-client"})
    elif case == "id":
        token = tokens(changes={"token_use": "id"})
    elif case == "empty-sub":
        token = tokens(sub=" ")
    elif case == "unknown-key":
        token = tokens(headers={"kid": "unknown"})
    elif case == "algorithm":
        import jwt

        token = jwt.encode(
            {"sub": "user-a"}, "a" * 32, algorithm="HS256", headers={"kid": "test-key"}
        )
    elif case.startswith("missing-"):
        token = tokens(remove=[case.removeprefix("missing-")])
    if case != "missing":
        client.headers["Authorization"] = ("Basic " if case == "basic" else "Bearer ") + token
    response = await client.get("/api/v1/items")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "/api/v1/items", None),
        ("POST", "/api/v1/items", {"name": "x"}),
        ("GET", "/api/v1/items/11111111-1111-1111-1111-111111111111", None),
        ("PATCH", "/api/v1/items/11111111-1111-1111-1111-111111111111", {"name": "x"}),
        ("DELETE", "/api/v1/items/11111111-1111-1111-1111-111111111111", None),
    ],
)
async def test_every_crud_route_requires_auth(client, method, path, body):
    client.headers.clear()
    response = await client.request(method, path, json=body)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_verifier_reuses_snapshot_without_network(client, tokens, monkeypatch):
    import urllib.request

    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *a, **kw: pytest.fail("Runtime network forbidden")
    )
    first = get_verifier()
    assert (await client.get("/api/v1/items")).status_code == 200
    assert (await client.get("/api/v1/items")).status_code == 200
    assert get_verifier() is first
    assert first.verify(tokens()).sub == "user-a"


async def test_health_remains_public(client):
    client.headers.clear()
    assert (await client.get("/health")).status_code == 200
    assert (await client.get("/api/v1/health/ready")).status_code == 200
