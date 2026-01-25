from __future__ import annotations

from app.features.tasks.repository import TasksRepository
from app.features.tasks.service import Tasks


def get_tasks_repo() -> TasksRepository:
    """Get tasks repository instance."""
    return TasksRepository.get_instance()


def get_tasks_service() -> Tasks:
    """Get tasks service instance."""
    return Tasks.get_instance()
