from app.features.dl_fields.repository import DLFieldsRepository


def get_dl_fields_repo() -> DLFieldsRepository:
    return DLFieldsRepository.get_instance()
