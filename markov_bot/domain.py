from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Iterable


class Skill(str, Enum):
    BODY = "body"
    CAPITAL = "capital"
    PRODUCTIVITY = "productivity"
    GAME_THINKING = "game_thinking"
    PSYCHE = "psyche"
    LANGUAGE = "language"


class TaskStatus(str, Enum):
    ASSIGNED = "assigned"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True)
class TaskTemplate:
    template_id: str
    skill: Skill
    title: str
    min_minutes: int
    max_minutes: int


@dataclass(frozen=True)
class TaskAssignment:
    assignment_id: str
    user_id: int
    template_id: str
    title: str
    skill: Skill
    date_assigned: date
    status: TaskStatus = TaskStatus.ASSIGNED


@dataclass(frozen=True)
class TaskEvent:
    event_id: str
    assignment_id: str
    user_id: int
    status: TaskStatus
    created_at: datetime
    note: str | None = None


@dataclass(frozen=True)
class DaySummary:
    date_value: date
    assigned: int
    done: int
    failed: int


@dataclass(frozen=True)
class WeekSummary:
    week_start: date
    week_end: date
    completion_rate: float
    overload_flag: bool
    stagnation_flag: bool
    critical_failures: int


@dataclass(frozen=True)
class MonthSummary:
    month_start: date
    month_end: date
    completion_rate: float
    closed_weeks: int
    critical_failures: int
    level_change: str


@dataclass(frozen=True)
class WeeklyAdjustment:
    week_start: date
    adjustment_note: str


@dataclass(frozen=True)
class LevelRules:
    level: int
    active_skills: tuple[Skill, ...]
    max_daily_tasks: int
    min_daily_tasks: int


def completion_rate(done: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(done / total, 4)


def summarize_day(assignments: Iterable[TaskAssignment]) -> DaySummary:
    items = list(assignments)
    assigned = len(items)
    done = sum(1 for item in items if item.status == TaskStatus.DONE)
    failed = sum(1 for item in items if item.status == TaskStatus.FAILED)
    if items:
        date_value = items[0].date_assigned
    else:
        date_value = date.today()
    return DaySummary(
        date_value=date_value,
        assigned=assigned,
        done=done,
        failed=failed,
    )
