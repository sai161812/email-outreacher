class AppError(ValueError):
    status = 400

class NotFound(AppError):
    status = 404

class Conflict(AppError):
    status = 409

class ProviderError(AppError):
    status = 502
