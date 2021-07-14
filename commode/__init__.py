
import json
import os
import shelve
from pathlib import Path

import click

from commode import common
from commode.boilerplate import Boilerplate, Files
from commode.common import bail, debug, error, warn
from commode.exceptions import Error, Unauthorized
from commode.file_entry import FileEntry
from commode.server import Server


def run():
    try:
        cli()  # pylint: disable=no-value-for-parameter
    except Unauthorized as e:
        bail(f'{e} (have you forgotten to configure username and password? See: `commode config --help`)')
    except Error as e:
        bail(e)
    except KeyboardInterrupt:
        print('Keyboard interrupt. Stopping.')


@click.group()
@click.option('-v', '--verbose', is_flag=True, help='Be verbose.')
@click.option('-q', '--quiet', is_flag=True, help='Be quiet.')
@click.option('--debug', is_flag=True, help='Run with debugging information.')
@click.option('--trace', is_flag=True, help='Run with debugging and trace information.')
@click.option('--log-out', 'logout', type=click.File('w'), help='Redirect log output to file.')
@click.option('--log-err', 'logerr', type=click.File('w'), help='Redirect log error output to file.')
@click.option('--log-err2out', 'err2out', is_flag=True, help='Write log errors to normal log output.')
def cli(verbose, quiet, debug, trace, logout, logerr, err2out):  # pylint: disable=too-many-arguments
    'Commode - client for the Cabinet file server.'
    common.DEBUG = debug
    common.QUIET = quiet
    common.VERBOSE = verbose
    common.TRACE = trace
    common.LOGOUT = logout
    common.LOGERR = common.LOGOUT if err2out else logerr

    # Server password are stored in plain text in config file - should warn user if
    # other users are able to read the config file
    if common.CONFIG_FILE.stat().st_mode & 0o044:
        warn(f'config file ({common.CONFIG_FILE}) is readable by group and others')

    # Setup from config
    cfg = common.CONFIG
    if (addr := cfg.get('server', 'address', fallback=None)):
        scheme = cfg.get('server', 'scheme', fallback='https')
        common.SERVER = Server(address=addr, scheme=scheme)


@cli.command()
@click.option('--server-address', help='Set the address of target Cabinet server')
@click.option('--user', help='Set username for server authentication')
@click.option('--password', help='Set password for server authentication')
def config(server_address, user, password):
    """Configure the client. When no option is provided the current config is printed."""
    cfg = common.CONFIG

    # Prepare config sections
    if 'server' not in cfg:
        cfg.add_section('server')

    if server_address:
        if not server_address.startswith('http'):
            bail('Server address should be an URL starting with http or https')
        from urllib.parse import urlparse
        url = urlparse(server_address)
        debug(f'Parsed server url: {url}')
        cfg.set('server', 'address', url.netloc)
        cfg.set('server', 'scheme', url.scheme or 'https')
    if user:
        cfg.set('server', 'user', user)
    if password:
        cfg.set('server', 'password', password)

    if server_address or user or password:
        common.write_config()
    else:
        print(common.CONFIG_FILE.read_text(), end='')


def verify_config():
    """Sanity checker ensuring that the server is properly configured before
    performing actions which rely on the server.
    """
    if common.SERVER is None:
        bail(f'server is not properly configured. Please run: `commode config --server-address <addr>`')


################################################################################
#                                                                              #
# Files interface
#                                                                              #
################################################################################

@cli.command()
@click.argument('file')
def download(file: str):
    'Download a file from the server'
    verify_config()
    with common.SERVER:
        f = FileEntry(file)
        txt = f.content()
    print(txt)


@cli.command()
@click.argument('srcfile')
@click.argument('dstfile')
def upload(srcfile: str, dstfile: str):
    'Upload a file to the server'
    verify_config()
    try:
        text = Path(srcfile).read_text()
    except FileNotFoundError:
        bail(f'source file not found: {srcfile}')
    with common.SERVER:
        f = FileEntry(dstfile)
        f.update(text)


@cli.command()
@click.argument('file')
def delete(file: str):
    'Delete a file on the server'
    verify_config()
    with common.SERVER:
        f = FileEntry(file)
        f.delete()


################################################################################
#                                                                              #
# Directory interface
#                                                                              #
################################################################################

@cli.command()
@click.argument('path', required=False, default='')
def ls(path: str):
    'List directory content on the server'
    verify_config()
    with common.SERVER as srv:
        content = srv.get_dir(path)
    print('\n'.join(sorted(content)))


@cli.command()
@click.argument('path')
def mkdir(path: str):
    'Create a directory on the server'
    verify_config()
    with common.SERVER as srv:
        srv.put_dir(path)


@cli.command()
@click.argument('path')
def rmdir(path: str):
    'Remove a directory on the server'
    verify_config()
    with common.SERVER as srv:
        srv.delete_dir(path)


################################################################################
#                                                                              #
# Boilerplates interface
#                                                                              #
################################################################################

@cli.command()
def boilerplates():
    'List all boilerplates on the server'
    verify_config()
    with common.SERVER as srv:
        names = srv.get_boilerplate_names()
    print('\n'.join(sorted(names)))


@cli.group()
def boilerplate():
    'Manage boilerplates'


@boilerplate.command()
@click.argument('name')
def download(name: str):
    'Download a boilerplate'
    verify_config()
    with common.SERVER:
        bp = Boilerplate(name)
        files = bp.files()
    print(json.dumps(files, indent=4))


@boilerplate.command()
@click.argument('name')
@click.argument('location', type=click.Path(exists=True, file_okay=False, writable=True))
@click.option('-f', '--force', is_flag=True, help='Overwrite any existing files during installation.')
def install(name: str, location: str, force: bool):
    """Install a boilerplate, downloading and installing all files in
    the boilerplate.
    """
    verify_config()
    os.chdir(location)
    with common.SERVER:
        bp = Boilerplate(name)
        files = bp.files()
        try:
            items = list(files.substituted_items())
        except KeyError as e:
            bail(f'Missing environment variable: {e}')
        for path, name in items:
            content = FileEntry(name).content()
            p = Path(path)
            if p.exists() and not force:
                raise Error(f'file already exists: {path} (use --force to overwrite)')
            elif not p.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)


@boilerplate.command()
@click.argument('srcfile', type=click.File())
@click.argument('name')
@click.option('--upload-files', is_flag=True, help='Upload all files referenced by the boilerplate before uploading the boilerplate itself.')
def upload(srcfile, name: str, upload_files: bool):
    """Upload a boilerplate to the server.
    The boilerplate is read from a local file (SRCFILE) which must be a correctly
    formatted JSON boilerplate object.

    The JSON object must be a mapping of client-side file path to
    server-side path:

    \b
        {
            "$HOME/.vimrc" : "linuxconfig/vimrc",
            "$HOME/.aliases" : "linuxconfig/aliases"
        }

    When uploading a boilerplate all files referenced in the boilerplate must
    exist on the server. The --upload-files option may be used to automatically
    upload all files referenced in the boilerplate.
    """
    verify_config()

    try:
        # Sanity checking of the boilerplate is handled by Files
        files = json.load(srcfile, object_hook=Files)
    except json.JSONDecodeError as e:
        bail(f'invalid JSON in source file: {e}')

    with common.SERVER:
        bp = Boilerplate(name)
        if upload_files:
            try:
                items = list(files.substituted_items())
            except KeyError as e:
                bail(f'Missing environment variable: {e}')
            for src, dst in items:
                debug(f'Uploading {src} -> {dst}')
                try:
                    text = Path(src).read_text()
                except FileNotFoundError:
                    bail(f'File not found: {src}')
                f = FileEntry(dst)
                f.update(text)
        bp.update(files)


@boilerplate.command()
@click.argument('name')
def delete(name: str):
    'Delete a boilerplate on the server.'
    verify_config()
    with common.SERVER:
        bp = Boilerplate(name)
        bp.delete()


################################################################################
#                                                                              #
# Cache handling
#                                                                              #
################################################################################

@cli.group()
def cache():
    'Inspect and manage cached files and boilerplates.'


@cache.command()
def files():
    'List all cached files with last modified timestamp and ETAG'
    with shelve.open(common.FILES_CACHE) as cache:
        # max() requires at least 1 item
        if len(cache) == 0:
            return
        w = max(len(name) for name in cache)
        for file in sorted(cache):
            etag, mod, _ = cache[file]
            print(f'{file:<{w}}\t{mod}\t{etag}')


@cache.command()
def boilerplates():
    'List all cached boilerplates with last modified timestamp and ETAG'
    with shelve.open(common.BOILERPLATE_CACHE) as cache:
        # max() requires at least 1 item
        if len(cache) == 0:
            return
        w = max(len(name) for name in cache)
        for bp in sorted(cache):
            etag, mod, _ = cache[bp]
            print(f'{bp:<{w}}\t{mod}\t{etag}')


@cache.command()
def clear():
    'Clear entire cache, both for boilerplates and files'
    with shelve.open(common.FILES_CACHE) as cache:
        cache.clear()
    with shelve.open(common.BOILERPLATE_CACHE) as cache:
        cache.clear()
