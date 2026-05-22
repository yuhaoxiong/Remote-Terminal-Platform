from __future__ import annotations

from datetime import datetime, timezone

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.base import BaseTrigger


class ScheduleExpressionError(ValueError):
    pass


def parse_schedule_trigger(expression: str) -> BaseTrigger:
    expression = expression.strip()
    if expression.startswith("interval:"):
        return _parse_interval(expression.removeprefix("interval:").strip())
    if expression.startswith("cron:"):
        return _parse_cron(expression.removeprefix("cron:").strip())
    raise ScheduleExpressionError("调度表达式必须以 interval: 或 cron: 开头")


def next_run_time(expression: str, now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    trigger = parse_schedule_trigger(expression)
    next_time = trigger.get_next_fire_time(None, now)
    if next_time is None:
        raise ScheduleExpressionError("调度表达式无法计算下一次执行时间")
    return next_time


def _parse_interval(value: str) -> IntervalTrigger:
    try:
        seconds = int(value)
    except ValueError as exc:
        raise ScheduleExpressionError("interval 调度表达式必须是正整数秒数") from exc
    if seconds <= 0:
        raise ScheduleExpressionError("interval 调度表达式必须大于 0 秒")
    return IntervalTrigger(seconds=seconds, timezone=timezone.utc)


def _parse_cron(value: str) -> CronTrigger:
    parts = value.split()
    if len(parts) != 5:
        raise ScheduleExpressionError("cron 调度表达式必须是 5 位格式")
    try:
        return CronTrigger.from_crontab(value, timezone=timezone.utc)
    except ValueError as exc:
        raise ScheduleExpressionError("cron 调度表达式非法") from exc
