def test_redirect_to_setup_if_no_token(client):
    response = client.get("/slides", follow_redirects=False)
    assert 300 <= response.status_code < 400
    assert response.next_request.url.path == "/setup"
