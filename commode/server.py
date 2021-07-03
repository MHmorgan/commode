"""Abstraction of server interface"""

from collections import namedtuple
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import ParseResult, urlunparse

from requests import Response, Session, ConnectionError

from commode.common import debug, traced
from commode.exceptions import Error, NotFound, PreconditionFailed, BadRequest
from commode.boilerplate import BoilerplateData, Files
from commode.file_entry import FileData


@dataclass
class Server:
    """Interface to the Cabinet server."""

    address: str
    scheme: str
    _session: Optional[Session] = None

    def __enter__(self):
        self._session = Session()
        return self

    def __exit__(self, *args):
        self._session.close()

    def _request(self, method: str, url: str, **kwargs) -> Response:
        debug(f'{method.upper()} {url} {kwargs}')
        with Session() as session:
            s = self._session or session
            try:
                r = s.request(method=method, url=url, **kwargs)
            except ConnectionError as e:
                raise Error(f'Server connection error: {e}')
        debug(f'Server response: {r} {r.headers=}')
        return r

    def _url(self, path: str) -> ParseResult:
        from urllib.parse import quote
        return ParseResult(
            scheme=self.scheme,
            netloc=self.address,
            path=quote(path),
            params='',
            query='',
            fragment=''
        )

    @traced
    def get_file(self,
                 name: str,
                 etag: Optional[str] = None,
                 modified_since: Optional[str] = None) -> Optional[FileData]:
        """Retrieve a file from the server. Returns None of the cache is valid
        (determined by `etag` and `modified_since` timestamp).

        Raises `NotFound` if the server returns 404.
        Raises `BadRequest` if the resource isn't a file.
        """
        headers = {}
        if etag:
            headers['If-None-Match'] = etag
        if modified_since:
            headers['If-Modified-Since'] = modified_since

        url = self._url(f'/files/{name}')
        r = self._request(
            method='get',
            url=urlunparse(url),
            headers=headers
        )

        # Return None if the cache was valid
        if r.status_code == 304:
            return None
        if r.status_code == 400:
            raise BadRequest(r.text)
        if r.status_code == 404:
            raise NotFound(r.text)
        # Fail early if an unexpected redirect or error code occurs
        if r.status_code >= 300:
            raise Exception(r.text)

        return FileData(
            etag=r.headers['etag'],
            modified=r.headers['last-modified'],
            content=r.text
        )

    @traced
    def file_head(self, name: str) -> FileData:
        """Return file data without file content.

        Raises `NotFound` if the server returns 404.
        Raises `BadRequest` if the resource isn't a file.
        """
        url = self._url(f'/files/{name}')
        r = self._request(
            method='head',
            url=urlunparse(url),
        )

        if r.status_code == 400:
            raise BadRequest(r.text)
        if r.status_code == 404:
            raise NotFound(r.text)
        # Fail early if an unexpected redirect or error code occurs
        if r.status_code >= 300:
            raise Exception(r.text)

        return FileData(
            etag=r.headers['etag'],
            modified=r.headers['last-modified'],
        )

    @traced
    def put_file(self,
                 name: str,
                 content: str,
                 etag: Optional[str] = None,
                 unmodified_since: Optional[str] = None):
        """Upload a file to the server. `etag` and `unmodified_since` are used
        to conditionally update the file only if the server and client aren't
        out of sync with file content.

        Raises `PreconditionFailed` if any of the conditionals fails.
        """
        headers = {}
        if etag:
            headers['If-Match'] = etag
        if unmodified_since:
            headers['If-Unmodified-Since'] = unmodified_since

        url = self._url(f'/files/{name}')
        r = self._request(
            method='put',
            url=urlunparse(url),
            headers=headers,
            data=content.encode()
        )

        if r.status_code == 400:
            raise BadRequest(r.text)
        if r.status_code == 412:
            raise PreconditionFailed(r.text)
        # Fail early if an unexpected redirect or error code occurs
        if r.status_code >= 300:
            raise Exception(r.text)

    @traced
    def delete_file(self,
                    name: str,
                    etag: Optional[str] = None,
                    unmodified_since: Optional[str] = None):
        """Delete a file from the server. `etag` and `unmodified_since` are used
        to conditionally delete the file only if the server and client aren't
        out of sync with file content.

        Raises `NotFound` if the file doesn't exist.
        Raises `PreconditionFailed` if any of the conditionals fails.
        Raises `BadRequest` if the file couldn't be deleted because it is
        referenced in one or more boilerplates, or if the resource isn't a file.
        """
        headers = {}
        if etag:
            headers['If-Match'] = etag
        if unmodified_since:
            headers['If-Unmodified-Since'] = unmodified_since

        url = self._url(f'/files/{name}')
        r = self._request(
            method='delete',
            url=urlunparse(url),
            headers=headers
        )

        if r.status_code == 400:
            raise BadRequest(r.text)
        if r.status_code == 404:
            raise NotFound(r.text)
        if r.status_code == 412:
            raise PreconditionFailed(r.text)
        # Fail early if an unexpected redirect or error code occurs
        if r.status_code >= 300:
            raise Exception(r.text)

    @traced
    def get_dir(self, name: str) -> List[str]:
        """Get the content of a directory as a list of entry names.

        Raises `NotFound` if the directory doesn't exist.
        Raises `BadRequest` if the resource isn't a directory.
        """
        url = self._url(f'/dirs/{name}')
        r = self._request(
            method='get',
            url=urlunparse(url),
        )

        if r.status_code == 400:
            raise BadRequest(r.text)
        if r.status_code == 404:
            raise NotFound(r.text)
        # Fail early if an unexpected redirect or error code occurs
        if r.status_code >= 300:
            raise Exception(r.text)

        content = r.json()
        assert isinstance(content, list)
        return content

    @traced
    def put_dir(self, name: str):
        """Create a directory on the server.

        Raises `BadRequest` if the resource exists but isn't a directory.
        """
        url = self._url(f'/dirs/{name}')
        r = self._request(
            method='put',
            url=urlunparse(url),
        )

        if r.status_code == 400:
            raise BadRequest(r.text)
        # Fail early if an unexpected redirect or error code occurs
        if r.status_code >= 300:
            raise Exception(r.text)

    @traced
    def delete_dir(self, name: str):
        """Delete a directory from the server. This will also delete all files
        in this directory and sub-directories.

        Raises `NotFound` if the directory doesn't exist.
        Raises `BadRequest` if the directory cannot be deleted because is
        referenced in one or more boilerplates, or if the resource isn't
        a directory.
        """
        url = self._url(f'/dirs/{name}')
        r = self._request(
            method='delete',
            url=urlunparse(url),
        )

        if r.status_code == 400:
            raise BadRequest(r.text)
        if r.status_code == 404:
            raise NotFound(r.text)
        # Fail early if an unexpected redirect or error code occurs
        if r.status_code >= 300:
            raise Exception(r.text)

    @traced
    def get_boilerplate_names(self) -> List[str]:
        """Get a list of names of all boilerplates stored on the server"""
        url = self._url(f'/boilerplates')
        r = self._request(
            method='get',
            url=urlunparse(url),
        )

        # Fail early if an unexpected redirect or error code occurs
        if r.status_code >= 300:
            raise Exception(r.text)

        content = r.json()
        assert isinstance(content, list)
        return content

    @traced
    def get_boilerplate(self,
                        name: str,
                        etag: Optional[str] = None,
                        modified_since: Optional[str] = None) -> Optional[BoilerplateData]:
        """Retrieve a boilerplate from the server. Returns None if the cache is
        valid (determined by `etag` and `modified_since` timestamp).

        Raises `NotFound` if the server returns 404.
        """
        headers = {}
        if etag:
            headers['If-None-Match'] = etag
        if modified_since:
            headers['If-Modified-Since'] = modified_since

        url = self._url(f'/boilerplates/{name}')
        r = self._request(
            method='get',
            url=urlunparse(url),
            headers=headers
        )

        # Return None if the cache was valid
        if r.status_code == 304:
            return None
        if r.status_code == 404:
            raise NotFound(r.text)
        # Fail early if an unexpected redirect or error code occurs
        if r.status_code >= 300:
            raise Exception(r.text)

        files = Files(r.json())
        assert isinstance(files, dict)
        return BoilerplateData(
            etag=r.headers['etag'],
            modified=r.headers['last-modified'],
            files=files
        )

    @traced
    def put_boilerplate(self,
                        name: str,
                        files: Files,
                        etag: Optional[str] = None,
                        unmodified_since: Optional[str] = None):
        """Upload a boilerplate to the server. `etag` and `unmodified_since`
        are used to conditionally update the boilerplate only if the server and
        client aren't out of sync.

        Raises `PreconditionFailed` if any of the conditionals fails.
        """
        headers = {}
        if etag:
            headers['If-Match'] = etag
        if unmodified_since:
            headers['If-Unmodified-Since'] = unmodified_since

        url = self._url(f'/boilerplates/{name}')
        r = self._request(
            method='put',
            url=urlunparse(url),
            headers=headers,
            json=files
        )

        if r.status_code == 400:
            raise BadRequest(r.text)
        if r.status_code == 412:
            raise PreconditionFailed(r.text)
        # Fail early if an unexpected redirect or error code occurs
        if r.status_code >= 300:
            raise Exception(r.text)

    @traced
    def delete_boilerplate(self,
                           name: str,
                           etag: Optional[str] = None,
                           unmodified_since: Optional[str] = None):
        """Delete a boilerplate from the server. `etag` and `unmodified_since`
        are used to conditionally delete the boilerplate only if the server and
        client aren't out of sync.

        Raises `NotFound` if the boilerplate doesn't exist.
        Raises `PreconditionFailed` if any of the conditionals fails.
        """
        headers = {}
        if etag:
            headers['If-Match'] = etag
        if unmodified_since:
            headers['If-Unmodified-Since'] = unmodified_since

        url = self._url(f'/boilerplates/{name}')
        r = self._request(
            method='delete',
            url=urlunparse(url),
            headers=headers
        )

        if r.status_code == 404:
            raise NotFound(r.text)
        if r.status_code == 412:
            raise PreconditionFailed(r.text)
        # Fail early if an unexpected redirect or error code occurs
        if r.status_code >= 300:
            raise Exception(r.text)
