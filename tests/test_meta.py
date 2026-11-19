"""Service endpoints, frontend delivery, security headers, demo data."""
import pytest

import crud
import demo_data
import main
from config import get_settings
from enums import ClientStatus, DealStage


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_config_lists_enums_from_backend(client):
    data = client.get("/api/config").json()
    assert data["deal_stages"] == [s.value for s in DealStage]
    assert data["client_statuses"] == [s.value for s in ClientStatus]
    assert set(data["closed_stages"]) == {"won", "lost"}


def test_demo_accounts_hidden_outside_demo_mode(client):
    data = client.get("/api/config").json()
    assert data["demo_mode"] is False
    assert data["demo_accounts"] == []


def test_demo_accounts_shown_in_demo_mode(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_mode", True)
    data = client.get("/api/config").json()
    assert {a["username"] for a in data["demo_accounts"]} == {"demo-admin", "anna", "jonas"}


def test_frontend_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_old_dashboard_url_redirects(client):
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/#/dashboard"


def test_security_headers(client):
    headers = client.get("/api/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["content-security-policy"].startswith("frame-ancestors")


def test_api_docs_available(client):
    assert client.get("/openapi.json").status_code == 200


# --- demo data ---

@pytest.fixture()
def seeded(db):
    demo_data.seed(db)
    return db


def test_demo_data_is_consistent(seeded):
    import models

    assert seeded.query(models.User).count() == len(demo_data.DEMO_ACCOUNTS)
    assert seeded.query(models.Client).count() == len(demo_data.COMPANIES)
    deals = seeded.query(models.Deal).all()
    assert len(deals) >= 20
    # Every deal's history ends in its current stage.
    for deal in deals:
        assert deal.stage_history[-1].to_stage == deal.stage
        assert deal.stage_history[0].from_stage is None


def test_demo_logins_work(client, seeded):
    for account in demo_data.DEMO_ACCOUNTS:
        response = client.post(
            "/api/auth/login", data={"username": account["username"], "password": account["password"]}
        )
        assert response.status_code == 200, account["username"]


def test_demo_dashboard_loads(client, seeded):
    admin = crud.get_user_by_username(seeded, "demo-admin")
    from conftest import auth_header

    data = client.get("/api/analytics/dashboard", headers=auth_header(admin)).json()
    assert data["total_deals_count"] > 0
    assert data["win_rate"] is not None


def test_demo_reset_removes_everything(seeded):
    import models

    demo_data.reset(seeded)
    assert seeded.query(models.User).count() == 0
    assert seeded.query(models.Deal).count() == 0


def test_demo_seed_is_reproducible(db):
    import models

    demo_data.seed(db)
    first = [(d.title, str(d.amount), d.stage) for d in db.query(models.Deal).order_by(models.Deal.id)]
    demo_data.reset(db)
    demo_data.seed(db)
    second = [(d.title, str(d.amount), d.stage) for d in db.query(models.Deal).order_by(models.Deal.id)]
    assert first == second


def test_app_title():
    assert main.app.title == "CRM API"
