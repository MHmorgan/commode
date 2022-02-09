"""Module containing the Boilerplate implementation - a class for interfacing
with boilerplates without having to explicitly handle server or cache
interaction.
"""

import shelve
from collections import namedtuple
from dataclasses import dataclass
from typing import Dict, Iterator, Optional, Tuple

from commode import common
from commode.common import debug
from commode.exceptions import Error, NotCached, NotCacheable, PreconditionFailed

BoilerplateData = namedtuple('BoilerplateData', 'etag, modified, files', defaults=[None]*3)

class Files(dict):

    def __init__(self, files: dict):

        # Sanity check
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in files.items()):
            raise InvalidBoilerplate('must be a mapping of { "clientfile" : "serverfile" }')

        super().__init__(files)

    def substituted_items(self) -> Iterator[Tuple[str, str]]:
        """Iterate through the file items, substituting environment
        variables in for the local file paths first.

        Raises `KeyError` if when encountering a missing environment variable.
        """
        from string import Template
        from os import environ

        for k, v in self.items():
            tmpl = Template(k)
            s = tmpl.substitute(environ)
            yield (s, v)


@dataclass
class Boilerplate:
    """Abstraction for interacting with boilerplates without
    having to worry about server communication and caching.
    """

    name: str
    _data: Optional[BoilerplateData] = None

    def files(self) -> Files:
        """Return all files referenced by this boilerplate.
        The files are mapping of client-side file path to server-side
        file path.
        """
        etag, mod, _ = self._safe_data()
        data = common.SERVER.get_boilerplate(self.name, etag, mod)
        # If the cache is valid the server will not return anything
        if data is not None:
            self._data = data
            self._write_cache()
        assert self._data is not None
        return self._data.files

    def update(self, files: Files):
        """Update the boilerplate files.
        This automatically updates the server side boilerplate as well.
        """
        etag, mod, _ = self._safe_data()
        try:
            common.SERVER.put_boilerplate(self.name, files, etag, mod)
        except PreconditionFailed as e:
            debug(e)
            raise Error(
                f'{self.name} has been modified on the server since your last access. Try downloading the boilerplate to review the changes.')
        # Update data to match server data
        self._data = common.SERVER.get_boilerplate(self.name)
        self._write_cache()

    def delete(self):
        """Delete the boilerplate, removing it both on the server
        and from cache.
        """
        etag, mod, _ = self._safe_data()
        common.SERVER.delete_boilerplate(self.name, etag, mod)
        self._delete_cache()

    def _safe_data(self) -> BoilerplateData:
        """Return file data for the file entry, guaranteeing to return
        a FileData object even if self._data is None and the file isn't cached.
        """
        if self._data is None:
            try:
                self._read_cache()
                debug(f'read boilerplate data for "{self.name}" from cache')
            except NotCached:
                debug(f'boilerplate data for "{self.name}" is not cached')
        return self._data or BoilerplateData()

    def _read_cache(self):
        """Read boilerplate data from cache.
        Raises NotCached exception if it fails.
        """
        with shelve.open(common.BOILERPLATE_CACHE) as cache:
            try:
                self._data = cache[self.name]
            except KeyError:
                raise NotCached(self.name)

    def _write_cache(self):
        """Write boilerplate data to cache.
        Raises NotCacheable if missing file data.
        """
        if self._data is None:
            raise NotCacheable()
        with shelve.open(common.BOILERPLATE_CACHE) as cache:
            cache[self.name] = self._data

    def _delete_cache(self):
        """Delete boilerplate from cache.
        Does not raise an exception if it isn't cached.
        """
        with shelve.open(common.BOILERPLATE_CACHE) as cache:
            try:
                del cache[self.name]
            except KeyError:
                pass


class InvalidBoilerplate(Error):
    def __init__(self, reason: str) -> None:
        super().__init__(f'invalid boilerplate: {reason}')
