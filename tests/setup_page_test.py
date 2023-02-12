def test_error_on_empty_client_id(client):
    response = client.post("/setup", data={"client_id": "", "client_secret": "abc"})
    assert response.status_code == 200
    assert b"Client ID is required" in response.content


def test_error_on_empty_client_secret(client):
    response = client.post("/setup", data={"client_id": "abc", "client_secret": ""})
    assert response.status_code == 200
    assert b"Client Secret is required" in response.content
