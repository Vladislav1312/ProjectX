from __future__ import annotations

import hashlib
import random
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from markov_bot.domain import (
    DaySummary,
    LevelRules,
    MonthSummary,
    Skill,
    TaskAssignment,
    TaskEvent,
    TaskStatus,
    TaskTemplate,
    WeekSummary,
    WeeklyAdjustment,
    completion_rate,
    summarize_day,
)
from markov_bot.storage import Storage


DEFAULT_TEMPLATES: tuple[TaskTemplate, ...] = (
    TaskTemplate("body-01", Skill.BODY, "Физическая активность", 15, 30),
    TaskTemplate("capital-01", Skill.CAPITAL, "Учёт расходов", 10, 20),
    TaskTemplate("productivity-01", Skill.PRODUCTIVITY, "План дня", 10, 20),
    TaskTemplate("game-01", Skill.GAME_THINKING, "Анализ решения", 10, 15),
    TaskTemplate("psyche-01", Skill.PSYCHE, "Фиксация состояния", 5, 10),
    TaskTemplate("language-01", Skill.LANGUAGE, "Практика языка", 15, 25),
)


DEFAULT_RULES = LevelRules(
    level=1,
    active_skills=(
        Skill.BODY,
        Skill.CAPITAL,
        Skill.PRODUCTIVITY,
        Skill.GAME_THINKING,
        Skill.PSYCHE,
        Skill.LANGUAGE,
    ),
    max_daily_tasks=3,
    min_daily_tasks=2,
)


@dataclass(frozen=True)
class DailyPlan:
    date_value: date
    assignments: tuple[TaskAssignment, ...]


class TaskService:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def seed_templates(self) -> None:
        for template in DEFAULT_TEMPLATES:
            self.storage.upsert_template(template)

    def generate_daily_plan(self, user_id: int, date_value: date, rules: LevelRules) -> DailyPlan:
        templates = [t for t in self.storage.list_templates() if t.skill in rules.active_skills]
        if not templates:
            templates = list(DEFAULT_TEMPLATES)
        rng = self._seeded_rng(user_id, date_value)
        count = rng.randint(rules.min_daily_tasks, rules.max_daily_tasks)
        selected = rng.sample(templates, k=min(count, len(templates)))
        assignments = tuple(
            TaskAssignment(
                assignment_id=self._assignment_id(user_id, date_value, template.template_id),
                user_id=user_id,
                template_id=template.template_id,
                title=template.title,
                skill=template.skill,
                date_assigned=date_value,
                status=TaskStatus.ASSIGNED,
            )
            for template in selected
        )
        self.storage.create_assignments(assignments)
        return DailyPlan(date_value=date_value, assignments=assignments)

    def record_result(
        self,
        user_id: int,
        assignment_id: str,
        status: TaskStatus,
        note: str | None = None,
    ) -> TaskEvent:
        event = TaskEvent(
            event_id=str(uuid.uuid4()),
            assignment_id=assignment_id,
            user_id=user_id,
            status=status,
            created_at=datetime.utcnow(),
            note=note,
        )
        self.storage.record_event(event)
        return event

    def daily_summary(self, user_id: int, date_value: date) -> DaySummary:
        assignments = self.storage.list_assignments_for_date(user_id, date_value)
        return summarize_day(assignments)

    def weekly_summary(self, user_id: int, week_start: date) -> WeekSummary:
        week_end = week_start + timedelta(days=6)
        assignments = self.storage.list_assignments_between(user_id, week_start, week_end)
        done = sum(1 for item in assignments if item.status == TaskStatus.DONE)
        failed = sum(1 for item in assignments if item.status == TaskStatus.FAILED)
        total = len(assignments)
        completion = completion_rate(done, total)
        overload_flag = total > 7 * DEFAULT_RULES.max_daily_tasks
        stagnation_flag = done == 0 and total > 0
        critical_failures = failed if failed >= 5 else 0
        return WeekSummary(
            week_start=week_start,
            week_end=week_end,
            completion_rate=completion,
            overload_flag=overload_flag,
            stagnation_flag=stagnation_flag,
            critical_failures=critical_failures,
        )

    def weekly_adjustment(self, summary: WeekSummary) -> WeeklyAdjustment:
        if summary.stagnation_flag:
            note = "Снижение нагрузки: застой"
        elif summary.overload_flag:
            note = "Снижение нагрузки: перегруз"
        elif summary.completion_rate > 0.8:
            note = "Усиление нагрузки: стабильное выполнение"
        else:
            note = "Нагрузка без изменений"
        return WeeklyAdjustment(week_start=summary.week_start, adjustment_note=note)

    def monthly_summary(self, user_id: int, month_start: date, level: int) -> MonthSummary:
        month_end = month_start + timedelta(days=29)
        assignments = self.storage.list_assignments_between(user_id, month_start, month_end)
        done = sum(1 for item in assignments if item.status == TaskStatus.DONE)
        failed = sum(1 for item in assignments if item.status == TaskStatus.FAILED)
        total = len(assignments)
        completion = completion_rate(done, total)
        closed_weeks = 4
        critical_failures = failed if failed >= 15 else 0
        level_change = self._level_decision(completion, closed_weeks, critical_failures, level)
        return MonthSummary(
            month_start=month_start,
            month_end=month_end,
            completion_rate=completion,
            closed_weeks=closed_weeks,
            critical_failures=critical_failures,
            level_change=level_change,
        )

    def _level_decision(
        self,
        completion: float,
        closed_weeks: int,
        critical_failures: int,
        level: int,
    ) -> str:
        if critical_failures:
            return "hold"
        if completion >= 0.8 and closed_weeks >= 4:
            return f"promote:{level + 1}"
        if completion < 0.5:
            return "hold"
        return "hold"

    @staticmethod
    def _assignment_id(user_id: int, date_value: date, template_id: str) -> str:
        raw = f"{user_id}:{date_value.isoformat()}:{template_id}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]

    @staticmethod
    def _seeded_rng(user_id: int, date_value: date) -> random.Random:
        seed = int(hashlib.sha256(f"{user_id}:{date_value.isoformat()}".encode()).hexdigest(), 16)
        return random.Random(seed)
