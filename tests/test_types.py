"""
Data types: money and time.

Both are cheap to get right on an empty database and expensive once there is
data, so they are pinned down by tests.
"""
from datetime import timezone
from decimal import Decimal

import pytest
from sqlalchemy import DateTime, Numeric

import models
from conftest import make_client, make_deal


@pytest.mark.parametrize(
    "table,column",
    [
        ("users", "created_at"),
        ("clients", "created_at"), ("clients", "updated_at"),
        ("deals", "created_at"), ("deals", "updated_at"),
        ("deal_stage_changes", "changed_at"),
        ("tasks", "due_date"), ("tasks", "created_at"), ("tasks", "updated_at"),
    ],
)
def test_all_dates_are_timezone_aware(table, column):
    col = models.Base.metadata.tables[table].c[column]
    column_type = getattr(col.type, "impl", col.type)  # UTCDateTime wraps DateTime
    assert isinstance(column_type, DateTime)
    assert column_type.timezone is True, f"{table}.{column} lost its time zone"


def test_deal_amount_is_numeric_not_float():
    col = models.Base.metadata.tables["deals"].c["amount"]
    assert isinstance(col.type, Numeric)
    assert (col.type.precision, col.type.scale) == (12, 2)
    assert col.nullable is False


@pytest.mark.parametrize(
    "table,column",
    [("clients", "status"), ("deals", "stage"), ("deals", "amount"), ("tasks", "is_done")],
)
def test_required_columns_are_not_null_with_server_default(table, column):
    """
    An ORM default alone does not protect rows written outside the app,
    and the response schemas treat these fields as required.
    """
    col = models.Base.metadata.tables[table].c[column]
    assert col.nullable is False
    assert col.server_default is not None


def test_utcnow_is_timezone_aware():
    now = models.utcnow()
    assert now.tzinfo is not None
    assert now.utcoffset() == timezone.utc.utcoffset(None)


def test_column_default_is_timezone_aware():
    default = models.Base.metadata.tables["clients"].c["created_at"].default
    assert default.arg(None).tzinfo is not None


def test_amounts_do_not_lose_cents(client, db, admin, admin_header):
    """
    Three deals of 10 cents must add up to exactly 0.30.
    With Float the sum was 0.30000000000000004.
    """
    acme = make_client(db, owner=admin)
    for _ in range(3):
        response = client.post(
            "/api/deals/", json={"title": "small", "amount": "0.10", "client_id": acme.id}, headers=admin_header
        )
        assert response.status_code == 201

    total = client.get("/api/analytics/dashboard", headers=admin_header).json()["total_amount"]
    assert total == 0.30


def test_amount_is_stored_as_decimal(db, admin):
    make_deal(db, make_client(db, owner=admin), owner=admin, amount="1500.50")
    stored = db.query(models.Deal).first().amount
    assert isinstance(stored, Decimal)
    assert stored == Decimal("1500.50")


@pytest.mark.parametrize(
    "amount",
    [
        "-1",              # negative amount
        "10.005",          # three decimal places
        "99999999999.99",  # 13 digits, more than NUMERIC(12, 2)
    ],
)
def test_invalid_amount_is_rejected(client, db, admin, admin_header, amount):
    acme = make_client(db, owner=admin)
    response = client.post(
        "/api/deals/", json={"title": "d", "amount": amount, "client_id": acme.id}, headers=admin_header
    )
    assert response.status_code == 422


def test_unknown_stage_is_rejected(client, db, admin, admin_header):
    acme = make_client(db, owner=admin)
    response = client.post(
        "/api/deals/",
        json={"title": "d", "amount": "1", "stage": "almost_won", "client_id": acme.id},
        headers=admin_header,
    )
    assert response.status_code == 422


def test_unknown_client_status_is_rejected(client, admin_header):
    response = client.post(
        "/api/clients/", json={"name": "k", "phone": "+491511234567", "status": "maybe"}, headers=admin_header
    )
    assert response.status_code == 422
