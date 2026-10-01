import aiosqlite
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)
DB_PATH = "crypto_alerts.db"

class AlertService:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    async def init_db(self):
        """Initializes the SQLite database and creates alerts table if not exists."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    target_price REAL NOT NULL,
                    condition TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
            logger.info("⚡ SQLite Alerts Database initialized.")

    async def add_alert(self, user_id: int, symbol: str, target_price: float, condition: str) -> int:
        """Adds a new price alert."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO alerts (user_id, symbol, target_price, condition) VALUES (?, ?, ?, ?)",
                (user_id, symbol.upper(), target_price, condition.upper())
            )
            await db.commit()
            return cursor.lastrowid

    async def get_user_alerts(self, user_id: int) -> List[Dict]:
        """Gets all active alerts for a specific user."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM alerts WHERE user_id = ?", (user_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_all_alerts(self) -> List[Dict]:
        """Gets all system alerts for background monitoring."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM alerts") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def delete_alert(self, alert_id: int, user_id: int) -> bool:
        """Deletes a specific alert owned by the user."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("DELETE FROM alerts WHERE id = ? AND user_id = ?", (alert_id, user_id))
            await db.commit()
            return cursor.rowcount > 0

    async def remove_triggered_alert(self, alert_id: int):
        """Removes an alert after it has been triggered and sent."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
            await db.commit()

alert_service = AlertService()