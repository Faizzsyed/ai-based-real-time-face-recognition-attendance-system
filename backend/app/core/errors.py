"""Safe application error contract."""


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def not_found(entity: str) -> AppError:
    return AppError("RESOURCE_NOT_FOUND", f"{entity} was not found.", 404)
