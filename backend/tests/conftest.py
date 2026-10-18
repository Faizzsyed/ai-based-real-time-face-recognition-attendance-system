"""Keep the backend suite independent of the developer's real MongoDB."""

import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def no_real_mongodb(monkeypatch):
    monkeypatch.setenv("MONGODB_URI", "")
    get_settings.cache_clear()

    def forbidden_client(*args, **kwargs):
        pytest.fail("Backend tests must use in-memory repositories, never a real MongoDB client")

    monkeypatch.setattr("app.db.mongo.MongoClient", forbidden_client)
    yield
    get_settings.cache_clear()
