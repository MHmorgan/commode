
class Error(Exception):
    pass


class NotCached(Error):
    def __init__(self, name: str) -> None:
        super().__init__(f'"{name}" not found in cache')


class NotCacheable(Error):
    pass