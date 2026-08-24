from __future__ import annotations

from app.features.tasks.repository import TasksRepository


def get_tasks_repo() -> TasksRepository:
    return TasksRepository.get_instance()
