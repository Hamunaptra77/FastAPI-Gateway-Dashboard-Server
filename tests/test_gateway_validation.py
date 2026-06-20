import datetime as dt

from app.models import License


def test_validate_license_success(client, seeded_license: License):
    response = client.get("/api/gateway/validate", headers={"X-License-Key": seeded_license.key})

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is True
    assert payload["email"] == "tester@example.com"
    assert payload["reason"] is None


def test_validate_license_missing_header(client):
    response = client.get("/api/gateway/validate")

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "http_error"
    assert "Missing X-License-Key header" in payload["error"]["message"]


def test_validate_license_expired(client, test_db_session, seeded_license: License):
    seeded_license.expires_at = dt.datetime.now(dt.UTC).replace(tzinfo=None) - dt.timedelta(days=1)
    test_db_session.add(seeded_license)
    test_db_session.commit()

    response = client.get("/api/gateway/validate", headers={"X-License-Key": seeded_license.key})

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["reason"] == "license_expired"


def test_validate_license_inactive(client, inactive_license: License):
    response = client.get("/api/gateway/validate", headers={"X-License-Key": inactive_license.key})

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["reason"] == "license_inactive"


def test_validate_license_nonexistent_key(client):
    response = client.get("/api/gateway/validate", headers={"X-License-Key": "LIC-DOES-NOT-EXIST"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["reason"] == "license_not_found"
