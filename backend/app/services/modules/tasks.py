from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import ScheduledTask
from backend.app.services.command import run_shell


def list_tasks(db: Session) -> list[ScheduledTask]:
    return list(db.scalars(select(ScheduledTask).order_by(ScheduledTask.created_at.desc())).all())


def create_task(db: Session, name: str, command: str, schedule: str) -> ScheduledTask:
    task = ScheduledTask(name=name, command=command, schedule=schedule)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def run_task(db: Session, task_id: int) -> str:
    task = db.get(ScheduledTask, task_id)
    if not task:
        raise ValueError("Task not found")
    result = run_shell(task.command, timeout=600).ensure_success("Unable to run task")
    return result.stdout


def delete_task(db: Session, task_id: int) -> None:
    task = db.get(ScheduledTask, task_id)
    if not task:
        raise ValueError("Task not found")
    db.delete(task)
    db.commit()

