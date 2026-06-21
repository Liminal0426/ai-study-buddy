"""SQLite database layer for AI Study Buddy.

Stores problems and wrong answers for review and analysis.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from study_buddy.config import config


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Create and return a database connection.

    Args:
        db_path: Path to the SQLite database file. Defaults to config value.

    Returns:
        A connection to the SQLite database.
    """
    path = Path(db_path or config.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: Optional[sqlite3.Connection] = None) -> None:
    """Initialize database tables.

    Creates the problems and wrong_answers tables if they do not exist.

    Args:
        conn: Database connection. Creates one if not provided.
    """
    close = conn is None
    if conn is None:
        conn = get_connection()

    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS problems (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                problem_text TEXT    NOT NULL,
                subject      TEXT    NOT NULL DEFAULT 'general',
                timestamp    TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS wrong_answers (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                problem_id    INTEGER NOT NULL,
                user_answer   TEXT    NOT NULL,
                correct_answer TEXT   NOT NULL,
                timestamp     TEXT    NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (problem_id) REFERENCES problems(id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_problems_subject
                ON problems(subject);
            CREATE INDEX IF NOT EXISTS idx_wrong_answers_problem_id
                ON wrong_answers(problem_id);
            """
        )
        conn.commit()
    finally:
        if close:
            conn.close()


def save_problem(
    problem_text: str,
    subject: str = "general",
    conn: Optional[sqlite3.Connection] = None,
) -> int:
    """Save a problem to the database.

    Args:
        problem_text: The text of the problem.
        subject: Subject category (e.g. 'math', 'physics').
        conn: Database connection. Creates one if not provided.

    Returns:
        The ID of the newly inserted problem.
    """
    close = conn is None
    if conn is None:
        conn = get_connection()

    try:
        cursor = conn.execute(
            "INSERT INTO problems (problem_text, subject) VALUES (?, ?)",
            (problem_text, subject),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]
    finally:
        if close:
            conn.close()


def save_wrong_answer(
    problem_id: int,
    user_answer: str,
    correct_answer: str,
    conn: Optional[sqlite3.Connection] = None,
) -> int:
    """Record a wrong answer in the database.

    Args:
        problem_id: The ID of the problem.
        user_answer: The user's incorrect answer.
        correct_answer: The correct answer.
        conn: Database connection. Creates one if not provided.

    Returns:
        The ID of the newly inserted wrong-answer record.
    """
    close = conn is None
    if conn is None:
        conn = get_connection()

    try:
        cursor = conn.execute(
            "INSERT INTO wrong_answers (problem_id, user_answer, correct_answer) "
            "VALUES (?, ?, ?)",
            (problem_id, user_answer, correct_answer),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]
    finally:
        if close:
            conn.close()


def get_recent_problems(
    limit: int = 10,
    conn: Optional[sqlite3.Connection] = None,
) -> List[dict]:
    """Fetch the most recent problems.

    Args:
        limit: Maximum number of problems to return.
        conn: Database connection. Creates one if not provided.

    Returns:
        A list of problem rows as dictionaries.
    """
    close = conn is None
    if conn is None:
        conn = get_connection()

    try:
        cursor = conn.execute(
            "SELECT id, problem_text, subject, timestamp "
            "FROM problems ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        if close:
            conn.close()


def get_wrong_answers_for_problem(
    problem_id: int,
    conn: Optional[sqlite3.Connection] = None,
) -> List[dict]:
    """Fetch all wrong answers recorded for a specific problem.

    Args:
        problem_id: The problem ID.
        conn: Database connection. Creates one if not provided.

    Returns:
        A list of wrong-answer rows as dictionaries.
    """
    close = conn is None
    if conn is None:
        conn = get_connection()

    try:
        cursor = conn.execute(
            "SELECT id, user_answer, correct_answer, timestamp "
            "FROM wrong_answers WHERE problem_id = ? "
            "ORDER BY timestamp DESC",
            (problem_id,),
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        if close:
            conn.close()
