"""Tasks: CRUD, ordering and filters."""
from datetime import datetime, timedelta, timezone

from conftest import auth_header, make_client, make_deal, make_task


def _deal(db, owner):
    return make_deal(db, make_client(db, owner=owner), owner=owner, title="Website")


def test_create_task_returns_deal_title(client, db, manager):
    deal = _deal(db, manager)
    response = client.post(
        "/api/tasks/",
        json={"title": "Send proposal", "deal_id": deal.id, "due_date": "2030-01-15T10:00:00+01:00"},
        headers=auth_header(manager),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["deal_title"] == "Website"
    assert body["is_done"] is False


def test_task_for_unknown_deal(client, admin_header):
    assert client.post("/api/tasks/", json={"title": "x", "deal_id": 999}, headers=admin_header).status_code == 404


def test_empty_title_is_rejected(client, db, manager):
    deal = _deal(db, manager)
    response = client.post("/api/tasks/", json={"title": "", "deal_id": deal.id}, headers=auth_header(manager))
    assert response.status_code == 422


def test_mark_done_and_filter(client, db, manager):
    deal = _deal(db, manager)
    task = make_task(db, deal, title="open one")
    make_task(db, deal, title="already done", is_done=True)

    client.patch(f"/api/tasks/{task.id}", json={"is_done": True}, headers=auth_header(manager))
    done = client.get("/api/tasks/", params={"is_done": True}, headers=auth_header(manager)).json()
    assert {t["title"] for t in done} == {"open one", "already done"}
    assert client.get("/api/tasks/", params={"is_done": False}, headers=auth_header(manager)).json() == []


def test_tasks_sorted_by_deadline_without_deadline_last(client, db, manager):
    deal = _deal(db, manager)
    now = datetime.now(timezone.utc)
    make_task(db, deal, title="no deadline")
    make_task(db, deal, title="later", due_date=now + timedelta(days=5))
    make_task(db, deal, title="sooner", due_date=now + timedelta(days=1))

    titles = [t["title"] for t in client.get("/api/tasks/", headers=auth_header(manager)).json()]
    assert titles == ["sooner", "later", "no deadline"]


def test_filter_by_deal(client, db, manager):
    first, second = _deal(db, manager), _deal(db, manager)
    make_task(db, first, title="a")
    make_task(db, second, title="b")
    response = client.get("/api/tasks/", params={"deal_id": second.id}, headers=auth_header(manager))
    assert [t["title"] for t in response.json()] == ["b"]


def test_delete_task(client, db, manager):
    task = make_task(db, _deal(db, manager))
    assert client.delete(f"/api/tasks/{task.id}", headers=auth_header(manager)).status_code == 204
    assert client.get(f"/api/tasks/{task.id}", headers=auth_header(manager)).status_code == 404


def test_timezone_of_due_date_is_kept(client, db, manager):
    """A deadline sent as 10:00 in Berlin must come back as the same moment."""
    deal = _deal(db, manager)
    body = client.post(
        "/api/tasks/",
        json={"title": "x", "deal_id": deal.id, "due_date": "2030-01-15T10:00:00+01:00"},
        headers=auth_header(manager),
    ).json()
    returned = datetime.fromisoformat(body["due_date"].replace("Z", "+00:00"))  # "Z" needs Python 3.11+
    assert returned.tzinfo is not None
    assert returned == datetime(2030, 1, 15, 9, 0, tzinfo=timezone.utc)
