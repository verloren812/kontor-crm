"""Clients: phone normalization, e-mail validation, duplicates, search."""
from unittest.mock import patch

import pytest

import crud
import schemas
from conftest import auth_header, make_client


def _create(client, header, **fields):
    payload = {"name": "Acme GmbH", "phone": "+49 151 1234567", **fields}
    return client.post("/api/clients/", json=payload, headers=header)


# --- phone normalization ---

@pytest.mark.parametrize(
    "raw",
    ["+49 151 1234567", "+49 (151) 123-45-67", "0049 151 1234567", "+49/151/1234567", " +491511234567 "],
)
def test_phone_is_normalized(raw):
    assert schemas.normalize_phone(raw) == "+491511234567"


@pytest.mark.parametrize("raw", ["", "abc", "12345", "+49 151 1234567 ext 5", "1" * 16])
def test_invalid_phone_is_rejected(raw):
    with pytest.raises(ValueError):
        schemas.normalize_phone(raw)


def test_same_number_written_differently_is_a_duplicate(client, manager_header):
    """Before normalization these two were "different" and both were saved."""
    assert _create(client, manager_header, phone="+49 151 1234567").status_code == 201
    response = _create(client, manager_header, name="Other", phone="+491511234567")
    assert response.status_code == 409


def test_created_client_has_normalized_phone(client, manager_header):
    body = _create(client, manager_header, phone="0049 (151) 123 45 67").json()
    assert body["phone"] == "+491511234567"


def test_race_condition_returns_409_not_500(client, db, manager_header):
    """
    Two parallel requests can both pass the "does this phone exist?" check.
    The second insert then hits the UNIQUE constraint; that must become a 409.
    """
    make_client(db, phone="+491511234567")
    with patch.object(crud, "get_client_by_phone", return_value=None):
        response = _create(client, manager_header, phone="+491511234567")
    assert response.status_code == 409


# --- e-mail ---

def test_invalid_email_is_rejected(client, manager_header):
    assert _create(client, manager_header, email="string").status_code == 422


def test_empty_email_is_stored_as_null(client, manager_header):
    body = _create(client, manager_header, email="").json()
    assert body["email"] is None


def test_valid_email_is_accepted(client, manager_header):
    assert _create(client, manager_header, email="info@acme.example").json()["email"] == "info@acme.example"


# --- update ---

def test_phone_can_be_corrected(client, db, manager):
    acme = make_client(db, owner=manager, phone="+491511111111")
    response = client.patch(
        f"/api/clients/{acme.id}", json={"phone": "+49 151 2222222"}, headers=auth_header(manager)
    )
    assert response.status_code == 200
    assert response.json()["phone"] == "+491512222222"


def test_phone_update_to_existing_number_is_rejected(client, db, manager):
    make_client(db, owner=manager, phone="+491511111111")
    second = make_client(db, owner=manager, phone="+491512222222")
    response = client.patch(
        f"/api/clients/{second.id}", json={"phone": "+49 151 1111111"}, headers=auth_header(manager)
    )
    assert response.status_code == 409


def test_saving_own_phone_again_is_allowed(client, db, manager):
    acme = make_client(db, owner=manager, phone="+491511111111")
    response = client.patch(
        f"/api/clients/{acme.id}", json={"phone": "+491511111111", "name": "Renamed"}, headers=auth_header(manager)
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed"


def test_partial_update_keeps_other_fields(client, db, manager):
    acme = make_client(db, owner=manager, email="old@acme.example")
    client.patch(f"/api/clients/{acme.id}", json={"name": "New name"}, headers=auth_header(manager))
    body = client.get(f"/api/clients/{acme.id}", headers=auth_header(manager)).json()
    assert body["email"] == "old@acme.example"


def test_status_endpoint(client, db, manager):
    acme = make_client(db, owner=manager)
    response = client.patch(
        f"/api/clients/{acme.id}/status", json={"status": "regular"}, headers=auth_header(manager)
    )
    assert response.json()["status"] == "regular"


def test_new_client_belongs_to_creator(client, manager, manager_header):
    assert _create(client, manager_header).json()["owner_id"] == manager.id


# --- list, search, filter ---

def test_search_by_name_phone_and_email(client, db, admin, admin_header):
    make_client(db, name="Nordlicht Logistik", phone="+491510000001")
    make_client(db, name="Bäckerei Sonnenkorn", phone="+491510000002", email="hello@sonnenkorn.example")

    def names(term):
        response = client.get("/api/clients/", params={"search": term}, headers=admin_header)
        return {c["name"] for c in response.json()}

    assert names("nordlicht") == {"Nordlicht Logistik"}
    assert names("0000002") == {"Bäckerei Sonnenkorn"}
    assert names("sonnenkorn.example") == {"Bäckerei Sonnenkorn"}


def test_filter_by_status(client, db, admin_header):
    make_client(db, name="a", status="new")
    make_client(db, name="b", status="regular")
    response = client.get("/api/clients/", params={"status": "regular"}, headers=admin_header)
    assert [c["name"] for c in response.json()] == ["b"]


def test_filter_with_unknown_status_is_rejected(client, admin_header):
    assert client.get("/api/clients/", params={"status": "maybe"}, headers=admin_header).status_code == 422


def test_newest_clients_first_and_pagination(client, db, admin_header):
    for index in range(5):
        make_client(db, name=f"c{index}")
    page = client.get("/api/clients/", params={"skip": 1, "limit": 2}, headers=admin_header).json()
    assert [c["name"] for c in page] == ["c3", "c2"]


def test_unknown_client_returns_404(client, admin_header):
    assert client.get("/api/clients/999", headers=admin_header).status_code == 404
