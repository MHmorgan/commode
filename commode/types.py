'''Commodes main types.

- File
- Boilerplate
'''

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from .exceptions import Error


@dataclass
class File:
    name: str
    text: str
    
    # Metadata received from the server - only interesting to the server.
    etag: str | None = None
    modified: str | None = None


@dataclass
class Boilerplate:
    name: str
    files: dict[str, str]

    # Metadata received from the server - only interesting to the server.
    modified: str | None = None

    @property
    def substituted_files(self) -> Iterator[tuple[Path, str]]:
        '''Iterator over the boilerplate files. Any environment variables in
        the local path is substituted, and it is returned as a Path.
        '''
        from string import Template
        from os import environ

        for k, v in self.files.items():
            tmpl = Template(k)
            try:
                s = tmpl.substitute(environ)
            except KeyError as e:
                raise Error(f'Bad local file path "{k}": {e}')
            p = Path(s)
            yield (p.expanduser(), v)

    def verify(self):
        '''Do sanity checks on the boilerplate,
        raising exceptions on errors.
        '''
        for k, v in self.files.items():
            if not (isinstance(k, str), isinstance(v, str)):
                msg = f'{self.name}: boilerplate files must be strings: "{k} : {v}"'
                raise Error(msg)