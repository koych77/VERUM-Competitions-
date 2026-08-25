from datetime import UTC, datetime, timedelta
from uuid import uuid4

from conftest import login_headers


def event_payload(*, allow_full=True, allow_short=True, allow_coach=True):
    today = datetime.now(UTC).date()
    return {
        "title": f"Test event {uuid4().hex[:8]}",
        "event_date": (today + timedelta(days=30)).isoformat(),
        "place": "Минск",
        "description": "Integration test",
        "image_url": None,
        "registration_opens_at": (today - timedelta(days=1)).isoformat(),
        "registration_closes_at": (today + timedelta(days=10)).isoformat(),
        "status": "open",
        "is_republic_championship": False,
        "allow_full_registration": allow_full,
        "allow_short_registration": allow_short,
        "allow_coach_registration": allow_coach,
        "nominations": [
            {
                "title": "Breaking Open",
                "min_age": 0,
                "max_age": 99,
                "gender_rule": "any",
                "battle_type": "solo",
                "experience": "",
                "description": "",
                "is_active": True,
                "sort_order": 10,
            }
        ],
    }


def participant_payload(telegram_id=2001):
    return {
        "user": {"telegram_id": telegram_id, "telegram_username": "participant"},
        "profile": {
            "full_name": "Иванов Иван",
            "nickname": "FLOW",
            "birth_date": "2012-04-15",
            "gender": "male",
            "phone": "+375291111111",
            "city": "Минск",
            "club": "VERUM",
            "trainer": "Тренер Тест",
        },
        "team_name": None,
        "team_members": None,
        "nomination_ids": [],
    }


def create_event(client, admin_headers, **flags):
    response = client.post("/api/events/admin", headers=admin_headers, json=event_payload(**flags))
    assert response.status_code == 200, response.text
    return response.json()


def test_admin_requires_signed_session(client):
    assert client.get("/api/events/admin").status_code == 401
    forged = client.get("/api/events/admin", headers={"X-Telegram-Id": "1001"})
    assert forged.status_code == 401
    missing_api = client.get("/api/does-not-exist")
    assert missing_api.status_code == 404
    assert missing_api.headers["content-type"].startswith("application/json")


def test_registration_ownership_idempotency_and_safe_delete(client, admin_headers, user_headers):
    event = create_event(client, admin_headers)
    payload = participant_payload()
    payload["nomination_ids"] = [event["nominations"][0]["id"]]

    first = client.post(f"/api/events/{event['id']}/register/full", headers=user_headers, json=payload)
    assert first.status_code == 200, first.text
    second = client.post(f"/api/events/{event['id']}/register/full", headers=user_headers, json=payload)
    assert second.status_code == 200, second.text
    assert first.json()["id"] == second.json()["id"]

    my_registrations = client.get("/api/registrations/me", headers=user_headers)
    assert my_registrations.status_code == 200
    assert len(my_registrations.json()) == 1
    assert my_registrations.json()[0]["event_title"] == event["title"]

    other_headers = login_headers(client, 2002)
    assert client.get("/api/registrations/me", headers=other_headers).json() == []
    forbidden_profile = client.get("/api/profiles/participant/2001", headers=other_headers)
    assert forbidden_profile.status_code == 403

    spoofed = participant_payload(2002)
    spoofed["nomination_ids"] = payload["nomination_ids"]
    spoofed_response = client.post(f"/api/events/{event['id']}/register/full", headers=user_headers, json=spoofed)
    assert spoofed_response.status_code == 403

    admin_spoof = client.post(f"/api/events/{event['id']}/register/full", headers=admin_headers, json=payload)
    assert admin_spoof.status_code == 403

    admin_profile_spoof = client.post(
        "/api/profiles/participant",
        headers=admin_headers,
        json={"user_in": payload["user"], "profile": payload["profile"]},
    )
    assert admin_profile_spoof.status_code == 403

    delete_response = client.delete(f"/api/events/admin/{event['id']}", headers=admin_headers)
    assert delete_response.status_code == 409
    assert "архив" in delete_response.json()["detail"].lower()


def test_server_enforces_disabled_registration_type(client, admin_headers, user_headers):
    event = create_event(client, admin_headers, allow_full=False)
    payload = participant_payload()
    payload["nomination_ids"] = [event["nominations"][0]["id"]]

    response = client.post(f"/api/events/{event['id']}/register/full", headers=user_headers, json=payload)
    assert response.status_code == 403


def test_event_rejects_registration_after_event_date(client, admin_headers):
    payload = event_payload()
    payload["registration_closes_at"] = (datetime.now(UTC).date() + timedelta(days=31)).isoformat()

    response = client.post("/api/events/admin", headers=admin_headers, json=payload)

    assert response.status_code == 400
    assert "даты мероприятия" in response.json()["detail"]


def test_coach_batch_is_atomic_and_idempotent(client, admin_headers):
    coach_headers = login_headers(client, 3001)
    event = create_event(client, admin_headers)
    nomination_id = event["nominations"][0]["id"]
    payload = {
        "user": {"telegram_id": 3001, "telegram_username": "coach"},
        "coach": {"full_name": "Тренер Тест", "phone": None, "city": "Минск", "club": "VERUM"},
        "registrations": [
            {
                "student": {
                    "full_name": "Ученик Тест",
                    "nickname": "SPIN",
                    "birth_date": "2013-05-20",
                    "gender": "female",
                    "city": "Минск",
                    "club": "VERUM",
                    "trainer": "Тренер Тест",
                },
                "nomination_ids": [nomination_id],
                "team_name": None,
                "team_members": None,
            }
        ],
    }

    first = client.post(f"/api/events/{event['id']}/register/coach", headers=coach_headers, json=payload)
    second = client.post(f"/api/events/{event['id']}/register/coach", headers=coach_headers, json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json()[0]["id"] == second.json()[0]["id"]

    profile = client.get("/api/profiles/coach/3001", headers=coach_headers).json()
    students = client.get(f"/api/profiles/coach/{profile['id']}/students", headers=coach_headers).json()
    assert len(students) == 1
