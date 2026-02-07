from __future__ import annotations

from datetime import date, datetime, timedelta
import asyncio
import sys
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from markov_bot.config import load_settings
from markov_bot.domain import TaskStatus
from markov_bot.services import DEFAULT_RULES, TaskService
from markov_bot.storage import Storage


def _today(timezone: str) -> date:
    return datetime.now(tz=ZoneInfo(timezone)).date()


def _parse_assignment_id(args: list[str]) -> str | None:
    if not args:
        return None
    return args[0]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    service: TaskService = context.bot_data["service"]
    service.storage.ensure_user(user.id)
    await update.message.reply_text(
        "Регистрация завершена. Дальше только факты. Используй /day для заданий."
    )


async def day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    service: TaskService = context.bot_data["service"]
    date_value = _today(context.bot_data["timezone"])
    assignments = service.storage.list_assignments_for_date(user.id, date_value)
    if not assignments:
        plan = service.generate_daily_plan(user.id, date_value, DEFAULT_RULES)
        assignments = list(plan.assignments)
    lines = ["Задания на сегодня:"]
    for item in assignments:
        lines.append(f"{item.assignment_id} | {item.skill.value} | {item.title}")
    await update.message.reply_text("\n".join(lines))


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    assignment_id = _parse_assignment_id(context.args)
    if not assignment_id:
        await update.message.reply_text("Укажи ID задания: /done <task_id>")
        return
    service: TaskService = context.bot_data["service"]
    assignment = service.storage.fetch_assignment(assignment_id)
    if not assignment or assignment.user_id != user.id:
        await update.message.reply_text("Задание не найдено.")
        return
    service.record_result(user.id, assignment_id, TaskStatus.DONE)
    await update.message.reply_text("Зафиксировано: выполнено.")


async def fail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    assignment_id = _parse_assignment_id(context.args)
    if not assignment_id:
        await update.message.reply_text("Укажи ID задания: /fail <task_id>")
        return
    service: TaskService = context.bot_data["service"]
    assignment = service.storage.fetch_assignment(assignment_id)
    if not assignment or assignment.user_id != user.id:
        await update.message.reply_text("Задание не найдено.")
        return
    service.record_result(user.id, assignment_id, TaskStatus.FAILED)
    await update.message.reply_text("Зафиксировано: провал.")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    service: TaskService = context.bot_data["service"]
    date_value = _today(context.bot_data["timezone"])
    summary = service.daily_summary(user.id, date_value)
    await update.message.reply_text(
        f"День {summary.date_value.isoformat()}: {summary.done}/{summary.assigned} выполнено, {summary.failed} провалено."
    )


async def week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    service: TaskService = context.bot_data["service"]
    today = _today(context.bot_data["timezone"])
    week_start = today - timedelta(days=today.weekday())
    summary = service.weekly_summary(user.id, week_start)
    adjustment = service.weekly_adjustment(summary)
    await update.message.reply_text(
        "\n".join(
            [
                f"Неделя {summary.week_start}–{summary.week_end}",
                f"Выполнение: {summary.completion_rate:.0%}",
                f"Перегруз: {'да' if summary.overload_flag else 'нет'}",
                f"Застой: {'да' if summary.stagnation_flag else 'нет'}",
                f"Коррекция: {adjustment.adjustment_note}",
            ]
        )
    )


async def month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    service: TaskService = context.bot_data["service"]
    today = _today(context.bot_data["timezone"])
    month_start = date(today.year, today.month, 1)
    summary = service.monthly_summary(user.id, month_start, DEFAULT_RULES.level)
    await update.message.reply_text(
        "\n".join(
            [
                f"Месяц {summary.month_start}–{summary.month_end}",
                f"Выполнение: {summary.completion_rate:.0%}",
                f"Закрытые недели: {summary.closed_weeks}",
                f"Критические провалы: {summary.critical_failures}",
                f"Решение по уровню: {summary.level_change}",
            ]
        )
    )


def build_app() -> Application:
    settings = load_settings()
    storage = Storage(settings.db_path)
    service = TaskService(storage)
    service.seed_templates()
    app = Application.builder().token(settings.token).build()
    app.bot_data["service"] = service
    app.bot_data["timezone"] = settings.timezone

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("day", day))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("fail", fail))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("week", week))
    app.add_handler(CommandHandler("month", month))
    return app


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    app = build_app()
    app.run_polling()


if __name__ == "__main__":
    main()
