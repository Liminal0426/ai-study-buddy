"""Persistent memory for AI Study Buddy.

SQLite-backed store that tracks:
- Problems solved (text, subject, timestamp, success)
- Concepts learned / weak areas
- User preferences (learning style, difficulty, export format)
- Session history for self-evolution analysis

Inspired by Hermes Agent's memory system (MEMORY.md + USER.md),
adapted for study-buddy's domain.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from study_buddy.platform import memory_db_path

logger = logging.getLogger(__name__)

# Default database path
_DEFAULT_DB = str(memory_db_path())


# ── Data classes ───────────────────────────────────────────────────────

@dataclass
class ProblemRecord:
    """A problem the user has worked on."""
    id: int = 0
    problem_text: str = ""
    subject: str = ""
    explanation: str = ""
    diagram_path: Optional[str] = None
    success: bool = True           # user got it right?
    difficulty_rating: int = 3     # 1-5
    timestamp: float = 0.0
    session_id: Optional[str] = None


@dataclass
class ConceptState:
    """What the user knows about a concept."""
    name: str = ""
    level: int = 0         # 0=unknown, 1=seen, 2=learning, 3=got it, 4=mastered
    attempts: int = 0
    correct: int = 0
    last_seen: float = 0.0
    notes: str = ""


@dataclass
class UserPref:
    """User preference or trait."""
    key: str = ""
    value: str = ""
    category: str = "general"  # learning_style, difficulty, format, etc.
    confidence: float = 1.0    # how sure we are


# ── MemoryStore ────────────────────────────────────────────────────────

class MemoryStore:
    """Persistent memory for study buddy.

    Thread-safe: uses WAL mode + retry on locked.
    Schema versioned for future migrations.
    """

    SCHEMA_VERSION = 1

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path or _DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    # ── Connection ────────────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), timeout=5)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=3000")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS problems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                problem_text TEXT NOT NULL,
                subject TEXT DEFAULT '',
                explanation TEXT DEFAULT '',
                diagram_path TEXT,
                success INTEGER DEFAULT 1,
                difficulty_rating INTEGER DEFAULT 3,
                timestamp REAL NOT NULL,
                session_id TEXT
            );

            CREATE TABLE IF NOT EXISTS concepts (
                name TEXT PRIMARY KEY,
                level INTEGER DEFAULT 0,
                attempts INTEGER DEFAULT 0,
                correct INTEGER DEFAULT 0,
                last_seen REAL DEFAULT 0,
                notes TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                confidence REAL DEFAULT 1.0,
                updated_at REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                started_at REAL,
                ended_at REAL,
                problem_count INTEGER DEFAULT 0,
                summary TEXT DEFAULT ''
            );
        """)
        # Schema version check
        ver = conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()
        if not ver:
            conn.execute(
                "INSERT INTO meta (key, value) VALUES ('schema_version', ?)",
                (str(self.SCHEMA_VERSION),),
            )
        conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Problem tracking ──────────────────────────────────────────────

    def save_problem(self, record: ProblemRecord) -> int:
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO problems
               (problem_text, subject, explanation, diagram_path,
                success, difficulty_rating, timestamp, session_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (record.problem_text, record.subject, record.explanation,
             record.diagram_path, int(record.success),
             record.difficulty_rating,
             record.timestamp or time.time(),
             record.session_id),
        )
        conn.commit()
        record.id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return record.id

    def recent_problems(self, limit: int = 10) -> List[ProblemRecord]:
        rows = self._get_conn().execute(
            "SELECT * FROM problems ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_problem(r) for r in rows]

    def _row_to_problem(self, row: sqlite3.Row) -> ProblemRecord:
        return ProblemRecord(
            id=row["id"],
            problem_text=row["problem_text"],
            subject=row["subject"],
            explanation=row["explanation"],
            diagram_path=row["diagram_path"],
            success=bool(row["success"]),
            difficulty_rating=row["difficulty_rating"],
            timestamp=row["timestamp"],
            session_id=row["session_id"],
        )

    # ── Concept tracking ──────────────────────────────────────────────

    def update_concept(self, name: str, level: int,
                       correct: bool = True, notes: str = ""):
        """Record progress on a concept. Level tracks mastery."""
        conn = self._get_conn()
        existing = conn.execute(
            "SELECT * FROM concepts WHERE name=?", (name,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE concepts SET
                   level = MAX(level, ?),
                   attempts = attempts + 1,
                   correct = correct + ?,
                   last_seen = ?,
                   notes = CASE WHEN ? != '' THEN ? ELSE notes END
                   WHERE name=?""",
                (level, int(correct), time.time(), notes, notes, name),
            )
        else:
            conn.execute(
                "INSERT INTO concepts (name, level, attempts, correct, last_seen, notes) "
                "VALUES (?, ?, 1, ?, ?, ?)",
                (name, level, int(correct), time.time(), notes),
            )
        conn.commit()

    def weak_concepts(self, limit: int = 5) -> List[ConceptState]:
        """Concepts with low correctness ratio, needing practice."""
        rows = self._get_conn().execute(
            """SELECT *, (CAST(correct AS REAL) / MAX(attempts, 1)) AS ratio
               FROM concepts
               WHERE attempts >= 2 AND ratio < 0.7
               ORDER BY ratio ASC, attempts DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [self._row_to_concept(r) for r in rows]

    def learned_concepts(self, limit: int = 10) -> List[ConceptState]:
        """Concepts at level 3+ (mastered)."""
        rows = self._get_conn().execute(
            "SELECT * FROM concepts WHERE level >= 3 ORDER BY last_seen DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_concept(r) for r in rows]

    def _row_to_concept(self, row: sqlite3.Row) -> ConceptState:
        return ConceptState(
            name=row["name"],
            level=row["level"],
            attempts=row["attempts"],
            correct=row["correct"],
            last_seen=row["last_seen"],
            notes=row["notes"],
        )

    # ── Preferences ───────────────────────────────────────────────────

    def set_preference(self, key: str, value: str,
                       category: str = "general", confidence: float = 1.0):
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO preferences
               (key, value, category, confidence, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (key, value, category, confidence, time.time()),
        )
        conn.commit()

    def get_preference(self, key: str) -> Optional[str]:
        row = self._get_conn().execute(
            "SELECT value FROM preferences WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def all_preferences(self) -> List[UserPref]:
        rows = self._get_conn().execute(
            "SELECT * FROM preferences ORDER BY confidence DESC"
        ).fetchall()
        return [self._row_to_pref(r) for r in rows]

    def _row_to_pref(self, row: sqlite3.Row) -> UserPref:
        return UserPref(
            key=row["key"],
            value=row["value"],
            category=row["category"],
            confidence=row["confidence"],
        )

    # ── Session management ────────────────────────────────────────────

    def start_session(self, session_id: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id, started_at) VALUES (?, ?)",
            (session_id, time.time()),
        )
        conn.commit()

    def end_session(self, session_id: str, summary: str = "") -> None:
        conn = self._get_conn()
        # Count problems in this session
        count = conn.execute(
            "SELECT COUNT(*) FROM problems WHERE session_id=?",
            (session_id,),
        ).fetchone()[0]
        conn.execute(
            """UPDATE sessions SET
               ended_at=?, problem_count=?, summary=?
               WHERE id=?""",
            (time.time(), count, summary, session_id),
        )
        conn.commit()

    def recent_sessions(self, limit: int = 5) -> List[Dict[str, Any]]:
        rows = self._get_conn().execute(
            "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Stats ─────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        conn = self._get_conn()
        problems = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
        concepts = conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
        weak = len(self.weak_concepts(100))
        sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        success_rate = conn.execute(
            "SELECT AVG(success) FROM problems"
        ).fetchone()[0] or 0.0
        return {
            "total_problems": problems,
            "concepts_tracked": concepts,
            "weak_concepts": weak,
            "total_sessions": sessions,
            "success_rate": round(success_rate * 100, 1),
        }

    def format_report(self) -> str:
        """Generate a text report of user's learning state for the bot."""
        s = self.stats()
        lines = [
            f"📊 Study Stats",
            f"   Problems solved: {s['total_problems']}",
            f"   Success rate: {s['success_rate']}%",
            f"   Concepts tracked: {s['concepts_tracked']}",
            "",
        ]
        weak = self.weak_concepts(5)
        if weak:
            lines.append("⚠️  Needs practice:")
            for c in weak:
                rate = (c.correct / max(c.attempts, 1)) * 100
                lines.append(f"   {c.name} — {c.attempts} tries, {rate:.0f}% correct")
            lines.append("")

        learned = self.learned_concepts(5)
        if learned:
            lines.append("✅  Mastered:")
            for c in learned:
                lines.append(f"   {c.name}")
            lines.append("")

        prefs = self.all_preferences()
        user_prefs = [p for p in prefs if p.confidence >= 0.7]
        if user_prefs:
            lines.append("🧠  Known preferences:")
            for p in user_prefs[:5]:
                lines.append(f"   {p.key} = {p.value}")
        return "\n".join(lines)


# ── Singleton ──────────────────────────────────────────────────────────

_store: Optional[MemoryStore] = None


def get_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store
