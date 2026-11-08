from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from concertrip.api.app import app
from concertrip.api.deps import get_db
from concertrip.db import Base
from concertrip.sources.seed import import_seed


def test_events_api_filters_and_pagination(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'api.db'}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    import_seed(session_factory=session_factory)

    def override_get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        registration = client.post(
            "/api/v1/auth/register",
            json={"email": "events@example.com", "password": "correct horse battery staple"},
        )
        verification = client.post(
            "/api/v1/auth/verify-email",
            json={"token": registration.json()["verificationToken"]},
        )
        assert verification.status_code == 200
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "events@example.com", "password": "correct horse battery staple"},
        )
        headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

        response = client.get("/api/v1/events?page_size=2", headers=headers)
        assert response.status_code == 200
        assert response.json()["total"] == 5
        assert len(response.json()["items"]) == 2
        assert response.json()["items"][0]["eventDate"] == "2027-05-28"

        response = client.get("/api/v1/events?country=GB&status=low", headers=headers)
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["city"] == "London"

        response = client.get("/api/v1/events?q=Rotterdam", headers=headers)
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["artist"] == "Tame Impala"

        response = client.get("/api/v1/events?q=missing", headers=headers)
        assert response.json() == {"items": [], "total": 0, "page": 1, "pageSize": 20}
    finally:
        app.dependency_overrides.clear()
