"""Abstraction of server interface."""

from dataclasses import dataclass
from typing import Optional
from requests import Session, Response
import requests
from .common import ctx

def foo():
    print(f'{ctx.X=}')

@dataclass
class Server:
    """Interface to the Cabinet server."""

    address: str
    _session: Optional[Session] = None

    def __enter__(self):
        self._session = Session()
        return self

    def __exit__(self, *args):
        self._session.close()

    def _request(self, method: str, url: str, **kwargs) -> Response:
        if self._session is not None:
            return self._session.request(method=method, url=url, **kwargs)
        with Session() as session:
            return session.request(method=method, url=url, **kwargs)
