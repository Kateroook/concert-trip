import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from concertrip.api.app import app
from concertrip.api.deps import get_db
from concertrip.db import Base


@pytest.fixture
def auth_client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'auth.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def register_and_verify(client: TestClient, email: str = "user@example.com") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct horse battery staple"},
    )
    assert response.status_code == 201
    verification_token = response.json()["verificationToken"]
    verified = client.post(
        "/api/v1/auth/verify-email", json={"token": verification_token}
    )
    assert verified.status_code == 200
    return response.json()


def test_auth_flow_protects_events_and_rotates_refresh_token(auth_client):
    client = auth_client
    register_and_verify(client)

    assert client.get("/api/v1/events").status_code == 401
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "USER@example.com", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    first_tokens = login.json()
    headers = {"Authorization": f"Bearer {first_tokens['accessToken']}"}

    assert client.get("/api/v1/auth/me", headers=headers).json()["email"] == "user@example.com"
    assert client.get("/api/v1/events", headers=headers).status_code == 200

    refresh = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first_tokens["refreshToken"]}
    )
    assert refresh.status_code == 200
    second_tokens = refresh.json()
    assert client.post(
        "/api/v1/auth/refresh", json={"refresh_token": first_tokens["refreshToken"]}
    ).status_code == 401

    assert client.post(
        "/api/v1/auth/logout", json={"refresh_token": second_tokens["refreshToken"]}
    ).status_code == 200
    assert client.post(
        "/api/v1/auth/refresh", json={"refresh_token": second_tokens["refreshToken"]}
    ).status_code == 401


def test_duplicate_email_and_unverified_login_are_rejected(auth_client):
    client = auth_client
    registration = client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "correct horse battery staple"},
    )
    assert registration.status_code == 201
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "correct horse battery staple"},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/register",
        json={"email": "USER@example.com", "password": "another password"},
    ).status_code == 409


def test_verification_token_is_one_time(auth_client):
    client = auth_client
    registration = client.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "correct horse battery staple"},
    )
    token = registration.json()["verificationToken"]
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 200
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 400
