import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_dashboard_get():
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert "vitals" in data
    assert "actions" in data
    assert "sparkline" in data

def test_inbox_get():
    response = client.get("/api/inbox")
    assert response.status_code == 200
    data = response.json()
    assert "inbox" in data

def test_simulate_advance_invalid():
    response = client.post("/api/simulate/advance", json={"days_offset": 35})
    assert response.status_code == 400

def test_simulate_advance_valid():
    response = client.post("/api/simulate/advance", json={"days_offset": 5})
    assert response.status_code == 200
    data = response.json()
    assert "simulated_as_of" in data
    assert "new_balance" in data

if __name__ == "__main__":
    pytest.main(["-v", __file__])
