
from .common import Error

class NotCached(Error):
    def __init__(self, name: str) -> None:
        super().__init__(f'"{name}" not found in cache')


class NotCacheable(Error):
    pass


class NotFound(Error):
    pass


class BadRequest(Error):
    pass


class PreconditionFailed(Error):
    pass

class Unauthorized(Error):
    pass