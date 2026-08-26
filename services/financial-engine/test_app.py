import math

import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_simple_interest(client):
    resp = client.post(
        "/api/financial",
        json={"operation": "simple_interest", "principal": 1000, "rate": 10, "time": 2},
    )
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["interest"] == 200.0
    assert data["total_amount"] == 1200.0


def test_compound_interest(client):
    resp = client.post(
        "/api/financial",
        json={"operation": "compound_interest", "principal": 1000, "rate": 10, "time": 1, "compounds_per_year": 1},
    )
    data = resp.get_json()
    assert resp.status_code == 200
    assert math.isclose(data["total_amount"], 1100.0, rel_tol=1e-6)


def test_emi(client):
    resp = client.post(
        "/api/financial",
        json={"operation": "emi", "principal": 100000, "annual_rate": 10, "tenure_months": 12},
    )
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["emi"] > 0


def test_invalid_operation(client):
    resp = client.post("/api/financial", json={"operation": "bogus"})
    assert resp.status_code == 400


def test_missing_field(client):
    resp = client.post("/api/financial", json={"operation": "simple_interest", "principal": 1000})
    assert resp.status_code == 400
