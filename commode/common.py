from _typeshed import FileDescriptor
import getpass
import sys
from dataclasses import dataclass
from typing import IO, NoReturn
from pathlib import Path

import arrow

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
FILES_CACHE: Path = CACHE_DIR / 'files'
BOILERPLATE_CACHE: Path = CACHE_DIR / 'boilerplates'

CACHE_DIR.mkdir(parents=True, exist_ok=True)
FILES_CACHE.mkdir(exist_ok=True)
BOILERPLATE_CACHE.mkdir(exist_ok=True)


class Error(Exception):
    pass


################################################################################
#                                                                              #
# Logging and printing
#                                                                              #
################################################################################

def timestamp() -> str:
    'Return a log timestamp.'
    return arrow.now().format('YYYY-MM-DD HH:mm:ss')


def log(*args, **kwargs):
    '''
    Print a log message. Will print to stdout by default.
    May be redirected by setting the LOGOUT global variable, or with a `file=`
    argument.
    If the log output is not redirected these messages will be suppressed
    if QUIET=True, to avoid cluttering stdout.
    '''
    # Logs statements should be quiet, unless they are
    # redirected to a file.
    if QUIET and LOGOUT is None and 'file' not in kwargs:
        return
    args = (f'[{timestamp()}]', *args)
    kwargs.setdefault('file', LOGOUT or sys.stdout)
    print(*args, **kwargs)


def warn(*args, **kwargs):
    '''
    Print a warning log message. Will print to stderr by default.
    May be redirected by setting the LOGERR global variable, or with a `file=`
    argument.
    '''
    args = (f'[{timestamp()}]', 'Warning:', *args)
    kwargs.setdefault('file', LOGERR or sys.stderr)
    kwargs.setdefault('flush', True)
    print(*args, **kwargs)


def error(*args, **kwargs):
    '''
    Print an error log message. Will print to stderr by default.
    May be redirected by setting the LOGERR global variable, or with a `file=`
    argument.
    '''
    args = (f'[{timestamp()}]', 'Error:', *args)
    kwargs.setdefault('file', LOGERR or sys.stderr)
    kwargs.setdefault('flush', True)
    print(*args, **kwargs)


def bail(*args, code: int = 1, **kwargs) -> NoReturn:
    '''
    Print an error message as described for `error()`, then exit.
    Default exit code is 1.
    '''
    error(*args, **kwargs)
    sys.exit(code)


def vprint(*args, **kwargs):
    '''
    Behaves just like `print()` when VERBOSE=True.
    Output is suppressed if VERBOSE=False or QUIET=True.
    If DEBUG=True this is always printed.
    '''
    if (VERBOSE and not QUIET) or DEBUG:
        print(*args, **kwargs)


def qprint(*args, **kwargs):
    '''
    Quiet printing - will not print if running with QUIET=True.
    Behaves like `print()` unless suppressed.
    If DEBUG=True this is always printed.
    '''
    if not QUIET or DEBUG:
        print(*args, **kwargs)


def debug(*args, **kwargs):
    'Print a debug message. Behaves like `log()` when DEBUG=True'
    if DEBUG:
        args = ('Debug:', *args)
        log(*args, **kwargs)


def trace(*args, **kwargs):
    'Print a trace message. Behaves like `log()` when TRACE=True'
    if TRACE:
        args = ('Trace:', *args)
        log(*args, **kwargs)


def traced(func):
    'Decorator for tracing functions and methods.'
    name = getattr(func, '__qualname__')
    module = getattr(func, '__module__')

    def wrapper(*args, **kwargs):
        trace(f'{module}.{name} {args=} {kwargs=}')
        return func(*args, **kwargs)

    return wrapper
