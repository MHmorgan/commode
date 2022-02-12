'''Abstraction of server interface'''

from collections import namedtuple
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import ParseResult, urlunparse

from requests import Response, Session, ConnectionError
from commode import common

from commode.common import debug, file_cache, boilerplate_cache
from commode.types import File, Boilerplate
from commode.exceptions import Error

@dataclass
class Server:
    '''Interface to the Cabinet server.'''

    address: str
    scheme: str
    _session: Optional[Session] = None

    def __enter__(self):
        self._session = Session()
        return self

    def __exit__(self, *args):
        self._session.close()

    def _request(self, method: str, url: str, **kwargs) -> Response:
        '''Do a request to the server. This wrapper handles Sessions,
        authorization and some common error conditions.
        '''
        debug(f'{method.upper()} {url} {kwargs}')
        with Session() as session:
            s = self._session or session
            if not s.auth:
                user = common.CONFIG.get('server', 'user', fallback=None)
                pswd = common.CONFIG.get('server', 'password', fallback=None)
                if user and pswd:
                    s.auth = (user, pswd)
            try:
                r = s.request(method=method, url=url, **kwargs)
            except ConnectionError as e:
                raise Error(f'Server connection error: {e}')
        debug(f'Server response: {r} {r.headers=}')
        if r.status_code == 401:
            raise Unauthorized(r.text)
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

    def get_file(self, name: str) -> File:
        '''Retrieve a file from the server (or cache).'''
        #
        # Look for cached file
        #
        with file_cache() as cache:
            file: File = cache.get(name, None)
        headers = {}
        if file: 
            assert isinstance(file, File)
            if file.etag:
                headers['If-None-Match'] = file.etag
            if file.modified:
                headers['If-Modified-Since'] = file.modified
        #
        # Get file from server
        #
        url = self._url(f'/files/{name}')
        r = self._request(
            method='get',
            url=urlunparse(url),
            headers=headers
        )
        #
        # Check request result
        #
        if r.status_code == 304:
            return file
        elif r.status_code >= 300:
            raise to_exc(r)
        elif r.status_code != 200:
            debug(f'GET {url} returned an unexpected success code: {r.status_code}')
        #
        # Update cache and return file 
        #
        file = File(
            name=name,
            text=r.text,
            etag=r.headers['etag'],
            modified=r.headers['last-modified']
        )
        with file_cache() as cache:
            cache[name] = file
        return file

    def put_file(self, name: str, text: str):
        '''Upload a file to the server.'''
        #
        # Check cached content
        #
        with file_cache() as cache:
            file: File = cache.get(name)
        headers = {}
        if file:
            assert isinstance(file, File)
            if file.text == text:
                debug(f"Won't upload {name}: content is equal to cached version.")
                return
            if file.etag:
                headers['If-Match'] = file.etag
            if file.modified:
                headers['If-Unmodified-Since'] = file.modified
        #
        # Send file to server
        #
        url = self._url(f'/files/{name}')
        r = self._request(
            method='put',
            url=urlunparse(url),
            headers=headers,
            data=text.encode()
        )
        if r.status_code >= 300:
            raise to_exc(r)

    def delete_file(self, name: str):
        '''Delete a file from the server.'''
        #
        # Check cached content
        #
        with file_cache() as cache:
            file: File = cache.get(name)
        headers = {}
        if file:
            assert isinstance(file, File)
            if file.etag:
                headers['If-Match'] = file.etag
            if file.modified:
                headers['If-Unmodified-Since'] = file.modified
        #
        # Delete request
        #
        url = self._url(f'/files/{name}')
        r = self._request(
            method='delete',
            url=urlunparse(url),
            headers=headers
        )
        if r.status_code >= 300:
            raise to_exc(r)

    def get_dir(self, name: str) -> list[str]:
        '''Get the content of a directory as a list of entry names.'''
        url = self._url(f'/dirs/{name}')
        r = self._request(
            method='get',
            url=urlunparse(url),
        )
        if r.status_code >= 300:
            raise to_exc(r)
        content = r.json()
        assert isinstance(content, list)
        return content

    def put_dir(self, name: str):
        '''Create a directory on the server.'''
        url = self._url(f'/dirs/{name}')
        r = self._request(
            method='put',
            url=urlunparse(url),
        )
        if r.status_code >= 300:
            raise to_exc(r)

    def delete_dir(self, name: str):
        '''Delete a directory from the server. This will also delete all files
        in this directory and sub-directories.
        '''
        url = self._url(f'/dirs/{name}')
        r = self._request(
            method='delete',
            url=urlunparse(url),
        )
        if r.status_code >= 300:
            raise to_exc(r)

    def get_boilerplate_names(self) -> list[str]:
        '''Get a list of names of all boilerplates stored on the server'''
        url = self._url(f'/boilerplates')
        r = self._request(
            method='get',
            url=urlunparse(url),
        )
        if r.status_code >= 300:
            raise to_exc(r)
        content = r.json()
        assert isinstance(content, list)
        return content

    def get_boilerplate(self, name: str) -> Boilerplate:
        '''Retrieve a boilerplate from the server.'''
        #
        # Check cache
        #
        with boilerplate_cache() as cache:
            bd: Boilerplate = cache.get(name)
        headers = {}
        if bd:
            if bd.modified:
                headers['If-Modified-Since'] = bd.modified
        #
        # Get boilerplate from server
        #
        url = self._url(f'/boilerplates/{name}')
        r = self._request(
            method='get',
            url=urlunparse(url),
            headers=headers
        )
        if r.status_code == 304:
            return bd
        elif r.status_code >= 300:
            raise to_exc(r)
        #
        # Update cache and return boilerplate
        #
        files = r.json()
        assert isinstance(files, dict)
        bp = Boilerplate(
            name=name,
            files=files,
            modified=r.headers['last-modified'],
        )
        with boilerplate_cache() as cache:
            cache[name] = bp
        return bp

    def put_boilerplate(self, name: str, files: dict[str,str]):
        '''Upload a boilerplate to the server.'''
        #
        # Check cached content
        #
        with boilerplate_cache() as cache:
            bp: Boilerplate = cache.get(name)
        headers = {}
        if bp:
            if bp.modified:
                headers['If-Unmodified-Since'] = bp.modified
        #
        # Send boilerplate to server
        #
        url = self._url(f'/boilerplates/{name}')
        r = self._request(
            method='put',
            url=urlunparse(url),
            headers=headers,
            json=files
        )
        if r.status_code >= 300:
            raise to_exc(r)

    def delete_boilerplate(self, name: str):
        '''Delete a boilerplate from the server.'''
        #
        # Check cached content
        #
        with boilerplate_cache() as cache:
            bp: Boilerplate = cache.get(name)
        headers = {}
        if bp:
            if bp.modified:
                headers['If-Unmodified-Since'] = bp.modified
        #
        # Send delete request
        #
        url = self._url(f'/boilerplates/{name}')
        r = self._request(
            method='delete',
            url=urlunparse(url),
            headers=headers
        )
        if r.status_code >= 300:
            raise to_exc(r)


def to_exc(resp: Response):
    match resp.status_code:
        case 400:
            return BadRequest(resp.text)
        case 404:
            return NotFound(resp.text)
        case 412:
            return PreconditionFailed(resp.text)
        case _:
            return Exception(resp.text)


class NotFound(Error):
    pass


class BadRequest(Error):
    pass


class PreconditionFailed(Error):
    pass

class Unauthorized(Error):
    pass