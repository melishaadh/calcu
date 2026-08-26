import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

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


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_create_and_list_history(client):
    resp = client.post(
        "/api/history",
        json={"expression": "sqrt(16)", "result": 4.0, "service_type": "scientific"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["expression"] == "sqrt(16)"
    assert data["result"] == 4.0

    resp = client.get("/api/history")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] >= 1


def test_create_missing_field(client):
    resp = client.post("/api/history", json={"expression": "sqrt(16)"})
    assert resp.status_code == 400


def test_filter_by_service_type(client):
    client.post(
        "/api/history",
        json={"expression": "EMI(P=1000)", "result": 88.0, "service_type": "financial"},
    )
    resp = client.get("/api/history?service_type=financial")
    data = resp.get_json()
    assert all(item["service_type"] == "financial" for item in data["history"])
