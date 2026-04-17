"""
MongoDB connection manager for chat history domain.
"""
from typing import Optional

from pymongo import MongoClient
from pymongo.database import Database

from core.config import settings


class MongoChatClient:
    """Manages MongoDB lifecycle for chat history collections."""

    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.db: Optional[Database] = None
        self.enabled: bool = bool(settings.ENABLE_MONGO_CHAT_HISTORY)

    async def connect(self):
        """Connect to MongoDB when chat history mode is enabled."""
        if not self.enabled:
            return

        self.client = MongoClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=5000,
            maxPoolSize=100,
            minPoolSize=5,
        )
        self.client.admin.command("ping")
        self.db = self.client[settings.MONGODB_DB_NAME]

    async def disconnect(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None

    def get_db(self) -> Optional[Database]:
        """Return active database handle."""
        return self.db


mongo_chat_client = MongoChatClient()
