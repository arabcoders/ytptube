from app.features.notifications.repository import NotificationsRepository


def get_notifications_repo() -> NotificationsRepository:
    return NotificationsRepository.get_instance()
