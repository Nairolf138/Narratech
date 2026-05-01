from fastapi.testclient import TestClient

from src.api.app import app


client = TestClient(app)


def test_generation_invalid_payload() -> None:
    response = client.post("/v1/generations", json={"prompt": ""})
    assert response.status_code == 400


def test_generation_nominal_and_status_retrieval() -> None:
    payload = {
        "prompt": "Raconte une aventure spatiale positive.",
        "user_context": {
            "preferences": {"genre": "sci-fi", "ambiance": "uplifting", "rhythm": "medium", "duration_sec": 30, "language": "fr"},
            "constraints": {"age_rating": "all", "culture": "global", "exclusions": []},
            "identity": {"session_id": "session_001"},
        },
    }
    create_response = client.post("/v1/generations", json=payload)
    assert create_response.status_code == 200
    request_id = create_response.json()["request_id"]

    status_response = client.get(f"/v1/generations/{request_id}")
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["status"] == "succeeded"
    assert body["narrative"]["request_id"] == request_id
