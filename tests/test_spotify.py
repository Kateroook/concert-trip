from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from concertrip.api.app import app
from concertrip.api.deps import get_db
from concertrip.api.services import spotify
from concertrip.config import settings
from concertrip.db import Base
from concertrip.models import ExternalAccount, MusicPreference


@pytest.fixture
def spotify_client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'spotify.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        with session_factory() as session:
            yield session

    original = {
        "client_id": settings.spotify_client_id,
        "client_secret": settings.spotify_client_secret,
        "redirect_uri": settings.spotify_redirect_uri,
        "encryption_key": settings.spotify_token_encryption_key,
    }
    object.__setattr__(settings, "spotify_client_id", "test-client")
    object.__setattr__(settings, "spotify_client_secret", "test-secret")
    object.__setattr__(settings, "spotify_redirect_uri", "http://test/callback")
    object.__setattr__(settings, "spotify_token_encryption_key", "test-encryption-key")
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app), session_factory
    finally:
        app.dependency_overrides.clear()
        for name, value in original.items():
            object.__setattr__(settings, f"spotify_{name}", value)


def _authenticated_client(client: TestClient):
    registration = client.post(
        "/api/v1/auth/register",
        json={"email": "spotify@example.com", "password": "correct horse battery staple"},
    )
    client.post(
        "/api/v1/auth/verify-email",
        json={"token": registration.json()["verificationToken"]},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "spotify@example.com", "password": "correct horse battery staple"},
    )
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


def test_spotify_oauth_state_and_status(spotify_client, monkeypatch):
    client, session_factory = spotify_client
    headers = _authenticated_client(client)
    authorize = client.get("/api/v1/integrations/spotify/authorize", headers=headers)
    assert authorize.status_code == 200
    query = parse_qs(urlparse(authorize.json()["authorizeUrl"]).query)
    state = query["state"][0]
    assert "user-top-read" in query["scope"][0]

    monkeypatch.setattr(
        spotify,
        "_token_request",
        lambda code=None, refresh_token=None: {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_in": 3600,
        },
    )
    monkeypatch.setattr(
        spotify,
        "_spotify_get",
        lambda access_token, path, params=None: {"account_id": "spotify-account"}
        if path == "/me"
        else {},
    )
    callback = client.get(
        f"/api/v1/integrations/spotify/callback?code=code&state={state}",
        follow_redirects=False,
    )
    assert callback.status_code == 303
    assert callback.headers["location"].startswith("concertrip://spotify/callback")
    assert client.get(
        "/api/v1/integrations/spotify/callback?code=code&state=" + state,
        follow_redirects=False,
    ).status_code == 303

    status = client.get("/api/v1/integrations/spotify/status", headers=headers)
    assert status.status_code == 200
    assert status.json()["connected"] is True
    assert status.json()["preferenceCount"] == 0

    with Session(session_factory.kw["bind"]) as session:
        account = session.scalar(select(ExternalAccount))
        assert account is not None
        assert account.access_token_encrypted != "access-token"


def test_spotify_sync_is_idempotent(spotify_client, monkeypatch):
    client, _ = spotify_client
    headers = _authenticated_client(client)
    state = parse_qs(
        urlparse(client.get("/api/v1/integrations/spotify/authorize", headers=headers).json()["authorizeUrl"]).query
    )["state"][0]
    monkeypatch.setattr(
        spotify,
        "_token_request",
        lambda code=None, refresh_token=None: {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_in": 3600,
        },
    )
    monkeypatch.setattr(
        spotify,
        "_spotify_get",
        lambda access_token, path, params=None: (
            {"account_id": "spotify-account"}
            if path == "/me"
            else {"items": [{"id": "artist-1", "name": "Tame Impala", "genres": ["rock"]}]}
            if path == "/me/top/artists"
            else {"items": [{"track": {"artists": [{"id": "artist-1", "name": "Tame Impala"}]}}]}
        ),
    )
    assert client.get(
        f"/api/v1/integrations/spotify/callback?code=code&state={state}",
        follow_redirects=False,
    ).status_code == 303
    first = client.post("/api/v1/integrations/spotify/sync", headers=headers)
    second = client.post("/api/v1/integrations/spotify/sync", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["imported"] == 4
    assert second.json()["imported"] == 4
    preferences = client.get("/api/v1/preferences/music", headers=headers)
    assert preferences.status_code == 200
    assert len(preferences.json()) == 4
