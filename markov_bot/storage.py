from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from markov_bot.domain import Skill, TaskAssignment, TaskEvent, TaskStatus, TaskTemplate


class Storage:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterable[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS task_templates (
                    template_id TEXT PRIMARY KEY,
                    skill TEXT NOT NULL,
                    title TEXT NOT NULL,
                    min_minutes INTEGER NOT NULL,
                    max_minutes INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS task_assignments (
                    assignment_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    template_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    skill TEXT NOT NULL,
                    date_assigned TEXT NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(user_id),
                    FOREIGN KEY(template_id) REFERENCES task_templates(template_id)
                );

                CREATE TABLE IF NOT EXISTS task_events (
                    event_id TEXT PRIMARY KEY,
                    assignment_id TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    note TEXT,
                    FOREIGN KEY(assignment_id) REFERENCES task_assignments(assignment_id)
                );
                """
            )

    def ensure_user(self, user_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users(user_id, created_at) VALUES (?, ?)",
                (user_id, datetime.utcnow().isoformat()),
            )

    def upsert_template(self, template: TaskTemplate) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO task_templates(template_id, skill, title, min_minutes, max_minutes)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(template_id) DO UPDATE SET
                    skill=excluded.skill,
                    title=excluded.title,
                    min_minutes=excluded.min_minutes,
                    max_minutes=excluded.max_minutes
                """,
                (
                    template.template_id,
                    template.skill.value,
                    template.title,
                    template.min_minutes,
                    template.max_minutes,
                ),
            )

    def list_templates(self) -> list[TaskTemplate]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM task_templates").fetchall()
        return [
            TaskTemplate(
                template_id=row["template_id"],
                skill=Skill(row["skill"]),
                title=row["title"],
                min_minutes=row["min_minutes"],
                max_minutes=row["max_minutes"],
            )
            for row in rows
        ]

    def create_assignments(self, assignments: Iterable[TaskAssignment]) -> None:
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO task_assignments(
                    assignment_id, user_id, template_id, title, skill, date_assigned, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        assignment.assignment_id,
                        assignment.user_id,
                        assignment.template_id,
                        assignment.title,
                        assignment.skill.value,
                        assignment.date_assigned.isoformat(),
                        assignment.status.value,
                    )
                    for assignment in assignments
                ],
            )

    def record_event(self, event: TaskEvent) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO task_events(
                    event_id, assignment_id, user_id, status, created_at, note
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.assignment_id,
                    event.user_id,
                    event.status.value,
                    event.created_at.isoformat(),
                    event.note,
                ),
            )
            conn.execute(
                "UPDATE task_assignments SET status = ? WHERE assignment_id = ?",
                (event.status.value, event.assignment_id),
            )

    def list_assignments_for_date(self, user_id: int, date_value: date) -> list[TaskAssignment]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM task_assignments
                WHERE user_id = ? AND date_assigned = ?
                ORDER BY assignment_id
                """,
                (user_id, date_value.isoformat()),
            ).fetchall()
        return [
            TaskAssignment(
                assignment_id=row["assignment_id"],
                user_id=row["user_id"],
                template_id=row["template_id"],
                title=row["title"],
                skill=Skill(row["skill"]),
                date_assigned=date.fromisoformat(row["date_assigned"]),
                status=TaskStatus(row["status"]),
            )
            for row in rows
        ]

    def list_assignments_between(
        self,
        user_id: int,
        start_date: date,
        end_date: date,
    ) -> list[TaskAssignment]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM task_assignments
                WHERE user_id = ? AND date_assigned BETWEEN ? AND ?
                ORDER BY date_assigned, assignment_id
                """,
                (user_id, start_date.isoformat(), end_date.isoformat()),
            ).fetchall()
        return [
            TaskAssignment(
                assignment_id=row["assignment_id"],
                user_id=row["user_id"],
                template_id=row["template_id"],
                title=row["title"],
                skill=Skill(row["skill"]),
                date_assigned=date.fromisoformat(row["date_assigned"]),
                status=TaskStatus(row["status"]),
            )
            for row in rows
        ]

    def update_assignment_status(self, assignment_id: str, status: TaskStatus) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE task_assignments SET status = ? WHERE assignment_id = ?",
                (status.value, assignment_id),
            )

    def fetch_assignment(self, assignment_id: str) -> TaskAssignment | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM task_assignments WHERE assignment_id = ?",
                (assignment_id,),
            ).fetchone()
        if not row:
            return None
        return TaskAssignment(
            assignment_id=row["assignment_id"],
            user_id=row["user_id"],
            template_id=row["template_id"],
            title=row["title"],
            skill=Skill(row["skill"]),
            date_assigned=date.fromisoformat(row["date_assigned"]),
            status=TaskStatus(row["status"]),
        )
