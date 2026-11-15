"""Топ-артистів Spotify, щоб позначити кого слухати. Рекомендацій тут немає."""

from __future__ import annotations

from urllib.parse import urlencode

import httpx

from concertrip.config import settings

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
TOP_URL = "https://api.spotify.com/v1/me/top/artists"


def authorize_url(state: str) -> str:
    query = urlencode(
        {
            "client_id": settings.spotify_client_id,
            "response_type": "code",
            "redirect_uri": settings.spotify_redirect_uri,
            "scope": "user-top-read",
            "state": state,
        }
    )
    return f"{AUTH_URL}?{query}"


def exchange_code(code: str, client: httpx.Client | None = None) -> dict:
    own = client is None
    client = client or httpx.Client(timeout=20.0)
    try:
        response = client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.spotify_redirect_uri,
            },
            auth=(settings.spotify_client_id, settings.spotify_client_secret),
        )
        response.raise_for_status()
        return response.json()
    finally:
        if own:
            client.close()


def top_artists(access_token: str, client: httpx.Client | None = None) -> list[dict]:
    own = client is None
    client = client or httpx.Client(timeout=20.0)
    try:
        response = client.get(
            TOP_URL,
            params={"limit": 20, "time_range": "medium_term"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        payload = response.json()
    finally:
        if own:
            client.close()
    artists = []
    for item in payload.get("items") or []:
        name = (item.get("name") or "").strip()
        if not name:
            continue
        artists.append(
            {
                "name": name,
                "spotify_id": item.get("id"),
                "popularity": item.get("popularity"),
                "genres": item.get("genres") or [],
            }
        )
    return artists
