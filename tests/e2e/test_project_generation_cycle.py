from fastapi.testclient import TestClient

from src.api.app import app


client = TestClient(app)


def test_full_project_cycle_create_generate_review_regenerate() -> None:
    create_response = client.post("/v1/generations", json={"prompt": "Créer une histoire sur un phare."})
    assert create_response.status_code == 200
    created = create_response.json()
    project_id = created["project_id"]
    first_generation_id = created["generation_id"]

    history_response = client.get(f"/v1/projects/{project_id}/generations")
    assert history_response.status_code == 200
    history = history_response.json()
    assert history["count"] >= 1
    assert any(item["generation_id"] == first_generation_id for item in history["items"])

    replay_response = client.post(f"/v1/projects/{project_id}/generations/{first_generation_id}/replay")
    assert replay_response.status_code == 200
    replayed = replay_response.json()
    second_generation_id = replayed["generation_id"]
    assert replayed["version"] > created["version"]

    compare_response = client.get(
        f"/v1/projects/{project_id}/compare",
        params={"left": first_generation_id, "right": second_generation_id},
    )
    assert compare_response.status_code == 200
    compared = compare_response.json()
    assert compared["left"]["generation_id"] == first_generation_id
    assert compared["right"]["generation_id"] == second_generation_id
    assert compared["diff"]["version_delta"] >= 1
