import configparser
import getpass
from multiprocessing import context
import shelve
import sys
from typing import IO, NoReturn, Optional
from pathlib import Path
from contextlib import contextmanager

import click
from click import echo, secho

# NOTE: Threading is not allowed in the application due to these global variables.

DEBUG: bool = False
QUIET: bool = False
TRACE: bool = False
VERBOSE: bool = False
DRY_RUN: bool = False

LOGOUT: IO[str] = None
LOGERR: IO[str] = None

USER: str = getpass.getuser()
HOME: Path = Path.home()
CACHE_DIR: Path = HOME / '.cache/commode'
CACHE_DIR.mkdir(parents=True, exist_ok=True)

APP_DIR: Path = Path(click.get_app_dir('commode'))
APP_DIR.mkdir(parents=True, exist_ok=True)

class Error(Exception):
    '''Base class for application errors.'''


################################################################################
#                                                                              #
# Cache
#                                                                              #
################################################################################

# Cache files must be `str` to work with shelve
FILES_CACHE: str = str(APP_DIR / 'files.cache')
BOILERPLATE_CACHE: str = str(APP_DIR / 'boilerplates.cache')


@contextmanager
def file_cache():
    '''Context manager returning a dictionary for the file cache.'''
    cache = shelve.open(FILES_CACHE)
    try:
        yield cache
    finally:
        cache.close()


@contextmanager
def boilerplate_cache():
    '''Context manager returning a dictionary for the boilerplate cache.'''
    cache = shelve.open(BOILERPLATE_CACHE)
    try:
        yield cache
    finally:
        cache.close()


################################################################################
#                                                                              #
# Config
#                                                                              #
################################################################################

CONFIG = configparser.ConfigParser()
CONFIG_FILE: Path = APP_DIR / 'commode.cfg'
CONFIG_FILE.touch(mode=0o600, exist_ok=True)

with CONFIG_FILE.open() as f:
    CONFIG.read_file(f)


def write_config():
    with CONFIG_FILE.open('w') as f:
        CONFIG.write(f)


################################################################################
#                                                                              #
# Logging and printing
#                                                                              #
################################################################################

def info(msg: str, **kwargs):
    '''Print an info message.'''
    kwargs.setdefault('err', True)
    secho(f'[*] {msg}', **kwargs)


def warn(msg: str, **kwargs):
    '''Print a warning message.'''
    kwargs.setdefault('err', True)
    kwargs.setdefault('fg', 'yellow')
    secho(f'[!] {msg}', **kwargs)


def err(msg: str, **kwargs):
    '''Print an error message.'''
    kwargs.setdefault('err', True)
    kwargs.setdefault('fg', 'red')
    secho(f'[!!] {msg}', **kwargs)


def bail(msg: str, *, code: int = 1, **kwargs) -> NoReturn:
    '''Print an error message and exit.'''
    err(msg, **kwargs)
    sys.exit(code)


def verbose(msg: str, **kwargs):
    '''Print an info message if verbose is enabled.'''
    if VERBOSE or DEBUG:
        info(msg, **kwargs)


def debug(msg: str, **kwargs):
    '''Print an info message if debug is enabled.'''
    if DEBUG:
        info(msg, **kwargs)
