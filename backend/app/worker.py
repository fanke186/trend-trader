from __future__ import annotations

from pathlib import Path
from typing import Any

from app.models import ScheduleSpec
from app.services import TrendTraderService


def start_worker(data_dir: Path) -> None:
    try:
        from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.date import DateTrigger
        from apscheduler.triggers.interval import IntervalTrigger
    except ModuleNotFoundError as exc:
        raise RuntimeError("APScheduler worker dependencies are missing. Run: pip install -r requirements.txt") from exc

    service = TrendTraderService(data_dir)
    scheduler = BlockingScheduler(
        timezone="Asia/Shanghai",
        jobstores={"default": SQLAlchemyJobStore(url=f"sqlite:///{data_dir / 'scheduler.sqlite3'}")},
    )

    for payload in service.repository.list_generic("schedules"):
        schedule = ScheduleSpec(**payload)
        if schedule.status != "enabled":
            continue
        trigger = _build_trigger(schedule)
        scheduler.add_job(
            lambda sid=schedule.id: service.run_schedule(int(sid)),
            trigger=trigger,
            id=f"schedule:{schedule.id}",
            name=schedule.name,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    scheduler.start()


def _build_trigger(schedule: ScheduleSpec) -> Any:
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.date import DateTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    trigger = schedule.trigger
    if trigger.type == "interval":
        return IntervalTrigger(seconds=int(trigger.every_seconds or 60), timezone=trigger.timezone)
    if trigger.type == "date":
        if not trigger.run_at:
            raise ValueError(f"schedule {schedule.name} date trigger requires run_at")
        return DateTrigger(run_date=trigger.run_at, timezone=trigger.timezone)
    parts = (trigger.cron or "").split()
    if len(parts) != 5:
        raise ValueError(f"schedule {schedule.name} cron must have 5 fields")
    minute, hour, day, month, day_of_week = parts
    return CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
        timezone=trigger.timezone,
    )
