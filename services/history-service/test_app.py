import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from datetime import datetime, timedelta, timezone

import pytest

import app as app_module

app_module.engine = app_module.create_engine(
    "sqlite:///:memory:", connect_args={"check_same_thread": False}
)
app_module.SessionLocal.configure(bind=app_module.engine)
app_module.Base.metadata.create_all(app_module.engine)

flask_app = app_module.app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def clean_table():
    """Every test starts with an empty table so retention-window assertions are reliable."""
    session = app_module.SessionLocal()
    session.query(app_module.CalculationHistory).delete()
    session.commit()
    app_module.SessionLocal.remove()
    yield


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_create_and_list_history(client):
    resp = client.post(
        "/api/history",
        json={"expression": "2 + 2", "result": 4.0, "service_type": "calculator"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["expression"] == "2 + 2"
    assert data["result"] == 4.0

    resp = client.get("/api/history")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] >= 1


def test_create_missing_field(client):
    resp = client.post("/api/history", json={"expression": "2 + 2"})
    assert resp.status_code == 400


def test_filter_by_service_type(client):
    client.post(
        "/api/history",
        json={"expression": "6 × 7", "result": 42.0, "service_type": "calculator"},
    )
    resp = client.get("/api/history?service_type=calculator")
    data = resp.get_json()
    assert all(item["service_type"] == "calculator" for item in data["history"])


def test_history_excludes_records_older_than_retention_window(client):
    session = app_module.SessionLocal()
    stale = app_module.CalculationHistory(
        expression="1 + 1",
        result=2.0,
        service_type="calculator",
        created_at=datetime.now(timezone.utc) - timedelta(days=app_module.HISTORY_RETENTION_DAYS + 1),
    )
    session.add(stale)
    session.commit()
    app_module.SessionLocal.remove()

    resp = client.get("/api/history")
    data = resp.get_json()
    assert all(item["expression"] != "1 + 1" for item in data["history"])


def test_cleanup_old_history_deletes_stale_rows():
    session = app_module.SessionLocal()
    stale = app_module.CalculationHistory(
        expression="9 - 9",
        result=0.0,
        service_type="calculator",
        created_at=datetime.now(timezone.utc) - timedelta(days=app_module.HISTORY_RETENTION_DAYS + 1),
    )
    session.add(stale)
    session.commit()
    app_module.SessionLocal.remove()

    deleted = app_module.cleanup_old_history()
    assert deleted >= 1
