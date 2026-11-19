"""Dashboard figures: pipeline, win rate, overdue tasks, per-manager revenue."""
from datetime import datetime, timedelta, timezone

import models
from conftest import auth_header, make_client, make_deal, make_task


def _dashboard(client, user):
    response = client.get("/api/analytics/dashboard", headers=auth_header(user))
    assert response.status_code == 200
    return response.json()


def test_empty_dashboard(client, admin):
    data = _dashboard(client, admin)
    assert data["total_deals_count"] == 0
    assert data["win_rate"] is None  # nothing closed yet: no rate rather than 0 %
    assert data["deals_by_stage"] == []


def test_pipeline_figures(client, db, admin):
    acme = make_client(db, owner=admin)
    for stage, amount in (("new", "100"), ("proposal", "200"), ("won", "300"), ("won", "400"), ("lost", "500")):
        make_deal(db, acme, owner=admin, stage=stage, amount=amount)

    data = _dashboard(client, admin)
    assert data["total_deals_count"] == 5
    assert data["total_amount"] == 1500
    assert data["open_amount"] == 300   # new + proposal
    assert data["won_amount"] == 700
    assert data["win_rate"] == round(2 / 3, 4)  # 2 won out of 3 closed
    assert data["clients_count"] == 1


def test_stages_follow_pipeline_order(client, db, admin):
    acme = make_client(db, owner=admin)
    for stage in ("won", "new", "negotiation", "lost", "qualified"):
        make_deal(db, acme, owner=admin, stage=stage)
    stages = [row["stage"] for row in _dashboard(client, admin)["deals_by_stage"]]
    assert stages == ["new", "qualified", "negotiation", "won", "lost"]


def test_won_and_lost_flags(client, db, admin):
    acme = make_client(db, owner=admin)
    for stage in ("won", "lost", "new"):
        make_deal(db, acme, owner=admin, stage=stage)
    rows = {row["stage"]: row for row in _dashboard(client, admin)["deals_by_stage"]}
    assert (rows["won"]["is_won"], rows["won"]["is_closed"]) == (True, True)
    assert (rows["lost"]["is_won"], rows["lost"]["is_closed"]) == (False, True)
    assert (rows["new"]["is_won"], rows["new"]["is_closed"]) == (False, False)


def test_unknown_stage_from_old_data_does_not_break_report(client, db, admin):
    """A stage written by an older version or outside the API must not cause a 500."""
    acme = make_client(db, owner=admin)
    db.add(models.Deal(title="legacy", amount=50, stage="approval", client_id=acme.id, owner_id=admin.id))
    db.commit()

    rows = {row["stage"]: row for row in _dashboard(client, admin)["deals_by_stage"]}
    assert (rows["approval"]["is_won"], rows["approval"]["is_closed"]) == (False, False)


def test_manager_sees_only_own_figures(client, db, manager, other_manager):
    make_deal(db, make_client(db, owner=manager), owner=manager, amount="100")
    make_deal(db, make_client(db, owner=other_manager), owner=other_manager, amount="900")

    data = _dashboard(client, manager)
    assert data["total_amount"] == 100
    assert data["clients_count"] == 1
    assert data["revenue_by_manager"] is None  # company-wide figures are admin only


def test_overdue_and_upcoming_tasks(client, db, admin):
    deal = make_deal(db, make_client(db, owner=admin), owner=admin)
    now = datetime.now(timezone.utc)
    make_task(db, deal, title="overdue", due_date=now - timedelta(days=2))
    make_task(db, deal, title="overdue but done", due_date=now - timedelta(days=1), is_done=True)
    make_task(db, deal, title="upcoming", due_date=now + timedelta(days=1))
    make_task(db, deal, title="someday")

    data = _dashboard(client, admin)
    assert [t["title"] for t in data["overdue_tasks"]] == ["overdue"]
    assert data["overdue_total"] == 1
    assert [t["title"] for t in data["upcoming_tasks"]] == ["upcoming", "someday"]


def test_overdue_list_is_capped_but_total_is_exact(db, admin):
    import crud

    deal = make_deal(db, make_client(db, owner=admin), owner=admin)
    past = datetime.now(timezone.utc) - timedelta(days=1)
    for index in range(5):
        make_task(db, deal, title=f"t{index}", due_date=past)

    data = crud.get_dashboard_data(db, owner_id=None, overdue_limit=3)
    assert len(data["overdue_tasks"]) == 3
    assert data["overdue_total"] == 5


def test_revenue_by_manager(client, db, admin, manager, other_manager):
    make_deal(db, make_client(db, owner=manager), owner=manager, stage="won", amount="1000")
    make_deal(db, make_client(db, owner=manager), owner=manager, stage="new", amount="500")
    make_deal(db, make_client(db, owner=other_manager), owner=other_manager, stage="won", amount="3000")
    make_deal(db, make_client(db), owner=None, stage="new", amount="10")

    rows = _dashboard(client, admin)["revenue_by_manager"]
    assert [(r["username"], r["won_amount"], r["total_amount"]) for r in rows] == [
        ("jonas", 3000, 3000),
        ("anna", 1000, 1500),
        ("Unassigned", 0, 10),
    ]
