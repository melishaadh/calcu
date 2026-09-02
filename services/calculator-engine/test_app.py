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


def test_add(client):
    resp = client.post("/api/calculate", json={"operation": "add", "operand1": 2, "operand2": 3})
    assert resp.status_code == 200
    assert resp.get_json()["result"] == 5.0


def test_subtract(client):
    resp = client.post("/api/calculate", json={"operation": "subtract", "operand1": 10, "operand2": 4})
    assert resp.status_code == 200
    assert resp.get_json()["result"] == 6.0


def test_multiply(client):
    resp = client.post("/api/calculate", json={"operation": "multiply", "operand1": 6, "operand2": 7})
    assert resp.status_code == 200
    assert resp.get_json()["result"] == 42.0


def test_divide(client):
    resp = client.post("/api/calculate", json={"operation": "divide", "operand1": 9, "operand2": 2})
    assert resp.status_code == 200
    assert resp.get_json()["result"] == 4.5


def test_divide_by_zero(client):
    resp = client.post("/api/calculate", json={"operation": "divide", "operand1": 1, "operand2": 0})
    assert resp.status_code == 400


def test_invalid_operation(client):
    resp = client.post("/api/calculate", json={"operation": "bogus", "operand1": 1, "operand2": 1})
    assert resp.status_code == 400


def test_missing_operand(client):
    resp = client.post("/api/calculate", json={"operation": "add", "operand1": 1})
    assert resp.status_code == 400


def test_non_numeric_operand(client):
    resp = client.post("/api/calculate", json={"operation": "add", "operand1": "x", "operand2": 1})
    assert resp.status_code == 400
