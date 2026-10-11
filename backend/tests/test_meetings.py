import uuid

import pytest
from sqlalchemy import select

from app.models import Item, Meeting

PAYLOAD = {
    "title": "Design review",
    "starts_at": "2026-10-09T10:30:00+03:00",
    "duration_minutes": 45,
    "participant_count": 3,
    "notes": "Review the agenda",
}


async def test_meeting_crud_and_task_regression(client, session):
    task = (await client.post("/api/v1/items", json={"name": "Keep this task"})).json()
    stored_task = await session.get(Item, uuid.UUID(task["id"]))
    before = {column.name: getattr(stored_task, column.name) for column in Item.__table__.columns}
    assert (await client.get("/api/v1/meetings")).json() == {"meetings": [], "total": 0}
    created = await client.post("/api/v1/meetings", json={**PAYLOAD, "title": "  Design review  "})
    assert created.status_code == 201
    meeting = created.json()
    assert meeting["title"] == "Design review"
    assert meeting["starts_at"] == "2026-10-09T07:30:00Z"
    assert meeting["created_at"] and meeting["updated_at"]
    assert "owner_id" not in meeting
    assert (await session.get(Meeting, uuid.UUID(meeting["id"]))).owner_id == "user-a"
    path = f"/api/v1/meetings/{meeting['id']}"
    assert (await client.get(path)).json() == meeting
    updated = await client.patch(path, json={"title": "Revised", "notes": None})
    assert updated.status_code == 200
    assert updated.json()["title"] == "Revised" and updated.json()["notes"] is None
    assert updated.json()["starts_at"] == meeting["starts_at"]
    assert (await client.get("/api/v1/meetings")).json()["total"] == 1
    assert (await client.delete(path)).status_code == 204
    assert (await client.get(path)).status_code == 404
    assert (await client.get("/api/v1/meetings")).json()["total"] == 0
    await session.refresh(stored_task)
    assert before == {
        column.name: getattr(stored_task, column.name) for column in Item.__table__.columns
    }
    assert (await client.get(f"/api/v1/items/{task['id']}")).json() == task


@pytest.mark.parametrize(
    "change",
    [
        {"title": ""},
        {"title": "   "},
        {"title": "x" * 121},
        {"title": None},
        {"starts_at": "2026-10-09T10:30:00"},
        {"starts_at": "invalid"},
        {"starts_at": "2026-02-30T10:00:00Z"},
        {"starts_at": None},
        {"starts_at": 12345},
        {"duration_minutes": 0},
        {"duration_minutes": 1441},
        {"duration_minutes": 1.5},
        {"duration_minutes": True},
        {"duration_minutes": "30"},
        {"duration_minutes": None},
        {"participant_count": 0},
        {"participant_count": 10001},
        {"participant_count": 1.5},
        {"participant_count": False},
        {"participant_count": None},
        {"notes": "x" * 2001},
        {"owner_id": "user-b"},
        {"id": str(uuid.uuid4())},
    ],
)
async def test_invalid_create_and_patch_are_rejected(client, change):
    created = (await client.post("/api/v1/meetings", json=PAYLOAD)).json()
    assert (await client.post("/api/v1/meetings", json={**PAYLOAD, **change})).status_code == 422
    path = f"/api/v1/meetings/{created['id']}"
    assert (await client.patch(path, json=change)).status_code == 422
    assert (await client.get(path)).json() == created


async def test_required_fields_and_optional_notes(client):
    for field in ("title", "starts_at", "duration_minutes", "participant_count"):
        payload = {key: value for key, value in PAYLOAD.items() if key != field}
        assert (await client.post("/api/v1/meetings", json=payload)).status_code == 422
    response = await client.post(
        "/api/v1/meetings", json={k: v for k, v in PAYLOAD.items() if k != "notes"}
    )
    assert response.status_code == 201 and response.json()["notes"] is None


async def test_ownership_isolation(client, session, tokens):
    a = (await client.post("/api/v1/meetings", json=PAYLOAD)).json()
    client.headers["Authorization"] = "Bearer " + tokens("user-b")
    b = (await client.post("/api/v1/meetings", json={**PAYLOAD, "title": "B private"})).json()
    listing = (await client.get("/api/v1/meetings")).json()
    assert listing["total"] == 1 and listing["meetings"][0]["id"] == b["id"]
    path = f"/api/v1/meetings/{a['id']}"
    assert (await client.get(path)).status_code == 404
    assert (await client.patch(path, json={"title": "Stolen"})).status_code == 404
    assert (await client.delete(path)).status_code == 404
    assert (
        await session.scalar(select(Meeting.title).where(Meeting.id == uuid.UUID(a["id"])))
        == PAYLOAD["title"]
    )
    client.headers["Authorization"] = "Bearer " + tokens("user-a")
    assert (await client.get(f"/api/v1/meetings/{b['id']}")).status_code == 404


@pytest.mark.parametrize("token", [None, "invalid"])
async def test_all_meeting_endpoints_require_access_token(client, token):
    client.headers.pop("Authorization", None)
    if token:
        client.headers["Authorization"] = "Bearer " + token
    path = f"/api/v1/meetings/{uuid.uuid4()}"
    for method, url, payload in (
        ("GET", "/api/v1/meetings", None),
        ("POST", "/api/v1/meetings", PAYLOAD),
        ("GET", path, None),
        ("PATCH", path, {"title": "x"}),
        ("DELETE", path, None),
    ):
        assert (await client.request(method, url, json=payload)).status_code == 401


async def test_pagination_and_deterministic_order(client):
    for day in (7, 9, 8):
        await client.post(
            "/api/v1/meetings",
            json={**PAYLOAD, "title": f"Day {day}", "starts_at": f"2026-10-{day:02d}T12:00:00Z"},
        )
    first = (await client.get("/api/v1/meetings", params={"limit": 2})).json()
    assert first["total"] == 3
    assert [m["title"] for m in first["meetings"]] == ["Day 9", "Day 8"]
    assert (await client.get("/api/v1/meetings", params={"offset": 2})).json()["meetings"][0][
        "title"
    ] == "Day 7"
    for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}):
        assert (await client.get("/api/v1/meetings", params=params)).status_code == 422
    for method in ("GET", "PATCH", "DELETE"):
        assert (
            await client.request(
                method, f"/api/v1/meetings/{uuid.uuid4()}", json={} if method == "PATCH" else None
            )
        ).status_code == 404


async def test_fold_instants_remain_distinct_and_patch_retains_precision(client):
    earlier = (
        await client.post(
            "/api/v1/meetings", json={**PAYLOAD, "starts_at": "2026-10-25T03:30:00.123+03:00"}
        )
    ).json()
    later = (
        await client.post(
            "/api/v1/meetings", json={**PAYLOAD, "starts_at": "2026-10-25T03:30:00+02:00"}
        )
    ).json()
    assert earlier["starts_at"] == "2026-10-25T00:30:00.123000Z"
    assert later["starts_at"] == "2026-10-25T01:30:00Z"
    patched = await client.patch(f"/api/v1/meetings/{earlier['id']}", json={"duration_minutes": 60})
    assert patched.json()["starts_at"] == earlier["starts_at"]
