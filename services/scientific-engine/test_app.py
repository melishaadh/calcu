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
    assert resp.get_json()["status"] == "healthy"


def test_sqrt(client):
    resp = client.post("/api/scientific", json={"operation": "sqrt", "value": 16})
    assert resp.status_code == 200
    assert resp.get_json()["result"] == 4.0


def test_sin(client):
    resp = client.post("/api/scientific", json={"operation": "sin", "value": 90})
    assert resp.status_code == 200
    assert math.isclose(resp.get_json()["result"], 1.0, abs_tol=1e-6)


def test_invalid_operation(client):
    resp = client.post("/api/scientific", json={"operation": "bogus", "value": 1})
    assert resp.status_code == 400


def test_missing_value(client):
    resp = client.post("/api/scientific", json={"operation": "sqrt"})
    assert resp.status_code == 400


def test_negative_sqrt_domain_error(client):
    resp = client.post("/api/scientific", json={"operation": "sqrt", "value": -4})
    assert resp.status_code == 400
