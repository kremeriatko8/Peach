from sqlalchemy import text
from test_meetings import PAYLOAD

AGENDA = {
    "items": [{"topic": "Pricing", "owner": "Олена", "minutes": 15}],
    "action_items": [{"task": "Compare", "owner": "Taras", "due": "2026-10-16"}],
    "language": "uk",
}


async def path(client):
    meeting = (await client.post("/api/v1/meetings", json=PAYLOAD)).json()
    return f"/api/v1/meetings/{meeting['id']}/agenda"


async def test_manual_crud_provenance_and_meeting_atomicity(client, session):
    url = await path(client)
    assert (await client.get(url)).json() is None
    first = (await client.put(url, json=AGENDA)).json()
    assert first["ai_suggestion"] is None
    suggestion = {
        "agenda": {**AGENDA, "title": None, "starts_at": None, "duration_minutes": None},
        "model": "amazon.nova-lite-v1:0",
        "prompt_version": "agenda-v1",
    }
    saved = await client.put(url, json={**AGENDA, "ai_suggestion": suggestion})
    assert saved.status_code == 200
    corrected = {**AGENDA, "items": [{"topic": "Corrected", "owner": "Олена", "minutes": 20}]}
    edited = (await client.put(url, json=corrected)).json()
    assert edited["ai_suggestion"] == suggestion and edited["items"][0]["topic"] == "Corrected"
    assert await session.scalar(text("SELECT count(*) FROM agendas")) == 1
    assert (await client.put(url, json={**corrected, "meeting": {"title": ""}})).status_code == 422
    assert (await client.get(url.rsplit("/", 1)[0])).json()["title"] == PAYLOAD["title"]
    assert (
        await client.put(url, json={**corrected, "meeting": {"title": "Reviewed"}})
    ).status_code == 200
    assert (await client.get(url.rsplit("/", 1)[0])).json()["title"] == "Reviewed"
    await client.delete(url.rsplit("/", 1)[0])
    assert await session.scalar(text("SELECT count(*) FROM agendas")) == 0


async def test_agenda_ownership_and_auth(client, tokens):
    url = await path(client)
    await client.put(url, json=AGENDA)
    client.headers["Authorization"] = "Bearer " + tokens("user-b")
    for method in ("GET", "PUT"):
        assert (
            await client.request(method, url, json=AGENDA if method == "PUT" else None)
        ).status_code == 404
    client.headers.pop("Authorization")
    for method in ("GET", "PUT"):
        assert (
            await client.request(method, url, json=AGENDA if method == "PUT" else None)
        ).status_code == 401


async def test_invalid_nested_values_are_rejected(client):
    url = await path(client)
    for change in (
        {"items": [{"topic": " "}]},
        {"items": [{"topic": "X", "minutes": 0}]},
        {"action_items": [{"task": "X", "due": "tomorrow"}]},
        {"language": " "},
        {"owner_id": "user-b"},
        {"ai_suggestion": {"model": "fake"}},
    ):
        assert (await client.put(url, json={**AGENDA, **change})).status_code == 422
