from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from concertrip.api.routes.auth import router as auth_router
from concertrip.api.routes.artists import router as artists_router
from concertrip.api.routes.events import router as events_router
from concertrip.api.routes.recommendations import actions_router, router as recommendations_router
from concertrip.api.routes.spotify import preferences_router, router as spotify_router
from concertrip.config import settings

app = FastAPI(title="ConcerTrip API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(events_router)
app.include_router(auth_router)
app.include_router(spotify_router)
app.include_router(preferences_router)
app.include_router(recommendations_router)
app.include_router(actions_router)
app.include_router(artists_router)
