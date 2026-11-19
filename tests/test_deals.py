"""Deals: CRUD, ownership and the stage history."""
from conftest import auth_header, make_client, make_deal


def test_create_deal_returns_client_and_owner_names(client, db, manager):
    acme = make_client(db, owner=manager, name="Acme GmbH")
    response = client.post(
        "/api/deals/",
        json={"title": "Online shop", "amount": "12500.00", "client_id": acme.id},
        headers=auth_header(manager),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["client_name"] == "Acme GmbH"
    assert body["owner_name"] == manager.username
    assert body["stage"] == "new"
    assert body["amount"] == 12500.0


def test_deal_for_unknown_client(client, admin_header):
    response = client.post("/api/deals/", json={"title": "x", "amount": "1", "client_id": 999}, headers=admin_header)
    assert response.status_code == 404


def test_deal_created_by_admin_belongs_to_clients_manager(client, db, admin, manager):
    """Otherwise the manager would not see a deal of their own client."""
    acme = make_client(db, owner=manager)
    response = client.post(
        "/api/deals/", json={"title": "x", "amount": "1", "client_id": acme.id}, headers=auth_header(admin)
    )
    assert response.json()["owner_id"] == manager.id


def test_deal_for_unassigned_client_belongs_to_creator(client, db, manager):
    acme = make_client(db, owner=None)
    response = client.post(
        "/api/deals/", json={"title": "x", "amount": "1", "client_id": acme.id}, headers=auth_header(manager)
    )
    assert response.json()["owner_id"] == manager.id


def test_filter_by_stage_and_client(client, db, admin, admin_header):
    acme = make_client(db, owner=admin)
    other = make_client(db, owner=admin)
    make_deal(db, acme, owner=admin, title="a", stage="new")
    make_deal(db, acme, owner=admin, title="b", stage="won")
    make_deal(db, other, owner=admin, title="c", stage="won")

    won = client.get("/api/deals/", params={"stage": "won"}, headers=admin_header).json()
    assert {d["title"] for d in won} == {"b", "c"}
    of_acme = client.get("/api/deals/", params={"client_id": acme.id}, headers=admin_header).json()
    assert {d["title"] for d in of_acme} == {"a", "b"}


def test_update_deal(client, db, manager):
    deal = make_deal(db, make_client(db, owner=manager), owner=manager)
    response = client.patch(
        f"/api/deals/{deal.id}", json={"title": "Renamed", "amount": "99.90"}, headers=auth_header(manager)
    )
    assert response.json()["title"] == "Renamed"
    assert response.json()["amount"] == 99.9


def test_manager_deletes_own_deal(client, db, manager):
    deal = make_deal(db, make_client(db, owner=manager), owner=manager)
    assert client.delete(f"/api/deals/{deal.id}", headers=auth_header(manager)).status_code == 204
    assert client.get(f"/api/deals/{deal.id}", headers=auth_header(manager)).status_code == 404


# --- stage history ---

def test_new_deal_has_initial_history_entry(client, db, manager):
    acme = make_client(db, owner=manager)
    deal_id = client.post(
        "/api/deals/", json={"title": "x", "amount": "1", "client_id": acme.id}, headers=auth_header(manager)
    ).json()["id"]

    history = client.get(f"/api/deals/{deal_id}/history", headers=auth_header(manager)).json()
    assert [(h["from_stage"], h["to_stage"]) for h in history] == [(None, "new")]


def test_stage_changes_are_recorded_in_order(client, db, manager):
    deal = make_deal(db, make_client(db, owner=manager), owner=manager)
    for stage in ("qualified", "proposal", "won"):
        client.patch(f"/api/deals/{deal.id}", json={"stage": stage}, headers=auth_header(manager))

    history = client.get(f"/api/deals/{deal.id}/history", headers=auth_header(manager)).json()
    assert [(h["from_stage"], h["to_stage"]) for h in history] == [
        (None, "new"),
        ("new", "qualified"),
        ("qualified", "proposal"),
        ("proposal", "won"),
    ]
    assert history[-1]["changed_by_name"] == manager.username


def test_editing_other_fields_does_not_add_history(client, db, manager):
    deal = make_deal(db, make_client(db, owner=manager), owner=manager)
    client.patch(f"/api/deals/{deal.id}", json={"title": "x"}, headers=auth_header(manager))
    client.patch(f"/api/deals/{deal.id}", json={"stage": "new"}, headers=auth_header(manager))  # same stage

    history = client.get(f"/api/deals/{deal.id}/history", headers=auth_header(manager)).json()
    assert len(history) == 1


def test_history_is_deleted_with_the_deal(client, db, admin, manager):
    import models

    deal = make_deal(db, make_client(db, owner=manager), owner=manager)
    client.patch(f"/api/deals/{deal.id}", json={"stage": "won"}, headers=auth_header(manager))
    client.delete(f"/api/deals/{deal.id}", headers=auth_header(admin))
    assert db.query(models.DealStageChange).count() == 0
