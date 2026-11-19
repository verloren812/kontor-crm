"""
Access control: managers see their own and unassigned records, admins see all.

The first test pins down a real bug: get_clients() accepted owner_id but never
applied it, so every manager received the company's entire client base.
"""
from conftest import auth_header, make_client, make_deal, make_task


def test_manager_sees_own_and_unassigned_clients(client, db, manager, other_manager):
    make_client(db, owner=manager, name="mine")
    make_client(db, owner=other_manager, name="foreign")
    make_client(db, owner=None, name="unassigned")

    response = client.get("/api/clients/", headers=auth_header(manager))
    assert response.status_code == 200
    assert {c["name"] for c in response.json()} == {"mine", "unassigned"}


def test_admin_sees_all_clients(client, db, admin, manager, other_manager):
    make_client(db, owner=manager, name="mine")
    make_client(db, owner=other_manager, name="foreign")
    make_client(db, owner=None, name="unassigned")

    response = client.get("/api/clients/", headers=auth_header(admin))
    assert {c["name"] for c in response.json()} == {"mine", "foreign", "unassigned"}


def test_foreign_client_returns_404_not_403(client, db, manager, other_manager):
    foreign = make_client(db, owner=other_manager)
    response = client.get(f"/api/clients/{foreign.id}", headers=auth_header(manager))
    # 404, not 403: a foreign record must not even be confirmed to exist.
    assert response.status_code == 404


def test_manager_cannot_edit_foreign_client(client, db, manager, other_manager):
    foreign = make_client(db, owner=other_manager)
    response = client.patch(f"/api/clients/{foreign.id}", json={"name": "x"}, headers=auth_header(manager))
    assert response.status_code == 404


def test_only_admin_deletes_clients(client, db, manager):
    own = make_client(db, owner=manager)
    assert client.delete(f"/api/clients/{own.id}", headers=auth_header(manager)).status_code == 403


def test_admin_deletes_client_with_deals_and_tasks(client, db, admin, manager):
    own = make_client(db, owner=manager)
    deal = make_deal(db, own, owner=manager)
    make_task(db, deal)

    assert client.delete(f"/api/clients/{own.id}", headers=auth_header(admin)).status_code == 204
    assert client.get("/api/deals/", headers=auth_header(admin)).json() == []
    assert client.get("/api/tasks/", headers=auth_header(admin)).json() == []


def test_manager_sees_only_accessible_deals(client, db, manager, other_manager):
    mine = make_deal(db, make_client(db, owner=manager), owner=manager, title="mine")
    make_deal(db, make_client(db, owner=other_manager), owner=other_manager, title="foreign")

    titles = {d["title"] for d in client.get("/api/deals/", headers=auth_header(manager)).json()}
    assert titles == {"mine"}
    assert client.get(f"/api/deals/{mine.id}", headers=auth_header(manager)).status_code == 200


def test_manager_cannot_open_foreign_deal_or_its_history(client, db, manager, other_manager):
    foreign = make_deal(db, make_client(db, owner=other_manager), owner=other_manager)
    assert client.get(f"/api/deals/{foreign.id}", headers=auth_header(manager)).status_code == 404
    assert client.get(f"/api/deals/{foreign.id}/history", headers=auth_header(manager)).status_code == 404


def test_manager_cannot_create_deal_for_foreign_client(client, db, manager, other_manager):
    foreign = make_client(db, owner=other_manager)
    response = client.post(
        "/api/deals/", json={"title": "x", "amount": "10", "client_id": foreign.id}, headers=auth_header(manager)
    )
    assert response.status_code == 404


def test_manager_sees_only_tasks_of_accessible_deals(client, db, manager, other_manager):
    make_task(db, make_deal(db, make_client(db, owner=manager), owner=manager), title="mine")
    foreign_task = make_task(
        db, make_deal(db, make_client(db, owner=other_manager), owner=other_manager), title="foreign"
    )

    titles = {t["title"] for t in client.get("/api/tasks/", headers=auth_header(manager)).json()}
    assert titles == {"mine"}
    assert client.get(f"/api/tasks/{foreign_task.id}", headers=auth_header(manager)).status_code == 404
    assert client.delete(f"/api/tasks/{foreign_task.id}", headers=auth_header(manager)).status_code == 404


def test_employee_list_is_admin_only(client, manager_header):
    assert client.get("/api/users/", headers=manager_header).status_code == 403


def test_admin_cannot_demote_themselves(client, admin, admin_header):
    response = client.patch(f"/api/users/{admin.id}/role", json={"role": "manager"}, headers=admin_header)
    assert response.status_code == 400


def test_other_admin_can_be_demoted_while_one_remains(client, db, admin, admin_header):
    from conftest import create_user
    from enums import Role

    second = create_user(db, "second", "long-enough-password", Role.ADMIN)
    response = client.patch(f"/api/users/{second.id}/role", json={"role": "manager"}, headers=admin_header)
    assert response.status_code == 200
    assert response.json()["role"] == "manager"


def test_admin_promotes_manager(client, manager, admin_header):
    response = client.patch(f"/api/users/{manager.id}/role", json={"role": "admin"}, headers=admin_header)
    assert response.json()["role"] == "admin"


def test_role_change_for_unknown_user(client, admin_header):
    assert client.patch("/api/users/999/role", json={"role": "admin"}, headers=admin_header).status_code == 404


def test_requests_without_token_are_rejected(client):
    for path in ("/api/clients/", "/api/deals/", "/api/tasks/", "/api/analytics/dashboard"):
        assert client.get(path).status_code == 401
