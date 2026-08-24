"""Optional synchronous MongoDB connection used by FastAPI sync routes."""

import logging

from pymongo import MongoClient
from pymongo.database import Database

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.indexes import initialize_phase2_indexes

logger = logging.getLogger(__name__)


class MongoConnection:
    def __init__(self) -> None:
        self.client: MongoClient | None = None
        self.database: Database | None = None
        self.status = "not_configured"
        self.database_name: str | None = None

    def configure(self) -> None:
        settings = get_settings()
        self.close()
        self.database_name = settings.mongodb_database
        if not settings.mongodb_uri:
            self.status = "not_configured"
            return
        try:
            client = MongoClient(
                settings.mongodb_uri,
                serverSelectionTimeoutMS=1500,
                connectTimeoutMS=1500,
                tz_aware=True,
            )
            client.admin.command("ping")
            database = client[settings.mongodb_database]
            initialize_phase2_indexes(database)
            self.client = client
            self.database = database
            self.status = "connected"
            logger.info("Database connected database=%s",settings.mongodb_database)
        except Exception:
            self.status = "disconnected"
            self.client = None
            self.database = None
            logger.warning("MongoDB is unavailable; continuing without database features.")

    def require_database(self) -> Database:
        if self.status != "connected" or self.database is None:
            logger.error("Database unavailable")
            raise AppError("DATABASE_UNAVAILABLE", "The academic database is unavailable.", 503)
        return self.database

    def close(self) -> None:
        if self.client is not None:
            self.client.close()
        self.client = None
        self.database = None


mongo = MongoConnection()
