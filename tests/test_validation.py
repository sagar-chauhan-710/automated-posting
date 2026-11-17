from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

VALID_MESSAGE = "Discover our new business platform today! https://example.com"


def test_valid_message_with_exactly_one_url():
    # Endpoint will attempt publishing; we only care that validation passes (not 422).
    response = client.post("/posting", json={"message": VALID_MESSAGE})
    assert response.status_code != 422


def test_empty_message():
    response = client.post("/posting", json={"message": ""})
    assert response.status_code == 422


def test_whitespace_only_message():
    response = client.post("/posting", json={"message": "   "})
    assert response.status_code == 422


def test_missing_message():
    response = client.post("/posting", json={})
    assert response.status_code == 422


def test_message_longer_than_200_characters():
    url = " https://example.com"
    message = ("A" * (201 - len(url))) + url
    assert len(message) > 200
    response = client.post("/posting", json={"message": message})
    assert response.status_code == 422


def test_message_without_url():
    response = client.post("/posting", json={"message": "Hello without a link"})
    assert response.status_code == 422


def test_message_with_two_urls():
    response = client.post(
        "/posting",
        json={"message": "See https://example.com and https://example.org"},
    )
    assert response.status_code == 422


def test_invalid_url_hostname():
    response = client.post(
        "/posting",
        json={"message": "Broken link https://"},
    )
    assert response.status_code == 422


def test_unsupported_url_scheme_javascript():
    response = client.post(
        "/posting",
        json={"message": "Bad scheme javascript:alert(1)"},
    )
    assert response.status_code == 422


def test_unsupported_url_scheme_ftp():
    response = client.post(
        "/posting",
        json={"message": "Bad scheme ftp://files.example.com/file"},
    )
    assert response.status_code == 422


def test_punctuation_after_url_is_not_second_url():
    response = client.post(
        "/posting",
        json={"message": "Check this out: https://example.com."},
    )
    assert response.status_code != 422


def test_url_with_whitespace_rejected():
    response = client.post(
        "/posting",
        json={"message": "Bad https://exa mple.com"},
    )
    assert response.status_code == 422


def test_empty_platforms_list_rejected():
    response = client.post(
        "/posting",
        json={"message": VALID_MESSAGE, "platforms": []},
    )
    assert response.status_code == 422


def test_invalid_platform_key_rejected():
    response = client.post(
        "/posting",
        json={"message": VALID_MESSAGE, "platforms": ["twitter"]},
    )
    assert response.status_code == 422
