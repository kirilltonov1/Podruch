import sqlite3
import json
from datetime import datetime

class Database:
    def __init__(self):
        self.conn = sqlite3.connect("bot.db", check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                role TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                content TEXT,
                done INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def add_message(self, user_id, role, content):
        self.conn.execute(
            "INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content)
        )
        self.conn.commit()

    def get_history(self, user_id, limit=20):
        cursor = self.conn.execute(
            "SELECT role, content FROM messages WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        rows = cursor.fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    def clear_history(self, user_id):
        self.conn.execute("DELETE FROM messages WHERE user_id=?", (user_id,))
        self.conn.commit()

    def add_memory(self, user_id, content):
        self.conn.execute(
            "INSERT INTO memory (user_id, content) VALUES (?, ?)",
            (user_id, content)
        )
        self.conn.commit()

    def get_memory(self, user_id):
        cursor = self.conn.execute(
            "SELECT content FROM memory WHERE user_id=? ORDER BY created_at DESC LIMIT 20",
            (user_id,)
        )
        rows = cursor.fetchall()
        return "\n".join([r[0] for r in rows]) if rows else ""

    def add_task(self, user_id, content):
        self.conn.execute(
            "INSERT INTO tasks (user_id, content) VALUES (?, ?)",
            (user_id, content)
        )
        self.conn.commit()

    def get_tasks(self, user_id):
        cursor = self.conn.execute(
            "SELECT content FROM tasks WHERE user_id=? AND done=0 ORDER BY created_at DESC",
            (user_id,)
        )
        return [r[0] for r in cursor.fetchall()]
