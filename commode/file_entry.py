"""Module containing the FileEntry implementation - a class for interfacing with
files without having to explicitly handle server or cache interaction.
"""

import shelve
from dataclasses import  dataclass
from pathlib import Path
from typing import Optional

from commode import common
from commode.common import debug, traced
from commode.exceptions import Error, NotCached, NotCacheable
from commode.server import FileData, PreconditionFailed


@dataclass
class FileEntry:
    """Abstraction for handling reading and writing file entries without
    having to worry about server communication and caching.
    """

    name: str
    _data: Optional[FileData] = None

    @traced
    def content(self) -> str:
        """Return the text content of the file entry.
        This handles any required server interaction.
        """
        etag, mod, _ = self._safe_data()
        data = common.SERVER.get_file(self.name, etag, mod)
        # If the cache is valid the server will not return anything
        if data is not None:
            self._data = data
            self._write_cache()
        assert self._data is not None
        return self._data.content

    @traced
    def update(self, content: str):
        """Update the file content of this entry.
        This automatically updates the server side file entry as well.
        """
        etag, mod, _ = self._safe_data()
        try:
            common.SERVER.put_file(self.name, content, etag, mod)
        except PreconditionFailed:
            raise Error(
                f'{self.name} has been modified on the server since your last access. Try downloading the file to review the changes.')
        # Update data to match server data (without requesting content)
        data = common.SERVER.file_head(self.name)
        self._data = data._replace(content=content)
        self._write_cache()

    @traced
    def delete(self):
        """Delete the file entry, removing it both on the server
        and from cache.
        """
        etag, mod, _ = self._safe_data()
        common.SERVER.delete_file(self.name, etag, mod)
        self._delete_cache()

    def _safe_data(self) -> FileData:
        """Return file data for the file entry, guaranteeing to return
        a FileData object even if self._data is None and the file isn't cached.
        """
        if self._data is None:
            try:
                self._read_cache()
                debug(f'read file data for "{self.name}" from cache')
            except NotCached:
                debug(f'file data for "{self.name}" is not cached')
        return self._data or FileData()

    def _read_cache(self):
        """Read file entry data from cache.
        Raises NotCached exception if it fails.
        """
        with shelve.open(common.FILES_CACHE) as cache:
            try:
                self._data = cache[self.name]
            except KeyError:
                raise NotCached(self.name)

    def _write_cache(self):
        """Write file entry data to cache.
        Raises NotCacheable if missing file data.
        """
        if self._data is None:
            raise NotCacheable()
        with shelve.open(common.FILES_CACHE) as cache:
            cache[self.name] = self._data

    def _delete_cache(self):
        """Delete file entry from cache.
        Does not raise an exception if it isn't cached.
        """
        with shelve.open(common.FILES_CACHE) as cache:
            try:
                del cache[self.name]
            except KeyError:
                pass
