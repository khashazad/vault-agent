import os
import sqlite3


# SQLite-backed key-value store for application settings.
class SettingsStore:
    # Initialize SQLite connection with WAL mode.
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = os.environ.get("DB_PATH", ".vault-agent.db")
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_table()

    # Create settings table if it doesn't exist.
    def _create_table(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        self._conn.commit()

    # Get a setting value by key.
    #
    # Args:
    #     key: Setting key.
    #
    # Returns:
    #     The value string, or None if not found.
    def get(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        return row["value"]

    # Set a setting value.
    #
    # Args:
    #     key: Setting key.
    #     value: Setting value.
    def set(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self._conn.commit()

    # Delete a setting by key.
    #
    # Args:
    #     key: Setting key to remove.
    def delete(self, key: str) -> None:
        self._conn.execute("DELETE FROM settings WHERE key = ?", (key,))
        self._conn.commit()

    # Close the SQLite connection.
    def close(self) -> None:
        self._conn.close()
