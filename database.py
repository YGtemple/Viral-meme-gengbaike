"""MongoDB storage layer — meme documents, user subscriptions, baseline data."""

from datetime import datetime
from typing import Optional

from memeclaw.config import config
from memeclaw.models.schemas import MemeDocument


class MemeDatabase:
    """Async MongoDB wrapper for memeclaw data persistence."""

    def __init__(self):
        self.client = None
        self.db = None

    async def connect(self):
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            self.client = AsyncIOMotorClient(config.mongo_uri, serverSelectionTimeoutMS=3000)
            self.db = self.client[config.db_name]
            # Ensure indexes
            await self.db["memes"].create_index("meme_name", unique=True)
            await self.db["memes"].create_index("aliases")
            await self.db["memes"].create_index("last_update_time")
            await self.db["subscriptions"].create_index("user_id", unique=True)
        except ImportError:
            self.db = None  # MongoDB is optional

    async def find_meme(self, name: str) -> Optional[MemeDocument]:
        """Look up a meme by name or alias. Returns None if not found."""
        if self.db is None:
            return None
        doc = await self.db["memes"].find_one({
            "$or": [{"meme_name": name}, {"aliases": name}]
        })
        if doc:
            doc.pop("_id", None)
            return MemeDocument(**doc)
        return None

    async def upsert_meme(self, meme: MemeDocument) -> None:
        """Insert or update a meme document."""
        if self.db is None:
            return
        meme.last_update_time = datetime.now()
        await self.db["memes"].update_one(
            {"meme_name": meme.meme_name},
            {"$set": meme.model_dump()},
            upsert=True,
        )

    async def add_subscriber(self, user_id: str, webhook_url: str = None, email: str = None) -> None:
        if self.db is None:
            return
        await self.db["subscriptions"].update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "subscribed_at": datetime.now(),
                "webhook_url": webhook_url,
                "email": email,
            }},
            upsert=True,
        )

    async def get_all_subscribers(self) -> list[dict]:
        if self.db is None:
            return []
        cursor = self.db["subscriptions"].find({})
        return [doc async for doc in cursor]
